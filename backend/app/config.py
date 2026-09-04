import os
import socket
from pydantic_settings import BaseSettings


def _detect_local_ip() -> str:
    """Auto-detect LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class Settings(BaseSettings):
    APP_NAME: str = "iVS - Internal Vibe Server"
    APP_VERSION: str = "1.9.2"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/ivs.db")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "ivs-dev-secret-change-in-production-2024")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    VAULT_KEY: str = os.getenv("VAULT_KEY", "ivs-vault-key-change-in-production!")

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/app/uploads")
    APPS_DIR: str = os.getenv("APPS_DIR", "/app/deployed_apps")

    DOMAIN_SUFFIX: str = os.getenv("DOMAIN_SUFFIX", "vibe.local")
    SERVER_IP: str = os.getenv("SERVER_IP", _detect_local_ip())

    CADDY_API_URL: str = os.getenv("CADDY_API_URL", "http://caddy:2019")
    COREDNS_CONFIG_PATH: str = os.getenv("COREDNS_CONFIG_PATH", "/etc/coredns")

    DOCKER_SOCKET: str = os.getenv("DOCKER_SOCKET", "unix:///var/run/docker.sock")
    DOCKER_NETWORK: str = os.getenv("DOCKER_NETWORK", "ivs-apps")

    # คำนำหน้าชื่อคอนเทนเนอร์ของแอปที่ดีพลอย — เป็นสมบัติของเครื่องติดตั้ง
    # ไม่ใช่ของรุ่น ตั้งครั้งเดียวตอนติดตั้งครั้งแรกแล้วห้ามเปลี่ยน เพราะแอปที่
    # รันอยู่ถูกค้นด้วยชื่อนี้ เปลี่ยนเมื่อไหร่แอปเดิมหายจากหน้าจอทั้งที่ยัง
    # ทำงานอยู่ ค่าที่ตั้งไว้จะถูกเทียบกับที่จดใน installation ทุกครั้งที่บูต
    CONTAINER_PREFIX: str = os.getenv("CONTAINER_PREFIX", "ivs-")

    # รุ่นย่อย — ชุดโมดูลที่กล่องนี้แจกมาเพื่อทำ คนละแกนกับระดับใบอนุญาต
    # ดู app/variants.py  เครื่องพัฒนาใช้ "all" เพื่อสาธิตได้ครบ
    IVS_VARIANT: str = os.getenv("IVS_VARIANT", "all")

    APP_PORT_RANGE_START: int = int(os.getenv("APP_PORT_RANGE_START", "10000"))
    APP_PORT_RANGE_END: int = int(os.getenv("APP_PORT_RANGE_END", "10999"))

    TUNNEL_PROVIDER: str = os.getenv("TUNNEL_PROVIDER", "frp")
    FRP_SERVER: str = os.getenv("FRP_SERVER", "")

    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    class Config:
        env_file = ".env"


settings = Settings()
