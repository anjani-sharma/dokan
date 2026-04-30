from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
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
