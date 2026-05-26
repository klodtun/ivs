"""
mDNS Service — Broadcasts IVS on the local network via Bonjour/Avahi.

Default hostname: ivs.local
Admin can change to avoid conflicts when multiple IVS instances exist.

Uses a dedicated thread to avoid event loop conflicts with uvicorn.
"""
import logging
import socket
import threading
from typing import Optional

from zeroconf import Zeroconf, ServiceInfo

logger = logging.getLogger(__name__)

DEFAULT_MDNS_HOSTNAME = "ivs"
MDNS_SERVICE_TYPE = "_http._tcp.local."


class MDNSService:
    def __init__(self):
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._current_hostname: str = DEFAULT_MDNS_HOSTNAME
        self._port: int = 80  # Caddy proxy port (production)
        self._running: bool = False
        self._lock = threading.Lock()

    @property
    def current_hostname(self) -> str:
        return self._current_hostname

    @property
    def mdns_address(self) -> str:
        return f"{self._current_hostname}.local"

    @property
    def is_running(self) -> bool:
        return self._running

    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _do_start(self, hostname: str, port: int):
        """Actually register the mDNS service (runs in a thread to avoid event loop conflicts)."""
        try:
            ip = self._get_local_ip()
            ip_bytes = socket.inet_aton(ip)

            service_name = f"IVS ({hostname})._http._tcp.local."

            self._service_info = ServiceInfo(
                MDNS_SERVICE_TYPE,
                service_name,
                addresses=[ip_bytes],
                port=port,
                properties={
                    "path": "/",
                    "product": "IVS - Internal Vibe Server",
                    "version": "1.0.0",
                    "hostname": hostname,
                },
                server=f"{hostname}.local.",
            )

            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(
                self._service_info,
                allow_name_change=True,
                cooperating_responders=True,
            )
            self._running = True

            logger.info(
                f"mDNS broadcasting: {hostname}.local → {ip}:{port}"
            )
        except Exception as e:
            logger.error(f"Failed to start mDNS: {type(e).__name__}: {e}")
            self._running = False

    def start(self, hostname: Optional[str] = None, port: int = 80):
        """Start broadcasting mDNS with the given hostname."""
        if hostname:
            self._current_hostname = hostname
        self._port = port

        with self._lock:
            self._stop_internal()

            # Run registration in a separate thread to avoid asyncio event loop conflicts
            t = threading.Thread(
                target=self._do_start,
                args=(self._current_hostname, self._port),
                daemon=True,
            )
            t.start()
            t.join(timeout=15)  # Wait up to 15s for registration

            if t.is_alive():
                logger.error("mDNS registration timed out")
                self._running = False

    def _stop_internal(self):
        """Stop without acquiring lock (called from within locked context)."""
        try:
            if self._zeroconf and self._service_info:
                self._zeroconf.unregister_service(self._service_info)
            if self._zeroconf:
                self._zeroconf.close()
        except Exception as e:
            logger.warning(f"Error stopping mDNS: {e}")
        finally:
            self._zeroconf = None
            self._service_info = None
            self._running = False

    def stop(self):
        """Stop mDNS broadcasting."""
        with self._lock:
            self._stop_internal()

    def update_hostname(self, new_hostname: str, port: Optional[int] = None):
        """Change the mDNS hostname (stops and restarts with new name)."""
        new_hostname = new_hostname.strip().lower().replace(".local", "")
        if not new_hostname:
            new_hostname = DEFAULT_MDNS_HOSTNAME

        # Remove invalid characters (only allow alphanumeric and hyphens)
        clean = "".join(c for c in new_hostname if c.isalnum() or c == "-")
        if not clean:
            clean = DEFAULT_MDNS_HOSTNAME

        self._current_hostname = clean
        self.start(clean, port or self._port)
        return self._current_hostname

    def get_status(self) -> dict:
        """Get current mDNS status."""
        return {
            "running": self._running,
            "hostname": self._current_hostname,
            "mdns_address": self.mdns_address,
            "default_hostname": DEFAULT_MDNS_HOSTNAME,
            "ip": self._get_local_ip(),
            "port": self._port,
        }


mdns_service = MDNSService()
