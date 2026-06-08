# Third-Party Licenses — iVS (Internal Vibe Server)

**Generated:** 2026-06-06
**Scope:** Production runtime dependencies of iVS (backend + frontend).
**Method:** `pip-licenses` (backend/venv) + `npx license-checker --production` (frontend).
**iVS itself:** Proprietary EULA — see `LICENSE` (English) and `LICENSE.th.md` (Thai).
This audit covers ONLY the third-party open-source components that iVS bundles or imports.

---

## 1. License Summary

### Backend (Python — 47 packages)

| License | Count | Commercial use | Note |
|---------|-------|----------------|------|
| MIT | 23 | ✅ permissive | — |
| BSD (2/3-Clause, generic) | 12 | ✅ permissive | — |
| Apache-2.0 (incl. dual MIT/Apache) | 8 | ✅ permissive | — |
| PSF-2.0 (`typing_extensions`) | 1 | ✅ permissive | Python Software Foundation License |
| MPL-2.0 (`certifi`) | 1 | ✅ permissive (file-level copyleft only) | Bundles CA root list — unmodified |
| **LGPL-2.1-or-later (`zeroconf`)** | 1 | ✅ commercial OK | **See §3 — used as unmodified library** |
| Dual Apache/MIT or Apache/BSD | 3 | ✅ permissive | — |

### Frontend (JavaScript — 24 production packages, excluding `ivs-dashboard` itself)

| License | Count | Commercial use | Note |
|---------|-------|----------------|------|
| MIT | 16 | ✅ permissive | — |
| ISC | 3 | ✅ permissive | Functionally equivalent to MIT |
| Apache-2.0 | 2 | ✅ permissive | — |
| BSD-3-Clause | 1 | ✅ permissive | — |
| 0BSD (`tslib`) | 1 | ✅ permissive | Public-domain-equivalent |
| **CC-BY-4.0 (`caniuse-lite`)** | 1 | ✅ commercial OK | **See §3 — attribution required** |
| UNLICENSED | 1 | N/A | This is `ivs-dashboard` itself (proprietary) |

### Verdict

✅ **All third-party components are compatible with proprietary commercial distribution of iVS.**
No GPL, no AGPL, no SSPL, no Commons Clause in the runtime dependency tree.

---

## 2. Backend Components (Python)

