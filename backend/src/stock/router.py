from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
from src.invoices.models import PurchaseInvoiceItem
from src.sales.models import DailySale
from src.stock.models import StockMovement
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    movement_type: str
    qty_change: Decimal
    reference_id: int | None
    reference_type: str | None
    note: str | None
    moved_at: datetime


router = APIRouter()


@router.get("/movements", response_model=list[MovementOut])
async def list_movements(
    product_id: int | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    q = select(StockMovement).order_by(StockMovement.moved_at.desc()).limit(limit)
    if product_id:
        q = q.where(StockMovement.product_id == product_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/inventory")
async def derived_inventory(db: AsyncSession = Depends(get_db)):
    """
    Derive current stock per item from purchase invoice items minus daily sales.
    Works even when no formal Product catalog entries exist.
    Returns items sorted by name with qty_purchased, qty_sold, and stock_on_hand.
    """
    # Sum purchased qty per product name
    purchased_rows = await db.execute(
        select(
            func.lower(PurchaseInvoiceItem.product_name_raw).label("name"),
            func.coalesce(func.sum(PurchaseInvoiceItem.qty), 0).label("qty"),
            func.max(PurchaseInvoiceItem.product_name_raw).label("display_name"),
            func.coalesce(func.sum(PurchaseInvoiceItem.unit_cost), 0).label("unit_cost_sum"),
            func.count(PurchaseInvoiceItem.id).label("purchase_count"),
        )
        .where(PurchaseInvoiceItem.product_name_raw.isnot(None))
        .group_by(func.lower(PurchaseInvoiceItem.product_name_raw))
    )

    purchased: dict[str, dict] = {}
    for row in purchased_rows:
        purchased[row.name] = {
            "display_name":   row.display_name,
            "qty_purchased":  float(row.qty),
            "unit_cost_avg":  float(row.unit_cost_sum) / row.purchase_count if row.purchase_count else 0,
        }

    # Sum sold qty per product name
    sold_rows = await db.execute(
        select(
            func.lower(DailySale.product_name_raw).label("name"),
            func.coalesce(func.sum(DailySale.qty_sold), 0).label("qty"),
        )
        .where(DailySale.product_name_raw.isnot(None))
        .group_by(func.lower(DailySale.product_name_raw))
    )

    sold: dict[str, float] = {}
    for row in sold_rows:
        sold[row.name] = float(row.qty)

    # Merge and compute stock on hand
    all_names = set(purchased.keys()) | set(sold.keys())
    items = []
    for key in sorted(all_names):
        p = purchased.get(key, {"display_name": key, "qty_purchased": 0, "unit_cost_avg": 0})
        qty_sold = sold.get(key, 0)
        items.append({
            "name":           p["display_name"],
            "qty_purchased":  p["qty_purchased"],
            "qty_sold":       qty_sold,
            "stock_on_hand":  p["qty_purchased"] - qty_sold,
            "unit_cost_avg":  round(p["unit_cost_avg"], 2),
        })

    return {"items": items, "total_items": len(items)}
