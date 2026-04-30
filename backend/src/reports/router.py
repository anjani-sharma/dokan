from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
from src.invoices.models import PurchaseInvoice
from src.reports.service import (
    get_daily_summary, get_weekly_summary,
    format_daily_report, format_weekly_report,
    send_daily_report, send_weekly_report,
)

router = APIRouter()


# ── Data endpoints (used by dashboard) ───────────────────────────────────────

@router.get("/daily")
async def daily_report(report_date: date | None = None):
    target = report_date or date.today()
    summary = await get_daily_summary(target)
    return {
        "date": str(summary["date"]),
        "total_sales": float(summary["total_sales"]),
        "received": float(summary["received"]),
        "paid_out": float(summary["paid_out"]),
        "sales_count": len(summary["sales"]),
        "low_stock_count": len(summary["low_stock_products"]),
        "sales": [
            {
                "id": s.id,
                "product_name": s.product_name_raw or f"Product #{s.product_id}",
                "qty_sold": float(s.qty_sold),
                "selling_price": float(s.selling_price),
                "line_total": float(s.line_total),
                "source": s.source,
            }
            for s in summary["sales"]
        ],
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount),
                "payment_mode": p.payment_mode,
                "direction": p.direction,
                "transaction_ref": p.transaction_ref,
            }
            for p in summary["payments"]
        ],
        "low_stock": [
            {
                "id": p.id,
                "name": p.name,
                "stock_qty": float(p.stock_qty),
                "reorder_level": float(p.reorder_level),
                "unit": p.unit,
            }
            for p in summary["low_stock_products"]
        ],
    }


@router.get("/weekly")
async def weekly_report(week_end: date | None = None):
    target = week_end or date.today()
    summary = await get_weekly_summary(target)
    return {
        "week_start": str(summary["week_start"]),
        "week_end": str(summary["week_end"]),
        "total_sales": float(summary["total_sales"]),
        "received": float(summary["received"]),
        "paid_out": float(summary["paid_out"]),
        "sales_count": summary["sales_count"],
        "total_outstanding": float(summary["total_outstanding"]),
        "top_by_qty": [
            {"name": name, "qty": float(qty)}
            for name, qty in summary["top_by_qty"]
        ],
        "top_by_revenue": [
            {"name": name, "revenue": float(rev)}
            for name, rev in summary["top_by_revenue"]
        ],
    }


@router.get("/outstanding")
async def outstanding_payables(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PurchaseInvoice)
        .where(PurchaseInvoice.status.in_(["unpaid", "partial"]))
        .order_by(PurchaseInvoice.invoice_date)
    )
    invoices = result.scalars().all()
    rows = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "supplier_id": inv.supplier_id,
            "invoice_date": str(inv.invoice_date),
            "total_amount": float(inv.total_amount),
            "paid_amount": float(inv.paid_amount),
            "outstanding": float(inv.total_amount - inv.paid_amount),
            "status": inv.status,
        }
        for inv in invoices
    ]
    return {
        "total_outstanding": sum(r["outstanding"] for r in rows),
        "invoices": rows,
    }


# ── Manual trigger endpoints ──────────────────────────────────────────────────

@router.post("/trigger/daily")
async def trigger_daily_report(report_date: date | None = None):
    """Send the daily report to Telegram immediately (optionally for a past date)."""
    if report_date:
        from src.reports.service import get_daily_summary, format_daily_report, _send_telegram
        summary = await get_daily_summary(report_date)
        text = format_daily_report(summary)
        await _send_telegram(text)
    else:
        await send_daily_report()
    return {"status": "sent"}


@router.post("/trigger/weekly")
async def trigger_weekly_report(week_end: date | None = None):
    """Send the weekly report to Telegram immediately."""
    if week_end:
        from src.reports.service import get_weekly_summary, format_weekly_report, _send_telegram
        summary = await get_weekly_summary(week_end)
        text = format_weekly_report(summary)
        await _send_telegram(text)
    else:
        await send_weekly_report()
    return {"status": "sent"}


@router.get("/preview/daily")
async def preview_daily_report(report_date: date | None = None):
    """Return the formatted daily report text without sending it."""
    target = report_date or date.today()
    summary = await get_daily_summary(target)
    return {"text": format_daily_report(summary)}


@router.get("/preview/weekly")
async def preview_weekly_report(week_end: date | None = None):
    """Return the formatted weekly report text without sending it."""
    target = week_end or date.today()
    summary = await get_weekly_summary(target)
    return {"text": format_weekly_report(summary)}
