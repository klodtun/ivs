# OpenCLI Bridge — Architecture & Schema (design draft)

> Status: **DESIGN — not yet implemented.** Review before code.
> Feature: middleware that reads a legacy system (read-only), strips PII,
> and emits an OpenCLI `cli-manifest.json` + Markdown structure so a future
> AI Agent can **clone and extend the system in natural language**.
> Ships as a base feature of **iVS Pro & Enterprise**.

---

## 1. Goal & success metric

**Goal:** bridge legacy systems → AI Agents, without persisting raw legacy data.

**Success metric (the acceptance test, not vibes):** a full round-trip —

```
IVS's own ivs.db  ──bridge──▶  manifest.json + markdown  ──AI Agent──▶  regenerated IVS
                                                                          │
                             assert: regenerated ≈ original  ◀────────────┘
                             + agent can add a feature via natural language
```

Dogfood target: import IVS's own SQLite DB, regenerate IVS. If an agent can
rebuild IVS from the artifacts, the bridge works.

---

## 2. Why not lock to one database (roadmap answer)

Future AI stores change (vector, graph, …). So split **3 concerns**, each its
own store. Only the middle one is future-sensitive, and we keep it as **files**.

| Concern | Store | Rebuildable? | Tier |
|---------|-------|--------------|------|
| History / hash / deletion log | SQLite → Postgres (ENT) | no (source of record) | Pro+ |
| **Transformed artifacts** (manifest + markdown) | **files on disk + git** | — (source of truth) | Pro+ |
| AI retrieval index (embeddings) | pluggable: pgvector / Qdrant | **yes, from files** | ENT |

**Principle:** durable output = **files**, not rows. DB holds only metadata +
history. Vector index is derived and throwaway. → future AI-DB swap = re-index
from files, zero migration.

**Already in the codebase:** `license_service.EDITIONS_WITH_EXTERNAL_DB =
{"PRO", "ENT"}` and `edition_supports_external_db()`. The Pro/ENT external-DB
gate exists — the bridge just calls it. No new licensing work.

Tier map:
- **FREE / LITE / STD** — no bridge.
- **PRO** — bridge + SQLite metadata + file artifacts + local single-node MCP.
- **ENT** — + Postgres metadata, + pluggable vector index, + multi-node MCP,
  + per-import RBAC.

---

## 3. Pipeline (5 stages)

```
Legacy source ─▶ [1 Import] ─▶ [2 PII Filter] ─▶ [3 Transform] ─▶ [4 Publish] ─▶ AI Agent
 DB/API/files    read-only,       exclude/anon      cli-manifest     MCP + .md      clone +
                 NOT saved                          .json + .md      server         extend (NL)
                     │
                     └─▶ [5 History]  importer + sha256 + deletion-log  (reuse audit_logs)
```

| Stage | Behaviour | Reuse |
|-------|-----------|-------|
| 1 Import | Read source into **memory only**. SHA-256 the raw bytes. Persist only a metadata row. Raw never touches DB or disk. | Level-0 pattern from 3-tier logging; `integrity_service` hashing |
| 2 PII Filter | Per-import profile: `EXCLUDE` (drop PII columns/rows) or `ANONYMIZE` (`pii_anonymizer.anonymize`). Applied **before** any artifact is written. | `services/pii_anonymizer.py:anonymize()` (HMAC-stable) |
| 3 Transform | Introspect source structure → emit `cli-manifest.json` (each capability = OpenCLI command obj) + Markdown structure tree for agent context. | new `services/opencli_service.py` |
| 4 Publish | Serve manifest + markdown as an **MCP server** so Claude/Cursor read it. | new `mcp/` module |
| 5 History | `opencli_imports` + `opencli_import_deletions` tables. Every import/delete audit-logged at WARNING. Retention-purge aware. | `audit_service.create_audit_log`, `retention_service` |

