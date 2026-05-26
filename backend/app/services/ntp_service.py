"""
NTP Time Service — เวลามาตรฐานตามกฎหมายไทย

ตาม พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2550
และประกาศกระทรวงดิจิทัลฯ เรื่อง หลักเกณฑ์การเก็บรักษาข้อมูลจราจรทางคอมพิวเตอร์

เวลาที่บันทึกต้องอ้างอิงจาก NTP Server ที่น่าเชื่อถือ ได้แก่:
  1. time.navy.mi.th     — สถาบันมาตรวิทยา กองทัพเรือ (หลัก)
  2. clock.nectec.or.th   — ศูนย์เทคโนโลยีอิเล็กทรอนิกส์และคอมพิวเตอร์แห่งชาติ
  3. ntp.ku.ac.th          — มหาวิทยาลัยเกษตรศาสตร์

ระบบจะ:
- sync เวลากับ NTP server ทุก 5 นาที (background)
- คำนวณ offset ระหว่าง system clock กับ NTP
- ใช้ offset แก้ไขเวลาเมื่อสร้าง audit log
- บันทึกว่า sync กับ server ไหน เมื่อไหร่
"""

import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import ntplib

logger = logging.getLogger(__name__)

# NTP Servers ตามมาตรฐานกฎหมายไทย (เรียงตามลำดับความสำคัญ)
THAI_NTP_SERVERS = [
    {
        "host": "time.navy.mi.th",
        "name": "Royal Thai Navy (กองทัพเรือ)",
        "authority": "สถาบันมาตรวิทยาแห่งชาติ กองทัพเรือ",
    },
    {
        "host": "clock.nectec.or.th",
        "name": "NECTEC",
        "authority": "ศูนย์เทคโนโลยีอิเล็กทรอนิกส์และคอมพิวเตอร์แห่งชาติ",
    },
    {
        "host": "ntp.ku.ac.th",
        "name": "Kasetsart University (ม.เกษตรศาสตร์)",
        "authority": "มหาวิทยาลัยเกษตรศาสตร์",
    },
]

SYNC_INTERVAL_SECONDS = 300  # sync ทุก 5 นาที


class NTPService:
    """NTP Time Synchronization Service"""

    def __init__(self):
        self._offset: float = 0.0  # seconds offset from NTP
        self._last_sync: Optional[datetime] = None
        self._sync_server: Optional[str] = None
        self._sync_server_name: Optional[str] = None
        self._sync_authority: Optional[str] = None
        self._sync_stratum: Optional[int] = None
        self._sync_delay: Optional[float] = None
        self._sync_count: int = 0
        self._sync_errors: int = 0
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._client = ntplib.NTPClient()

    def start(self):
        """Start background NTP sync thread."""
        if self._running:
            return
        self._running = True
        # Initial sync (blocking)
        self._sync_once()
        # Start background thread
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info(f"NTP Service started — syncing with Thai NTP servers every {SYNC_INTERVAL_SECONDS}s")

    def stop(self):
        """Stop background sync."""
        self._running = False

    def _sync_once(self):
        """Try each NTP server in order until one succeeds."""
        for server_info in THAI_NTP_SERVERS:
            host = server_info["host"]
            try:
                response = self._client.request(host, version=3, timeout=5)
                with self._lock:
                    self._offset = response.offset
                    self._last_sync = datetime.now(timezone.utc)
                    self._sync_server = host
                    self._sync_server_name = server_info["name"]
                    self._sync_authority = server_info["authority"]
                    self._sync_stratum = response.stratum
                    self._sync_delay = response.delay
                    self._sync_count += 1

                offset_ms = round(response.offset * 1000, 1)
                logger.info(
                    f"NTP sync OK: {host} ({server_info['name']}) "
                    f"offset={offset_ms}ms stratum={response.stratum} "
                    f"delay={round(response.delay * 1000, 1)}ms"
                )
                return True
            except Exception as e:
                logger.warning(f"NTP sync failed for {host}: {e}")
                continue

        # All servers failed
        with self._lock:
            self._sync_errors += 1
        logger.error("NTP sync failed — all Thai NTP servers unreachable, using system clock")
        return False

    def _sync_loop(self):
        """Background sync loop."""
        while self._running:
            time.sleep(SYNC_INTERVAL_SECONDS)
            if self._running:
                self._sync_once()

    def now(self) -> datetime:
        """Get current time corrected by NTP offset."""
        with self._lock:
            offset = self._offset
        return datetime.now(timezone.utc) + timedelta(seconds=offset)

    def get_status(self) -> dict:
        """Get NTP sync status for display/API."""
        with self._lock:
            return {
                "synced": self._last_sync is not None,
                "ntp_server": self._sync_server,
                "ntp_server_name": self._sync_server_name,
                "ntp_authority": self._sync_authority,
                "ntp_stratum": self._sync_stratum,
                "offset_ms": round(self._offset * 1000, 2) if self._offset else 0,
                "delay_ms": round(self._sync_delay * 1000, 2) if self._sync_delay else None,
                "last_sync": self._last_sync.isoformat() if self._last_sync else None,
                "sync_count": self._sync_count,
                "sync_errors": self._sync_errors,
                "sync_interval_seconds": SYNC_INTERVAL_SECONDS,
            }


# Singleton instance
ntp_service = NTPService()
