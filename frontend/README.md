# SYJ OpenTrade Logic — Dashboard (v0.5.0)

A Vite + React + TypeScript dashboard for the SYJ OpenTrade Logic API. Vite + React was chosen over Next.js specifically for this release given Termux/mobile constraints — much lighter dev server, no native-module build steps like Next.js sometimes needs (e.g. `sharp`).

> **Honesty note on scope:** this couldn't be `npm install`'d or built in the sandbox that generated it (no network access there). Every import has been cross-checked by script against files that actually exist and packages actually declared in `package.json`, and there are no unbalanced braces/parens — but the real proof is running `npm install && npm run dev` for real, which needs to happen on your machine. Report back anything that breaks and we'll fix it together, the same way we did for the backend.

## What's included

- **Auth** — login, registration (creates org + owner), automatic JWT refresh (queues concurrent requests during a token refresh so they don't race each other)
- **Dashboard overview** — real stats from your data (classification count, product count, average confidence) with a chart
- **Classify** — search box + full GRI decision-path visualization (the core differentiator: every classification shows its reasoning, not just a code)
- **Product catalog** — CRUD table + CSV/Excel bulk import with per-row error reporting
- **Members** — invite users, change roles, all RBAC-gated in the UI to match what the backend actually allows (a viewer never even sees the "Add product" button)

## Setup (Termux)

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `.env` if your API isn't on `localhost:8000`.

```bash
npm run dev
```

Open the URL it prints (usually `http://localhost:5173`) in your phone's browser. Make sure the FastAPI server (`server_fastapi/main.py`) is running at the same time — this dashboard is a pure client for that API, it does nothing on its own.

### If `npm install` is slow or runs out of memory

Termux devices vary a lot. If install hangs or the dev server is sluggish:
```bash
npm install --prefer-offline --no-audit --no-fund
```
And close other apps to free RAM before running `npm run dev`.

### CORS

The backend already allows all origins (`server_fastapi/main.py`'s `CORSMiddleware`), so no extra backend config should be needed — but if you see CORS errors in the browser console, that's the first place to check.

## Known gaps (by design, not oversight)

- No dark/light mode toggle yet (ships dark-only, matching the SYJ brand) — v0.5.1
- No command palette / keyboard shortcuts yet — v0.5.1
- Passwords for invited members are set by the inviter and shared out-of-band; no invite-link/email flow yet
- No pagination UI yet on the product table (backend supports `limit`/`offset`, just not wired to UI controls) — quick follow-up