**PII invariant:** raw bytes exist only in stage-1 process memory. Every artifact
that reaches disk has already passed stage 2. Right-to-be-forgotten = no-op on
artifacts (no PII in them); deletion history covers the metadata rows.

---

## 4. Source connectors (don't commit to one format)

Interface mirrors OpenCLI's `strategy` field. Ship `sqlite` first (dogfood IVS).

```python
# services/opencli/connectors/base.py
class SourceConnector(Protocol):
    strategy: str                       # "local" | "cookie" | "public" | "intercept" | "ui"
    def probe(self, ref: str) -> SourceMeta: ...        # size, kind, no data read
    def stream(self, ref: str) -> Iterator[Record]: ... # yields records, never persists
    def structure(self, ref: str) -> Structure: ...     # schema/graph for the manifest
```

| Connector | strategy | ref example | Phase |
|-----------|----------|-------------|-------|
| `SqliteConnector` | local | `/path/legacy.db` | P1 (first) |
| `RestConnector` | intercept | `https://host/api` or `ivs-<slug>` container | P2 |
| `FileConnector` | local | uploaded CSV / JSON / MD | P2 |

---

## 5. DB schema (new tables)

Follows IVS conventions: add model class (auto-`create_all`); new column on
existing table → PRAGMA-checked `ALTER TABLE` in `main.py`.

```python
# models.py  (append)

class OpenCliImport(Base):
    __tablename__ = "opencli_imports"
    id            = Column(Integer, primary_key=True)
    importer_id   = Column(Integer, ForeignKey("users.id"), nullable=False)  # WHO
    source_kind   = Column(String, nullable=False)   # "sqlite" | "rest" | "file"
    source_ref    = Column(String, nullable=False)   # path/url (no data, ref only)
    source_bytes  = Column(Integer, nullable=False)  # size probed
    sha256_raw    = Column(String, nullable=False)   # HASH of raw import (your req)
    pii_profile   = Column(String, nullable=False)   # "EXCLUDE" | "ANONYMIZE"
    status        = Column(String, nullable=False)   # pending|transformed|published|deleted
    artifact_dir  = Column(String, nullable=True)    # path to manifest+md (files, not blob)
    manifest_sha  = Column(String, nullable=True)    # sha256 of emitted cli-manifest.json
    created_at    = Column(DateTime, default=utcnow) # legal-grade ts
    # NOTE: raw imported data is intentionally NOT a column here.

class OpenCliImportDeletion(Base):
    __tablename__ = "opencli_import_deletions"
    id           = Column(Integer, primary_key=True)
    import_id    = Column(Integer, ForeignKey("opencli_imports.id"), nullable=False)
    deleted_by   = Column(Integer, ForeignKey("users.id"), nullable=False)  # WHO deleted
    reason       = Column(String, nullable=True)
    sha256_raw   = Column(String, nullable=False)   # preserved for the record
    deleted_at   = Column(DateTime, default=utcnow)
    # deletion history survives even after the import row is gone.
```

Both write an `audit_logs` row via `create_audit_log(...)` at WARNING.
Destructive delete reuses the existing `PasswordConfirmModal` re-auth pattern.

---

## 6. OpenCLI manifest mapping

Each legacy capability → one command object (schema from jackwener/opencli):

```jsonc
// artifact_dir/cli-manifest.json  (array)
[{
  "site": "legacy-crm",           // system id
  "name": "list-customers",       // capability
  "access": "read",               // read | write
  "domain": "internal",
  "strategy": "local",            // = connector strategy
  "browser": false,
  "args": [{"name":"limit","type":"int","default":50,"help":"rows"}],
  "columns": ["id","name","status"],   // PII columns already stripped in stage 2
  "type": "js",
  "modulePath": "./commands/list-customers.js",
  "sourceFile": "table:customers"
}]
```

Alongside it, `artifact_dir/structure.md` — human+agent readable tree
(entities, relations, flows) that gives the agent context to regenerate.

---

## 7. MCP interface (stage 4)

Local MCP server exposes each import's artifacts to any agent:

