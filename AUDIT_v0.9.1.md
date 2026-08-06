# SYJ OpenTrade Logic — Production Engineering Audit
**Baseline: v0.9.1 (post-Docker/CI, pre-dashboard-polish-verification)**
**Date: 2026-08-05**

## How to read this document

This audit is written from accumulated knowledge of building every module in this
repository across ten releases (v0.1.0–v0.9.0 plus an unreleased polish pass) —
not from a fresh re-read of the live files, since the sandbox that built this
project reset partway through the last session. Where a finding depends on
something that should be spot-checked against the real repo before acting on
it, that's noted explicitly. Everything else reflects deliberate decisions
made and documented during development, or gaps that were flagged at the time
and never circled back to.

**Severity key:** 🔴 Must-fix before calling this production-ready · 🟡 Should
fix before v1.0.0 · 🟢 Worth doing, not blocking

---

## 1. Overall Architecture

**What's there:** A clean three-tier split — `core/` (zero-dependency
classification/search/duty logic), `server_fastapi/` (the API, auth, DB
layer), `frontend/` (Vite+React dashboard). This separation has held up well:
`core/` genuinely has no third-party dependencies across four modules
(`gri_engine.py`, `rulings_search.py`, `duty_calculator.py`), which made every
one of them fully unit-testable without network access throughout
development — a real, validated payoff of that early architectural choice.

**Findings:**
- 🟡 The `GRIEngine` and `RulingsSearchIndex` are loaded once into memory at
  FastAPI module import time (`main.py`, `routes_rulings.py`). This is fine
  at current scale (~17k HTS records, 6 rulings) but means updating the HTS
  dataset or rulings sample requires a full process restart — no hot-reload.
- 🟡 No caching layer (Redis or in-process) for repeated identical
  `/classify` or `/rulings/search` queries. Not urgent at current traffic
  assumptions, but worth planning for before real multi-tenant load.
- 🔴 **Webhook delivery is synchronous, in-request** (`webhook_triggers.py`
  calls `deliver_webhook()` directly inside the route handler, with a 5s
  timeout per webhook). A slow or hanging receiver on `product.created` will
  add up to 5 seconds — multiplied by however many webhooks are registered
  — to that request's latency. This should move to a background task queue
  before this is exposed to real users with real webhook integrations.

## 2. Backend (FastAPI, SQLAlchemy, API design)

**Findings:**
- 🟡 `@app.on_event("startup")` is deprecated (confirmed via real
  `DeprecationWarning` output in test runs throughout v0.4.0–v0.9.0). Never
  migrated to FastAPI's `lifespan` context manager pattern. Purely cosmetic
  today (still works), but will eventually be removed upstream.
- 🟡 Several Pydantic schemas (`ClassificationHistoryItem`, `UserOut`,
  `OrganizationOut`, `ProductOut`, `AuditLogOut`, `WebhookDeliveryOut`) use
  the deprecated `class Config: from_attributes = True` pattern instead of
  Pydantic v2's `ConfigDict`. Confirmed via repeated `PydanticDeprecatedSince20`
  warnings in every single test run since v0.4.0 — never addressed despite
  being visible in every CI log.
- 🟡 **Inconsistent response envelopes.** Paginated list endpoints
  (`/classifications`, `/products`, `/audit-log`) return
  `{count, limit, offset, results}`. Others (`GET /organizations/members`,
  `GET /webhooks/{id}/deliveries`) return a bare array. Not a bug, but a real
  API-consistency debt that will bite an API consumer building against this.
- 🔴 **No rate limiting anywhere**, most critically on `POST /auth/login`.
  This was explicitly flagged as a known gap in the v0.4.0 release notes and
  never revisited. Brute-force credential attacks are fully unmitigated today.
- 🔴 **CORS is wide open** (`allow_origins=["*"]`) in `main.py`. Reasonable
  for local development against `localhost:5173`, actively dangerous for any
  real public deployment — should become an environment-configurable
  allowlist before going live anywhere public.
