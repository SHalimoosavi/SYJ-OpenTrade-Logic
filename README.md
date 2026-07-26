<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=26&pause=1200&color=6366F1&center=true&vCenter=true&width=760&lines=SYJ+OpenTrade+Logic;Deterministic+HTS+Classification+Engine;Open+Source+%C2%B7+Apache+2.0+%C2%B7+Zero+Black+Boxes" alt="SYJ OpenTrade Logic" />

### The Linux of International Trade Compliance

**An open-source, explainable HTS classification engine and REST API — built to replace black-box AI classifiers with deterministic, auditable trade rules.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-26%20passing-brightgreen)](#-testing)
[![Core Dependencies](https://img.shields.io/badge/core%20engine-zero%20dependencies-success)](./core)
[![Status](https://img.shields.io/badge/status-active%20development-orange)](#-release-roadmap)
[![Maintained by](https://img.shields.io/badge/maintained%20by-Sayanjali%20Nexus-6366F1)](https://github.com/SHalimoosavi)

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [How Classification Works](#-how-classification-works) · [API](#-rest-api) · [Roadmap](#-release-roadmap) · [Contributing](#-contributing)

</div>

---

## Why This Exists

Post-2026 tariff volatility turned customs compliance into a weekly operational fire drill. Companies in the **$50M–$500M** revenue band are stuck between two bad options:

| | Enterprise Trade Suites (SAP GTS, Oracle GTM) | Black-Box AI Classifiers |
|---|---|---|
| **Cost** | $250K–$2M+ implementations | Often cheap, sometimes free |
| **Transparency** | Proprietary rule engines | Zero — you can't audit a prediction |
| **Speed to deploy** | 6–18 months | Fast, but you're flying blind |
| **Explainability** | Partial, vendor-locked | None — "trust the model" |

**SYJ OpenTrade Logic takes a third path:** deterministic classification using the actual **General Rules of Interpretation (GRI)** that customs authorities use, with AI permitted only as an *assistant* — never as the decision-maker. Every classification returns a full, human-readable decision path. Nothing is a guess dressed up as a percentage.

> 📖 **On honesty as a design principle:** this README documents exactly what has been built and verified, release by release. Nothing below is aspirational copy for unwritten code — see [Release Roadmap](#-release-roadmap) for what's real today versus what's planned.

---

## 🏗 Architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        CLI["CLI<br/><i>cli/classify.py</i>"]
        HTTP["HTTP Clients<br/><i>curl · Postman · your app</i>"]
        SWAGGER["Swagger UI<br/><i>/docs</i>"]
    end

    subgraph API["API Layer — server_fastapi/"]
        FASTAPI["FastAPI App<br/><i>main.py</i>"]
        SCHEMAS["Pydantic Schemas<br/><i>schemas.py</i>"]
    end

    subgraph Core["Core Engine — core/ (zero dependencies)"]
        ENGINE["GRIEngine<br/><i>gri_engine.py</i>"]
        MODELS["Data Models<br/><i>models.py</i>"]
    end

    subgraph Data["Data Layer"]
        HTS["HTS Tariff Tree<br/><i>data/hts_full.json</i><br/>99 chapters · live USITC feed"]
        DB[("SQLite / Postgres<br/><i>server_fastapi/database.py</i>")]
    end

    subgraph External["External Sources"]
        USITC["USITC REST API<br/><i>hts.usitc.gov</i>"]
        IMPORTER["Importer<br/><i>scripts/import_hts_data.py</i>"]
    end

    CLI --> ENGINE
    HTTP --> FASTAPI
    SWAGGER --> FASTAPI
    FASTAPI --> SCHEMAS
    FASTAPI --> ENGINE
    FASTAPI --> DB
    ENGINE --> MODELS
    ENGINE --> HTS
    USITC -->|"~17,000+ HTS-10 records"| IMPORTER
    IMPORTER -->|"builds nested tree"| HTS

    style Core fill:#6366F1,stroke:#4338CA,color:#fff
    style API fill:#0EA5E9,stroke:#0369A1,color:#fff
    style Data fill:#10B981,stroke:#047857,color:#fff
    style External fill:#F59E0B,stroke:#B45309,color:#fff
```

**Design principle:** the core engine (`core/`) has **zero third-party dependencies** and doesn't know or care whether it's called from a CLI, a stdlib HTTP server, or FastAPI. This is deliberate — classification logic should outlive any particular web framework choice.

---

## 🧠 How Classification Works

Classification follows the **General Rules of Interpretation (GRI)** as a Directed Acyclic Graph traversal — not a black-box model call.

```mermaid
flowchart TD
    START(["Product description<br/>e.g. 'cordless electric drill'"]) --> TOKENIZE["Tokenize description"]
    TOKENIZE --> SCORE_HEAD["<b>GRI 1</b><br/>Score every heading in the HTS tree<br/>against heading terms + legal notes"]
    SCORE_HEAD --> CHECK{"Top score<br/>&gt; 0?"}
    CHECK -->|No| UNRESOLVED["❌ Return UNRESOLVED<br/>never guess"]
    CHECK -->|Yes| CLOSE{"Runner-up heading<br/>within 0.10 of top score?"}
    CLOSE -->|Yes| GRI3A["<b>GRI 3(a)</b><br/>Flag competing heading,<br/>prefer more specific description"]
    CLOSE -->|No| SCORE_SUB
    GRI3A --> SCORE_SUB["<b>GRI 6</b><br/>Score subheadings under<br/>the selected heading"]
    SCORE_SUB --> RESULT["✅ Return classification:<br/>• Final HTS code<br/>• Confidence score<br/>• Full decision path<br/>• Alternatives considered<br/>• Supporting legal notes<br/>• Duty rate"]
    UNRESOLVED --> DONE(["Auditable JSON result"])
    RESULT --> DONE

    style CHECK fill:#F59E0B,color:#000
    style CLOSE fill:#F59E0B,color:#000
    style UNRESOLVED fill:#EF4444,color:#fff
    style RESULT fill:#10B981,color:#fff
    style GRI3A fill:#6366F1,color:#fff
    style SCORE_HEAD fill:#6366F1,color:#fff
    style SCORE_SUB fill:#6366F1,color:#fff
```

**Key engineering decision:** real HTS heading text is terse legal language ("Automatic data processing machines and units thereof") that rarely contains the everyday words a user types ("laptop"). Those live at the subheading level. The engine's `_effective_heading_score()` scores each heading by the *better* of its own text or its best-matching child subheading — otherwise correct classifications would silently fail once real USITC data replaced hand-curated samples. This was a real bug, found and fixed during v0.3.0 development, and is permanently covered by `tests/test_importer_and_terse_headings.py`.

### Example: a request end-to-end

```mermaid
sequenceDiagram
    participant U as User / Client
    participant A as FastAPI (main.py)
    participant E as GRIEngine (core/gri_engine.py)
    participant D as SQLite/Postgres (database.py)

    U->>A: POST /classify {"description": "cordless electric drill"}
    A->>E: engine.classify(description)
    E->>E: GRI 1 — score all headings
    E->>E: GRI 6 — score subheadings of top heading
    E-->>A: ClassificationResult (decision path, confidence, alternatives)
    A->>D: persist result as audit record
    D-->>A: record id
    A-->>U: 201 Created {id, final_code: "8467.21", decision_path: [...], ...}
```

---

## 🚀 Quick Start

### Option A — Zero-dependency core (works anywhere, including Termux)

```bash
git clone https://github.com/SHalimoosavi/SYJ-OpenTrade-Logic.git
cd SYJ-OpenTrade-Logic/syj-opentrade-logic

python3 -m unittest tests.test_gri_engine -v
python3 cli/classify.py "cordless electric drill"
python3 cli/classify.py "cotton t-shirt" --json
```

### Option B — Full REST API (FastAPI + SQLAlchemy)

```bash
pip install -r server_fastapi/requirements.txt --break-system-packages
pip install httpx --break-system-packages   # for TestClient

# Pull the real, full 99-chapter HTS dataset from the official USITC API
python3 scripts/import_hts_data.py

# Run the full test suite
python3 -m unittest tests.test_gri_engine tests.test_api tests.test_importer_and_terse_headings -v
python3 -m unittest server_fastapi.test_main -v

# Launch the live server
python3 -m uvicorn server_fastapi.main:app --reload --port 8000
```

Open **`http://localhost:8000/docs`** for a live, auto-generated Swagger UI.

```bash
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"description": "cordless electric drill"}'
```

---

## 📦 Project Layout

```
syj-opentrade-logic/
├── core/                    # Zero-dependency classification engine
│   ├── models.py            #   HTS tree + result dataclasses
│   └── gri_engine.py        #   GRI 1 / 3(a) / 6 DAG traversal
├── cli/
│   └── classify.py          # Standalone CLI, no dependencies
├── server/                  # v0.2.0 — stdlib http.server REST layer
│   ├── app.py
│   ├── db.py                #   raw sqlite3 persistence
│   └── openapi_spec.py      #   hand-written OpenAPI doc
├── server_fastapi/          # v0.3.0 — real FastAPI + SQLAlchemy
│   ├── main.py               #   route-for-route port of server/app.py
│   ├── database.py           #   SQLAlchemy models (SQLite by default, Postgres-ready)
│   ├── schemas.py            #   Pydantic request/response contracts
│   └── test_main.py          #   FastAPI TestClient integration tests
├── scripts/
│   └── import_hts_data.py   # Pulls full 99-chapter HTS from the live USITC API
├── data/
│   ├── hts_sample.json      # Small demo dataset (laptops, t-shirts, drills, phones)
│   └── hts_full.json        # Generated by the importer — not committed, ~17k+ records
├── tests/
│   ├── test_gri_engine.py
│   ├── test_api.py
│   └── test_importer_and_terse_headings.py
├── LICENSE                  # Apache 2.0
└── README.md
```

---

## 🌐 REST API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/classify` | Classify a product description, persist the result |
| `GET` | `/classifications?limit=&offset=` | Paginated classification history |
| `GET` | `/classifications/{id}` | Fetch one classification record |
| `DELETE` | `/classifications/{id}` | Delete one classification record |
| `GET` | `/docs` | Interactive Swagger UI (auto-generated by FastAPI) |
| `GET` | `/openapi.json` | Machine-readable OpenAPI 3.0 spec |

<details>
<summary><b>Example response — <code>POST /classify</code></b></summary>

```json
{
  "id": 1,
  "product_description": "cordless electric drill",
  "final_code": "8467.21",
  "final_description": "Drills of all kinds, hand-held, electric motor",
  "confidence": 0.87,
  "is_classified": true,
  "duty_rate": "1.7%",
  "decision_path": [
    {
      "node_code": "8467",
      "node_description": "Tools for working in the hand...",
      "rule_applied": "GRI 1",
      "reasoning": "Heading 8467 scored highest (0.82) against the terms of the heading, per GRI 1...",
      "score": 0.82
    },
    {
      "node_code": "8467.21",
      "node_description": "Drills of all kinds, hand-held, electric motor",
      "rule_applied": "GRI 6",
      "reasoning": "Subheading 8467.21 scored highest (0.91) among subheadings of 8467, per GRI 6...",
      "score": 0.91
    }
  ],
  "alternatives": [],
  "supporting_notes": []
}
```

</details>

---

## 🤖 Why Deterministic, Not AI-First

> AI should **assist** — cleaning descriptions, extracting attributes, summarizing rulings, suggesting candidates for a human to review. AI must **never replace** deterministic GRI-based classification.

This isn't a limitation — it's the whole point. A customs broker who gets asked *"why did the system pick this code?"* needs an answer rooted in the actual legal text of the tariff schedule, not a confidence score from an opaque model. Every result this engine returns can be defended in an audit.

---

## 🗺 Release Roadmap

```mermaid
timeline
    title SYJ OpenTrade Logic — Release Progression
    v0.1.0 : GRI classification engine
           : Zero-dependency core, 12 tests
    v0.2.0 : stdlib REST API
           : SQLite persistence, 22 tests
    v0.3.0 : Real FastAPI + SQLAlchemy
           : Full 99-chapter USITC import, 26 tests
    v0.4.0 : Auth, RBAC, organizations
           : Product catalog, CSV/Excel import
    v0.5.0 : Next.js dashboard
           : shadcn/ui, Tailwind, dark mode
    v0.6.0 : Semantic search
           : CBP CROSS rulings, vector DB
    v0.7.0 : Duty calculator
           : Section 301/232/122, AD/CVD
    v0.8.0 : Reports & audit trails
           : PDF/CSV/Excel export, webhooks
    v0.9.0 : Production DevOps
           : Docker, CI/CD, deployment docs
```

| Release | Scope | Status |
|---|---|---|
| **v0.1.0** | GRI classification engine | ✅ Done — 12 tests passing |
| **v0.2.0** | stdlib REST API + SQLite persistence | ✅ Done — 22 tests passing |
| **v0.3.0** | Real FastAPI + SQLAlchemy; full 99-chapter HTS import | ✅ Done — 26 tests passing, live against USITC data |
| **v0.4.0** | Auth (JWT/RBAC), organizations, product catalog, CSV/Excel import | 🔜 Planned — needs Postgres |
| **v0.5.0** | Vite+React dashboard (shadcn/Tailwind) — swapped from Next.js for Termux/mobile practicality | ✅ Code complete, import/export/syntax-verified by script; `npm install` + real run needed on your machine |
| **v0.6.0** | Semantic search over CBP CROSS rulings (vector DB) | 🔜 Planned — needs Pinecone/Milvus + embeddings API |
| **v0.7.0** | Duty calculator, Section 301/232/122, AD/CVD tariff library | 🔜 Planned — needs tariff data sources |
| **v0.8.0** | Reports (PDF/CSV/Excel), audit trails, webhooks | 🔜 Planned |
| **v0.9.0** | Docker/Compose, GitHub Actions CI/CD, deployment docs | 🔜 Planned |

---

## 🧪 Testing

```bash
# Core engine + stdlib API (no extra deps required)
python3 -m unittest tests.test_gri_engine tests.test_api tests.test_importer_and_terse_headings -v

# FastAPI layer (requires server_fastapi/requirements.txt + httpx)
python3 -m unittest server_fastapi.test_main -v
```

**26 tests, all passing**, covering: correct GRI-based classification, refusal to guess on unmatched products, decision-path integrity, live HTTP integration against a real running server, direct SQLite file verification (bypassing the API to prove persistence isn't mocked), and the real-data chapter-detection regression found while importing the live USITC feed.

---

## 🤝 Contributing

This project is built in the open, in public, with every bug and fix documented rather than hidden. Issues and PRs welcome once the repository is public-ready for external contributors (tracked for v0.9.0 alongside CI/CD). Until then, feel free to open issues for bugs or design discussion.

## 📄 License

Apache 2.0 — see [`LICENSE`](./LICENSE).

---

<div align="center">
<sub>Built by <a href="https://github.com/SHalimoosavi">Sayanjali Nexus Private Limited</a> · Hyderabad, India</sub>
</div>
