# Operating iVS without losing data

This is for whoever runs an iVS box — an operator, or an agent working on one.
It is not about the code. It is the short list of things that destroy data or
quietly stop working, and what to do instead.

Everything here is a property of iVS itself, not of any particular machine.

---

## Redeploying an app destroys that app's data

There is no in-place update. Redeploy rebuilds the image, and the app's data
directory is replaced with a fresh one. A deployed app keeps its database inside
its own container, so **redeploy means the records are gone** — not corrupted,
gone, with no copy anywhere else unless someone made one.

Before redeploying anything that has been in service:

1. Export the app's data through the app's own export
2. Tell whoever owns that app that you are about to do it
3. Keep the export until the new version is confirmed working

This is also why the delete and redeploy buttons are not reversible. Treat them
the way you would treat `DROP TABLE`.

---

## ROPA is never cleared, never deleted, never renumbered

The record of processing activities only ever grows. Rows are added; no row is
removed, and no row is reordered. This is a rule about the product, not a
setting on a box, and it holds even when the thing a row describes is gone.

**Deleting an app does not delete its ROPA row.** The row is stamped with the
date the app was removed and stays in the register, in its original position,
with its original number. Removing an app does not undo the fact that it once
processed somebody's personal data, and PDPA never asks for this record to be
erased — it asks that the record exist. An auditor asks what processing has
happened, not only what is happening today; a register that quietly drops the
answers as systems are retired cannot answer either question.

Because the app row itself is gone, the app's name and slug are copied into the
ROPA row at the moment of deletion. Without that copy the register would keep an
`app_id` that nobody can translate back into a system — a record that survives
but says nothing, which is the same as not keeping it.

What this rules out:

- No "clean up old ROPA entries" job, on any schedule, for any reason.
- No cascade from app deletion. Everything else belonging to a deleted app —
  catalog entries, dependency edges, field policies, tunnels, access grants —
  is cleaned up, because those describe a system that no longer exists. The
  ROPA row describes something that happened, which is still true.
- No renumbering. Rows are listed in the order they were created, so a number
  cited in an exported report still points at the same row a year later.

The one thing that may remove a ROPA row is an explicit decision by the data
controller under a retention policy, made deliberately and recorded. It is never
a side effect of pressing delete.

---

## `data/EVENT-LIVE` — the flag that outranks everything

When something is running that cannot be interrupted — an event, a clinic
session, a day of real use — create this file:

```bash
touch data/EVENT-LIVE
```

While it exists: **no deploy, no restart, no stop, no migration, no compose, no
edits to DNS or the proxy.** Not for a small fix. Not for a label change.

Delete it when the work is over. A flag nobody removes becomes a flag nobody
believes.

The reason is specific. Restarting an app mid-session re-enrols every terminal
that talks to it and loses whatever that session recorded — who arrived, at which
gate, at what time. That ledger usually exists in one place and is the thing the
whole system was set up to produce.

---

## The guard refuses the commands that lose data

`.claude/hooks/ivs-guard.sh` runs before any shell command an agent issues. It
refuses, permanently:

- removing a Docker volume, or pruning volumes
- bringing a compose stack down together with its volumes
- removing any `ivs-*` container

and while `data/EVENT-LIVE` exists, it also refuses deploy, restart, stop and
compose. Editing DNS or the proxy config always asks first, because those change
routing for every app at once.

**A refusal is correct. Find another way; do not work around it.** If you really
mean it, type the command yourself in your own terminal — the guard only sees an
agent's commands.

Two things worth knowing:

- **iVS itself is unaffected.** It drives Docker through the Python client, not
  the shell, so delete, restart and redeploy in the web UI keep working normally.
  The guard exists to stop an agent from doing by hand what the UI does with
  confirmation.
- **It matches on the text of the command.** A command that merely mentions a
  blocked phrase — writing documentation about it, grepping for it — is refused
  too. Put such text in a file and reference the file.

---

## Getting HTTPS that a phone will actually trust

Anything that needs a camera, Web NFC, geolocation or a service worker requires a
secure context. Those APIs are simply absent over plain HTTP on a LAN address, so
QR scanning by camera will not work no matter how the app is written.

Starting Caddy is necessary for domain routing but **does not solve this on its
own**: Caddy issues certificates from its own internal CA, which no stock phone
trusts.

| Route | Trusted by a stock phone | Effort |
| --- | --- | --- |
| **Tunnel** — built in (ngrok / Cloudflare / localtunnel) | yes | a button in the UI |
| Real domain + real certificate | yes | needs a domain and reachable DNS |
| Install Caddy's root CA on every device | yes | per device, by hand |
| Caddy with its internal CA only | **no** | does not help here |

The tunnel is the fastest honest answer, and it returns an `https://` URL the
moment it starts. Note what it means for the data — traffic leaves the LAN
through a third party — so it is a deliberate trade, not a default.

---

## Check the box before trusting anything written down

A state file written by hand is wrong by the following week. Look at the machine:

```bash
docker ps --filter name=ivs- --format '{{.Names}}\t{{.Ports}}\t{{.Status}}'
curl -s -m 3 localhost:2019/config/apps/http/servers | head   # Caddy admin, empty = not running
cat coredns/hosts
ls data/EVENT-LIVE 2>/dev/null && echo "SOMETHING IS LIVE"
```

`.claude/hooks/ivs-state.sh` prints this at the start of every agent session. If
a document disagrees with what the box says, the box is right.

### Two things that go stale silently

- **Caddy may not be running.** The Caddyfile, the `caddy_data` volume and
  `dns_service._update_caddy_route()` all exist whether or not a container is up.
  When it is down, `register_app()` falls through to its fallback and hands out
  `http://<SERVER_IP>:<port>` straight to the container. Nothing errors. Apps
  simply become plain HTTP, and the camera stops working.

- **`coredns/hosts` records the IP the box had at registration time.** The address
  moves with DHCP; the file does not follow. Give the box a static address or a
  DHCP reservation before relying on `*.vibe.local`, and re-register the affected
  apps after any address change.

Also: phones will not resolve `*.vibe.local` on their own. CoreDNS answers on
port 53 of the box, but wifi hands out the router's resolver. Point the router's
DHCP at the box for DNS, or set it per device — otherwise the domain works on the
box and nowhere else.

---

## Timestamps that have to line up with something else

iVS synchronises against a reference time source and records which one in its
audit exports, design history files and e-Contract records. That is what makes
its timestamps defensible.

If those timestamps have to be compared against a **separate** recorder — CCTV, a
video recorder, another system's log — then both sides must discipline against
**the same source**, or the two clocks drift apart and the comparison proves
nothing.

- If the network reaches the Internet: point the other device at the same public
  source iVS uses.
- If the network is closed: public sources never resolve. Run a time server on
  the iVS box and point everything on the venue network at it.

Record what you configured on the other device — a screenshot of its time
settings with the date is enough. iVS keeps its own side automatically; nothing
keeps the other side's.

---

## Identify an app by its entry in the UI, not by its container name

The container name comes from the slug. The slug and the display name are not
always the same word, and two unrelated projects can end up with container names
that look like variants of each other. Confirm against the app list in the iVS UI
before assuming two deployments are duplicates of one thing.
