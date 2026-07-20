# SYJ OpenTrade Logic

An open-source, deterministic HTS classification engine — the first building
block toward a full trade-compliance platform. By **Sayanjali Nexus Private
Limited**.

# SYJ OpenTrade Logic

An open-source, deterministic HTS classification engine with a REST API —
building block toward a full trade-compliance platform. By **Sayanjali
Nexus Private Limited**.

## v0.3.0 — real FastAPI + SQLAlchemy, and the full 99-chapter HTS dataset

> **What's genuinely new vs. described-but-untested:** the FastAPI/SQLAlchemy
> code below is a careful route-for-route port of the v0.2.0 stdlib server,
> and I proved its core fix (heading-scoring against terse real HTS legal
> text) against a realistic fixture, with a permanent regression test. But
> `pip install fastapi` and the live USITC data pull both require real
> internet access that this sandbox doesn't have — **you need to run the
> commands below yourself**, ideally with me watching the output so we can
> fix anything that doesn't match on the first try.

### Step 1 — install real dependencies (on your Termux/dev machine)

```bash
cd syj-opentrade-logic
pip install -r server_fastapi/requirements.txt --break-system-packages
pip install httpx --break-system-packages   # needed for FastAPI's TestClient
```

### Step 2 — pull the real, full HTS dataset (chapters 01–99)

```bash
python3 scripts/import_hts_data.py
```

This hits the **official USITC REST API**
(`https://hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false`,
confirmed from USITC's own published "HTS System User Guide"), pulls all
~17,000+ live HTS-10 line items, and writes `data/hts_full.json` in the
tree shape the engine expects.

**Important:** the script prints the raw JSON field names of the first
record before parsing anything, and warns loudly if it parses fewer than 90
chapters. If either of those looks wrong, stop and paste the output back to
me here — the USITC API's field names have shifted before, and I'd rather
fix the parser with you than have it silently produce a broken dataset.

### Step 3 — run the tests (now against the real stack)

```bash
python3 -m unittest tests.test_gri_engine tests.test_api tests.test_importer_and_terse_headings -v
python3 -m unittest server_fastapi.test_main -v
```

### Step 4 — run the real server

```bash
python3 -m uvicorn server_fastapi.main:app --reload --port 8000
```

Then open `http://localhost:8000/docs` — that's a **real, auto-generated
Swagger UI** (FastAPI does this for free; `server/openapi_spec.py` from
v0.2.0 is now obsolete). Try `/classify` against real product descriptions
and watch it hit the full dataset.

### What changed under the hood (fixed while building this)

Real HTS heading text is terse legal language ("Automatic data processing
machines and units thereof") that usually doesn't contain the everyday
words people type ("laptop"). Those live at the subheading level. The v0.1
engine only matched at the heading level before descending, so it silently
returned "unresolved" for perfectly classifiable products once real data
replaced the hand-curated sample. Fixed in `core/gri_engine.py`
(`_effective_heading_score`) and covered by
`tests/test_importer_and_terse_headings.py`.

---
> **Honesty note on scope:** the original spec described a full enterprise
> SaaS platform (FastAPI + PostgreSQL + Redis + Celery + Next.js + a vector
> database). This sandbox has no network access, so packages like FastAPI,
> SQLAlchemy, and uvicorn can't be installed here. What's shipped below is
> real, running, and tested against a live server and a real SQLite file on
> disk — nothing is described-but-not-executed.

## v0.2.0 — REST API + SQLite persistence (new)

- **`server/app.py`** — a REST API server built on Python's stdlib
  `http.server` (since FastAPI can't be installed in this sandbox). Every
  route's docstring notes the equivalent FastAPI decorator, so porting this
  to real FastAPI later is close to copy-paste.
- **`server/db.py`** — SQLite persistence layer (stdlib `sqlite3`) storing
  every classification as an auditable history record.
- **`server/openapi_spec.py`** — hand-written OpenAPI 3.0 document, served
  live at `GET /openapi.json`.
- **`tests/test_api.py`** — 10 integration tests that start a **real**
  server on a real TCP socket (via `threading` + `build_server(port=0)`)
  and issue real HTTP requests with `urllib`, including one test that
  bypasses the API entirely and reads the SQLite file directly to prove
  persistence isn't mocked.

**Routes:**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness check |
| POST | `/classify` | classify a product description, persist it |
| GET | `/classifications?limit=&offset=` | paginated history |
| GET | `/classifications/{id}` | fetch one record |
| DELETE | `/classifications/{id}` | delete one record |
| GET | `/openapi.json` | live OpenAPI 3.0 spec |

### Run the server for real

```bash
python3 server/app.py --port 8000 --db syj_opentrade.db
# then, in another terminal:
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"description":"cordless electric drill"}'
```

### Run all tests (unit + live HTTP integration)

```bash
python3 -m unittest tests.test_gri_engine tests.test_api -v
# 22 tests, all passing: 12 unit tests on the GRI engine,
# 10 integration tests against a real running server.
```

## v0.1.0 — GRI classification engine

- **`core/models.py`** — typed dataclasses for the HTS tree, decision
  steps, and classification results.
- **`core/gri_engine.py`** — DAG traversal applying **GRI 1** (heading
  terms + legal notes), **GRI 6** (subheading comparison), and **GRI 3(a)**
  specificity tie-break flagging. Every result includes a full decision
  path, alternatives considered, confidence score, and supporting legal
  notes — no black-box output.
- **`data/hts_sample.json`** — sample HTS tree (laptops, t-shirts, drills,
  phones/routers) for demonstration. Not the full HTS schedule.
- **`cli/classify.py`** — zero-dependency CLI.

Zero third-party dependencies anywhere in this repo. Runs on plain Python 3
— including under Termux on Android.

## Why deterministic, not AI-first

AI should *assist* (cleaning descriptions, extracting attributes,
summarizing rulings) but must **never** replace deterministic GRI-based
classification. This engine follows that strictly — classification is
lexical/rule-based graph traversal, and every step is explainable.

## Honest roadmap

| Release | Scope | Status |
|---|---|---|
| v0.1.0 | GRI classification engine | ✅ done, 12 tests passing |
| v0.2.0 | stdlib REST API + SQLite persistence + history | ✅ done, 22 tests passing |
| v0.3.0 | Real FastAPI + SQLAlchemy port; full 99-chapter HTS import script | ✅ code + logic proven on fixtures (25 tests passing here); **you run `pip install` + the importer on your machine** to activate against the live dataset |
| v0.4.0 | Auth (JWT/RBAC), organizations, product catalog, CSV/Excel import | needs Postgres |
| v0.5.0 | Next.js/React dashboard (shadcn/Tailwind) | needs `npm` registry access |
| v0.6.0 | Semantic search over CBP CROSS rulings (vector DB) | needs Pinecone/Milvus + embeddings API |
| v0.7.0 | Duty calculator, Section 301/232/122, AD/CVD tariff library | needs tariff data sources |
| v0.8.0 | Reports (PDF/CSV/Excel), audit trails, webhooks | — |
| v0.9.0 | Docker/Compose, GitHub Actions CI/CD, deployment docs | — |

**Recommended next step:** push this repo to GitHub (`SHalimoosavi`), then
from a machine with `pip`/`npm` access we can port `server/app.py` to real
FastAPI + SQLAlchemy line-by-line and stand up the full stack.

## License

Apache 2.0 — see `LICENSE`.

