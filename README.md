# IVS — Internal Vibe Server

**Current version: v1.0.14 (Free Edition)** — see [Releases](https://github.com/klodtun/ivs/releases) for the latest.

Self-hosted platform for deploying AI-built apps on your own NAS or mini-PC. Drag-and-drop deploy, no DevOps needed.

## Requirements

- Docker Desktop (or Docker Engine on Linux)
- Git
- 4 GB RAM minimum
- No external API keys required

## Install (with AI assistant)

The easiest way is to let Claude Code Desktop guide you through the setup:

```bash
git clone https://github.com/klodtun/ivs.git
cd IVS
```

Then open Claude Code Desktop, drag the `IVS` folder into the chat, and paste the contents of [`INSTALL_WITH_AI.md`](INSTALL_WITH_AI.md).

## Install (manual)

```bash
git clone https://github.com/klodtun/ivs.git
cd IVS

# Copy and edit environment config
cp .env.example .env
# Edit .env: set SECRET_KEY, VAULT_KEY, ADMIN_PASSWORD, SERVER_IP

# Start IVS
docker compose -f docker-compose.free.yml up -d
```

Open `http://localhost:3000` — default login: `admin` / `admin123` (change immediately).

## First-time setup checklist

- [ ] Change `ADMIN_PASSWORD` in `.env` before going live
- [ ] Generate a strong `SECRET_KEY` (`openssl rand -hex 32`)
- [ ] Generate a strong `VAULT_KEY` (`openssl rand -hex 32`)
- [ ] Set `SERVER_IP` to your machine's LAN IP

## Stop / restart

```bash
docker compose -f docker-compose.free.yml down
docker compose -f docker-compose.free.yml up -d
```

## Edition

This is **IVS Free** — single-machine, unlimited app deployments, full audit log, PDPA/GDPR compliance tools.

For multi-machine management and enterprise features, see [IVS Enterprise](#) (coming soon).

## License

**Proprietary — IVS Free Edition EULA.** See [`LICENSE`](LICENSE) (English) and [`LICENSE.th.md`](LICENSE.th.md) (Thai).

This is **NOT open-source software.** Redistribution, resale, and removal of copyright notices are prohibited. Free for personal and internal non-commercial use on a single machine. Commercial or multi-machine deployments require an [IVS Enterprise](#) license.

Copyright © 2026 IVS Project. All Rights Reserved.
