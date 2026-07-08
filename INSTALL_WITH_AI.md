# IVS — AI-Assisted Installation Guide

Paste this entire file into Claude Code Desktop (or any Claude chat with file access) after cloning the repo.

---

## Prompt to paste into Claude Code Desktop

```
I want to install IVS (Internal Vibe Server) on this machine.
The project folder is already open. Please help me:

1. Check if Docker Desktop is installed and running. If not, tell me how to install it for my OS.
2. Check if the .env file exists. If not, copy .env.example to .env.
3. Generate a secure SECRET_KEY using: openssl rand -hex 32
4. Generate a secure VAULT_KEY using: openssl rand -hex 32
5. Detect my machine's LAN IP address and set SERVER_IP in .env.
6. Set ADMIN_PASSWORD to a random secure password and tell me what it is.
7. Run: docker compose -f docker-compose.free.yml up -d
8. Wait for services to be healthy, then open http://localhost:3000 in my browser.
9. Tell me the admin username and password so I can log in.

Please do each step one at a time, confirm it worked, then move to the next.
```

---

## What Claude will set up automatically

| Component | Description |
|-----------|-------------|
| **Backend** | FastAPI on port 8000 — app management API |
| **Frontend** | Next.js on port 3000 — dashboard UI |
| **Caddy** | Reverse proxy on port 80/443 |
| **CoreDNS** | Local DNS so deployed apps get `.vibe.local` domains |

## What stays on your machine

All data lives in the `IVS/` folder you cloned:

```
data/          SQLite database
deployed_apps/ Source code of apps you deploy
uploads/       App zip files you upload
```

Nothing is sent to external servers. No telemetry.

## Troubleshooting prompts

If something doesn't work, paste one of these into Claude:

- "The IVS frontend isn't loading at localhost:3000 — check docker compose logs"
- "I can't log in with admin credentials — reset the admin password"
- "I want to update IVS to the latest version — pull git and rebuild"
- "Show me the IVS machine fingerprint / serial number"

## Machine fingerprint

Your IVS installation has a unique machine fingerprint tied to your hardware.
Find it at: **Settings → Machine Serial** in the dashboard.

This fingerprint is used for IVS Enterprise multi-machine management.
