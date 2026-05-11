from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.customers.models import Customer
from src.customers.service import summarise_customer
from src.dependencies import get_db
from src.invoices.models import PurchaseInvoice
from src.payments.models import Payment
from src.products.models import Product, Supplier
from src.products.supplier_service import summarise_supplier
from src.sales.models import DailySale
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


# ── Analytics overview (used by the dashboard home page) ─────────────────────

@router.get("/analytics")
async def analytics(db: AsyncSession = Depends(get_db)):
    """One-shot aggregate for the analytics dashboard.

    Returns sales trend, top products, low stock, customer + supplier
    outstanding (top 10 each), stock-on-hand value, and KPIs for
    today / week / month. Designed so the dashboard makes ONE request, not six.
    """
    today = date.today()
    last_30 = today - timedelta(days=29)
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    # ── Sales trend (30 days, one row per day, zero-filled) ─────────────────
    trend_rows = (await db.execute(
        select(
            DailySale.sale_date,
            func.coalesce(func.sum(DailySale.qty_sold * DailySale.selling_price), 0),
        )
        .where(DailySale.sale_date >= last_30)
        .group_by(DailySale.sale_date)
    )).all()
    trend_by_date = {r[0]: float(r[1]) for r in trend_rows}
    sales_trend_30d = []
    for i in range(30):
        d = last_30 + timedelta(days=i)
        sales_trend_30d.append({"date": d.isoformat(), "total": trend_by_date.get(d, 0.0)})

    # ── Top products (30 days, by qty + revenue) ────────────────────────────
    top_rows = (await db.execute(
        select(
            DailySale.product_name_raw,
            func.coalesce(func.sum(DailySale.qty_sold), 0),
            func.coalesce(func.sum(DailySale.qty_sold * DailySale.selling_price), 0),
        )
        .where(DailySale.sale_date >= last_30, DailySale.product_name_raw.is_not(None))
        .group_by(DailySale.product_name_raw)
        .order_by(func.sum(DailySale.qty_sold * DailySale.selling_price).desc())
        .limit(10)
    )).all()
    sales_by_product_30d = [
        {"name": r[0], "qty": float(r[1]), "revenue": float(r[2])} for r in top_rows
    ]

    # ── Low stock list ──────────────────────────────────────────────────────
    low_stock_res = await db.execute(
        select(Product).where(
            Product.is_active.is_(True),
            Product.reorder_level > 0,
            Product.stock_qty <= Product.reorder_level,
        ).order_by(Product.name)
    )
    low_stock = [
        {
            "id": p.id,
            "name": p.name,
            "stock_qty": float(p.stock_qty),
            "reorder_level": float(p.reorder_level),
            "unit": p.unit,
        }
        for p in low_stock_res.scalars().all()
    ]

    # ── Stock value on hand (cost basis) ────────────────────────────────────
    stock_value_row = (await db.execute(
        select(func.coalesce(func.sum(Product.stock_qty * Product.cost_price), 0))
        .where(Product.is_active.is_(True))
    )).scalar()
    stock_value_on_hand = float(stock_value_row or 0)

    # ── Customer outstanding (top 10) ───────────────────────────────────────
    customers_outstanding = []
    customer_res = await db.execute(select(Customer))
    for c in customer_res.scalars().all():
        summary = await summarise_customer(db, c)
        if summary.balance > 0:
            customers_outstanding.append({
                "id": summary.id,
                "name": summary.name,
                "phone": summary.phone,
                "balance": float(summary.balance),
                "last_activity": summary.last_activity.isoformat() if summary.last_activity else None,
            })
    customers_outstanding.sort(key=lambda x: x["balance"], reverse=True)
    customers_outstanding = customers_outstanding[:10]

    # ── Supplier outstanding (top 10) ───────────────────────────────────────
    suppliers_outstanding = []
    supplier_res = await db.execute(select(Supplier))
    for s in supplier_res.scalars().all():
        summary = await summarise_supplier(db, s)
        if summary.balance > 0:
            suppliers_outstanding.append({
                "id": summary.id,
                "name": summary.name,
                "phone": summary.phone,
                "balance": float(summary.balance),
                "last_activity": summary.last_activity.isoformat() if summary.last_activity else None,
            })
    suppliers_outstanding.sort(key=lambda x: x["balance"], reverse=True)
    suppliers_outstanding = suppliers_outstanding[:10]

    # ── KPIs (today / week / month) ─────────────────────────────────────────
    async def _kpi_window(start: date, end: date) -> dict:
        sales = float((await db.execute(
            select(func.coalesce(func.sum(DailySale.qty_sold * DailySale.selling_price), 0))
            .where(DailySale.sale_date >= start, DailySale.sale_date <= end)
        )).scalar() or 0)
        received = float((await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.direction == "inflow",
                   Payment.payment_date >= start, Payment.payment_date <= end)
        )).scalar() or 0)
        paid_out = float((await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.direction == "outflow",
                   Payment.payment_date >= start, Payment.payment_date <= end)
        )).scalar() or 0)
        return {"sales": sales, "received": received, "paid_out": paid_out, "net": received - paid_out}

    kpis = {
        "today": await _kpi_window(today, today),
        "week":  await _kpi_window(week_start, today),
        "month": await _kpi_window(month_start, today),
    }

    return {
        "sales_trend_30d":       sales_trend_30d,
        "sales_by_product_30d":  sales_by_product_30d,
        "low_stock":             low_stock,
        "stock_value_on_hand":   stock_value_on_hand,
        "customers_outstanding": customers_outstanding,
        "suppliers_outstanding": suppliers_outstanding,
        "kpis":                  kpis,
    }


# ── All-time shop totals (for dashboard Overview section) ─────────────────────

@router.get("/totals")
async def shop_totals(db: AsyncSession = Depends(get_db)):
    """All-time aggregates: total sales, invoices, payments, outstanding."""

    total_sales_result = await db.execute(
        select(func.coalesce(func.sum(DailySale.line_total), 0))
    )
    total_sales = float(total_sales_result.scalar())

    sales_count_result = await db.execute(select(func.count(DailySale.id)))
    sales_count = sales_count_result.scalar() or 0

    invoices_result = await db.execute(
        select(
            func.count(PurchaseInvoice.id),
            func.coalesce(func.sum(PurchaseInvoice.total_amount), 0),
            func.coalesce(func.sum(PurchaseInvoice.paid_amount), 0),
        )
    )
    inv_row = invoices_result.one()
    invoice_count      = inv_row[0] or 0
    invoice_total      = float(inv_row[1])
    invoice_paid       = float(inv_row[2])
    total_outstanding  = invoice_total - invoice_paid

    received_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.direction == "inflow")
    )
    total_received = float(received_result.scalar())

    paid_out_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.direction == "outflow")
    )
    total_paid_out = float(paid_out_result.scalar())

    return {
        "total_sales":       total_sales,
        "sales_count":       sales_count,
        "invoice_count":     invoice_count,
        "invoice_total":     invoice_total,
        "invoice_paid":      invoice_paid,
        "total_outstanding": total_outstanding,
        "total_received":    total_received,
        "total_paid_out":    total_paid_out,
        "net_cash":          total_received - total_paid_out,
    }