- 🟢 No API versioning prefix (`/v1/...`). Not urgent pre-1.0, but retrofitting
  versioning after external consumers exist is much more painful than adding
  it now while the API surface is still small.

## 3. Frontend (React, Vite, routing, UI/UX)

**Findings:**
- 🟢 Recent polish pass (code-splitting, dark/light mode, toast
  notifications, Command Palette, breadcrumbs, error boundary, real 404 page,
  Product Catalog pagination) is real and substantial — but **the final
  `npm run build` after the last batch of changes (Command Palette +
  Breadcrumbs) has not yet been confirmed successful.** This is the single
  most important open verification item right now, ahead of anything in this
  audit.
- 🟡 Pagination is only wired up on the Product Catalog table. Classification
  history (Classify page), Audit Log, Webhooks list, and Org Members list
  either show a fixed-size slice with no controls, or (Audit Log) fetch up to
  100 rows with no "load more." Inconsistent UX once any of these lists grow.
- 🟡 No accessibility audit has ever been performed. Some `aria-label`s exist
  (mobile menu buttons), but form-label associations, color contrast in both
  themes, and full keyboard navigability beyond the Command Palette are
  unverified.
- 🟢 Bundle size was 887kB as a single chunk before code-splitting was added;
  the actual post-split chunk sizes have not been confirmed since that build
  never completed verification.

## 4. Authentication and RBAC

**Findings:**
- 🟢 Solid fundamentals: PBKDF2-HMAC-SHA256 password hashing (260k
  iterations, random salt per password — verified via real hash round-trip
  tests), short-lived access tokens (15 min) with longer refresh tokens (30
  days), refresh token rotation on every `/auth/refresh` call.
- 🔴 **No server-side refresh token revocation.** There's no token blacklist
  or session store — a stolen refresh token remains valid for up to 30 days
  with no way to invalidate it server-side. "Logout" is purely client-side
  (deletes the local token); the JWT itself is still valid if intercepted
  beforehand. This is the single biggest auth gap for a real production
  deployment.
- 🔴 No account lockout or brute-force protection on login (ties directly to
  the rate-limiting gap in §2).
- 🟡 No email verification on registration, no password reset flow, no 2FA.
  Reasonable to defer for an internal/trusted-org tool, but genuinely
  necessary before "production ready for everyone" in the sense of arbitrary
  public signups.
- 🟢 RBAC itself (flat viewer/member/admin/owner per organization) is simple,
  consistently enforced via the `require_role()` dependency, and was verified
  multiple times against real API calls across all four roles — this part is
  in good shape.

## 5. HTS Classification Engine

**Findings:**
- 🟢 This is the most thoroughly tested and validated part of the entire
  system — 12+ unit tests, three real bugs found and fixed via live-data
  spot-checking against the actual USITC feed (the stemmer's silent-e-plural
  bug, the Chapter 99 heading-scoring bug, the terse-heading-matching gap).
  The GRI 1/3(a)/6 decision-path logic is sound and genuinely explainable.
- 🟢 **Known, documented limitation, not a bug:** pure lexical (BM25-style)
  matching means true synonyms or unusual phrasings outside a heading's
  indexed vocabulary won't match. This was an explicit, deliberate tradeoff
  for zero-dependency operation — worth stating plainly in any customer-facing
  materials so it's understood as a design choice, not an oversight.
