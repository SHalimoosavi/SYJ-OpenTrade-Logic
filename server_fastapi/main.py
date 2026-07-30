"""
SYJ OpenTrade Logic - FastAPI server (v0.4.0)
================================================
v0.3.0 added real FastAPI + SQLAlchemy + the full HTS dataset.
v0.4.0 adds: JWT auth, organizations, RBAC users, and a product catalog
with CSV/Excel import. The classification endpoints below remain
unauthenticated on purpose -- they're the open, public-facing core of the
project (classification is meant to be freely usable); auth is required
only for organization-scoped resources (users, products).

Run:
    pip install -r server_fastapi/requirements.txt
    python3 -m uvicorn server_fastapi.main:app --reload --port 8000

Then open http://localhost:8000/docs for interactive Swagger UI.
"""

import json
import os
import sys

from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gri_engine import GRIEngine  # noqa: E402
from server_fastapi.database import init_db, get_db, ClassificationRecord, User  # noqa: E402
from server_fastapi.schemas import (  # noqa: E402
    ClassifyRequest,
    ClassificationOut,
    ClassificationListOut,
    ClassificationHistoryItem,
    DeleteOut,
    HealthOut,
)
from server_fastapi import routes_auth, routes_catalog, routes_org, routes_rulings, routes_duty  # noqa: E402
from server_fastapi import routes_webhooks, routes_audit, routes_reports  # noqa: E402
from server_fastapi.dependencies import get_current_user_optional  # noqa: E402
from server_fastapi.audit import log_action  # noqa: E402
from server_fastapi.webhook_triggers import trigger_webhooks  # noqa: E402

DEFAULT_HTS_DATA = os.environ.get(
    "SYJ_HTS_DATA_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_full.json"),
)
FALLBACK_HTS_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_sample.json"
)

app = FastAPI(
    title="SYJ OpenTrade Logic API",
    version="0.7.0",
    description="Deterministic, explainable HTS classification REST API with organizations, RBAC, and a product catalog.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_catalog.router)
app.include_router(routes_org.router)
app.include_router(routes_rulings.router)
app.include_router(routes_duty.router)
app.include_router(routes_webhooks.router)
app.include_router(routes_audit.router)
app.include_router(routes_reports.router)

# Load the full 99-chapter dataset if it exists (built by scripts/import_hts_data.py);
# fall back to the small demo dataset from v0.1.0/v0.2.0 otherwise, so the server
# still boots cleanly on a fresh checkout before you've run the importer.
_data_path = DEFAULT_HTS_DATA if os.path.exists(DEFAULT_HTS_DATA) else FALLBACK_HTS_DATA
engine = GRIEngine(_data_path)


@app.on_event("startup")
def on_startup():
    init_db()
    print(f"[SYJ OpenTrade Logic] Loaded HTS dataset from: {_data_path}")
    if _data_path == FALLBACK_HTS_DATA:
        print("[SYJ OpenTrade Logic] WARNING: using the small demo dataset. "
              "Run scripts/import_hts_data.py to load the full 99-chapter HTS.")


@app.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok", "service": "SYJ OpenTrade Logic", "version": "0.7.0"}


@app.post("/classify", response_model=ClassificationOut, status_code=201)
def classify(
    req: ClassifyRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    result = engine.classify(req.description)
    result_dict = result.to_dict()

    # v0.6.0: surface related CROSS rulings as supporting precedent. This is
    # the "AI assists, never overrides" principle in practice -- rulings are
    # additional context for a human to review, not a second vote on the
    # classification itself. Combine two signals: rulings whose text matches
    # the product description lexically, and rulings tagged with the same
    # HTS heading as the result, deduped, capped at 3.
    text_matches = routes_rulings.rulings_index.search(req.description, top_k=3)
    code_matches = routes_rulings.rulings_index.search_by_hts_prefix(result_dict.get("final_code"), top_k=3)

    seen_ids = set()
    related_rulings = []
    for r in text_matches:
        if r.ruling.id not in seen_ids:
            seen_ids.add(r.ruling.id)
            related_rulings.append(r.to_dict())
    for ruling in code_matches:
        if ruling.id not in seen_ids:
            seen_ids.add(ruling.id)
            related_rulings.append(
                {
                    "id": ruling.id,
                    "url": ruling.url,
                    "date": ruling.date,
                    "title": ruling.title,
                    "hts_codes": ruling.hts_codes,
                    "gri_rules_cited": ruling.gri_rules_cited,
                    "excerpt": ruling.full_text,
                    "score": 0.0,
                    "matched_terms": [],
                }
            )
    result_dict["related_rulings"] = related_rulings[:3]

    # v0.8.0: if the caller happens to be authenticated, scope this
    # classification to their organization -- this is what makes org-scoped
    # reports/audit trails/webhooks have real data to work with, while
    # keeping /classify fully usable anonymously (organization_id stays
    # NULL for anonymous calls, same as before).
    organization_id = current_user.organization_id if current_user else None

    record = ClassificationRecord(
        organization_id=organization_id,
        product_description=result_dict["product_description"],
        final_code=result_dict.get("final_code"),
        final_description=result_dict.get("final_description"),
        confidence=result_dict.get("confidence"),
        is_classified=result_dict.get("is_classified", False),
        duty_rate=result_dict.get("duty_rate"),
        unresolved_reason=result_dict.get("unresolved_reason"),
        result_json=json.dumps(result_dict),
    )
    db.add(record)

    if organization_id:
        log_action(
            db, organization_id, current_user,
            action="classification.created", resource_type="classification",
            details={"product_description": req.description, "final_code": result_dict.get("final_code")},
        )
        trigger_webhooks(db, organization_id, "classification.created", {
            "product_description": req.description,
            "final_code": result_dict.get("final_code"),
            "is_classified": result_dict.get("is_classified"),
        })

    db.commit()
    db.refresh(record)

    return {"id": record.id, **result_dict}


@app.get("/classifications", response_model=ClassificationListOut)
def list_classifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.query(ClassificationRecord).count()
    rows = (
        db.query(ClassificationRecord)
        .order_by(ClassificationRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return {
        "count": total,
        "limit": limit,
        "offset": offset,
        "results": [ClassificationHistoryItem.model_validate(r) for r in rows],
    }


@app.get("/classifications/{record_id}", response_model=ClassificationOut)
def get_classification(record_id: int, db: Session = Depends(get_db)):
    record = db.query(ClassificationRecord).filter(ClassificationRecord.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"No classification record with id {record_id}")
    result_dict = json.loads(record.result_json)
    return {"id": record.id, **result_dict}


@app.delete("/classifications/{record_id}", response_model=DeleteOut)
def delete_classification(record_id: int, db: Session = Depends(get_db)):
    record = db.query(ClassificationRecord).filter(ClassificationRecord.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"No classification record with id {record_id}")
    db.delete(record)
    db.commit()
    return {"deleted": True, "id": record_id}
