"""
Demo seed script — populates the database with realistic electrical shop data.

Run once before the client demo:
    python seed_demo.py

Run with --clear to wipe and re-seed:
    python seed_demo.py --clear

All data uses a fictional shop "Sharma Electricals" so nothing is real.
After demo, swap .env and run --clear to start fresh for the real client.
"""
import asyncio
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

# Make sure src is importable
sys.path.insert(0, ".")

from src.db import engine, AsyncSessionLocal, Base
from src.products.models import Supplier, Product
from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem
from src.sales.models import DailySale
from src.payments.models import Payment
from src.stock.models import StockMovement


# ── Demo data ─────────────────────────────────────────────────────────────────

SUPPLIERS = [
    {"name": "Ravi Electricals", "phone": "98765-43210"},
    {"name": "Sharma & Sons Wholesale", "phone": "98111-22333"},
    {"name": "City Electric Store", "phone": "80001-99887"},
]

PRODUCTS = [
    {"sku": "MCB-32A-SP", "name": "MCB 32A Single Pole",      "unit": "piece", "cost_price": 65,  "selling_price": 85,  "stock_qty": 120, "reorder_level": 20},
    {"sku": "MCB-16A-SP", "name": "MCB 16A Single Pole",      "unit": "piece", "cost_price": 55,  "selling_price": 72,  "stock_qty": 85,  "reorder_level": 20},
    {"sku": "MCB-63A-DP", "name": "MCB 63A Double Pole",      "unit": "piece", "cost_price": 180, "selling_price": 240, "stock_qty": 40,  "reorder_level": 10},
    {"sku": "RCCB-25A",   "name": "RCCB 25A 30mA",            "unit": "piece", "cost_price": 320, "selling_price": 420, "stock_qty": 25,  "reorder_level": 8},
    {"sku": "WIRE-2.5MM", "name": "Wire 2.5mm FRLS 90m",      "unit": "coil",  "cost_price": 520, "selling_price": 650, "stock_qty": 18,  "reorder_level": 5},
    {"sku": "WIRE-4MM",   "name": "Wire 4mm FRLS 90m",        "unit": "coil",  "cost_price": 780, "selling_price": 950, "stock_qty": 12,  "reorder_level": 4},
    {"sku": "WIRE-6MM",   "name": "Wire 6mm FRLS 90m",        "unit": "coil",  "cost_price": 1100,"selling_price": 1350,"stock_qty": 7,   "reorder_level": 3},
    {"sku": "SWITCH-6A",  "name": "Modular Switch 6A",        "unit": "piece", "cost_price": 28,  "selling_price": 38,  "stock_qty": 200, "reorder_level": 50},
    {"sku": "SOCKET-6A",  "name": "Modular Socket 6A",        "unit": "piece", "cost_price": 32,  "selling_price": 45,  "stock_qty": 180, "reorder_level": 50},
    {"sku": "DB-4WAY",    "name": "Distribution Box 4-way",   "unit": "piece", "cost_price": 220, "selling_price": 290, "stock_qty": 15,  "reorder_level": 5},
    {"sku": "DB-8WAY",    "name": "Distribution Box 8-way",   "unit": "piece", "cost_price": 380, "selling_price": 490, "stock_qty": 10,  "reorder_level": 3},
    {"sku": "LED-9W",     "name": "LED Bulb 9W",              "unit": "piece", "cost_price": 32,  "selling_price": 45,  "stock_qty": 300, "reorder_level": 60},
    {"sku": "LED-15W",    "name": "LED Bulb 15W",             "unit": "piece", "cost_price": 48,  "selling_price": 65,  "stock_qty": 220, "reorder_level": 50},
    {"sku": "COND-20MM",  "name": "Conduit Pipe 20mm 3m",     "unit": "piece", "cost_price": 38,  "selling_price": 52,  "stock_qty": 4,   "reorder_level": 20},  # low stock
    {"sku": "COND-25MM",  "name": "Conduit Pipe 25mm 3m",     "unit": "piece", "cost_price": 52,  "selling_price": 68,  "stock_qty": 6,   "reorder_level": 20},  # low stock
    {"sku": "FAN-CAP",    "name": "Fan Capacitor 2.5µF",      "unit": "piece", "cost_price": 22,  "selling_price": 35,  "stock_qty": 80,  "reorder_level": 20},
    {"sku": "TAPE-PVC",   "name": "PVC Insulation Tape",      "unit": "piece", "cost_price": 12,  "selling_price": 20,  "stock_qty": 150, "reorder_level": 40},
    {"sku": "EARTH-WIRE", "name": "Earthing Wire 4mm 90m",    "unit": "coil",  "cost_price": 680, "selling_price": 850, "stock_qty": 8,   "reorder_level": 3},
]