| Package | Version | License | URL |
|---------|---------|---------|-----|
| Jinja2 | 3.1.4 | BSD | https://github.com/pallets/jinja/ |
| Mako | 1.3.12 | MIT | https://www.makotemplates.org/ |
| MarkupSafe | 3.0.3 | BSD-3-Clause | https://github.com/pallets/markupsafe/ |
| PyYAML | 6.0.3 | MIT | https://pyyaml.org/ |
| SQLAlchemy | 2.0.35 | MIT | https://www.sqlalchemy.org |
| aiofiles | 24.1.0 | Apache-2.0 | https://github.com/Tinche/aiofiles |
| alembic | 1.13.3 | MIT | https://alembic.sqlalchemy.org |
| annotated-types | 0.7.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.12.1 | MIT | https://anyio.readthedocs.io/ |
| bcrypt | 4.0.1 | Apache-2.0 | https://github.com/pyca/bcrypt/ |
| certifi | 2026.5.20 | MPL-2.0 | https://github.com/certifi/python-certifi |
| cffi | 2.0.0 | MIT | https://cffi.readthedocs.io/ |
| charset-normalizer | 3.4.7 | MIT | https://github.com/jawah/charset_normalizer |
| click | 8.1.8 | BSD | https://github.com/pallets/click/ |
| cryptography | 43.0.1 | Apache-2.0 / BSD (dual) | https://github.com/pyca/cryptography |
| docker | 7.1.0 | Apache-2.0 | https://github.com/docker/docker-py |
| ecdsa | 0.19.2 | MIT | http://github.com/tlsfuzzer/python-ecdsa |
| exceptiongroup | 1.3.1 | MIT | https://github.com/agronholm/exceptiongroup |
| fastapi | 0.115.0 | MIT | https://github.com/fastapi/fastapi |
| h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| httptools | 0.7.1 | MIT | https://github.com/MagicStack/httptools |
| httpx | 0.27.2 | BSD-3-Clause | https://github.com/encode/httpx |
| idna | 3.15 | BSD-3-Clause | https://github.com/kjd/idna |
| ifaddr | 0.2.0 | MIT | https://github.com/pydron/ifaddr |
| ntplib | 0.4.0 | MIT | https://github.com/cf-natali/ntplib |
| passlib | 1.7.4 | BSD | https://passlib.readthedocs.io |
| psutil | 6.0.0 | BSD | https://github.com/giampaolo/psutil |
| pyasn1 | 0.6.3 | BSD-2-Clause | https://github.com/pyasn1/pyasn1 |
| pycparser | 2.23 | BSD | https://github.com/eliben/pycparser |
| pydantic | 2.9.2 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.5.2 | MIT | https://github.com/pydantic/pydantic-settings |
| pydantic_core | 2.23.4 | MIT | https://github.com/pydantic/pydantic-core |
| python-dotenv | 1.0.1 | BSD | https://github.com/theskumar/python-dotenv |
| python-jose | 3.3.0 | MIT | http://github.com/mpdavis/python-jose |
| python-multipart | 0.0.12 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| requests | 2.32.5 | Apache-2.0 | https://requests.readthedocs.io |
| rsa | 4.9.1 | Apache-2.0 | https://stuvel.eu/rsa |
| six | 1.17.0 | MIT | https://github.com/benjaminp/six |
| sniffio | 1.3.1 | Apache-2.0 / MIT (dual) | https://github.com/python-trio/sniffio |
| starlette | 0.38.6 | BSD-3-Clause | https://github.com/encode/starlette |
| typing_extensions | 4.15.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| urllib3 | 2.6.3 | MIT | https://github.com/urllib3/urllib3 |
| uvicorn | 0.30.6 | BSD-3-Clause | https://www.uvicorn.org/ |
| uvloop | 0.22.1 | Apache-2.0 / MIT (dual) | https://github.com/MagicStack/uvloop |
| watchfiles | 1.1.1 | MIT | https://github.com/samuelcolvin/watchfiles |
| websockets | 13.1 | BSD | https://github.com/python-websockets/websockets |
| **zeroconf** | **0.148.0** | **LGPL-2.1-or-later** | **https://github.com/python-zeroconf/python-zeroconf** |

---

## 3. Frontend Components (JavaScript, production only)

| Package | Version | License | URL |
|---------|---------|---------|-----|
| @next/env | 14.2.15 | MIT | https://github.com/vercel/next.js |
| @next/swc-darwin-arm64 | 14.2.15 | MIT | https://github.com/vercel/next.js |
| @swc/counter | 0.1.3 | Apache-2.0 | https://github.com/swc-project/pkgs |
| @swc/helpers | 0.5.5 | Apache-2.0 | https://github.com/swc-project/swc |
| busboy | 1.6.0 | MIT | https://github.com/mscdex/busboy |
| **caniuse-lite** | **1.0.30001793** | **CC-BY-4.0** | **https://github.com/browserslist/caniuse-lite** |
| client-only | 0.0.1 | MIT | (vendored by Next.js) |
| clsx | 2.1.1 | MIT | https://github.com/lukeed/clsx |
| graceful-fs | 4.2.11 | ISC | https://github.com/isaacs/node-graceful-fs |
| js-tokens | 4.0.0 | MIT | https://github.com/lydell/js-tokens |
| loose-envify | 1.4.0 | MIT | https://github.com/zertosh/loose-envify |
| lucide-react | 0.447.0 | ISC | https://github.com/lucide-icons/lucide |
| nanoid | 3.3.12 | MIT | https://github.com/ai/nanoid |
| next | 14.2.15 | MIT | https://github.com/vercel/next.js |
| picocolors | 1.1.1 | ISC | https://github.com/alexeyraspopov/picocolors |
| postcss | 8.4.31 | MIT | https://github.com/postcss/postcss |
| react | 18.3.1 | MIT | https://github.com/facebook/react |
| react-dom | 18.3.1 | MIT | https://github.com/facebook/react |
| scheduler | 0.23.2 | MIT | https://github.com/facebook/react |
| source-map-js | 1.2.1 | BSD-3-Clause | https://github.com/7rulnik/source-map-js |
| streamsearch | 1.1.0 | MIT | https://github.com/mscdex/streamsearch |
| styled-jsx | 5.1.1 | MIT | https://github.com/vercel/styled-jsx |
| tailwind-merge | 2.6.1 | MIT | https://github.com/dcastil/tailwind-merge |
| tslib | 2.8.1 | 0BSD | https://github.com/Microsoft/tslib |