- 🟡 The confidence score is a heuristic lexical-overlap score, not a
  calibrated probability. Nothing currently prevents someone from treating
  "97% confidence" as a statistically meaningful figure it isn't. Worth an
  explicit disclaimer anywhere confidence is surfaced for compliance
  decisions (it already has strong disclaimers on the duty calculator; the
  classification engine's UI does not carry an equivalent caveat).

## 6. Duty Calculation Logic

**Findings:**
- 🟢 Correctly scoped and honestly labeled: a small, dated, sourced sample
  (`trade_programs_sample.json`, `adcvd_sample.json`) with an `as_of_date`
  and disclaimer surfaced in every API response — not a "download once and
  forget" dataset pretending to be authoritative.
- 🔴 **No mechanism to detect or alert on staleness.** Section 301/232 rates
  are genuinely volatile (an executive order changed IEEPA tariff status in
  February 2026, discovered mid-development). There's no automated check that
  compares `as_of_date` against "today" and warns an admin the data may be
  outdated — today it relies entirely on someone reading the disclaimer text.
- 🟢 The refusal to auto-calculate compound/specific rates (e.g. `$0.28/kg`)
  rather than guessing is the right call and is tested.

## 7. CROSS (Rulings) Integration

**Findings:**
- 🟡 **This is the most content-limited part of the product.** Six real,
  correctly-sourced rulings — enough to prove the BM25 search and the
  classify-page integration work correctly, but not enough to be genuinely
  useful for a real user searching for precedent on an arbitrary product.
  Expanding this has no "run one script" shortcut (CBP publishes no bulk
  API, confirmed via research during v0.6.0), so it's a real, ongoing content
  investment, not a code task.
- 🟢 The architecture (BM25 index + HTS-prefix matching + "AI assists, never
  overrides" principle) is sound and would scale fine to a much larger
  ruling corpus without redesign.

## 8. Data Model

**Findings:**
- 🔴 **No migrations tool (Alembic or equivalent).** Every schema change so
  far has been handled by deleting the SQLite file and letting
  `Base.metadata.create_all()` recreate it from scratch — explicitly
  instructed in every release's upgrade notes ("delete your existing dev
  database"). This is acceptable for a solo dev database, **not acceptable
  for any deployment with real user data**, since it means schema changes
  destroy existing data.
- 🟡 **SQLite foreign-key enforcement should be verified.** SQLite does not
  enforce `FOREIGN KEY` constraints by default unless `PRAGMA foreign_keys =
  ON` is set per-connection. It's not confirmed whether `database.py`
  configures this — if not, the FK relationships defined in the SQLAlchemy
  models (Organization → User → Product/AuditLog/Webhook, etc.) are
  advisory only at the database level today, not actually enforced.
  **Action: check `server_fastapi/database.py`'s `create_engine()` call for
  a `PRAGMA foreign_keys=ON` event listener; add one if missing.**
- 🟡 Hard deletes throughout (products, webhooks) — no soft-delete pattern.
  The audit log captures a snapshot of what was deleted, but the resource
  itself is gone, which may not satisfy a real compliance retention
  requirement for a trade-compliance product specifically.
- 🟢 Postgres migration path is documented in `DEPLOYMENT.md`
  (`SYJ_DATABASE_URL`) but has never actually been run against a real
  Postgres instance — the SQLite→Postgres switch is untested in practice.

## 9. Security Posture

**Consolidated from findings above, plus:**
- 🔴 CORS wide open (§2)
- 🔴 No rate limiting (§2, §4)
- 🔴 No refresh token revocation (§4)
- 🟡 No dependency vulnerability scanning in CI — no `pip-audit`, no
  `npm audit` gate, no Dependabot/Renovate configuration. CI currently
  verifies *that things build and tests pass*, not *that dependencies are
  free of known CVEs*.
- 🟡 File upload size limits for CSV/Excel import (`/products/import`) are
  not confirmed to be enforced — worth verifying a malicious/oversized file
  can't be used for a resource-exhaustion attempt.
- 🟢 No CSRF exposure — this is a pure Bearer-token JWT API, not
  cookie-session-based, so CSRF doesn't apply in the traditional sense. This
  is correctly designed, not an oversight.
- 🟢 Input validation via Pydantic is consistently applied and was tested
  (422 responses for malformed input verified across most endpoints).

## 10. Dependency Management

**Findings:**
- 🟡 Python dependencies use loose version ranges (`>=x,<y`) in
  `requirements.txt`/`requirements-dev.txt` rather than an exact lockfile
  (`pip-compile`, Poetry, or similar). This already caused one real,
  confirmed problem: the `httpx2` version-range bug that broke a test install
  mid-development because the assumed range didn't match reality.
- 🔴 **Frontend lockfile status is genuinely uncertain.** CI's
  `frontend-build` job deliberately uses `npm install` instead of `npm ci`
  specifically because it could not be confirmed whether `package-lock.json`
  is committed and in sync. **Action: run `git ls-files frontend/package-lock.json`
  in the real repo — if it's tracked, switch CI back to `npm ci` for faster,
  fully reproducible builds; if not, commit it.**
- 🟢 The `requirements.txt`/`requirements-dev.txt` split (production vs.
  test-only deps) is good practice and correctly keeps the Docker image lean.

## 11. Test Coverage

**Findings:**
- 🟢 **Backend: excellent, genuinely verified.** 103 tests across the core
  engine, stdlib API, FastAPI integration, auth/RBAC, rulings search, duty
  calculation, webhooks (including real HTTP delivery to a real local
  server with independent signature verification), and reports (including
  real PDF/Excel files generated and read back to confirm content). This is
  not aspirational — every one of these was actually run and confirmed
  passing multiple times throughout development.
- 🔴 **Frontend: zero automated tests.** No Vitest/Jest unit tests, no React
  Testing Library component tests, no Playwright/Cypress end-to-end tests.
  All frontend verification to date has been static analysis (import
  resolution, brace balancing, export-name cross-checking) plus manual
  on-device clicking by the repo owner. This is the single largest test
  coverage gap in the project and should be the top priority before v1.0.0.
- 🟡 CI runs the full backend suite and a real `npm run build`, but does not
  run ESLint (configured, never wired into `ci.yml`) or any frontend test
  command, since none currently exist.

## 12. Docker and Deployment

**Findings:**
- 🟢 Dockerfiles (multi-stage, non-root user, healthchecks) and
  `docker-compose.yml` are real and CI-verified — GitHub Actions genuinely
  builds both images and smoke-tests that the backend container starts and
  responds healthy, and that the frontend container serves real content
  including correct SPA fallback routing. Confirmed green in a real CI run.
- 🟡 **Never deployed to an actual production host.** Everything Docker-related
  has been validated in CI's ephemeral runners, never run "in anger" on a
  real VPS with real persistent volumes, real DNS, real TLS termination, or
  under real traffic.
- 🟡 No documented backup/restore procedure for the `syj-data` Docker volume
  (which holds the SQLite DB and the HTS dataset). If that volume is lost,
  there's no documented recovery path beyond re-running the HTS importer
  (which rebuilds the dataset but not user data).
- 🟢 The `docker-entrypoint.sh` auto-building the HTS dataset on first run is
  a thoughtful touch that avoids requiring a separate manual step.

## 13. GitHub Actions / CI

**Findings:**
- 🟢 Three-job pipeline (`backend-tests`, `frontend-build`, `docker-build`)
  is real, well-structured, and confirmed passing end-to-end at least once.
  The comments in `ci.yml` correctly document a real bug found during
  development (combining FastAPI-app-instantiating test modules in one
  process silently breaks database isolation) — good, since that's exactly
  the kind of non-obvious gotcha a future contributor would otherwise
  rediscover the hard way.
- 🟡 CI-only, no CD — no automatic deployment to any environment on a
  successful `main` build.
- 🟢 No branch protection rules, PR template, or CODEOWNERS file could be
  confirmed (this needs a direct check of the real repo's Settings, not
  something visible from code) — worth verifying and setting up before
  accepting external contributions.

## 14. Performance

**Findings:**
- 🟢 Core engine performance has never been a bottleneck at current dataset
  size (~17k HTS records load and query fast in-memory).
- 🟡 No load testing has been performed against the API at all — no k6,
  Locust, or similar. Unknown behavior under concurrent load, especially
  given SQLite's single-writer limitation (see §8) and synchronous webhook
  delivery (see §1).
- 🟡 No explicit database indexes beyond what SQLAlchemy auto-creates for
  primary/foreign keys. Frequently-filtered columns like `organization_id`
  (used in nearly every query across Products, Classifications, AuditLog,
  Webhooks) should be spot-checked for explicit indexing as data volume grows.
- 🟢 `nginx.conf` correctly sets aggressive caching on hashed Vite build
  assets — a real, working performance decision, not just a default.

## 15. Documentation

**Findings:**
- 🟢 `README.md` is genuinely thorough — architecture diagrams, honest
  scope statements per release, real setup instructions. `DEPLOYMENT.md` is
  solid and clearly separates the Termux dev workflow from real Docker
  deployment.
- 🟡 No `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, or `SECURITY.md`
  (vulnerability disclosure policy) exist despite being explicitly mentioned
  as a goal in the original v0.9.0 scope ("welcoming to contributors, issue
  templates") — this part of that release's intent was never actually built;
  only the Docker/CI half was.
- 🟡 No `CHANGELOG.md` file exists in the repo itself — release notes were
  generated in chat for several versions but not consistently committed as
  files (only `RELEASES/v0.4.0.md` is confirmed to exist as a committed
  file; later releases' notes were only ever shared in conversation).

## 16. Open-Source Readiness

**Findings:**
- 🟢 Apache 2.0 license is in place and correctly referenced.
- 🔴 No issue templates, no PR template, no CODEOWNERS, no CONTRIBUTING
  guide — despite the README stating "Issues and PRs welcome." A genuine
  outside contributor today would have no structured way to know how to
  propose a change or what's expected.
- 🟡 No governance model documented (who merges PRs, how releases are cut,
  how decisions get made) — fine for a solo-maintained project today, but
  worth having in writing before actively soliciting contributors.

## 17. Release Engineering

**Findings:**
- 🟡 **Git history doesn't cleanly mirror the documented release notes.**
  Confirmed during development: v0.7.0 and v0.8.0's files were never
  actually committed/pushed individually — they were bundled together into
  the v0.9.0 commit when that finally got pushed. So while the *release
  notes* for v0.7.0/v0.8.0 are accurate descriptions of what was built and
  tested, the git tags for those specific versions don't exist, and the
  commit history doesn't reflect three separate releases the way the
  version numbers imply.
- 🟡 No automated changelog/release generation (no `release-please`,
  `semantic-release`, or similar) — every release note was hand-written.
- 🟢 Semantic versioning itself has been followed sensibly in spirit (each
  version number corresponds to a real, coherent scope of work), even where
  the git mechanics lagged behind.

## 18. Repository Hygiene

**Findings:**
- 🟡 At least one confirmed incident of stray duplicate files landing in the
  repo root (`ClassifyPage.tsx`, `DutyCalculatorPage.tsx`, `schemas.py`)
  from a manual copy/download workflow — caught and cleaned up, but signals
  that the manual file-transfer process (necessitated by the Termux/sandbox
  environment split) is error-prone and worth tightening if this becomes a
  team project rather than a solo one.
- 🟢 `.gitignore` is reasonably thorough (build artifacts, `node_modules`,
  `.env` files, generated `hts_full.json`, test temp directories).
- 🔴 No pre-commit hooks or automated formatting/linting gate. ESLint is
  configured (`.eslintrc.cjs`) but not run in CI or on commit — nothing
  currently prevents lint violations from being merged.

---

## Consolidated Technical Debt (Priority Order)

| # | Item | Severity | Area |
|---|---|---|---|
| 1 | No refresh token revocation | 🔴 | Auth |
| 2 | No rate limiting (esp. login) | 🔴 | Security |
| 3 | CORS wide open (`*`) | 🔴 | Security |
| 4 | No Alembic migrations | 🔴 | Data model |
| 5 | Zero frontend automated tests | 🔴 | Testing |
| 6 | Webhook delivery blocks the request | 🔴 | Architecture |
| 7 | No pre-commit/lint gate in CI | 🔴 | Repo hygiene |
| 8 | Frontend lockfile status unconfirmed | 🟡 | Dependencies |
| 9 | SQLite FK enforcement unconfirmed | 🟡 | Data model |
| 10 | No dependency vulnerability scanning | 🟡 | Security |
| 11 | Inconsistent pagination across list views | 🟡 | Frontend |
| 12 | No CONTRIBUTING/issue templates/CODEOWNERS | 🟡 | Open-source readiness |
| 13 | No duty-data staleness alerting | 🟡 | Duty calculator |
| 14 | Postgres path never tested end-to-end | 🟡 | Deployment |
| 15 | No load testing performed | 🟡 | Performance |
| 16 | Docker never deployed to a real host | 🟡 | Deployment |
| 17 | on_event/Pydantic Config/datetime.utcnow deprecations | 🟢 | Code quality |
| 18 | No CHANGELOG.md, incomplete release notes as files | 🟢 | Release engineering |
| 19 | Inconsistent API response envelopes | 🟢 | API design |
| 20 | CROSS rulings dataset very small (content, not code) | 🟢 | Content |

---

## Roadmap to v1.0.0

Proposed sequencing — each stage is independently shippable and testable,
matching the pattern that's worked well across v0.1–v0.9:

**v0.9.2 — Security hardening (🔴 items first)**
Rate limiting on auth endpoints, CORS allowlist (env-configurable), refresh
token revocation (a minimal server-side denylist table is enough — doesn't
need a full session store), `PRAGMA foreign_keys=ON` verification/fix, move
webhook delivery to a background task (FastAPI's `BackgroundTasks` is
enough at this scale — no need for Celery yet).

**v0.9.3 — Data model durability**
Introduce Alembic, generate an initial migration matching the current
schema, document the upgrade path for existing SQLite databases. Actually
run the Postgres path end-to-end at least once and fix whatever breaks.

**v0.9.4 — Frontend test coverage**
Vitest + React Testing Library for component/hook tests (start with
`use-toast`, `theme-context`, `auth-context` — pure logic, easiest to test
well). Wire ESLint into CI. If time allows, a small Playwright smoke suite
covering login → classify → logout.

**v0.9.5 — Content & UX consistency**
Expand the CROSS rulings sample meaningfully (even 20-30 more real,
sourced rulings would be a big improvement). Consistent pagination across
all list views. Duty-data staleness warning when `as_of_date` is older than
some threshold.

**v0.9.6 — Open-source readiness**
`CONTRIBUTING.md`, issue templates, PR template, `CODEOWNERS`,
`SECURITY.md`, `CHANGELOG.md`, pre-commit hooks (ruff/black for Python,
ESLint/Prettier for frontend).

**v1.0.0 — Production validation**
Deploy to a real VPS end-to-end, document the actual deployment (not just
the theoretical `docker-compose up`), set up and document backup/restore
for the data volume, basic load testing to establish real capacity
expectations, first official tagged GitHub Release with complete notes.

---

## Bottom Line

The core intellectual property of this project — the GRI classification
engine, the duty calculator, the rulings search — is genuinely well-built
and thoroughly tested; that's not in question. The gaps are almost entirely
in the *production operations* layer (auth revocation, rate limiting, CORS,
migrations, frontend testing) rather than the core logic, which is exactly
the pattern you'd expect from a project built by iterating fast on features
first. That's a very fixable, very typical shape for a pre-1.0 project to be
in — none of the 🔴 items are architecturally hard, they're each a bounded,
well-understood piece of work.
