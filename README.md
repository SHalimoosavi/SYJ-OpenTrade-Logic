# SYJ OpenTrade Logic

An open-source, deterministic HTS classification engine — the first building
block toward a full trade-compliance platform. By **Sayanjali Nexus Private
Limited**.

> **Honesty note on scope (read this first):** the original spec for this
> project described a full enterprise SaaS platform (FastAPI + PostgreSQL +
> Redis + Celery + Next.js + a vector database + CI/CD + Docker). This
> release, **v0.1.0**, delivers the one component that can be fully real,
> fully tested, and dependency-free right now: the **GRI classification
> engine**. Everything else is laid out below as an honest roadmap, not
> pretend-finished code. No placeholders were shipped in what *is* here —
> every function in this release runs and is covered by a passing test.

## What's actually in v0.1.0

- **`core/models.py`** — typed dataclasses for the HTS tree, decision steps,
  and classification results.
- **`core/gri_engine.py`** — a Directed-Acyclic-Graph classification engine
  that applies **GRI 1** (heading terms + legal notes) and **GRI 6**
  (subheading comparison), with **GRI 3(a)** specificity tie-break flagging.
  Every classification returns a full, auditable **decision path**,
  **alternatives considered**, **confidence score**, and **supporting legal
  notes** — no black-box output.
- **`data/hts_sample.json`** — a small sample HTS tree (laptops, t-shirts,
  drills, phones/routers) to demonstrate real traversal. This is a
  demonstration dataset, not the full HTS schedule.
- **`cli/classify.py`** — a zero-dependency command-line interface.
- **`tests/test_gri_engine.py`** — 12 real unit tests, all passing, covering
  correct classification, refusal-to-guess on unmatched products, and
  decision-path integrity.

Zero third-party dependencies. Runs on plain Python 3 — including under
Termux on Android, matching how you build everything else.

## Quick start

```bash
python3 -m unittest tests.test_gri_engine -v      # run the test suite
python3 cli/classify.py "cordless electric drill"  # human-readable output
python3 cli/classify.py "cotton t-shirt" --json     # JSON output
```

## Why deterministic, not AI-first

Per the original design brief: AI should *assist* (cleaning descriptions,
extracting attributes, summarizing rulings) but must **never** replace
deterministic GRI-based classification. This engine follows that principle
strictly — classification is lexical/rule-based graph traversal, and every
step is explainable. An AI layer can be added on top later as a *suggestion*
source that still has to pass through this engine, never around it.

## Honest roadmap (not yet built)

These are correctly scoped as **future releases**, each requiring
infrastructure this sandbox doesn't have (network access, a running
Postgres/Redis, an npm registry):

| Release | Scope | Needs |
|---|---|---|
| v0.1.0 | GRI classification engine (this release) | ✅ done, tested |
| v0.2.0 | FastAPI REST wrapper + SQLite persistence + classification history | `pip install fastapi sqlalchemy uvicorn` |
| v0.3.0 | Full HTS dataset (all 99 chapters) replacing the sample dataset | USITC HTS data import |
| v0.4.0 | Auth (JWT/RBAC), organizations, product catalog, CSV/Excel import | Postgres |
| v0.5.0 | Next.js/React dashboard (shadcn/Tailwind) | Node + npm registry access |
| v0.6.0 | Semantic search over CBP CROSS rulings (vector DB) | Pinecone/Milvus + embeddings API |
| v0.7.0 | Duty calculator, Section 301/232/122, AD/CVD tariff library | Tariff data sources |
| v0.8.0 | Reports (PDF/CSV/Excel), audit trails, webhooks | — |
| v0.9.0 | Docker/Compose, GitHub Actions CI/CD, deployment docs | — |

**Recommended next step:** move this repo to your GitHub
(`SHalimoosavi`) from a machine/environment with `pip` and `npm` access, and
I can help you build v0.2.0 (the FastAPI + SQLite layer) directly against a
real running server so it's genuinely tested end-to-end rather than just
described.

## License

Apache 2.0 — see `LICENSE`.
