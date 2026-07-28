"""
Tunnel Service — creates real public tunnels using ngrok, cloudflare, or
localtunnel.

Credentials are per-iVS: each instance stores its OWN provider token in
system_config (encrypted), so different iVS installs never share one free
ngrok/cloudflare account. The token is passed to the provider process via
env/flag — never written to a global config file.

Priority when provider = "auto": ngrok (if token) → cloudflare (if token)
→ localtunnel (no account). Otherwise the chosen provider is used directly.
"""
import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from app.models import Tunnel, TunnelStatus, App, SystemConfig
from app.services.vault_service import vault_service

logger = logging.getLogger(__name__)

# system_config keys
CFG_PROVIDER = "tunnel.provider"          # auto | ngrok | cloudflare | localtunnel
CFG_NGROK_TOKEN = "tunnel.ngrok_authtoken"    # encrypted
CFG_CF_TOKEN = "tunnel.cloudflare_token"      # encrypted


# Common install dirs to search beyond PATH. A backend launched from a
# minimal-PATH shell (or a GUI launcher) often can't see Homebrew/nvm, so
# `shutil.which` alone would wrongly report ngrok/cloudflared as missing.
_EXTRA_BIN_DIRS = [
    "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
    os.path.expanduser("~/.nvm/versions/node"),  # nvm (searched shallowly below)
]


def _which(name: str) -> Optional[str]:
    """Resolve a binary via PATH, then common install dirs (Homebrew, nvm)."""
    p = shutil.which(name)
    if p:
        return p
    for d in _EXTRA_BIN_DIRS:
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    # nvm keeps binaries under versions/node/<ver>/bin — scan one level deep
    nvm = os.path.expanduser("~/.nvm/versions/node")
    if os.path.isdir(nvm):
        for ver in sorted(os.listdir(nvm), reverse=True):
            cand = os.path.join(nvm, ver, "bin", name)
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
    return None


def _get_cfg(db: Session, key: str) -> str:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return row.value if row and row.value else ""


def get_tunnel_config(db: Session) -> dict:
    """Return the tunnel provider + decrypted tokens for THIS iVS instance."""
    provider = _get_cfg(db, CFG_PROVIDER) or "auto"
    ngrok_enc = _get_cfg(db, CFG_NGROK_TOKEN)
    cf_enc = _get_cfg(db, CFG_CF_TOKEN)
    ngrok_token = vault_service.decrypt(ngrok_enc) if ngrok_enc else ""
    cf_token = vault_service.decrypt(cf_enc) if cf_enc else ""
    return {"provider": provider, "ngrok_token": ngrok_token, "cf_token": cf_token}


def set_tunnel_config(db: Session, provider: str = None,
                      ngrok_token: str = None, cf_token: str = None):
    """Persist tunnel config. Tokens are encrypted; pass "" to clear a token,
    or None to leave it unchanged."""
    def _upsert(key: str, value: str):
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if not row:
            row = SystemConfig(key=key, value=value)
            db.add(row)
        else:
            row.value = value

    if provider is not None:
        _upsert(CFG_PROVIDER, provider)
    if ngrok_token is not None:
        _upsert(CFG_NGROK_TOKEN, vault_service.encrypt(ngrok_token) if ngrok_token else "")
    if cf_token is not None:
        _upsert(CFG_CF_TOKEN, vault_service.encrypt(cf_token) if cf_token else "")
    db.commit()


