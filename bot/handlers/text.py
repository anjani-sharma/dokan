from datetime import date, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from services.nlp import extract_sales
from services.api_client import (
    create_sale, search_products, get_daily_report, get_outstanding,
    list_sales, update_sale, delete_sale,
)
from services.matcher import find_best_match

import httpx
from settings import settings


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>Ananta Shop Assistant</b>\n\n"
        "Send me:\n"
        "  📸 Invoice photo — to record a purchase\n"
        "  📸 Payment slip (caption: 'payment'/'gpay') — to record payment\n"
        "  🎤 Voice message — to record today's sales\n"
        "  💬 Text — to record sales or corrections\n\n"
        "Commands:\n"
        "  /report — today's summary\n"
        "  /weekly — this week's statement\n"
        "  /outstanding — unpaid invoices\n"
        "  /help — this message",
        parse_mode="HTML",
    )


async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await get_daily_report()
    except Exception as e:
        await update.message.reply_text(f"Could not fetch report: {e}")
        return

    lines = [
        f"<b>📊 Today's Report — {data['date']}</b>",
        f"Sales recorded: {data['sales_count']}",
        f"Total sales: <b>₹{data['total_sales']:,.2f}</b>",
        f"Payments received: ₹{data['received']:,.2f}",
        f"Payments made: ₹{data['paid_out']:,.2f}",
    ]
    if data.get("sales"):
        lines.append("\nItems sold:")
        for s in data["sales"][:8]:
            lines.append(f"  • {s['product_name']} × {s['qty_sold']} — ₹{s['line_total']:,.2f}")
        if len(data["sales"]) > 8:
            lines.append(f"  ... and {len(data['sales']) - 8} more")
    if data["low_stock_count"]:
        lines.append(f"\n⚠️ Low stock: {data['low_stock_count']} item(s) need restocking")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def handle_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and send this week's formatted report on demand."""
    await update.message.reply_text("Generating weekly report...")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{settings.backend_url}/reports/preview/weekly")
            r.raise_for_status()
            text = r.json()["text"]
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Could not generate weekly report: {e}")


async def handle_outstanding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await get_outstanding()
    except Exception as e:
        await update.message.reply_text(f"Could not fetch outstanding: {e}")
        return

    invoices = data.get("invoices", [])
    if not invoices:
        await update.message.reply_text("✅ No outstanding payables.")
        return

    lines = [f"<b>💸 Outstanding Payables — ₹{data['total_outstanding']:,.2f}</b>\n"]
    for inv in invoices[:10]:
        lines.append(
            f"  • #{inv['invoice_number']} | {inv['invoice_date']} "
            f"| ₹{inv['outstanding']:,.2f} ({inv['status']})"
        )
    if len(invoices) > 10:
        lines.append(f"  ... and {len(invoices) - 10} more")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    # Keyword shortcuts
    if text.lower() in ("report", "today", "summary", "aaj"):
        await handle_report(update, context)
        return
    if text.lower() in ("weekly", "week", "hafte", "is hafte"):
        await handle_weekly(update, context)
        return
    if text.lower() in ("outstanding", "pending", "baaki", "udhar"):
        await handle_outstanding(update, context)
        return

    try:
        parsed = extract_sales(text)
    except Exception as e:
        await update.message.reply_text(f"Could not understand: {e}")
        return

    intent = parsed.get("intent", "unknown")
    items = parsed.get("items", [])
    date_hint = parsed.get("date_hint")
    sale_date = (date.today() - timedelta(days=1)).isoformat() \
        if date_hint == "yesterday" else date.today().isoformat()

    if intent == "record_sale" and items:
        recorded = []
        for item in items:
            name = item.get("product_name", "")
            qty = item.get("qty")
            selling_price = item.get("selling_price")
            if not name or not qty:
                continue
            matches = await search_products(name)
            product_id = matches[0]["id"] if matches else None
            if selling_price is None and matches:
                selling_price = float(matches[0]["selling_price"])
            selling_price = selling_price or 0.0
            try:
                await create_sale({
                    "sale_date": sale_date,
                    "product_id": product_id,
                    "product_name_raw": name,
                    "qty_sold": qty,
                    "selling_price": selling_price,
                    "source": "text",
                    "raw_input": text,
                })
                recorded.append(f"  • {name} × {qty}")
            except Exception:
                pass
        reply = ("<b>Recorded:</b>\n" + "\n".join(recorded)) if recorded \
            else "Nothing recorded. Try: <i>sold 5 MCB and 2 wire coils</i>"
        await update.message.reply_text(reply, parse_mode="HTML")

    elif intent == "edit_sale" and items:
        existing = await list_sales(sale_date)
        updated = []
        for item in items:
            name = item.get("product_name", "")
            new_qty = item.get("qty")
            match = find_best_match(
                name,
                [{"id": s["id"], "name": s.get("product_name_raw") or ""} for s in existing],
                threshold=0.4,
            )
            if match and new_qty:
                await update_sale(match["id"], {"qty_sold": new_qty})
                updated.append(f"  • {name} → {new_qty}")
        reply = ("<b>Updated:</b>\n" + "\n".join(updated)) if updated \
            else "Could not find matching sale to edit."
        await update.message.reply_text(reply, parse_mode="HTML")

    elif intent == "delete_sale" and items:
        existing = await list_sales(sale_date)
        removed = []
        for item in items:
            name = item.get("product_name", "")
            match = find_best_match(
                name,
                [{"id": s["id"], "name": s.get("product_name_raw") or ""} for s in existing],
                threshold=0.4,
            )
            if match:
                await delete_sale(match["id"])
                removed.append(f"  • {name}")
        reply = ("<b>Removed:</b>\n" + "\n".join(removed)) if removed \
            else "Could not find matching sale to remove."
        await update.message.reply_text(reply, parse_mode="HTML")

    elif intent == "query":
        await handle_report(update, context)

    else:
        await update.message.reply_text(
            "I didn't understand that. Try:\n"
            "<i>sold 10 MCB 32A and 3 wire coils</i>",
            parse_mode="HTML",
        )