# Sales for the last 14 days
DAILY_SALES_TEMPLATES = [
    ("MCB 32A Single Pole",   (5, 20),  85),
    ("MCB 16A Single Pole",   (3, 15),  72),
    ("Wire 2.5mm FRLS 90m",   (1, 4),   650),
    ("Modular Switch 6A",     (10, 40), 38),
    ("Modular Socket 6A",     (8, 30),  45),
    ("LED Bulb 9W",           (10, 50), 45),
    ("LED Bulb 15W",          (5, 25),  65),
    ("PVC Insulation Tape",   (5, 20),  20),
    ("Fan Capacitor 2.5µF",   (2, 8),   35),
    ("RCCB 25A 30mA",         (1, 3),   420),
]


# ── Seeder ────────────────────────────────────────────────────────────────────

async def clear_all(db: AsyncSession) -> None:
    print("Clearing existing data...")
    for model in [StockMovement, Payment, DailySale, PurchaseInvoiceItem,
                  PurchaseInvoice, Product, Supplier]:
        await db.execute(delete(model))
    await db.commit()
    print("  Done.")


async def seed(db: AsyncSession) -> None:
    # Suppliers
    print("Creating suppliers...")
    supplier_objs = []
    for s in SUPPLIERS:
        obj = Supplier(**s)
        db.add(obj)
        supplier_objs.append(obj)
    await db.flush()

    # Products
    print("Creating products...")
    product_map: dict[str, Product] = {}
    for i, p in enumerate(PRODUCTS):
        obj = Product(**p, supplier_id=supplier_objs[i % len(supplier_objs)].id)
        db.add(obj)
        product_map[p["name"]] = obj
    await db.flush()

    # Purchase invoices (last 3 weeks)
    print("Creating purchase invoices...")
    invoice_data = [
        {
            "days_ago": 18,
            "supplier_idx": 0,
            "invoice_number": "RAVI-2024-001",
            "items": [
                ("MCB 32A Single Pole", 50, 65),
                ("MCB 16A Single Pole", 40, 55),
                ("RCCB 25A 30mA",       10, 320),
            ],
            "paid": True,
        },
        {
            "days_ago": 11,
            "supplier_idx": 1,
            "invoice_number": "SHARMA-2024-087",
            "items": [
                ("Wire 2.5mm FRLS 90m", 10, 520),
                ("Wire 4mm FRLS 90m",    5, 780),
                ("Earthing Wire 4mm 90m", 4, 680),
            ],
            "paid": True,
        },
        {
            "days_ago": 5,
            "supplier_idx": 0,
            "invoice_number": "RAVI-2024-002",
            "items": [
                ("LED Bulb 9W",          100, 32),
                ("LED Bulb 15W",          60, 48),
                ("Modular Switch 6A",     80, 28),
                ("Modular Socket 6A",     80, 32),
            ],
            "paid": False,
        },
        {
            "days_ago": 2,
            "supplier_idx": 2,
            "invoice_number": "CITY-2024-441",
            "items": [
                ("Distribution Box 4-way",  6, 220),
                ("Distribution Box 8-way",  4, 380),
                ("Fan Capacitor 2.5µF",    20, 22),
            ],
            "paid": False,
        },
    ]

    for inv_data in invoice_data:
        inv_date    = date.today() - timedelta(days=inv_data["days_ago"])
        total       = sum(qty * cost for _, qty, cost in inv_data["items"])
        paid_amount = Decimal(total) if inv_data["paid"] else Decimal(0)

        inv = PurchaseInvoice(
            invoice_number = inv_data["invoice_number"],
            supplier_id    = supplier_objs[inv_data["supplier_idx"]].id,
            invoice_date   = inv_date,
            total_amount   = Decimal(total),
            paid_amount    = paid_amount,
            status         = "paid" if inv_data["paid"] else "unpaid",
        )
        db.add(inv)
        await db.flush()

        for product_name, qty, unit_cost in inv_data["items"]:
            product = product_map.get(product_name)
            db.add(PurchaseInvoiceItem(
                purchase_invoice_id = inv.id,
                product_id          = product.id if product else None,
                product_name_raw    = product_name,
                qty                 = Decimal(qty),
                unit_cost           = Decimal(unit_cost),
            ))
            if product:
                db.add(StockMovement(
                    product_id     = product.id,
                    movement_type  = "purchase",
                    qty_change     = Decimal(qty),
                    reference_id   = inv.id,
                    reference_type = "purchase_invoice",
                ))

        if inv_data["paid"]:
            db.add(Payment(
                payment_date    = inv_date + timedelta(days=1),
                amount          = paid_amount,
                payment_mode    = random.choice(["bank_deposit", "gpay"]),
                direction       = "outflow",
                purchase_invoice_id = inv.id,
                transaction_ref = f"UTR{random.randint(100000000, 999999999)}",
            ))

    await db.flush()

    # Daily sales for last 14 days
    print("Creating daily sales...")
    for days_ago in range(14, 0, -1):
        sale_date = date.today() - timedelta(days=days_ago)
        # Skip Sundays (shop closed)
        if sale_date.weekday() == 6:
            continue

        # Pick 4–7 random products for this day
        day_items = random.sample(DAILY_SALES_TEMPLATES, k=random.randint(4, 7))
        for product_name, qty_range, price in day_items:
            qty     = random.randint(*qty_range)
            product = product_map.get(product_name)

            db.add(DailySale(
                sale_date        = sale_date,
                product_id       = product.id if product else None,
                product_name_raw = product_name,
                qty_sold         = Decimal(qty),
                selling_price    = Decimal(price),
                source           = "voice",
            ))
            if product:
                db.add(StockMovement(
                    product_id     = product.id,
                    movement_type  = "sale",
                    qty_change     = -Decimal(qty),
                    reference_type = "daily_sale",
                ))

        # Cash/GPay received
        day_revenue = sum(
            qty * price
            for _, (lo, hi), price in day_items
            for qty in [random.randint(lo, hi)]
        )
        db.add(Payment(
            payment_date = sale_date,
            amount       = Decimal(random.randint(int(day_revenue * 0.6), int(day_revenue * 0.9))),
            payment_mode = random.choice(["gpay", "cash", "upi"]),
            direction    = "inflow",
            note         = "Daily sales collection",
        ))

    await db.commit()
    print("✅ Demo data seeded successfully!")
    print()
    print("Summary:")
    print(f"  • {len(SUPPLIERS)} suppliers")
    print(f"  • {len(PRODUCTS)} products ({sum(1 for p in PRODUCTS if p['stock_qty'] <= p['reorder_level'])} low stock)")
    print(f"  • {len(invoice_data)} purchase invoices (2 paid, 2 unpaid)")
    print(f"  • 14 days of daily sales")
    print()
    print("Ready for demo! Start the bot and visit the dashboard.")


async def main():
    do_clear = "--clear" in sys.argv

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        if do_clear:
            await clear_all(db)
        await seed(db)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
