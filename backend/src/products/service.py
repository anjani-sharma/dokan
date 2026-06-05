"""Product helpers shared across domains.

`upsert_product_by_name` is used by the invoices and sales routers when
the caller has a free-text product name (e.g. from OCR or the bot's NLP
extractor) but no `product_id`. Creating a placeholder product means the
stock movement is recorded against a real row — otherwise stock_qty drifts
out of sync with what actually moved through the shop.
"""

import re
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.products.models import Product, Supplier


def _slug_sku(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper()[:80]
    return base or "PROD"


async def upsert_product_by_name(
    db: AsyncSession,
    name: str,
    *,
    default_cost: Decimal | None = None,
    default_unit: str | None = None,
) -> Product | None:
    """Find a product by case-insensitive name, or create a minimal one.

    Returns None for empty names. Caller is expected to be inside a
    transaction — this only `flush()`es so the new id is available.
    """
    clean = (name or "").strip()
    if not clean:
        return None

    existing = await db.execute(
        select(Product).where(func.lower(Product.name) == clean.lower())
    )
    found = existing.scalar_one_or_none()
    if found:
        return found

    base_sku = _slug_sku(clean)
    sku = base_sku
    suffix = 1
    while True:
        clash = await db.execute(select(Product).where(Product.sku == sku))
        if not clash.scalar_one_or_none():
            break
        suffix += 1
        sku = f"{base_sku}-{suffix}"

    product = Product(
        sku=sku,
        name=clean,
        unit=default_unit,
        cost_price=default_cost if default_cost is not None else Decimal("0"),
    )
    db.add(product)
    await db.flush()
    return product


async def upsert_supplier_by_name(
    db: AsyncSession,
    name: str,
    *,
    auto_created: bool = True,
) -> Supplier | None:
    """Find supplier by case-insensitive name, or create with `auto_created=True`.

    Used by the bulk-import worker so OCR'd vendor names don't fail the
    invoice insert when the supplier doesn't exist yet. The flag lets the
    dashboard surface a "review / merge" affordance later.
    """
    clean = (name or "").strip()
    if not clean:
        return None

    existing = await db.execute(
        select(Supplier).where(func.lower(Supplier.name) == clean.lower())
    )
    found = existing.scalar_one_or_none()
    if found:
        return found

    supplier = Supplier(name=clean, auto_created=auto_created)
    db.add(supplier)
    await db.flush()
    return supplier
