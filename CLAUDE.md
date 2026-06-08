# IVS — Internal Vibe Server

Self-hosted app deployment platform that lets non-DevOps users deploy AI-built
apps to a private server (NAS / mini-PC) with one drag-and-drop. Production
target: Synology NAS. Dev target: macOS.

## Tech stack

- **Backend**: FastAPI (Python 3.9) + SQLAlchemy + SQLite + `python-docker`.
  Entry: `backend/app/main.py`. Routes in `backend/app/routers/*.py`.
- **Frontend**: Next.js 14 (App Router, `"use client"` for interactive pages).
  Entry: `frontend/src/app/dashboard/`. Tailwind + custom `brand` color palette.
- **Process model**: One uvicorn (port 8000) + one Next.js (port 3000),
  orchestrated by `scripts/start-ivs.sh`. Deployed user apps run as plain
  Docker containers named `ivs-<slug>` on per-app ports.

## Important directories

```
backend/app/
  main.py              FastAPI lifespan: migrations, NTP, mDNS, background loops
  database.py          SQLAlchemy engine (sqlite:///./data/ivs.db)
  models.py            All tables (one big file, not split)
  schemas.py           Pydantic request/response models
  middleware/auth.py   verify_password / require_role / get_current_user
  routers/             apps.py, system.py, auth.py, vault.py, tunnels.py, pdpa.py
  services/            Plain Python modules with side effects:
                       docker_service, dns_service, vault_service,
                       audit_service, ntp_service, resource_service,
                       app_log_service, retention_service, mdns_service

frontend/src/
  app/dashboard/       One folder per route — page.tsx + layout.tsx
  components/          Shared widgets (AppCard, DeleteAppModal, Pagination, ...)
  lib/utils.ts         Date helpers, cn() classname merger
  lib/api.ts           Single object with one function per endpoint
  lib/i18n.ts          Thai + English dictionary — keep both in sync

scripts/start-ivs.sh   Launches backend + frontend with mode toggle
```

## Dev workflow

```bash
# Default = dev mode: uvicorn --reload + next dev (hot reload both sides)
bash scripts/start-ivs.sh

# Production mode (used on the NAS deploy): next start (pre-built .next/)
IVS_MODE=prod bash scripts/start-ivs.sh
```

In **dev mode** code edits take effect immediately — backend reloads, browser
hot-replaces the module. In **prod mode** the script auto-runs `npm run build`
if `.next/` is missing.

If a change isn't showing up: it's almost always either (a) browser cache
(Cmd+Shift+R), or (b) you're in prod mode and forgot to `npm run build`.

## Database & migrations

SQLite at `backend/data/ivs.db`. No alembic. Two paths for schema changes:

1. **New table** — just add the model class; `Base.metadata.create_all()` in
   the lifespan handler picks it up on next restart.
2. **New column on an existing table** — add to the model AND append a
   PRAGMA-checked `ALTER TABLE` in `main.py:_apply_lightweight_migrations()`.
   SQLite < 3.35 has no `ADD COLUMN IF NOT EXISTS`, so we introspect first.

## Background loops (in `main.py` lifespan)

| Loop | Interval | What it does |
|------|----------|--------------|
| `tunnel_cleanup_loop` | 30s | Expire ngrok-style tunnels past `expires_at` |
| `resource_collection_loop` | 60s | Snapshot CPU/RAM/disk into `resource_metrics` |
| `app_log_collection_loop` | 30s | Mirror `docker logs` of every running container into `app_log_entries` |
| `retention_purge_loop` | 24h | Delete rows past their configured retention window |

All loops use `SessionLocal()` per iteration (never a shared session).

## Background context the next agent needs

These were debated and settled — don't re-litigate without reason:

### Legal / compliance

