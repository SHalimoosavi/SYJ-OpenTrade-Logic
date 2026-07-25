"""
SYJ OpenTrade Logic - Product catalog routes (v0.4.0)
========================================================
All routes scoped to current_user.organization_id -- no endpoint accepts
an org_id from the client, so there is no path for one organization to
read or write another's data by guessing IDs.

RBAC:
    VIEWER  - GET only
    MEMBER  - + POST/PUT (create/edit), + import
    ADMIN   - + DELETE
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server_fastapi.database import get_db, Product, User, UserRole
from server_fastapi.dependencies import require_role
from server_fastapi.schemas import (
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductOut,
    ProductListOut,
    ImportSummaryOut,
    ImportRowResult,
)
from server_fastapi.catalog_import import parse_upload, ImportParseError

router = APIRouter(prefix="/products", tags=["catalog"])


@router.get("", response_model=ProductListOut)
def list_products(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    q = db.query(Product).filter(Product.organization_id == current_user.organization_id)
    total = q.count()
    rows = q.order_by(Product.created_at.desc()).limit(limit).offset(offset).all()
    return {"count": total, "limit": limit, "offset": offset, "results": rows}


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.VIEWER)),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.organization_id == current_user.organization_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product with id {product_id}")
    return product


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    req: ProductCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MEMBER)),
):
    existing = (
        db.query(Product)
        .filter(Product.organization_id == current_user.organization_id, Product.sku == req.sku)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"A product with SKU '{req.sku}' already exists")

    product = Product(organization_id=current_user.organization_id, **req.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    req: ProductUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MEMBER)),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.organization_id == current_user.organization_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product with id {product_id}")

    updates = req.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.organization_id == current_user.organization_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product with id {product_id}")
    db.delete(product)
    db.commit()
    return {"deleted": True, "id": product_id}


@router.post("/import", response_model=ImportSummaryOut)
async def import_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MEMBER)),
):
    file_bytes = await file.read()
    try:
        parsed_rows = parse_upload(file.filename, file_bytes)
    except ImportParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    created = 0
    updated = 0
    errors = 0
    row_results = []

    for row in parsed_rows:
        if row["error"]:
            errors += 1
            row_results.append(ImportRowResult(row_number=row["row_number"], sku=None, status="error", error=row["error"]))
            continue

        product_data = row["product"]
        try:
            existing = (
                db.query(Product)
                .filter(Product.organization_id == current_user.organization_id, Product.sku == product_data["sku"])
                .first()
            )
            if existing is not None:
                for field in ("name", "description", "hts_code", "duty_rate"):
                    if product_data.get(field) is not None:
                        setattr(existing, field, product_data[field])
                status = "updated"
                updated += 1
            else:
                new_product = Product(organization_id=current_user.organization_id, **product_data)
                db.add(new_product)
                status = "created"
                created += 1

            db.commit()
            row_results.append(ImportRowResult(row_number=row["row_number"], sku=product_data["sku"], status=status))
        except IntegrityError as e:
            db.rollback()
            errors += 1
            row_results.append(ImportRowResult(
                row_number=row["row_number"], sku=product_data.get("sku"), status="error", error=str(e.orig)
            ))

    return ImportSummaryOut(
        total_rows=len(parsed_rows),
        created=created,
        updated=updated,
        errors=errors,
        row_results=row_results,
    )
