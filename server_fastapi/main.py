"""
SYJ OpenTrade Logic - FastAPI server (v0.3.0)
================================================
Real FastAPI + SQLAlchemy port of the v0.2.0 stdlib http.server (server/app.py).
Route-for-route equivalent, same status codes, same response shapes -- so any
client built against v0.2.0 keeps working.

Run:
    pip install -r server_fastapi/requirements.txt
    python3 -m uvicorn server_fastapi.main:app --reload --port 8000

Then open http://localhost:8000/docs for interactive Swagger UI (auto-generated
-- this is the "Swagger / OpenAPI documentation" requirement from the original
spec, now free instead of hand-written).
"""

import json
import os
import sys

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gri_engine import GRIEngine  # noqa: E402
from server_fastapi.database import init_db, get_db, ClassificationRecord  # noqa: E402
from server_fastapi.schemas import (  # noqa: E402
    ClassifyRequest,
    ClassificationOut,
    ClassificationListOut,
    ClassificationHistoryItem,
    DeleteOut,
    HealthOut,
)

DEFAULT_HTS_DATA = os.environ.get(
    "SYJ_HTS_DATA_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_full.json"),
)
FALLBACK_HTS_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hts_sample.json"
)

app = FastAPI(
    title="SYJ OpenTrade Logic API",
    version="0.3.0",
    description="Deterministic, explainable HTS classification REST API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok", "service": "SYJ OpenTrade Logic", "version": "0.3.0"}


@app.post("/classify", response_model=ClassificationOut, status_code=201)
def classify(req: ClassifyRequest, db: Session = Depends(get_db)):
    result = engine.classify(req.description)
    result_dict = result.to_dict()

    record = ClassificationRecord(
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