- **Thai Computer Crime Act (พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560) §26**: traffic
  data must be retained ≥ 90 days; officer can extend up to 2 years (730 d)
  or more. We allow admin-set retention from `MIN_DAYS_BY_TYPE` up to
  `MAX_ALLOWED = 3650` (10 y hard cap so a typo can't pin forever).
- **Audit log table is for system events only** — login, deploy, delete,
  config changes. Container stdout/stderr lives in a SEPARATE table
  (`app_log_entries`) so the legal audit view stays focused. Both get bundled
  into the same export .zip though, in different subfolders.
- **NTP**: Backend syncs against Thai legal NTP servers (`time.navy.mi.th`
  etc.) via `ntp_service`. Audit exports record the NTP source in the
  manifest so timestamps are defensible.

### Retention service (`services/retention_service.py`)

Single source of truth for "how long do we keep X". Reads from
`system_config` table keyed `retention.<log_type>`. Used by:
- The daily `retention_purge_loop`
- The manual `POST /system/retention/purge` endpoint
- `app_log_service.purge_old_logs()` is now a thin shim around it

**Defaults**: audit_logs=730, app_logs=90, resource_metrics=30, exports=365.
Each is clamped to its own `MIN_DAYS_BY_TYPE` floor on write.

### Export bundles (v2 manifest)

`POST /api/system/audit-logs/export` produces a `.zip` containing:

```
audit_log_part_NNN.md           system events (existing)
apps/<slug>/app_log_part_NNN.md per-app container logs (added recently)
manifest.json                   has separate "audit_logs" + "app_logs" sections
README.txt                      human-readable layout + §26 citation
```

Each chunk embeds its own SHA-256 at the bottom. `manifest.json` lists the
expected SHA-256 of every chunk. The DB's `audit_log_exports.sha256_hash`
covers the outer .zip. Date range and chunk size in the request apply to
BOTH audit logs and per-app logs.

### App export (`POST /api/apps/{id}/export`)

Bundles `deployed_apps/<slug>/` + container `/app/backend/{data,uploads,db}`
(and a few fallback paths) into a `.zip` so users can update an app by
delete+redeploy without losing data. **Restricted to the original deployer
(`app.owner_id == user.id`).** Admins do NOT get an override — copyright
protection. Denied attempts are audit-logged.

### Destructive actions require password re-auth

`POST /api/system/retention/purge` requires `{ "password": "..." }` body and
verifies via `verify_password()`. Generic 403 on failure. Both success and
failure are audit-logged at WARNING. The frontend uses
`<PasswordConfirmModal>` (`components/password-confirm-modal.tsx`) — that
component is generic, reuse it for any future destructive action with legal
weight.

### Disk + RAM math on macOS (psutil gotcha)

On macOS APFS, `psutil.disk_usage('/').total` includes "purgeable" space
shared with other volumes, so `used + free ≠ total`. We deliberately report
`used + free` as the effective total in `system.py` and `resource_service.py`
so the gauge percentage and the displayed bytes agree. On Linux/Synology,
`used + free == total` so it's a no-op.

Similarly for RAM: `mem.percent` uses `(total - available)/total` while
`mem.used` excludes inactive/cached on macOS. We use `total - available` for
displayed memory_used so percentage and bytes match.

The capacity estimator (`apps_can_add`) targets `WARN_MEM = 75%` — it tells
the user "how many more apps fit while staying under the warning line",
NOT "how many fit until OOM". This avoids the dashboard advising "add 17
more apps" while also flashing a 75% RAM warning.

### Fullstack Dockerfile generator (`docker_service._generate_fullstack_files`)

Multi-stage build: Stage 1 is `node:20-alpine` running `npm run build`,
Stage 2 is `python:3.12-slim` + nginx. The generator checks that
`frontend/dist/` exists **and is non-empty** before taking the fast (no
node-builder) path — an empty `dist/` triggered the welcome-page bug.

The generated nginx config caches `/assets/*` for 1y (Vite hashes filenames)
but `/index.html` is `no-store, no-cache` so deploys take effect on next
load without users having to hard-refresh.

### Pagination + tables

Shared `<Pagination/>` + `usePagination<T>()` hook in
`components/pagination.tsx`. All large tables (audit logs, export history,
users, tunnels, per-app resources) use them. Default page size is 25; the
export-history table uses 10 because each row is dense.

### Legal-grade timestamps

`formatLegalTimestamp(date)` in `lib/utils.ts` renders
`"2026-05-27 20:09:03 (UTC+07:00)"` — full ISO with explicit offset. Use
this for any column that may end up in a compliance export or print. Don't
use the relative `timeAgo()` helper for anything law-adjacent.

## Conventions

- **Audit log every state change that affects another user**. The helper is
  `create_audit_log(db, request, user, action, resource_type, ...)`.
  Default level INFO; raise to WARNING for destructive/admin actions.
- **Role gates**: `require_role(UserRole.ADMIN)` or `require_role(ADMIN, DEVELOPER)`
  as a FastAPI dependency. Viewers never get write paths.
- **i18n**: every visible string goes through `t("key")`. Keys are
  dot-delimited (`settings.export_logs`). Always add BOTH Thai (top of file)
  and English (bottom of file) entries.
- **Modals over `confirm()`/`alert()`**: for anything that destroys data,
  use a dedicated modal with explicit consequences. `DeleteAppModal` for
  app deletion (type-the-name confirm); `PasswordConfirmModal` for actions
  with legal weight (password re-auth).
- **No tracking cookies / external analytics** — IVS targets on-prem PDPA-
  conscious deployments.

## Things to avoid

- Don't add scheduled work outside the `main.py` lifespan loops. Cron is
  someone else's problem on this host.
- Don't query `audit_logs` to render the AppCard "View Logs" view. That's
  what `app_log_service.get_logs_for_export` is for, and the live view goes
  straight to Docker.
- Don't store secrets in env vars in deployed apps. Use `vault_service` —
  it injects vault values into the container at runtime.
- Don't call `alert()` from React components for error display. Surface
  errors inline (toast, banner, modal `error` slot).
- Don't bypass `_can_access_app` checks. Developers see their own apps
  plus apps assigned to them via `UserAppAccess`. Admins see all.

### v1.0 scope — feature flags (`frontend/src/lib/features.ts`)

These features have working backend code but their UI is hidden in
v1.0. Flip the flag to true to re-expose:

| Flag | Hides | Plan |
|------|-------|------|
| `api_catalog` | sidebar "คลัง API สาธารณะ" | v1.2 |
| `dns_tab` | settings DNS & Domain tab | v1.1 |
| `network_tab` | settings Network tab | v1.1 |
| `gitea_tab` | settings Gitea tab | v1.2 (optional plugin) |

Backend routes for these stay live — only sidebar + tab list filter
them out via `isEnabled(...)`. Re-enabling = single boolean flip.

### 3-Tier Privacy-Compliant Logging Architecture

This is the model behind every log table in IVS — PDPA/GDPR/APPI all
demand the same idea: PII never persists in identifiable form.

```
  Level 0 — Raw Data (PII intact)
  ┌──────────────────────────────────────────────────────────┐
  │  Source: docker logs, FastAPI request handlers           │
  │  Lifetime: process memory only — NEVER written to DB     │
  │  Access:  root / live debug only                         │
  └──────────────────────────────────────────────────────────┘
                          │
                          │  services/pii_anonymizer.anonymize()
                          ▼
  Level 1 — System Storage (anonymized, durable)
  ┌──────────────────────────────────────────────────────────┐
  │  Tables: app_log_entries, audit_logs                     │
  │  Email     → u#<hash>@<domain>                           │
  │  Public IP → <network>.[ANON_<hash>] (private IPs kept)  │
  │  Thai ID/CC/JWT/Bearer → [REDACTED:TYPE]                 │
  │  Right-to-be-Forgotten: no-op — no PII exists to delete  │
  └──────────────────────────────────────────────────────────┘
                          │
                          │  routers/system.export_audit_logs()
                          ▼
  Level 2 — Export (tamper-evident)
  ┌──────────────────────────────────────────────────────────┐
  │  Per-chunk SHA-256 embedded in .md                       │
  │  manifest.json with all chunk hashes                     │
  │  Outer .zip SHA-256 stored in audit_log_exports          │
  └──────────────────────────────────────────────────────────┘
```

**Where the boundary lives:** `app_log_service.collect_one_pass()`
runs `anonymize_pii(text)` BEFORE the `db.add(AppLogEntry(...))` call.
Never store raw container output. The "View Logs" button on AppCard
goes straight to `docker logs` (Level 0) — that's fine because it's
ephemeral and only admin-visible.

**HMAC stability:** the anonymizer uses HMAC-SHA256 keyed off
`settings.SECRET_KEY` so the same email always maps to the same
opaque token — ops can correlate without re-identifying.

### i18n & regulatory mapping

Four locales (`lib/i18n.ts`):

| Locale | Flag | Regulator | Note |
|--------|------|-----------|------|
| `th` | 🇹🇭 | PDPA (2562/2019) | Full dictionary |
| `en` | 🇬🇧 | Generic English | Full dictionary, default fallback |
| `en-EU` | 🇪🇺 | GDPR (2016/679) | Overlay — only Art. 5/13/17/25/30/32-specific strings; rest falls back to `en` |
| `ja` | 🇯🇵 | APPI (2003 + 2022 amendments) | Overlay — core nav + compliance strings; rest falls back to `en` |

Add new compliance-sensitive strings to the en-EU and ja overlays when
the wording differs by regulator. UI-only strings can stay en-only.

### Vault reveal-for-copy

`POST /api/vault/{id}/reveal` returns the decrypted plaintext for
one-shot clipboard copy. Admin + Developer roles. Every call is
audit-logged as `reveal_key` at WARNING level — that's the primary
forensic signal if a key gets leaked. The Vault page's per-card
"คัดลอก" button uses this endpoint; plaintext never enters React
state, the toast clears after 2s.

## Quick reference — recent commits worth knowing

```
7dacacb  feat(retention): password re-auth for manual purge
fba751e  feat(retention-panel): collapse-by-default, persisted choice
d789b4c  feat(retention): centralized configurable auto-delete for all logs
09ac982  feat(ui): legal-grade timestamps + pagination across all data tables
b023ffc  feat(audit): 90-day app log retention + per-app export files
45f4d69  feat(audit-export): date-range filter + chunked .zip bundle
7be4105  feat(apps): export app source + runtime data as a single .zip bundle
78d6174  feat(export): restrict export to original deployer (copyright)
d6ff271  feat(app-card): rich delete confirmation modal (type-to-confirm)
ed23d86  chore(scripts): start-ivs.sh defaults to dev mode with hot reload
906a751  fix(docker): multi-stage build for fullstack apps
```

See `git log --oneline` for the full list.
