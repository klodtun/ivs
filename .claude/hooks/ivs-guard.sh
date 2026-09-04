#!/usr/bin/env bash
# Refuses the shell commands that lose iVS data, and everything risky while an
# event is running. Reads the PreToolUse payload on stdin, answers with a
# permission decision.
#
# This is the part that actually stops damage. CLAUDE.md tells an agent what not
# to do; nothing makes it obey. This does.
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
EVENT_FLAG="$REPO/data/EVENT-LIVE"

payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

deny() {
  jq -nc --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

ask() {
  jq -nc --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# ---------------------------------------------------------------- never, ever
# A deployed app keeps its database inside its own container and volume. Removing
# either destroys an event's records with no copy anywhere else. A human who
# really means it can run this in their own terminal.
case "$cmd" in
  *"docker volume rm"*|*"docker volume prune"*)
    deny "ลบ volume = ข้อมูลของแอปหายถาวร กู้ไม่ได้ ถ้าตั้งใจจริงให้พิมพ์เองใน terminal" ;;
  *"docker compose down"*"-v"*|*"docker-compose down"*"-v"*)
    deny "down -v ลบ volume ทั้งหมดรวม caddy_data (ใบรับรอง) และข้อมูลทุกแอป" ;;
esac

# `docker rm ivs-<slug>` throws away that app's data directory with the container.
if printf '%s' "$cmd" | grep -qE '\bdocker[[:space:]]+(container[[:space:]]+)?rm\b' \
   && printf '%s' "$cmd" | grep -qE '\bivs-[a-z0-9._-]+'; then
  deny "ลบคอนเทนเนอร์ ivs-* = ข้อมูลแอปนั้นหาย ให้ redeploy ผ่านหน้า iVS แทน"
fi

# ------------------------------------------------------- while an event is on
# The riskiest hour is the one where people are actually walking through a gate.
# A single flag file, set by a person, closes the door on everything that could
# interrupt or erase a live event.
if [ -f "$EVENT_FLAG" ]; then
  if printf '%s' "$cmd" | grep -qE '\bdocker\b.*\b(stop|restart|kill|rm|up|start|compose)\b' \
     || printf '%s' "$cmd" | grep -qE '\b(start-ivs|deploy)\b'; then
    deny "มีงานจัดอยู่ (data/EVENT-LIVE) — ห้าม deploy/restart/stop ระหว่างนี้ เพราะ redeploy ล้างบันทึกของแอปทิ้ง ลบไฟล์ธงก่อนถ้างานจบแล้ว"
  fi
fi

# ------------------------------------------------ high blast radius, ask first
# Editing these breaks name resolution or routing for every app at once —
# legitimate, but never something to do without a person looking.
if printf '%s' "$cmd" | grep -qE '(coredns/hosts|caddy/Caddyfile)' \
   && printf '%s' "$cmd" | grep -qE '(>|>>|sed -i|tee|rm |mv )'; then
  ask "แก้ DNS/proxy กระทบทุกแอปพร้อมกัน ยืนยันก่อน"
fi

exit 0
