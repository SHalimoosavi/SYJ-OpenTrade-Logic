"""
SYJ OpenTrade Logic - Reports routes (v0.8.0)
================================================
GET /reports/classifications/csv    - export classification history as CSV
GET /reports/classifications/excel  - export classification history as Excel
GET /reports/products/csv           - export product catalog as CSV
GET /reports/products/excel         - export product catalog as Excel
GET /reports/classifications/{id}/pdf - single-classification PDF report

All scoped to the caller's organization, VIEWER+ (these are read/export
operations, not data mutations).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, ClassificationRecord, Product, User, UserRole
from server_fastapi.dependencies import require_role
from server_fastapi.reports import (
    classifications_to_csv,
    classifications_to_excel,
    products_to_csv,
    products_to_excel,
    classification_to_pdf,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _classification_rows(db: Session, organization_id: int) -> list:
    rows = (
        db.query(ClassificationRecord)
        .filter(ClassificationRecord.organization_id == organization_id)
        .order_by(ClassificationRecord.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "product_description": r.product_description,
            "final_code": r.final_code,
            "final_description": r.final_description,
            "confidence": r.confidence,
            "is_classified": r.is_classified,
            "duty_rate": r.duty_rate,
            "created_at": r.created_at,
        }
        for r in rows
    ]


def _product_rows(db: Session, organization_id: int) -> list:
    rows = db.query(Product).filter(Product.organization_id == organization_id).all()
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "description": p.description,
            "hts_code": p.hts_code,
            "duty_rate": p.duty_rate,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in rows
    ]


@router.get("/classifications/csv")
def export_classifications_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    rows = _classification_rows(db, current_user.organization_id)
    csv_bytes = classifications_to_csv(rows)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=classifications.csv"},
    )


@router.get("/classifications/excel")
def export_classifications_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    rows = _classification_rows(db, current_user.organization_id)
    xlsx_bytes = classifications_to_excel(rows)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=classifications.xlsx"},
    )


@router.get("/products/csv")
def export_products_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    rows = _product_rows(db, current_user.organization_id)
    csv_bytes = products_to_csv(rows)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


@router.get("/products/excel")
def export_products_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    rows = _product_rows(db, current_user.organization_id)
    xlsx_bytes = products_to_excel(rows)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=products.xlsx"},
    )


@router.get("/classifications/{classification_id}/pdf")
def export_classification_pdf(
    classification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    record = (
        db.query(ClassificationRecord)
        .filter(
            ClassificationRecord.id == classification_id,
            ClassificationRecord.organization_id == current_user.organization_id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"No classification with id {classification_id}")

    result_dict = json.loads(record.result_json)
    pdf_bytes = classification_to_pdf(result_dict)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=classification_{classification_id}.pdf"},
    )
