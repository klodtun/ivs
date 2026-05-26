"""
Tunnel Service — creates real public tunnels using ngrok or localtunnel.

Priority: ngrok (if installed & configured) → localtunnel (via npx, fallback)
Each tunnel runs as a subprocess; PID stored for lifecycle management.
"""
import asyncio
import json
import logging
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from app.models import Tunnel, TunnelStatus, App

logger = logging.getLogger(__name__)


class TunnelService:
    def __init__(self):
        self._processes: dict[int, asyncio.subprocess.Process] = {}

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

        # Try tunnel providers in priority order
        proc, public_url, provider = await self._try_providers(app.port)

        if not public_url:
            raise RuntimeError(
                "Failed to create tunnel — no provider available. "
                "Install ngrok (https://ngrok.com) or ensure npx is available for localtunnel."
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
        self, port: int
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str], str]:
        """Try tunnel providers in order: ngrok → localtunnel."""

        # 1. ngrok
        proc, url = await self._start_ngrok(port)
        if url:
            return proc, url, "ngrok"

        # 2. localtunnel (via npx)
        proc, url = await self._start_localtunnel(port)
        if url:
            return proc, url, "localtunnel"

        return None, None, "none"

    # ── ngrok ───────────────────────────────────────────────────

    async def _start_ngrok(
        self, port: int
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str]]:
        """Start an ngrok tunnel and extract the public URL from JSON logs."""
        if not shutil.which("ngrok"):
            logger.info("ngrok not found in PATH, skipping")
            return None, None

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "ngrok", "http", str(port),
                "--log", "stdout", "--log-format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            url = await asyncio.wait_for(self._parse_ngrok_url(proc), timeout=15)

            if url:
                logger.info(f"ngrok tunnel ready: {url} (pid={proc.pid})")
                return proc, url
            else:
                logger.warning("ngrok started but no URL obtained")
                proc.terminate()
                return None, None

        except asyncio.TimeoutError:
            logger.warning("ngrok timed out waiting for tunnel URL")
            if proc:
                proc.terminate()
            return None, None
        except Exception as e:
            logger.warning(f"ngrok failed: {e}")
            if proc and proc.returncode is None:
                proc.terminate()
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
                    logger.warning(f"ngrok error: {err}")
                    return None
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        return None

    # ── localtunnel ─────────────────────────────────────────────

    async def _start_localtunnel(
        self, port: int
    ) -> Tuple[Optional[asyncio.subprocess.Process], Optional[str]]:
        """Start a localtunnel via npx and extract the public URL."""
        npx_path = shutil.which("npx")
        if not npx_path:
            logger.info("npx not found in PATH, skipping localtunnel")
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
