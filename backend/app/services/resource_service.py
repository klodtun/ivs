"""Resource monitoring, capacity analysis, and report generation."""
import json
import logging
import subprocess
import psutil
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import App, AppStatus, ResourceMetric
from app.services.docker_service import docker_service

logger = logging.getLogger(__name__)

# Capacity thresholds
WARN_CPU = 70
CRIT_CPU = 90
WARN_MEM = 75
CRIT_MEM = 90
WARN_DISK = 80
CRIT_DISK = 95
ESTIMATED_APP_RAM_MB = 200  # average RAM per app for capacity estimation


def _get_gpu_info() -> dict:
    """Try to detect GPU memory via nvidia-smi or Apple Silicon."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            timeout=5, stderr=subprocess.DEVNULL,
        ).decode().strip()
        parts = out.split(",")
        return {"used_mb": int(parts[0].strip()), "total_mb": int(parts[1].strip()), "type": "nvidia"}
    except Exception:
        pass
    # Apple Silicon — unified memory, report as shared with RAM
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=3, stderr=subprocess.DEVNULL)
        total_mb = int(out.strip()) // (1024 * 1024)
        mem = psutil.virtual_memory()
        # Use (total - available) so bytes match mem.percent on macOS
        used_mb = (mem.total - mem.available) // (1024 * 1024)
        return {"used_mb": used_mb, "total_mb": total_mb, "type": "apple_silicon"}
    except Exception:
        return {"used_mb": None, "total_mb": None, "type": "none"}


def _get_per_app_stats(db: Session) -> list[dict]:
    """Get resource usage per running app from Docker."""
    apps = db.query(App).filter(App.status == AppStatus.RUNNING, App.container_id.isnot(None)).all()
    result = []
    for app in apps:
        # Self-heal stale container_id (rebuilt outside IVS)
        live_id = docker_service.resolve_live_container_id(app.container_id or "", f"ivs-{app.slug}")
        if live_id and live_id != app.container_id:
            app.container_id = live_id
            try: db.commit()
            except Exception: db.rollback()
        stats = docker_service.get_container_stats(live_id or app.container_id)
        result.append({
            "slug": app.slug,
            "name": app.name,
            "app_type": app.app_type.value if hasattr(app.app_type, "value") else str(app.app_type),
            "cpu_percent": stats.get("cpu_percent", 0),
            "memory_mb": round(stats.get("memory_usage", 0) / (1024 * 1024), 1),
            "memory_limit_mb": round(stats.get("memory_limit", 0) / (1024 * 1024), 1),
            "port": app.port,
        })
    return result


def collect_snapshot(db: Session):
    """Collect a single resource snapshot and store it."""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = _get_gpu_info()
    # Count from database (source of truth) instead of Docker labels
    total = db.query(App).count()
    running = db.query(App).filter(App.status == AppStatus.RUNNING).count()
    per_app = _get_per_app_stats(db)

    # Match the same accounting as get_current_resources() for chart consistency
    metric = ResourceMetric(
        cpu_percent=int(cpu),
        memory_used_mb=int((mem.total - mem.available) / (1024 * 1024)),
        memory_total_mb=int(mem.total / (1024 * 1024)),
        disk_used_gb=int(disk.used / (1024 ** 3)),
        disk_total_gb=int((disk.used + disk.free) / (1024 ** 3)),
        gpu_memory_used_mb=gpu["used_mb"],
        gpu_memory_total_mb=gpu["total_mb"],
        apps_running=running,
        apps_total=total,
        per_app_json=json.dumps(per_app),
    )
    db.add(metric)
    db.commit()

    # Retention purge moved out of the hot path — centralized in
    # services.retention_service.purge_all() and run once a day by the
    # retention_purge_loop in main.py. This keeps collect_snapshot fast
    # and means the retention window is configurable per-deploy.

    return metric


def get_current_resources(db: Session) -> dict:
    """Get current system resources + per-app stats + capacity analysis."""
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu = _get_gpu_info()
    # Count from database (source of truth) instead of Docker labels
    total = db.query(App).count()
    running = db.query(App).filter(App.status == AppStatus.RUNNING).count()
    per_app = _get_per_app_stats(db)

    # Memory accounting — keep bytes, percent, and "free for new apps" consistent:
    #   - memory_used_mb     uses (total - available), matches mem.percent
    #     (otherwise on macOS inactive/cached pages cause bytes vs % mismatch).
    #   - mem_available_mb   = psutil's "actually free for new processes"
    #     used for capacity planning (apps_can_add).
    mem_total_mb = int(mem.total / (1024 * 1024))
    mem_used_mb = int((mem.total - mem.available) / (1024 * 1024))
    mem_available_mb = int(mem.available / (1024 * 1024))

    # Disk accounting — on macOS APFS, disk.total includes purgeable space
    # shared with other volumes (used + free ≠ total). psutil.disk.percent uses
    # used / (used + free), so use that as the effective total to stay consistent.
    disk_used_gb = round(disk.used / (1024 ** 3), 1)
    disk_total_gb = round((disk.used + disk.free) / (1024 ** 3), 1)

    # Capacity estimation — goal is "how many more apps can we add while keeping
    # RAM usage below the WARN_MEM threshold (75%)?"
    #
    # If we used the full available memory we'd just be telling the user to fill
    # the box until it crashes, which contradicts the warning that fires at 75%.
    # Instead, compute the headroom from current usage up to the warning line.
    # If we're already over the line, capacity is 0 (the user must reduce load,
    # not add more).
    target_used_mb = int(mem_total_mb * WARN_MEM / 100)
    headroom_mb = max(0, target_used_mb - mem_used_mb)
    apps_can_add = headroom_mb // ESTIMATED_APP_RAM_MB

    # Alerts
    alerts = []
    if cpu >= CRIT_CPU:
        alerts.append({"level": "critical", "type": "cpu", "message": f"CPU {cpu:.0f}% (critical >{CRIT_CPU}%)"})
    elif cpu >= WARN_CPU:
        alerts.append({"level": "warning", "type": "cpu", "message": f"CPU {cpu:.0f}% (warning >{WARN_CPU}%)"})

    if mem.percent >= CRIT_MEM:
        alerts.append({"level": "critical", "type": "memory", "message": f"RAM {mem.percent:.0f}% (critical >{CRIT_MEM}%)"})
    elif mem.percent >= WARN_MEM:
        alerts.append({"level": "warning", "type": "memory", "message": f"RAM {mem.percent:.0f}% (warning >{WARN_MEM}%)"})

    if disk.percent >= CRIT_DISK:
        alerts.append({"level": "critical", "type": "disk", "message": f"Disk {disk.percent:.0f}% (critical >{CRIT_DISK}%)"})
    elif disk.percent >= WARN_DISK:
        alerts.append({"level": "warning", "type": "disk", "message": f"Disk {disk.percent:.0f}% (warning >{WARN_DISK}%)"})

    # Capacity guidance — phrased so it can't contradict the RAM warning.
    # If RAM is already past the warning line, capacity is 0 by construction
    # (see headroom calc above), so we tell the user to free resources instead
    # of suggesting they can still add apps.
    if running > 0:
        if apps_can_add == 0 and mem.percent >= WARN_MEM:
            alerts.append({
                "level": "warning",
                "type": "capacity",
                "message": f"At capacity — RAM at {mem.percent:.0f}% (target ≤{WARN_MEM}%). Stop or scale down apps before deploying more.",
            })
        elif apps_can_add <= 1:
            alerts.append({
                "level": "warning",
                "type": "capacity",
                "message": f"Near capacity — only ~{apps_can_add} more app(s) can run while keeping RAM ≤{WARN_MEM}%",
            })

    return {
        "system": {
            "cpu_percent": round(cpu, 1),
            "cpu_cores": psutil.cpu_count(),
            "memory_used_mb": mem_used_mb,
            "memory_total_mb": mem_total_mb,
            "memory_percent": round(mem.percent, 1),
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "disk_percent": round(disk.percent, 1),
            "gpu_type": gpu["type"],
            "gpu_used_mb": gpu["used_mb"],
            "gpu_total_mb": gpu["total_mb"],
        },
        "capacity": {
            "apps_running": running,
            "apps_total": total,
            "estimated_apps_can_add": apps_can_add,
            "estimated_ram_per_app_mb": ESTIMATED_APP_RAM_MB,
            "ram_free_mb": mem_available_mb,
        },
        "per_app": per_app,
        "alerts": alerts,
    }


def get_history(db: Session, hours: int = 24) -> list[dict]:
    """Get historical resource metrics."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    metrics = db.query(ResourceMetric).filter(
        ResourceMetric.created_at >= cutoff
    ).order_by(ResourceMetric.created_at.asc()).all()

    return [{
        "time": m.created_at.isoformat(),
        "cpu": m.cpu_percent,
        "mem_used": m.memory_used_mb,
        "mem_total": m.memory_total_mb,
        "disk_used": m.disk_used_gb,
        "disk_total": m.disk_total_gb,
        "gpu_used": m.gpu_memory_used_mb,
        "gpu_total": m.gpu_memory_total_mb,
        "apps_running": m.apps_running,
        "per_app": json.loads(m.per_app_json) if m.per_app_json else [],
    } for m in metrics]


