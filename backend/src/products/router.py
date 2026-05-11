from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, require_token
from src.products.models import Product, Supplier
from src.products.schemas import (
    ProductCreate, ProductOut, ProductUpdate,
    SupplierCreate, SupplierOut,
)
from src.products.supplier_service import (
    SupplierLedger, SupplierSummary, SupplierUpdate,
    build_supplier_ledger, summarise_supplier,
)

router = APIRouter()


# ── Suppliers ──────────────────────────────────────────────────────────────

@router.get("/suppliers", response_model=list[SupplierOut])
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Supplier).order_by(Supplier.name))
    return result.scalars().all()


@router.post("/suppliers", response_model=SupplierOut, status_code=201, dependencies=[Depends(require_token)])
async def create_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db)):
    supplier = Supplier(**body.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.post("/suppliers/upsert", response_model=SupplierOut, dependencies=[Depends(require_token)])
async def upsert_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db)):
    """Find supplier by name (case-insensitive) or create if not found."""
    result = await db.execute(select(Supplier).order_by(Supplier.name))
    for s in result.scalars().all():
        if s.name.strip().lower() == body.name.strip().lower():
            return s
    supplier = Supplier(**body.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/suppliers/summaries", response_model=list[SupplierSummary])
async def supplier_summaries(db: AsyncSession = Depends(get_db)):
    """All suppliers with totals (for the Suppliers page list view)."""
    result = await db.execute(select(Supplier).order_by(Supplier.name))
    return [await summarise_supplier(db, s) for s in result.scalars().all()]


@router.get("/suppliers/outstanding", response_model=list[SupplierSummary])
async def supplier_outstanding(db: AsyncSession = Depends(get_db)):
    """Suppliers we still owe, highest balance first."""
    result = await db.execute(select(Supplier))
    summaries = [await summarise_supplier(db, s) for s in result.scalars().all()]
    summaries = [s for s in summaries if s.balance > 0]
    summaries.sort(key=lambda s: s.balance, reverse=True)
    return summaries


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut, dependencies=[Depends(require_token)])
async def update_supplier(supplier_id: int, body: SupplierUpdate, db: AsyncSession = Depends(get_db)):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(supplier, field, value)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}/ledger", response_model=SupplierLedger)
async def supplier_ledger(supplier_id: int, db: AsyncSession = Depends(get_db)):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return await build_supplier_ledger(db, supplier)


# ── Products ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[ProductOut])
async def list_products(active_only: bool = True, db: AsyncSession = Depends(get_db)):
    q = select(Product).order_by(Product.name)
    if active_only:
        q = q.where(Product.is_active == True)  # noqa: E712
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/search", response_model=list[ProductOut])
async def search_products(
    name: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Substring search on name, SKU, or barcode (all case-insensitive)."""
    q = name.strip()
    result = await db.execute(
        select(Product)
        .where(
            Product.is_active == True,  # noqa: E712
            (
                Product.name.ilike(f"%{q}%")
                | Product.sku.ilike(f"%{q}%")
                | Product.barcode.ilike(f"%{q}%")
            ),
        )
        .order_by(Product.name)
        .limit(10)
    )
    return result.scalars().all()


@router.get("/barcode/{code}", response_model=ProductOut)
async def get_by_barcode(code: str, db: AsyncSession = Depends(get_db)):
    """Exact barcode lookup — used by the dashboard's scan flow."""
    result = await db.execute(
        select(Product).where(Product.barcode == code, Product.is_active == True)  # noqa: E712
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="No product with that barcode")
    return product


@router.get("/low-stock", response_model=list[ProductOut])
async def low_stock_products(db: AsyncSession = Depends(get_db)):
    """Products where stock_qty <= reorder_level (and reorder_level > 0)."""
    result = await db.execute(
        select(Product).where(
            Product.is_active == True,  # noqa: E712
            Product.reorder_level > 0,
            Product.stock_qty <= Product.reorder_level,
        ).order_by(Product.name)
    )
    return result.scalars().all()


@router.post("", response_model=ProductOut, status_code=201, dependencies=[Depends(require_token)])
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = Product(**body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductOut, dependencies=[Depends(require_token)])
async def update_product(product_id: int, body: ProductUpdate, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product
