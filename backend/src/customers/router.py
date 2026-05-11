from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.customers.models import Customer
from src.customers.schemas import (
    CustomerCreate, CustomerLedger, CustomerOut, CustomerSummary, CustomerUpdate,
)
from src.customers.service import build_ledger, summarise_customer
from src.dependencies import get_db, require_token

router = APIRouter()


@router.get("", response_model=list[CustomerSummary])
async def list_customers(
    q: str | None = Query(None, min_length=1, description="Case-insensitive name substring"),
    db: AsyncSession = Depends(get_db),
):
    """List all customers with their running balances."""
    stmt = select(Customer).order_by(Customer.name)
    if q:
        stmt = stmt.where(Customer.name.ilike(f"%{q}%"))
    result = await db.execute(stmt)
    customers = result.scalars().all()
    return [await summarise_customer(db, c) for c in customers]


@router.get("/outstanding", response_model=list[CustomerSummary])
async def outstanding_customers(db: AsyncSession = Depends(get_db)):
    """Customers with a non-zero balance (they owe the shop), highest first."""
    result = await db.execute(select(Customer))
    summaries = [await summarise_customer(db, c) for c in result.scalars().all()]
    summaries = [s for s in summaries if s.balance > 0]
    summaries.sort(key=lambda s: s.balance, reverse=True)
    return summaries


@router.post("", response_model=CustomerOut, status_code=201, dependencies=[Depends(require_token)])
async def create_customer(body: CustomerCreate, db: AsyncSession = Depends(get_db)):
    customer = Customer(**body.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.post("/upsert", response_model=CustomerOut, dependencies=[Depends(require_token)])
async def upsert_customer(body: CustomerCreate, db: AsyncSession = Depends(get_db)):
    """Find a customer by name (case-insensitive) or create one. Mirrors the supplier upsert."""
    result = await db.execute(select(Customer))
    for c in result.scalars().all():
        if c.name.strip().lower() == body.name.strip().lower():
            return c
    customer = Customer(**body.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerOut, dependencies=[Depends(require_token)])
async def update_customer(customer_id: int, body: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/{customer_id}/ledger", response_model=CustomerLedger)
async def customer_ledger(customer_id: int, db: AsyncSession = Depends(get_db)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return await build_ledger(db, customer)