class TunnelService:
    def __init__(self):
        self._processes: dict[int, asyncio.subprocess.Process] = {}
        # Human-readable reason the last provider attempt failed (surfaced to
        # the user instead of the generic "configure a token" message).
        self._last_error: Optional[str] = None

    async def create_tunnel(
        self,
        db: Session,
        app: App,
        duration_minutes: int,
        user_id: int,
    ) -> Tunnel:
        if not app.port:
            raise ValueError("App has no port assigned — cannot create tunnel")

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        # Read this iVS instance's tunnel credentials
        cfg = get_tunnel_config(db)

        # Try tunnel providers per config
        proc, public_url, provider = await self._try_providers(app.port, cfg)

        if not public_url:
            if self._last_error:
                raise RuntimeError(f"Failed to create tunnel: {self._last_error}")
            raise RuntimeError(
                "Failed to create tunnel. Configure an ngrok authtoken or "
                "Cloudflare token in Settings → Tunnel, or ensure npx is "
                "available for the no-account localtunnel fallback."
            )

        tunnel = Tunnel(
            app_id=app.id,
            public_url=public_url,
            status=TunnelStatus.ACTIVE,
            expires_at=expires_at,
            container_id=str(proc.pid) if proc else None,
            created_by=user_id,
        )
        db.add(tunnel)
        db.commit()
        db.refresh(tunnel)

        if proc:
            self._processes[tunnel.id] = proc

        logger.info(
            f"Tunnel created [{provider}] for {app.slug}: {public_url} "
            f"(expires in {duration_minutes}m, pid={proc.pid if proc else 'N/A'})"
        )
        return tunnel

    # ── Provider orchestration ──────────────────────────────────

    async def _try_providers(
        self, port: int, cfg: dict
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str], str]:
        """Try tunnel providers according to the instance config.

        provider == "ngrok"/"cloudflare"/"localtunnel" -> only that one.
        provider == "auto" -> ngrok (if token) -> cloudflare (if token)
        -> localtunnel.
        """
        self._last_error = None
        provider = (cfg.get("provider") or "auto").lower()
        ngrok_token = cfg.get("ngrok_token") or ""
        cf_token = cfg.get("cf_token") or ""

        if provider == "ngrok":
            proc, url = await self._start_ngrok(port, ngrok_token)
            return (proc, url, "ngrok") if url else (None, None, "none")
        if provider == "cloudflare":
            proc, url = await self._start_cloudflare(port, cf_token)
            return (proc, url, "cloudflare") if url else (None, None, "none")
        if provider == "localtunnel":
            proc, url = await self._start_localtunnel(port)
            return (proc, url, "localtunnel") if url else (None, None, "none")

        # auto
        if ngrok_token:
            proc, url = await self._start_ngrok(port, ngrok_token)
            if url:
                return proc, url, "ngrok"
        if cf_token:
            proc, url = await self._start_cloudflare(port, cf_token)
            if url:
                return proc, url, "cloudflare"
        proc, url = await self._start_localtunnel(port)
        if url:
            return proc, url, "localtunnel"

        return None, None, "none"

    # ── ngrok ───────────────────────────────────────────────────

    async def _start_ngrok(
        self, port: int, authtoken: str = ""
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str]]:
        """Start an ngrok tunnel and extract the public URL from JSON logs.

        The authtoken is passed via the NGROK_AUTHTOKEN env var so it's scoped
        to THIS process — it never touches the machine's global ngrok config,
        which is what previously made every iVS share one free account.
        """
        ngrok_bin = _which("ngrok")
        if not ngrok_bin:
            self._last_error = "ngrok binary not found on this server"
            logger.info("ngrok not found in PATH or common dirs, skipping")
            return None, None

        # Per-instance env: inherit PATH etc., override the authtoken.
        env = os.environ.copy()
        if authtoken:
            env["NGROK_AUTHTOKEN"] = authtoken

        # ngrok's free tier allows ONE online endpoint per account. A tunnel
        # that iVS lost track of (stale process from a crash/restart) keeps the
        # endpoint online and makes every new tunnel fail with ERR_NGROK_334.
        # Try once; if we hit that, reap orphan ngrok processes and retry.
        for attempt in range(2):
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    ngrok_bin, "http", str(port),
                    "--log", "stdout", "--log-format", "json",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

                url = await asyncio.wait_for(self._parse_ngrok_url(proc), timeout=15)

                if url:
                    logger.info(f"ngrok tunnel ready: {url} (pid={proc.pid})")
                    return proc, url

                if proc.returncode is None:
                    proc.terminate()

                already_online = self._last_error and "ERR_NGROK_334" in self._last_error
                if attempt == 0 and already_online and self._reap_orphan_ngrok(env):
                    logger.info("reaped orphan ngrok endpoint, retrying tunnel")
                    await asyncio.sleep(1)
                    continue

                logger.warning(f"ngrok started but no URL obtained: {self._last_error}")
                return None, None

            except asyncio.TimeoutError:
                self._last_error = "ngrok timed out waiting for tunnel URL"
                logger.warning(self._last_error)
                if proc:
                    proc.terminate()
                return None, None
            except Exception as e:
                self._last_error = f"ngrok failed: {e}"
                logger.warning(self._last_error)
                if proc and proc.returncode is None:
                    proc.terminate()
                return None, None

        return None, None

    async def _parse_ngrok_url(self, proc: asyncio.subprocess.Process) -> Optional[str]:
        """Read ngrok JSON log lines until we find the tunnel URL or an error."""
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode().strip())
                # Success: {"msg":"started tunnel","url":"https://xxx.ngrok-free.dev",...}
                if data.get("msg") == "started tunnel" and "url" in data:
                    return data["url"]
                # Error: {"err":"...", "msg":"..."}
                err = data.get("err")
                if err and err != "<nil>":
                    self._last_error = self._humanize_ngrok_err(err)
                    logger.warning(f"ngrok error: {err}")
                    return None
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        return None

    @staticmethod
    def _humanize_ngrok_err(err: str) -> str:
        """Turn a raw ngrok error into a short, user-facing reason."""
        if "ERR_NGROK_334" in err:
            return ("an ngrok tunnel is already online for this account "
                    "(free tier allows one) [ERR_NGROK_334]")
        if "ERR_NGROK_108" in err or "authtoken" in err.lower():
            return "the ngrok authtoken is invalid or unauthorized"
        if "ERR_NGROK_105" in err or "ERR_NGROK_107" in err:
            return "ngrok could not authenticate — check the authtoken"
        # Keep it to the first line, trimmed.
        return err.strip().splitlines()[0][:200]

    def _reap_orphan_ngrok(self, env: dict) -> bool:
        """Kill ngrok endpoint processes that iVS is no longer tracking.

        The free tier's single-endpoint limit means a stale ngrok (left over
        from a crash/restart) blocks every new tunnel. We only reap ngrok
        processes NOT in self._processes so live iVS tunnels are untouched.
        """
        tracked = {p.pid for p in self._processes.values() if p and p.pid}
        killed = False
        try:
            out = subprocess.run(
                ["pgrep", "-f", "ngrok http"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            return False
        for line in out.split():
            try:
                pid = int(line)
            except ValueError:
                continue
            if pid == os.getpid() or pid in tracked:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                killed = True
                logger.info(f"reaped orphan ngrok pid={pid}")
            except (ProcessLookupError, PermissionError):
                continue
        return killed

    # ── cloudflare ──────────────────────────────────────────────

    async def _start_cloudflare(
        self, port: int, token: str = ""
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str]]:
        """Start a cloudflared tunnel.

        With a token -> a named tunnel bound to the user's Cloudflare account
        (`cloudflared tunnel run --token`), which routes to their configured
        hostname. Without a token -> an ephemeral quick tunnel
        (`--url http://localhost:PORT`) on trycloudflare.com, no account.
        """
        cf_bin = _which("cloudflared")
        if not cf_bin:
            logger.info("cloudflared not found in PATH or common dirs, skipping")
            return None, None

        if token:
            args = [cf_bin, "tunnel", "--no-autoupdate", "run", "--token", token]
        else:
            args = [cf_bin, "tunnel", "--no-autoupdate",
                    "--url", f"http://localhost:{port}"]

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            url = await asyncio.wait_for(self._parse_cloudflare_url(proc), timeout=30)
            if url:
                logger.info(f"cloudflare tunnel ready: {url} (pid={proc.pid})")
                return proc, url
            # Named-tunnel run doesn't print a trycloudflare URL — the public
            # hostname is the one configured in the CF dashboard. Keep the
            # process alive and report that hostname is external.
            if token and proc.returncode is None:
                logger.info("cloudflare named tunnel started (hostname set in CF dashboard)")
                return proc, "cloudflare-named-tunnel"
            logger.warning("cloudflare started but no URL obtained")
            if proc.returncode is None:
                proc.terminate()
            return None, None
        except asyncio.TimeoutError:
            logger.warning("cloudflare timed out waiting for URL")
            if proc:
                proc.terminate()
            return None, None
        except Exception as e:
            logger.warning(f"cloudflare failed: {e}")
            if proc and proc.returncode is None:
                proc.terminate()
            return None, None

    async def _parse_cloudflare_url(self, proc: asyncio.subprocess.Process) -> Optional[str]:
        """Read cloudflared output for the trycloudflare.com quick-tunnel URL."""
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            if "trycloudflare.com" in text:
                for tok in text.split():
                    if tok.startswith("https://") and "trycloudflare.com" in tok:
                        return tok
        return None

    # ── localtunnel ─────────────────────────────────────────────

    async def _start_localtunnel(
        self, port: int
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str]]:
        """Start a localtunnel via npx and extract the public URL."""
        npx_path = _which("npx")
        if not npx_path:
            logger.info("npx not found in PATH or common dirs, skipping localtunnel")
            return None, None

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                npx_path, "localtunnel", "--port", str(port),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            url = await asyncio.wait_for(self._parse_lt_url(proc), timeout=30)

            if url:
                logger.info(f"localtunnel ready: {url} (pid={proc.pid})")
                return proc, url
            else:
                logger.warning("localtunnel started but no URL obtained")
                proc.terminate()
                return None, None

        except asyncio.TimeoutError:
            logger.warning("localtunnel timed out waiting for URL")
            if proc:
                proc.terminate()
            return None, None
        except Exception as e:
            logger.warning(f"localtunnel failed: {e}")
            if proc and proc.returncode is None:
                proc.terminate()
            return None, None

    async def _parse_lt_url(self, proc: asyncio.subprocess.Process) -> Optional[str]:
        """Read localtunnel stdout until we find 'your url is: https://...'."""
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode().strip()
            # localtunnel outputs: "your url is: https://xxx.loca.lt"
            if "your url is:" in text.lower():
                url = text.split("is:")[-1].strip()
                if url.startswith("http"):
                    return url
        return None

    # ── Lifecycle management ────────────────────────────────────

    async def revoke_tunnel(self, db: Session, tunnel: Tunnel):
        """Stop the tunnel process and mark as revoked."""
        await self._stop_process(tunnel.id)
        tunnel.status = TunnelStatus.REVOKED
        db.commit()
        logger.info(f"Tunnel {tunnel.id} revoked and process stopped")

    async def cleanup_expired(self, db: Session):
        """Stop expired tunnel processes and update status."""
        now = datetime.now(timezone.utc)
        expired = db.query(Tunnel).filter(
            Tunnel.status == TunnelStatus.ACTIVE,
            Tunnel.expires_at <= now,
        ).all()

        for tunnel in expired:
            await self._stop_process(tunnel.id)
            tunnel.status = TunnelStatus.EXPIRED
            logger.info(f"Tunnel {tunnel.id} expired — process stopped")

        if expired:
            db.commit()

    async def _stop_process(self, tunnel_id: int):
        """Gracefully stop a tunnel subprocess."""
        proc = self._processes.pop(tunnel_id, None)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
                logger.debug(f"Tunnel process {proc.pid} terminated")
            except asyncio.TimeoutError:
                proc.kill()
                logger.warning(f"Tunnel process {proc.pid} killed (did not terminate gracefully)")
            except Exception as e:
                logger.warning(f"Error stopping tunnel process for tunnel {tunnel_id}: {e}")

    def get_active_tunnels(self, db: Session) -> list[Tunnel]:
        return db.query(Tunnel).filter(Tunnel.status == TunnelStatus.ACTIVE).all()


tunnel_service = TunnelService()
