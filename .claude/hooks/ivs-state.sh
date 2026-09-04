#!/usr/bin/env bash
# Hands every new session the state of the actual machine.
#
# CLAUDE.md can describe how iVS works, but not what this box is doing right now:
# which apps are up, which ports they hold, whether an event is running, whether
# the proxy is even alive. That is where the damage happens, and a file written
# by hand would be stale the day after it was written. So it is measured, not
# remembered.
set -uo pipefail
REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

report="สถานะเครื่อง iVS ตอนนี้ (วัดสดตอนเปิดเซสชัน ไม่ใช่ไฟล์ที่เขียนไว้):"

if [ -f "$REPO/data/EVENT-LIVE" ]; then
  report="$report
  ⚠️ มีงานจัดอยู่ — data/EVENT-LIVE ถูกตั้งไว้ ห้าม deploy/restart/stop อะไรทั้งสิ้น"
fi

apps=$(docker ps --filter name=ivs- --format '{{.Names}} {{.Ports}} {{.Status}}' 2>/dev/null | head -20)
report="$report
  แอปที่รันอยู่:
${apps:-  (docker ไม่ตอบ หรือไม่มีคอนเทนเนอร์)}"

if docker ps --filter name=caddy --format '{{.Names}}' 2>/dev/null | grep -q .; then
  report="$report
  Caddy: รันอยู่ — แอปเข้าถึงได้ผ่านชื่อโดเมนและ HTTPS"
else
  report="$report
  Caddy: ไม่ได้รัน — register_app() จึงตกไปคืน URL แบบ IP:PORT ซึ่งเป็น HTTP ล้วน
    ผลตามมา: กล้องสแกน QR และ Web NFC ใช้ไม่ได้บนมือถือ เพราะต้องการ secure context
    ทางลัดที่ใช้ได้ทันที: เปิด Tunnel ในหน้า iVS — ได้ https จาก ngrok/cloudflare
    ที่มือถือเชื่อถือ โดยไม่ต้องตั้ง Caddy หรือติดตั้งใบรับรองลงเครื่องใดเลย"
fi

ip=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
stale=$(grep -cvE "^#|^${ip:-0.0.0.0} " "$REPO/coredns/hosts" 2>/dev/null || echo 0)
report="$report
  IP เครื่องตอนนี้: ${ip:-ไม่ทราบ} · รายการใน coredns/hosts ที่ชี้ไป IP อื่น: $stale
    (IP เครื่องเปลี่ยนตาม DHCP แต่ hosts จดค่าตอนลงทะเบียน รายการเก่าจึงชี้ผิดเงียบๆ)"

jq -nc --arg c "$report" '{
  hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: $c }
}'