def generate_report(db: Session) -> str:
    """Generate Markdown resource report for meetings."""
    res = get_current_resources(db)
    hist = get_history(db, hours=24)
    sys = res["system"]
    cap = res["capacity"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# IVS Resource & Capacity Report",
        "",
        f"**Generated**: {now}",
        "",
        "---",
        "",
        "## System Hardware",
        "",
        f"| Resource | Used | Total | Usage |",
        f"|----------|------|-------|-------|",
        f"| CPU | {sys['cpu_percent']}% | {sys['cpu_cores']} cores | {'🔴' if sys['cpu_percent']>CRIT_CPU else '🟡' if sys['cpu_percent']>WARN_CPU else '🟢'} |",
        f"| RAM | {sys['memory_used_mb']:,} MB | {sys['memory_total_mb']:,} MB | {'🔴' if sys['memory_percent']>CRIT_MEM else '🟡' if sys['memory_percent']>WARN_MEM else '🟢'} {sys['memory_percent']}% |",
        f"| Storage | {sys['disk_used_gb']} GB | {sys['disk_total_gb']} GB | {'🔴' if sys['disk_percent']>CRIT_DISK else '🟡' if sys['disk_percent']>WARN_DISK else '🟢'} {sys['disk_percent']}% |",
    ]

    if sys["gpu_type"] != "none":
        gpu_label = "GPU (Apple Silicon)" if sys["gpu_type"] == "apple_silicon" else "GPU (NVIDIA)"
        lines.append(f"| {gpu_label} | {sys['gpu_used_mb'] or 'N/A'} MB | {sys['gpu_total_mb'] or 'N/A'} MB | - |")

    lines += [
        "",
        "## Capacity Analysis",
        "",
        f"- **Running Apps**: {cap['apps_running']} / {cap['apps_total']}",
        f"- **Free RAM**: {cap['ram_free_mb']:,} MB",
        f"- **Estimated additional apps**: ~{cap['estimated_apps_can_add']} more (at ~{cap['estimated_ram_per_app_mb']} MB/app)",
        "",
    ]

    # Alerts
    if res["alerts"]:
        lines += ["## Alerts", ""]
        for a in res["alerts"]:
            icon = "🔴" if a["level"] == "critical" else "🟡"
            lines.append(f"- {icon} **{a['type'].upper()}**: {a['message']}")
        lines.append("")

    # Per-app usage
    if res["per_app"]:
        lines += [
            "## Per-App Resource Usage",
            "",
            "| App | Type | CPU | RAM (MB) | Port |",
            "|-----|------|-----|----------|------|",
        ]
        total_cpu = 0
        total_mem = 0
        for a in res["per_app"]:
            lines.append(f"| {a['name']} | {a['app_type']} | {a['cpu_percent']}% | {a['memory_mb']} | {a['port']} |")
            total_cpu += a["cpu_percent"]
            total_mem += a["memory_mb"]
        lines.append(f"| **Total** | | **{round(total_cpu,1)}%** | **{round(total_mem,1)}** | |")
        lines.append("")

    # 24h summary
    if hist:
        cpus = [h["cpu"] for h in hist]
        mems = [h["mem_used"] for h in hist]
        lines += [
            "## 24-Hour Summary",
            "",
            f"- **CPU**: avg {sum(cpus)//len(cpus)}%, max {max(cpus)}%, min {min(cpus)}%",
            f"- **RAM**: avg {sum(mems)//len(mems):,} MB, max {max(mems):,} MB, min {min(mems):,} MB",
            f"- **Data Points**: {len(hist)}",
            "",
        ]

    # Recommendations
    lines += [
        "## Recommendations",
        "",
    ]
    if sys["memory_percent"] > WARN_MEM:
        lines.append(
            f"- **Reduce RAM load**: Current usage {sys['memory_percent']}% exceeds the {WARN_MEM}% target. "
            f"Stop unused apps or upgrade RAM before deploying more."
        )
    if sys["disk_percent"] > WARN_DISK:
        lines.append(f"- **Expand Storage**: Current usage {sys['disk_percent']}% — recommend larger disk or cleanup")
    if cap["estimated_apps_can_add"] == 0:
        lines.append(
            f"- **At capacity**: No new apps can be added while keeping RAM ≤{WARN_MEM}%. "
            f"Free resources or scale the host first."
        )
    elif cap["estimated_apps_can_add"] <= 2:
        lines.append(
            f"- **Scale Resources**: Only ~{cap['estimated_apps_can_add']} more app(s) fit under the {WARN_MEM}% RAM target — consider hardware upgrade soon."
        )
    if not res["alerts"] and cap["estimated_apps_can_add"] > 5:
        lines.append("- System resources are healthy. No immediate action required.")

    lines += ["", "---", f"*Report generated by IVS v1.0.0*", ""]
    return "\n".join(lines)
