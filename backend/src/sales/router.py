from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, require_token
from src.sales.models import DailySale
from src.sales.schemas import SaleCreate, SaleOut, SaleUpdate
from src.stock.service import record_stock_movement, reverse_stock_movement

router = APIRouter()


@router.get("/daily", response_model=list[SaleOut])
async def list_sales(
    sale_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(DailySale).order_by(DailySale.sale_date.desc(), DailySale.created_at.desc())
    if sale_date:
        q = q.where(DailySale.sale_date == sale_date)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/daily", response_model=SaleOut, status_code=201, dependencies=[Depends(require_token)])
async def create_sale(body: SaleCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a sale. If the same product_id already has an entry for that date,
    the quantities are combined (upsert) rather than creating a duplicate row.
    """
    # Upsert: check for existing record with same product_id + date
    if body.product_id:
        existing_result = await db.execute(
            select(DailySale).where(
                DailySale.sale_date == body.sale_date,
                DailySale.product_id == body.product_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            extra_qty = body.qty_sold
            existing.qty_sold += extra_qty
            if body.selling_price:
                existing.selling_price = body.selling_price
            existing.raw_input = (existing.raw_input or "") + " | " + (body.raw_input or "")
            await record_stock_movement(
                db,
                product_id=body.product_id,
                movement_type="sale",
                qty_change=-extra_qty,
                reference_id=existing.id,
                reference_type="daily_sale_upsert",
            )
            await db.commit()
            await db.refresh(existing)
            return existing

    sale = DailySale(**body.model_dump())
    db.add(sale)
    await db.flush()

    if body.product_id:
        await record_stock_movement(
            db,
            product_id=body.product_id,
            movement_type="sale",
            qty_change=-body.qty_sold,
            reference_id=sale.id,
            reference_type="daily_sale",
        )

    await db.commit()
    await db.refresh(sale)
    return sale


@router.put("/daily/{sale_id}", response_model=SaleOut, dependencies=[Depends(require_token)])
async def update_sale(sale_id: int, body: SaleUpdate, db: AsyncSession = Depends(get_db)):
    sale = await db.get(DailySale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    if body.qty_sold is not None and sale.product_id:
        qty_diff = body.qty_sold - sale.qty_sold
        if qty_diff != 0:
            await record_stock_movement(
                db,
                product_id=sale.product_id,
                movement_type="adjustment",
                qty_change=-qty_diff,
                reference_id=sale.id,
                reference_type="daily_sale_edit",
            )

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(sale, field, value)

    await db.commit()
    await db.refresh(sale)
    return sale


@router.delete("/daily/{sale_id}", status_code=204, dependencies=[Depends(require_token)])
async def delete_sale(sale_id: int, db: AsyncSession = Depends(get_db)):
    sale = await db.get(DailySale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    if sale.product_id:
        await reverse_stock_movement(
            db,
            product_id=sale.product_id,
            qty_change=sale.qty_sold,
            reference_id=sale.id,
            reference_type="daily_sale_delete",
        )

    await db.delete(sale)
    await db.commit()


@router.get("/daily/summary/week", response_model=list[SaleOut])
async def this_week_sales(db: AsyncSession = Depends(get_db)):
    """All sales from the last 7 days."""
    week_ago = date.today() - timedelta(days=7)
    result = await db.execute(
        select(DailySale)
        .where(DailySale.sale_date >= week_ago)
        .order_by(DailySale.sale_date.desc())
    )
    return result.scalars().all()
