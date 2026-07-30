# Deployment Guide

SYJ OpenTrade Logic has two genuinely different deployment paths, and it's
important not to confuse them.

## 1. Local development on Termux/Android (what you've been doing)

This is the native `pip install` / `npm install` workflow documented in the
main `README.md`. It runs directly on-device with no containers involved.
**Keep using this for day-to-day development.** Nothing about Docker
changes this workflow or replaces it.

## 2. Production deployment via Docker (new in v0.9.0)

For deploying this to a real server -- a VPS, a cloud VM, a Kubernetes
cluster -- so other people can actually use it over the internet, not just
you on your own device.

> **Important:** Docker will very likely **not run natively on Termux/Android**.
> Android's kernel typically lacks the namespace/cgroup support Docker
> needs. The files in this section are for deploying to an actual Linux
> host (any $5/mo VPS works fine), not for running locally on your phone.

### Quick start (on a real Linux host)

```bash
git clone https://github.com/SHalimoosavi/SYJ-OpenTrade-Logic.git
cd SYJ-OpenTrade-Logic/syj-opentrade-logic

cp .env.docker.example .env.docker
# Edit .env.docker -- at minimum, set a real SYJ_SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"

docker compose --env-file .env.docker up --build
```

First startup takes longer than subsequent ones: the backend's entrypoint
script (`docker-entrypoint.sh`) builds the full ~17,000-record HTS dataset
from the live USITC API on first run, since that dataset is deliberately
not committed to git (see the main README). This needs real internet
access from the container and takes 10-60 seconds.

Once up:
- Backend API: `http://your-server:8000` (Swagger docs at `/docs`)
- Dashboard: `http://your-server:8080`

### What's in each file

| File | Purpose |
|---|---|
| `Dockerfile.backend` | FastAPI backend image (Python 3.12-slim, non-root user, healthcheck) |
| `Dockerfile.frontend` | Multi-stage build: Node compiles the Vite app, nginx serves the static output |
| `docker-entrypoint.sh` | Builds the HTS dataset on first run if missing, then starts uvicorn |
| `nginx.conf` | SPA routing fallback -- without this, refreshing the browser on e.g. `/classify` 404s |
| `docker-compose.yml` | Wires backend + frontend together, with a persistent volume for the SQLite DB and HTS dataset |
| `.env.docker.example` | Template for required environment variables |
| `.dockerignore` | Keeps builds consistent regardless of local checkout state |

### Moving beyond SQLite

The default `docker-compose.yml` still uses SQLite (matching this
project's SQLite-first philosophy), persisted in a named volume. For real
multi-user production traffic, set `SYJ_DATABASE_URL` in `.env.docker` to
a real Postgres connection string:

```
SYJ_DATABASE_URL=postgresql://user:password@host:5432/dbname
```

You'll need `psycopg2-binary` added to `server_fastapi/requirements.txt`
for this -- not included by default since it's an extra native dependency
this project hasn't needed until now.

### Secrets

`SYJ_SECRET_KEY` signs every JWT this app issues. If it's ever exposed or
guessable, an attacker can forge valid login tokens for any user. Generate
a real random one (shown above) and never commit it to git -- that's why
`.env.docker` (not `.env.docker.example`) is in `.gitignore`.

### Reverse proxy / HTTPS

Neither Dockerfile terminates TLS. For a real public deployment, put a
reverse proxy (nginx, Caddy, Traefik, or your cloud provider's load
balancer) in front of both services to handle HTTPS certificates --
Caddy in particular is a good fit here since it handles Let's Encrypt
certificates automatically with almost no configuration.

---

## Continuous Integration (GitHub Actions)

`.github/workflows/ci.yml` runs automatically on every push to `main` and
every pull request. Unlike the Termux sandbox this project is built in
(no network access) or Termux itself (no Docker), **GitHub's runners are a
real, complete Linux environment** -- so this is the first point in this
project's history where the full stack gets genuinely verified end-to-end
in one place: real `pip install`, real `npm install`, a real Vite
production build, and real `docker build` for both images, including a
smoke test that the backend container actually starts and responds
healthy.

Three jobs:
1. **backend-tests** -- runs all ~103 Python tests, split into separate
   steps for anything that instantiates a FastAPI app (a real bug, found
   during development, means combining those in one process silently
   breaks database isolation between them -- see the workflow file's
   comments for the full story)
2. **frontend-build** -- `npm install` + the real production build
   (`tsc -b && vite build`)
3. **docker-build** -- builds both Docker images for real, then starts the
   backend container and polls `/health` until it responds, failing the
   build (and printing container logs) if it doesn't come up within 60
   seconds

If any of these go red on GitHub after you push, that's a real signal
worth investigating -- it means something that worked in one environment
(Termux, the dev sandbox) doesn't work in a clean, real Linux environment,
which is exactly the kind of gap CI exists to catch.
