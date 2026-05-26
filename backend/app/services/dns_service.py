import os
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class DNSService:
    """Manages CoreDNS records and Caddy reverse proxy config for app subdomains."""

    def __init__(self):
        self.domain_suffix = settings.DOMAIN_SUFFIX
        self.server_ip = settings.SERVER_IP  # Always current — detected at startup
        self.caddy_api = settings.CADDY_API_URL
        self.dns_hosts_file = os.path.join(settings.COREDNS_CONFIG_PATH, "hosts")
        logger.info(f"DNSService initialized with server_ip={self.server_ip}")

    def get_app_domain(self, app_slug: str) -> str:
        return f"{app_slug}.{self.domain_suffix}"

    async def register_app(self, app_slug: str, port: int) -> str:
        domain = self.get_app_domain(app_slug)
        self._update_dns_hosts(app_slug, domain)
        caddy_ok = await self._update_caddy_route(app_slug, domain, port)
        if caddy_ok:
            logger.info(f"Registered {domain} -> port {port}")
            return f"http://{domain}"
        else:
            # Caddy not available — return direct IP:port URL for dev/LAN access
            direct_url = f"http://{self.server_ip}:{port}"
            logger.info(f"Caddy not available, using direct URL: {direct_url}")
            return direct_url

    async def unregister_app(self, app_slug: str):
        domain = self.get_app_domain(app_slug)
        self._remove_dns_host(app_slug)
        await self._remove_caddy_route(app_slug)
        logger.info(f"Unregistered {domain}")

    def _update_dns_hosts(self, app_slug: str, domain: str):
        os.makedirs(os.path.dirname(self.dns_hosts_file), exist_ok=True)
        entries = {}
        if os.path.exists(self.dns_hosts_file):
            with open(self.dns_hosts_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            entries[parts[1]] = parts[0]

        entries[domain] = self.server_ip

        with open(self.dns_hosts_file, "w") as f:
            f.write("# IVS Auto-generated DNS hosts\n")
            for host, ip in sorted(entries.items()):
                f.write(f"{ip} {host}\n")

    def _remove_dns_host(self, app_slug: str):
        domain = self.get_app_domain(app_slug)
        if not os.path.exists(self.dns_hosts_file):
            return
        with open(self.dns_hosts_file, "r") as f:
            lines = f.readlines()
        with open(self.dns_hosts_file, "w") as f:
            for line in lines:
                if domain not in line:
                    f.write(line)

    async def _update_caddy_route(self, app_slug: str, domain: str, port: int) -> bool:
        """Update Caddy reverse proxy route. Returns True if successful."""
        route_id = f"ivs-{app_slug}"
        route_config = {
            "@id": route_id,
            "match": [{"host": [domain]}],
            "handle": [
                {
                    "handler": "reverse_proxy",
                    "upstreams": [{"dial": f"ivs-{app_slug}:{port}"}],
                }
            ],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.caddy_api}/config/apps/http/servers/srv0/routes",
                    json=route_config,
                    timeout=5.0,
                )
                if resp.status_code not in (200, 201):
                    logger.warning(f"Caddy route update returned {resp.status_code}: {resp.text}")
                    return False
                return True
        except Exception as e:
            logger.warning(f"Could not update Caddy (may not be running): {e}")
            return False

    async def _remove_caddy_route(self, app_slug: str):
        route_id = f"ivs-{app_slug}"
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(f"{self.caddy_api}/id/{route_id}", timeout=5.0)
        except Exception as e:
            logger.warning(f"Could not remove Caddy route: {e}")

    def get_all_domains(self) -> list[dict]:
        domains = []
        if os.path.exists(self.dns_hosts_file):
            with open(self.dns_hosts_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            domains.append({"ip": parts[0], "domain": parts[1]})
        return domains


dns_service = DNSService()
