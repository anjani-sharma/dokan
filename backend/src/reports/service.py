"""
Report generation and Telegram delivery.

Daily report  — sent every day at 8 PM IST via APScheduler.
Weekly report — sent every Monday 9 AM IST via APScheduler.
Both can also be triggered manually via the /reports/trigger/* API endpoints.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from src.db import AsyncSessionLocal
from src.invoices.models import PurchaseInvoice
from src.payments.models import Payment
from src.products.models import Product
from src.sales.models import DailySale


# ── Data builders ────────────────────────────────────────────────────────────

async def get_daily_summary(target_date: date) -> dict:
    async with AsyncSessionLocal() as db:
        sales = (await db.execute(
            select(DailySale).where(DailySale.sale_date == target_date)
        )).scalars().all()

        payments = (await db.execute(
            select(Payment).where(Payment.payment_date == target_date)
        )).scalars().all()

        low_stock = (await db.execute(
            select(Product).where(
                Product.is_active == True,       # noqa: E712
                Product.reorder_level > 0,
                Product.stock_qty <= Product.reorder_level,
            ).order_by(Product.name)
        )).scalars().all()

    total_sales = sum(s.line_total for s in sales)
    received    = sum(p.amount for p in payments if p.direction == "inflow")
    paid_out    = sum(p.amount for p in payments if p.direction == "outflow")

    return {
        "date": target_date,
        "sales": sales,
        "total_sales": total_sales,
        "received": received,
        "paid_out": paid_out,
        "payments": payments,
        "low_stock_products": low_stock,
    }


async def get_weekly_summary(week_end: date) -> dict:
    week_start = week_end - timedelta(days=6)

    async with AsyncSessionLocal() as db:
        sales = (await db.execute(
            select(DailySale).where(
                DailySale.sale_date >= week_start,
                DailySale.sale_date <= week_end,
            )
        )).scalars().all()

        payments = (await db.execute(
            select(Payment).where(
                Payment.payment_date >= week_start,
                Payment.payment_date <= week_end,
            )
        )).scalars().all()

        outstanding_invoices = (await db.execute(
            select(PurchaseInvoice).where(
                PurchaseInvoice.status.in_(["unpaid", "partial"])
            ).order_by(PurchaseInvoice.invoice_date)
        )).scalars().all()

    total_sales = sum(s.line_total for s in sales)
    received    = sum(p.amount for p in payments if p.direction == "inflow")
    paid_out    = sum(p.amount for p in payments if p.direction == "outflow")

    # Aggregate qty sold per product name for top-5 ranking
    qty_by_product: dict[str, Decimal] = defaultdict(Decimal)
    revenue_by_product: dict[str, Decimal] = defaultdict(Decimal)
    for s in sales:
        key = s.product_name_raw or f"Product #{s.product_id}"
        qty_by_product[key] += s.qty_sold
        revenue_by_product[key] += s.line_total

    top_by_qty = sorted(qty_by_product.items(), key=lambda x: x[1], reverse=True)[:5]
    top_by_revenue = sorted(revenue_by_product.items(), key=lambda x: x[1], reverse=True)[:5]

    total_outstanding = sum(
        inv.total_amount - inv.paid_amount for inv in outstanding_invoices
    )

    return {
        "week_start": week_start,
        "week_end": week_end,
        "sales": sales,
        "total_sales": total_sales,
        "received": received,
        "paid_out": paid_out,
        "sales_count": len(sales),
        "top_by_qty": top_by_qty,
        "top_by_revenue": top_by_revenue,
        "outstanding_invoices": outstanding_invoices,
        "total_outstanding": total_outstanding,
    }


# ── Formatters ───────────────────────────────────────────────────────────────

def _fmt(amount: Decimal | float) -> str:
    return f"₹{float(amount):,.2f}"


def format_daily_report(summary: dict) -> str:
    d = summary["date"].strftime("%d %b %Y")
    lines = [f"<b>📊 Daily Report — {d}</b>\n"]

    sales = summary["sales"]
    if sales:
        lines.append("<b>Items Sold Today:</b>")
        for s in sales:
            name = s.product_name_raw or f"Product #{s.product_id}"
            lines.append(f"  • {name} × {s.qty_sold} — {_fmt(s.line_total)}")
    else:
        lines.append("No sales recorded today.")

    lines.append("")
    lines.append(f"Total Sales: <b>{_fmt(summary['total_sales'])}</b>")

    # Payment breakdown by mode
    payments = summary.get("payments", [])
    inflows  = [p for p in payments if p.direction == "inflow"]
    outflows = [p for p in payments if p.direction == "outflow"]

    if inflows:
        lines.append("\n<b>Payments Received:</b>")
        for p in inflows:
            ref = f" ({p.transaction_ref})" if p.transaction_ref else ""
            lines.append(f"  • {_fmt(p.amount)} via {p.payment_mode}{ref}")

    if outflows:
        lines.append("\n<b>Payments Made:</b>")
        for p in outflows:
            ref = f" ({p.transaction_ref})" if p.transaction_ref else ""
            lines.append(f"  • {_fmt(p.amount)} via {p.payment_mode}{ref}")

    if not inflows and not outflows:
        lines.append("No payments recorded today.")

    low_stock = summary["low_stock_products"]
    if low_stock:
        lines.append("\n<b>⚠️ Low Stock Alert:</b>")
        for p in low_stock:
            lines.append(f"  • {p.name} — only {p.stock_qty} {p.unit or ''} left")

    return "\n".join(lines)


def format_weekly_report(summary: dict) -> str:
    ws = summary["week_start"].strftime("%d %b")
    we = summary["week_end"].strftime("%d %b %Y")
    lines = [f"<b>📅 Weekly Statement — {ws} to {we}</b>\n"]

    lines.append(f"Total Sales:           <b>{_fmt(summary['total_sales'])}</b>")
    lines.append(f"Payments Received:     {_fmt(summary['received'])}")
    lines.append(f"Payments Made:         {_fmt(summary['paid_out'])}")
    net = summary["received"] - summary["paid_out"]
    lines.append(f"Net Cash Flow:         {_fmt(net)}")
    lines.append(f"Total Outstanding:     <b>{_fmt(summary['total_outstanding'])}</b>")

    top_qty = summary["top_by_qty"]
    if top_qty:
        lines.append("\n<b>Top 5 Items by Quantity Sold:</b>")
        for i, (name, qty) in enumerate(top_qty, 1):
            lines.append(f"  {i}. {name} — {qty} units")

    top_rev = summary["top_by_revenue"]
    if top_rev:
        lines.append("\n<b>Top 5 Items by Revenue:</b>")
        for i, (name, rev) in enumerate(top_rev, 1):
            lines.append(f"  {i}. {name} — {_fmt(rev)}")

    outstanding = summary["outstanding_invoices"]
    if outstanding:
        lines.append(f"\n<b>Outstanding Invoices ({len(outstanding)}):</b>")
        for inv in outstanding[:5]:
            due = inv.total_amount - inv.paid_amount
            lines.append(f"  • #{inv.invoice_number} — {_fmt(due)} pending ({inv.status})")
        if len(outstanding) > 5:
            lines.append(f"  ... and {len(outstanding) - 5} more")

    return "\n".join(lines)


# ── Telegram sender ──────────────────────────────────────────────────────────

async def _send_telegram(text: str) -> None:
    from src.settings import settings
    if not settings.telegram_bot_token or not settings.shop_chat_id:
        return
    import httpx
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={
                "chat_id": settings.shop_chat_id,
                "text": text,
                "parse_mode": "HTML",
            },
        )


# ── Scheduled jobs (called by APScheduler) ───────────────────────────────────

async def send_daily_report() -> None:
    summary = await get_daily_summary(date.today())
    text = format_daily_report(summary)
    await _send_telegram(text)


async def send_weekly_report() -> None:
    summary = await get_weekly_summary(date.today())
    text = format_weekly_report(summary)
    await _send_telegram(text)