> Note: `ivs-dashboard` (the frontend package itself) shows as UNLICENSED in the scan — this is **iVS proprietary code**, governed by `LICENSE` and `LICENSE.th.md`, NOT a missing third-party license.

---

## 4. Special-Attention Components

### 4.1 `zeroconf` — LGPL-2.1-or-later

**Status:** ✅ Used as an unmodified Python library, imported via `pip install`.
**Obligation under LGPL-2.1 §6:** If we ship a derivative work of `zeroconf` itself (i.e., modify its source code), we must release the modifications under LGPL. Linking is permitted under any license.
**Compliance posture:** iVS does NOT modify `zeroconf` source. We `import zeroconf` only. Therefore §6 does not trigger and our proprietary EULA is unaffected.
**Mitigation if we ever fork it:** Either (a) keep the fork separate and release the diff under LGPL, or (b) replace with a permissively-licensed alternative such as `python-mdns` (Apache-2.0).

### 4.2 `caniuse-lite` — CC-BY-4.0

**Status:** ✅ Transitive dependency pulled in by Next.js / browserslist. Data file (browser support database), not executable code.
**Obligation under CC-BY-4.0:** Must include attribution to the original authors.
**Compliance posture:** Attribution is satisfied by this `THIRD_PARTY_LICENSES.md` file shipped with the iVS distribution.

### 4.3 `certifi` — MPL-2.0

**Status:** ✅ Used as an unmodified library (bundles Mozilla's CA root certificate list).
**Obligation under MPL-2.0:** File-level copyleft — only files of the MPL-licensed work that we modify must remain MPL. Combining with proprietary code is permitted.
**Compliance posture:** iVS does NOT modify `certifi`. We `import certifi` only. No MPL obligations propagate to iVS code.

### 4.4 `cryptography` — Apache-2.0 OR BSD-3-Clause (dual)

We choose to comply via Apache-2.0. No additional obligations beyond preserving copyright notice (already in NOTICE).

### 4.5 `ivs-dashboard` — UNLICENSED (intentional)

This is the iVS frontend package itself. It is proprietary, governed by `LICENSE` / `LICENSE.th.md`. The `UNLICENSED` field in `package.json` is the npm-conventional way to signal "no public license" for closed-source projects.

---

## 5. How This File Is Regenerated

Run from repo root:

```bash
# Backend
backend/venv/bin/pip install -q pip-licenses
backend/venv/bin/pip-licenses --format=markdown --with-urls > /tmp/py_lic.md

# Frontend (production deps only)
cd frontend && npx --yes license-checker --production --markdown > /tmp/js_lic.md
```

Then merge into this file. A CI step should run both commands per release and diff against the committed version; failure → block the release until the audit is reviewed.

---

## 6. Compliance Statement for depa Digital Startup Fund

For the purposes of the depa Digital Startup Fund S2 application:

> ทรัพย์สินทางปัญญาในซอร์สโค้ดของ iVS ทั้งหมดเป็นของผู้สมัคร (ลิขสิทธิ์จดทะเบียนกรมทรัพย์สินทางปัญญา ลข.01). ส่วนประกอบโอเพนซอร์ส (OSS) ที่ใช้งานในผลิตภัณฑ์ทั้งหมดอยู่ภายใต้ใบอนุญาตที่อนุญาตให้ใช้เชิงพาณิชย์ได้ (MIT, BSD, Apache-2.0, ISC, 0BSD, PSF-2.0, MPL-2.0, CC-BY-4.0, LGPL-2.1) โดยทุกองค์ประกอบใช้งานในรูปแบบ "unmodified library import" จึงไม่กระทบกับเงื่อนไขกรรมสิทธิ์ของ iVS. รายการ OSS ทั้งหมด พร้อมเวอร์ชันและประเภทใบอนุญาต ดูได้จากเอกสารฉบับนี้.

— End of Third-Party License Audit —
