from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, require_token
from src.payments.models import Payment
from src.products.service import upsert_product_by_name
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
    # If the caller didn't supply a product_id but did give us a name,
    # auto-create a placeholder product so the stock movement is recorded.
    if not body.product_id and body.product_name_raw:
        product = await upsert_product_by_name(
            db,
            body.product_name_raw,
            default_cost=body.selling_price,
        )
        if product:
            body.product_id = product.id

    # Pop POS-payment fields — they live on the request body but not on the
    # DailySale row. We use them after the sale is flushed to create an
    # inflow Payment in the same transaction.
    pos_amount = body.payment_amount
    pos_mode = body.payment_mode
    sale_data = body.model_dump(exclude={"payment_amount", "payment_mode"})

    target_sale: DailySale

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
            target_sale = existing
        else:
            target_sale = DailySale(**sale_data)
            db.add(target_sale)
            await db.flush()
            await record_stock_movement(
                db,
                product_id=body.product_id,
                movement_type="sale",
                qty_change=-body.qty_sold,
                reference_id=target_sale.id,
                reference_type="daily_sale",
            )
    else:
        target_sale = DailySale(**sale_data)
        db.add(target_sale)
        await db.flush()

    # Point-of-sale payment: write an inflow Payment row so the cash drawer
    # and the customer ledger reflect the cash that just changed hands.
    if pos_amount and pos_amount > 0 and pos_mode:
        db.add(Payment(
            payment_date=body.sale_date,
            amount=pos_amount,
            payment_mode=pos_mode,
            direction="inflow",
            customer_id=body.customer_id,
            note=f"Point-of-sale payment for sale #{target_sale.id}",
        ))

    await db.commit()
    await db.refresh(target_sale)
    return target_sale


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