| MCP tool | Returns |
|----------|---------|
| `list_imports()` | published imports (id, site, status) |
| `get_manifest(import_id)` | the `cli-manifest.json` |
| `get_structure(import_id)` | `structure.md` |
| `get_command(import_id, name)` | one command's full spec |

ENT: multi-node + per-import RBAC on these tools.

---

## 8. Frontend

- Feature flag `opencli_bridge` in `frontend/src/lib/features.ts` (gate on
  edition PRO/ENT via existing license check).
- Dashboard route `app/dashboard/bridge/` — import wizard (source → PII profile
  → preview manifest → publish), import-history table (reuse `<Pagination>` +
  `formatLegalTimestamp`), deletion-history view.
- i18n: TH + EN both (+ en-EU / ja overlays for compliance strings).

---

## 9. Phased plan

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **P0** (this doc) | Architecture + schema — review gate | ✅ done |
| **P1** | SQLite connector + stages 1,2,3,5. Dogfood: import `ivs.db` → emit manifest+md → history row. No UI. | ✅ done (19 cmds, PII excluded, git-per-import) |
| **P2** | MCP server (stage 4) + router + PRO/ENT gate + dashboard UI | ✅ done (REST/File connectors deferred) |
| **P3** | Round-trip acceptance test + REST connector | ✅ done (fidelity 100% on ivs.db: 19/19 tables, 190/190 cols) |
| **P4** | ENT vector index + regeneration handoff + Postgres note | ✅ done (39 chunks, keyword backend; pgvector/Qdrant pluggable) |
| **P5** | Pre-flight Advisor — inspect source before import, recommend settings | ✅ done (ivs.db: 3 critical, 13 warn; auto-recommends ANONYMIZE + exclude users/vault_keys) |
| **P6** | Embedded regen — multi-provider LLM (vendor-neutral), config, generate | ✅ done (manual default offline; anthropic + openai-compatible incl. on-prem Ollama) |
| **P7** | Project/App model — group imports, multi-user, versioned | ✅ done (`OpenCliProject`; `project_id` on imports; wizard picks/creates project) |
| **P8** | Code versions + Deploy/Export | ✅ done (`OpenCliCodeVersion` history; regen→version; Deploy reuses app-deploy; Export .zip; delete=password+audit) |
| **P9** | MCP token management (ENT) — connect external agents | ✅ done (`OpenCliMcpToken`; mint-once/list-masked/revoke; scoped per project) |
| **P10** | SQL connectors — Postgres / MySQL / SQL Server / Oracle | ✅ done (one SQLAlchemy connector, dialect-agnostic; verified via sqlite URL: 22 tables, schema fingerprint) |
| **P11** | Control-center dashboard + natural-language chat | ✅ done (summary counts + hero cards; `POST /chat` grounded on project manifest, provider-neutral) |
| **P12** | SQL dump (.sql) connector — schema-only, no data load | ✅ done (parses CREATE TABLE DDL; ignores INSERTs; file SHA-256 verifiable; kind `sqldump`) |
| **P13** | Legacy code analyzer (the "โค้ดเดิม" input) — Project Analyzer | ✅ done (folder→code map: modules/roles/tables + secret detection; attached to project; enriches regen brief) |
| **P14** | Module-by-module regeneration — step-by-step / multi-agent foundation | ✅ done (`modules.py`; group by table prefix; scoped brief per module; `generate_module`; parse-safe so a bad model reply isn't silent) |

### Module-by-module regen (P14) — the realistic + multi-agent path

One-shot whole-app generation is beyond any single call for a real system. `modules.py`
groups the manifest into modules by table prefix (bill1/2/3→bill, customer*→customer),
and `generate_module` builds a **scoped brief** (only that module's tables) so small
models handle each chunk and each step maps to a natural-language "build the <module>
module" command. Each module = its own `OpenCliCodeVersion` (tagged `module`), kept as
history; doing all modules = the whole app. This is the foundation for **multi-agent**
(fan modules out to several AIs later). Endpoints `GET /imports/{id}/modules`,
`POST /imports/{id}/regen/module`. UI: "Modules" button → per-module Build. Verified:
Bizsale → 12 modules. Also: `parse_files_safe` — a model reply that isn't a parseable
file set now returns files=0 + the raw text snippet (no more silent generate).

### Legacy code analyzer (P13) — DB schema alone can't rebuild a working system

`code_analyzer.py` — reads a legacy source folder (PHP/py/js/…), builds a **code
map** (modules→operations, roles from nav, tables referenced) WITHOUT storing raw
code, and **detects secrets** (DB credentials, hardcoded passwords, API keys) to
exclude them. Map is stored per-project (`_projects/<pid>/code_map.md`);
`regen.build_brief` includes it (`legacy_code_map`) so the AI regenerates a
*faithful working replacement* from DB schema **+** app structure, not just the
schema. Endpoint `POST /projects/{id}/analyze-code`; UI "Attach legacy code" panel
when a project is selected. Verified on real Bizsale PHP: 213 files, 18 modules,
26 tables cross-linked to the DB, 6 secret files caught (connectdb.php + passwords).
This is the roadmap's second input (code) and the infographic's "Project Analyzer".

### SQL dump connector (P12) — read a `.sql` export, no live DB, no data

`connectors/sqldump_conn.py` parses `CREATE TABLE` DDL from a mysqldump / pg_dump
/ generic `.sql` file to build the schema. **INSERT rows are never parsed** — the
bridge needs structure only, so no real data/PII is read. The whole file is
SHA-256'd (importer can `sha256sum` + verify → Row1). No temp DB, no engine, no
data load → faster + more compliant than restore-then-drop. Kind `sqldump`;
preflight uses the parsed structure (`inspect_structure`). The live-DB connector
now rejects a file path / `file://` / `.sql` ref with a clear message (was 500).
Verified on a real 1.6MB MariaDB dump: 24 tables, `admin.password` dropped under
EXCLUDE.

### SQL connectors (P10) — closes the "connect to their DB" gap

`connectors/sqlalchemy_conn.py` — a **single** connector for Postgres / MySQL /
SQL Server / Oracle via SQLAlchemy reflection (Inspector: tables/columns/PK/FK).
`source_ref` is a SQLAlchemy URL; the DB driver (psycopg2 / pymysql / pyodbc /
oracledb) is lazy-loaded per target. Stage-1 hash for a live DB is a deterministic
**schema fingerprint** (tables+columns+types+PK/FK) + row count — proves the
analyzed schema matches the source without copying data. Kinds `postgres|mysql|
mssql|oracle|sql` in the pipeline registry; preflight has a matching SQL path.
Frontend wizard has a source-kind dropdown with per-dialect URL placeholders.
Verified end-to-end through a `sqlite:///` URL (identical code path for all dialects).

### Control Center + NL chat (P11) — matches the exec infographic hero

`GET /dashboard` → counts (projects / imports / code versions / deployed / active
tokens) + provider + edition → hero card row. `POST /chat` (`chat_service.py`) —
natural-language command grounded on the selected project's latest manifest, using
the configured LLM provider (manual returns an offline helper message; anthropic /
openai call the model). UI: a chat panel above the workflow.

### Project / Code versions / MCP tokens (P7–P9)

- **P7** `OpenCliProject` groups imports (each import = a source version). `project_id`
  FK added to `opencli_imports` (PRAGMA-checked ALTER in main.py). `project_service`
  (create/list with counts). Endpoints `GET/POST /projects`. Import wizard picks or
  creates a project first.
- **P8** `OpenCliCodeVersion` — every regeneration is a kept history version (own dir
  `<artifact_dir>/code/vN`). `code_service` records on generate, lists, **exports .zip**,
  **deploys** by reusing the IVS app-deploy primitives (`docker_service.detect_app_type`
  /`build_and_run` + `dns_service.register_app`; needs Docker). Delete = password
  re-auth + audit (iVS destructive standard), soft (row kept). New source data → regen =
  new version; old kept until deleted. Endpoints: `GET /imports/{id}/code`,
  `POST /code/{id}/deploy`, `GET /code/{id}/export`, `DELETE /code/{id}`.
- **P9** `OpenCliMcpToken` (ENT) — the ENT "AI search" panel became **Connect external
  AI Agent**: mint scoped MCP tokens per project (only SHA-256 stored, plaintext shown
  once), list masked, revoke. `mcp_token_service.verify()` resolves a presented token
  for a future HTTP-MCP gateway. Q&A search kept as a small sub-feature. Endpoints:
  `GET/POST /projects/{id}/tokens`, `DELETE /tokens/{id}`.

### Embedded regeneration — multi-provider (P6), NO vendor lock-in

Government/enterprise procurement rejects single-vendor lock. So the LLM layer is
provider-neutral: `services/opencli/llm/` (`base` + `registry` + provider classes).

| provider | what | key |
|----------|------|-----|
| `manual` (default) | **no external call** — returns the brief for an external agent via MCP | none |
| `anthropic` | Claude (`claude-opus-4-8`, adaptive thinking, effort high, streamed) | required |
| `openai` | OpenAI **chat-completions-compatible** — OpenAI, Azure, and via `base_url` **local Ollama / vLLM / LM Studio** (fully on-prem, no foreign vendor) | placeholder ok for local |

Config in `system_config` (`opencli.llm.provider/model/base_url`); API key encrypted
at rest with the existing `vault_service` (never returned — only `has_key`).
Endpoints: `GET/PUT /llm/config` (PUT = ADMIN, audit WARNING),
`POST /imports/{id}/regen/generate`. Generate writes files to
`<artifact_dir>/candidate/` and runs `regen.verify_candidate` (IVS deploy-time
check). `regen_service.generate` orchestrates brief → provider → files → verify.
Adding a provider = one class + registry entry; the manifest+brief contract is
provider-agnostic, so no other code changes.

### Pre-flight Advisor (P5) — `services/opencli/preflight.py`

Read-only inspection **before** any transform/hash/persist. `POST /imports/preflight`
(same `ImportCreate` body). Returns findings + `recommended_pii_profile` +
`recommended_exclude_tables`; the UI "Pre-flight check" button applies the PII
recommendation automatically. SQLite gets deep introspection; other connectors
get structural findings only. Checks:

| code | severity | catches |
|------|----------|---------|
| `sensitive-table` | critical | table name ~ user/auth/vault/secret/token → exclude whole table |
| `pii-freetext` | warn | free-text column (note/comment/address/…) regex can't scrub → ANONYMIZE |
| `no-pk` | warn | no primary key → relations may not round-trip |
| `blob` | warn | binary column → can't be a command, skipped |
| `large-table` | warn | > 100k rows → sample |
| `view` / `trigger` | info | behavioral logic not in schema → won't round-trip |
| `no-fk` | info | no foreign keys → agent infers relations from names |

### AI retrieval index (P4, Enterprise) — `services/opencli/vector.py`

Derived + rebuildable from artifact files (never source of truth). `chunk_import()`
splits manifest + structure.md into stable-id chunks (`<import_id>:<kind>:<ref>`);
`VectorIndex` protocol is pluggable — default `KeywordIndex` (TF-IDF, **no deps**)
so the pipeline is testable now; ENT registers a pgvector/Qdrant backend that
embeds the **same chunks**. Index persists to `artifact_dir/index.json`,
rebuildable any time → future AI-DB swap = re-index, zero migration.
Endpoints (ENT-gated via `edition_supports_vector_index`, ENT-only):
`POST /imports/{id}/index/rebuild`, `POST /imports/{id}/index/query`.
Verified: 39 chunks from ivs.db; query "users login" → `list-users` top hit.

### Regeneration handoff (P4) — `services/opencli/regen.py`

Closes the behavioral loop. `build_brief(imp)` → self-contained payload for an
external agent (manifest + structure + target zip layout + acceptance criteria +
MCP config). `verify_candidate(dir)` runs the agent's produced app through IVS's
own `_validate_zip_structure` (the exact deploy-time check) so a bad regeneration
is rejected before deploy. Endpoint: `GET /imports/{id}/regen/brief`.
Full loop: brief → external Claude Code writes app/ → verify_candidate →
`POST /api/apps` runs it → re-import → round-trip fidelity == 1.0.

### Postgres metadata (P4, Enterprise) — config, not code

Bridge models are plain SQLAlchemy → engine-agnostic. ENT points `DATABASE_URL`
at Postgres; no model changes. External-DB gate already exists
(`edition_supports_external_db`). No P4 code needed beyond documenting it.

### Round-trip acceptance test (P3, the success metric)

`services/opencli/roundtrip.py` + `GET /api/opencli/imports/{id}/roundtrip` + UI
button. Deterministic: reconstructs schema from the emitted `cli-manifest.json`,
diffs it against the live source under the PII policy, returns:

```
fidelity = reconstructed_non_pii_columns_correct / columns_expected
passed   = all tables present AND fidelity == 1.0 AND no missing/extra cols
```

Dogfood (import IVS's own ivs.db, EXCLUDE): **fidelity 100%, 19/19 tables,
190/190 columns, 7 PII columns correctly dropped, 0 defects.** This is the
structural proxy for "an agent can regenerate the system"; behavioral identity
is the agent's job via the MCP server. `scripts/roundtrip_bridge.py [id]` runs it
from the CLI (exit 1 on defect → CI-gate-able).

### REST connector (P3, experimental)

`connectors/rest_conn.py` (strategy `intercept`). Reads `<base>/openapi.json`
(any FastAPI app, incl. deployed `ivs-<slug>` containers) and maps each operation
to a command (GET→`read`, write verbs→`write`). Stage-1 hash = the openapi.json
bytes. Introspection-only — `stream()` is intentionally unimplemented. Verified:
111 commands parsed from IVS's own OpenAPI.

### MCP server config (for external agent, P2)

Add to the agent's `.mcp.json` (Claude Code / Cursor):

```json
{"mcpServers": {"ivs-opencli": {
  "command": "bash",
  "args": ["-c", "cd /Users/klod/IVS/backend && source venv/bin/activate && python -m app.services.opencli.mcp_server"]
}}}
```

Tools exposed: `list_imports`, `get_manifest`, `get_structure`, `get_command`.

---

## 10. Decisions (locked 2026-07-11)

1. **Regeneration engine = hybrid, 2 handoffs.**
   IVS deploy path (`POST /apps`) only *runs* a pre-built `.zip` — it validates
   zip structure (`_validate_zip_structure`) + generates a Dockerfile + starts a
   container. It does **not** generate code from a spec. So:
   - **Write step** (manifest+md → source): external Claude Code / MCP agent.
     It emits a `.zip` matching the structure `_validate_zip_structure` expects.
   - **Run step** (`.zip` → container): existing IVS deploy path, unchanged.
   MCP server (stage 4) is exactly the bridge between the two — it feeds the
   external agent. P3 round-trip test drives: bridge → MCP → agent writes zip →
   `POST /apps` runs it → diff against original.
2. **Artifact storage = git-per-import.** Each import gets its own repo:
   `deployed_apps/_bridge/<import_id>/` with `git init` on first transform.
   Every re-transform = a commit → per-import version history for free.
3. **PII = regex in P1, ML classifier flagged for ENT.** `pii_anonymizer`
   (email/ip/phone/thai-id/cc/jwt) ships P1. Free-text-column ML detection is an
   ENT-tier upgrade, deferred.
4. **Connector order = SQLite (P1) → REST (P2), experimental.** REST introspects
   a live `ivs-<slug>` container. Revisit vs. flat-file after P1 dogfood.
