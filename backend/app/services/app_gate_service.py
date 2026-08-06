"""App Gate — puts the iVS login in front of a deployed app.

Without this, a deployed app publishes its port on 0.0.0.0 and anyone who
knows `IP:PORT` reaches it directly. That bypasses the iVS login, so nothing
about the visit lands in the audit log and the PDPA notice never gets shown —
the compliance story iVS is built on only holds for the dashboard, not for the
apps it deploys.

When an app is set to `protected`:

  * Docker publishes the container on 127.0.0.1:<port + PORT_OFFSET>, so it is
    unreachable from the network.
  * iVS itself listens on 0.0.0.0:<port> — the address users already use — and
    forwards a connection only after checking the iVS session cookie and the
    app's access rules.

The gate speaks just enough HTTP to read the request head; after that it pipes
bytes in both directions, so websockets and streaming responses keep working.
Keeping the public port unchanged matters: the app still believes it is served
from the root of its origin, so its asset paths, cookies and redirects work
exactly as they did before.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from jose import JWTError

from app.database import SessionLocal
from app.middleware.auth import decode_token
from app.models import App, User

logger = logging.getLogger(__name__)

# Internal (loopback-only) port = public port + this. The app port range is
# 10000-10999, so the shadow range 20000-20999 stays clear of it.
PORT_OFFSET = 10000

# Max bytes we read while looking for the end of the request head. A request
# head larger than this is malformed for our purposes.
MAX_HEAD_BYTES = 32 * 1024
HEAD_TIMEOUT_SECONDS = 15

# One audit entry per (user, app) per this window — a single page load fires
# dozens of requests and would otherwise flood the log.
AUDIT_WINDOW = timedelta(minutes=30)


def internal_port(public_port: int) -> int:
    return public_port + PORT_OFFSET


class _GateRequest:
    """Minimal stand-in for a FastAPI Request, so audit rows written by the
    gate carry the same IP / user-agent / session fields as HTTP ones."""

    class _Client:
        def __init__(self, host: str):
            self.host = host

    def __init__(self, client_ip: str, user_agent: str):
        self.client = self._Client(client_ip)
        self.headers = {"User-Agent": user_agent}
        self.cookies: Dict[str, str] = {}

    # audit_service calls .headers.get(...) — a plain dict already satisfies it.


class AppGate:
    """One listening socket in front of one app."""

    def __init__(self, slug: str, app_id: int, public_port: int, login_url: str):
        self.slug = slug
        self.app_id = app_id
        self.public_port = public_port
        self.target_port = internal_port(public_port)
        self.login_url = login_url
        self._server: Optional[asyncio.AbstractServer] = None
        self._last_audit: Dict[int, datetime] = {}

    # ── lifecycle ────────────────────────────────────────────────

    async def start(self):
        if self._server:
            return
        self._server = await asyncio.start_server(
            self._handle, host="0.0.0.0", port=self.public_port
        )
        logger.info(
            f"App gate up for {self.slug}: 0.0.0.0:{self.public_port} "
            f"-> 127.0.0.1:{self.target_port} (login required)"
        )

    async def stop(self):
        if not self._server:
            return
        self._server.close()
        try:
            await self._server.wait_closed()
        except Exception:
            pass
        self._server = None
        logger.info(f"App gate down for {self.slug} (port {self.public_port})")

    # ── request handling ─────────────────────────────────────────

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            head = await asyncio.wait_for(
                self._read_head(reader), timeout=HEAD_TIMEOUT_SECONDS
            )
        except (asyncio.TimeoutError, Exception):
            await self._close(writer)
            return

        if head is None:
            await self._close(writer)
            return

        token = self._cookie_value(head, "access_token")
        user = self._authenticate(token)

        if user is None:
            await self._deny(writer, head)
            return

        peer = writer.get_extra_info("peername")
        client_ip = peer[0] if peer else "unknown"
        self._audit_visit(user, client_ip, self._header_value(head, "user-agent"))

        # Authenticated: hand the connection to the app, replaying the head we
        # already consumed, then pipe both directions untouched.
        try:
            up_reader, up_writer = await asyncio.open_connection("127.0.0.1", self.target_port)
        except Exception as e:
            logger.warning(f"gate {self.slug}: upstream unreachable: {e}")
            await self._respond(
                writer, 502, "text/plain; charset=utf-8",
                b"App is not running.\n",
            )
            return

        up_writer.write(head)
        try:
            await up_writer.drain()
        except Exception:
            await self._close(writer)
            return

        await asyncio.gather(
            self._pipe(reader, up_writer),
            self._pipe(up_reader, writer),
            return_exceptions=True,
        )

    async def _read_head(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        """Read up to and including the blank line that ends the request head."""
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = await reader.read(4096)
            if not chunk:
                return buf or None
            buf += chunk
            if len(buf) > MAX_HEAD_BYTES:
                return None
        return buf

    @staticmethod
    def _header_value(head: bytes, name: str) -> str:
        text = head.decode("latin-1", errors="ignore")
        for line in text.split("\r\n"):
            if line.lower().startswith(f"{name}:"):
                return line.split(":", 1)[1].strip()
        return ""

    @staticmethod
    def _cookie_value(head: bytes, name: str) -> Optional[str]:
        try:
            text = head.decode("latin-1", errors="ignore")
        except Exception:
            return None
        for line in text.split("\r\n"):
            if line.lower().startswith("cookie:"):
                for part in line.split(":", 1)[1].split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == name and v:
                        return v
        return None

    def _authenticate(self, token: Optional[str]) -> Optional[User]:
        """Return the iVS user this request belongs to, or None.

        Mirrors the dashboard's own rules: the token must be valid, the user
        active, and the user allowed to see this particular app.
        """
        if not token:
            return None
        try:
            payload = decode_token(token)
        except JWTError:
            return None
        except Exception:
            return None
        username = payload.get("sub")
        if not username:
            return None

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user is None or not user.is_active:
                return None
            app = db.query(App).filter(App.id == self.app_id).first()
            if app is None:
                return None
            # Imported lazily: apps.py imports services, so importing it at
            # module scope would be circular.
            from app.routers.apps import _can_access_app
            if not _can_access_app(user, app, db):
                return None
            # Detach a usable copy — the session closes below.
            db.expunge(user)
            return user
        except Exception as e:
            logger.warning(f"gate {self.slug}: auth check failed: {e}")
            return None
        finally:
            db.close()

    def _audit_visit(self, user: User, client_ip: str, user_agent: str):
        """Record that this user opened the app — throttled per user.

        The audit row must carry the visitor's IP and user-agent to be worth
        anything under §26, so we hand create_audit_log a small stand-in for
        the Request it would normally read those from.
        """
        now = datetime.now(timezone.utc)
        last = self._last_audit.get(user.id)
        if last and now - last < AUDIT_WINDOW:
            return
        self._last_audit[user.id] = now

        db = SessionLocal()
        try:
            from app.services.audit_service import create_audit_log
            create_audit_log(
                db, _GateRequest(client_ip, user_agent),
                user=user, action="app_access", resource_type="app",
                resource_id=str(self.app_id),
                details=f"เข้าใช้งานแอป {self.slug} ผ่านการยืนยันตัวตนของ iVS",
            )
            db.commit()
        except Exception as e:
            logger.warning(f"gate {self.slug}: could not audit access: {e}")
        finally:
            db.close()

    # ── responses ────────────────────────────────────────────────

    def _login_location(self, head: bytes) -> str:
        """Build the login URL from the Host the visitor actually used.

        Deriving it from the configured SERVER_IP breaks whenever the machine's
        address changes after boot (DHCP), sending people to a login page that
        isn't there. The host in front of us is by definition reachable.
        """
        host = self._header_value(head, "host")
        hostname = host.rsplit(":", 1)[0] if host else ""
        if not hostname:
            return self.login_url
        return f"http://{hostname}:3000/login"

    async def _deny(self, writer: asyncio.StreamWriter, head: bytes):
        """Send the visitor to the iVS login, or a 401 for non-navigations."""
        if self._is_navigation(head):
            location = f"{self._login_location(head)}?next=/dashboard"
            body = (
                "<!doctype html><meta charset='utf-8'>"
                f"<title>ต้องเข้าสู่ระบบ iVS</title>"
                f"<meta http-equiv='refresh' content='0;url={location}'>"
                f"<p>แอปนี้ต้องเข้าสู่ระบบ iVS ก่อน — "
                f"<a href='{location}'>ไปหน้าเข้าสู่ระบบ</a></p>"
            ).encode()
            await self._respond(
                writer, 302, "text/html; charset=utf-8", body,
                extra_headers=[f"Location: {location}"],
            )
        else:
            await self._respond(
                writer, 401, "application/json; charset=utf-8",
                b'{"detail":"iVS login required"}',
            )

    @staticmethod
    def _is_navigation(head: bytes) -> bool:
        """True when a browser is loading a page (as opposed to fetching an
        asset or calling an API) — those are the ones worth redirecting."""
        text = head.decode("latin-1", errors="ignore")
        first = text.split("\r\n", 1)[0]
        if not first.upper().startswith("GET"):
            return False
        # Modern browsers say so outright; fall back to the Accept header.
        for line in text.split("\r\n"):
            if line.lower().startswith("sec-fetch-mode:"):
                return "navigate" in line.lower()
        return bool(re.search(r"accept:[^\r\n]*text/html", text, re.I))

    async def _respond(
        self, writer: asyncio.StreamWriter, status: int, content_type: str,
        body: bytes, extra_headers: Optional[list] = None,
    ):
        reason = {302: "Found", 401: "Unauthorized", 502: "Bad Gateway"}.get(status, "OK")
        lines = [
            f"HTTP/1.1 {status} {reason}",
            f"Content-Type: {content_type}",
            f"Content-Length: {len(body)}",
            "Cache-Control: no-store",
            "Connection: close",
        ]
        if extra_headers:
            lines.extend(extra_headers)
        head = ("\r\n".join(lines) + "\r\n\r\n").encode()
        try:
            writer.write(head + body)
            await writer.drain()
        except Exception:
            pass
        await self._close(writer)

    @staticmethod
    async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    @staticmethod
    async def _close(writer: asyncio.StreamWriter):
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


class AppGateManager:
    """Owns every running gate, keyed by app id."""

    def __init__(self):
        self._gates: Dict[int, AppGate] = {}

    def login_url(self) -> str:
        from app.config import settings
        return f"http://{settings.SERVER_IP}:3000/login"

    async def start_gate(self, app: App) -> bool:
        if not app.port:
            return False
        await self.stop_gate(app.id)
        gate = AppGate(app.slug, app.id, app.port, self.login_url())
        try:
            await gate.start()
        except OSError as e:
            logger.error(f"Could not open gate port {app.port} for {app.slug}: {e}")
            return False
        self._gates[app.id] = gate
        return True

    async def stop_gate(self, app_id: int):
        gate = self._gates.pop(app_id, None)
        if gate:
            await gate.stop()

    def is_running(self, app_id: int) -> bool:
        return app_id in self._gates

    async def sync_all(self):
        """Bring gates in line with the database — used at startup."""
        db = SessionLocal()
        try:
            apps = db.query(App).filter(App.access_mode == "protected").all()
            for app in apps:
                if app.status and str(app.status).endswith("RUNNING"):
                    await self.start_gate(app)
        except Exception as e:
            logger.warning(f"Gate sync failed: {e}")
        finally:
            db.close()

    async def stop_all(self):
        for app_id in list(self._gates):
            await self.stop_gate(app_id)


app_gate_manager = AppGateManager()
