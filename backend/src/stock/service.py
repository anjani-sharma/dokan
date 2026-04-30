from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.stock.models import StockMovement
from src.products.models import Product


async def record_stock_movement(
    db: AsyncSession,
    product_id: int,
    movement_type: str,
    qty_change: Decimal,
    reference_id: int | None = None,
    reference_type: str | None = None,
    note: str | None = None,
) -> StockMovement:
    movement = StockMovement(
        product_id=product_id,
        movement_type=movement_type,
        qty_change=qty_change,
        reference_id=reference_id,
        reference_type=reference_type,
        note=note,
    )
    db.add(movement)
    await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(stock_qty=Product.stock_qty + qty_change)
    )
    return movement


async def reverse_stock_movement(
    db: AsyncSession,
    product_id: int,
    qty_change: Decimal,
    reference_id: int | None = None,
    reference_type: str | None = None,
) -> StockMovement:
    return await record_stock_movement(
        db,
        product_id=product_id,
        movement_type="adjustment",
        qty_change=qty_change,
        reference_id=reference_id,
        reference_type=reference_type,
        note="reversal",
    )
