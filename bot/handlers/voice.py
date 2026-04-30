import os
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.transcriber import transcribe
from services.nlp import extract_sales
from services.api_client import (
    create_sale, search_products, list_sales, update_sale, delete_sale,
)
from services.matcher import find_best_match
from settings import settings

# Pending sales waiting for price confirmation: {key: [sale_dicts]}
_PENDING_SALES: dict[str, list[dict]] = {}


def _resolve_date(date_hint: str | None) -> str:
    if date_hint == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    return date.today().isoformat()


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🎤 Voice received, transcribing...")

    # 1. Download OGG from Telegram
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    os.makedirs(settings.images_dir, exist_ok=True)
    local_path = os.path.join(settings.images_dir, f"voice_{voice.file_unique_id}.ogg")
    await tg_file.download_to_drive(local_path)

    # 2. Transcribe
    try:
        transcript = transcribe(local_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Could not transcribe: {e}")
        return
    finally:
        _safe_remove(local_path)

    await update.message.reply_text(f"Heard: <i>{transcript}</i>", parse_mode="HTML")

    # 3. Extract intent
    try:
        parsed = extract_sales(transcript)
    except Exception as e:
        await update.message.reply_text(f"❌ Could not understand: {e}")
        return

    intent    = parsed.get("intent", "unknown")
    items     = parsed.get("items", [])
    sale_date = _resolve_date(parsed.get("date_hint"))

    if intent == "record_sale":
        await _record_sales(update, context, items, transcript, sale_date)
    elif intent == "edit_sale":
        await _edit_sales(update, items, transcript, sale_date)
    elif intent == "delete_sale":
        await _delete_sales(update, items, sale_date)
    elif intent == "query":
        from handlers.text import handle_report
        await handle_report(update, context)
    else:
        await update.message.reply_text(
            "I couldn't identify what to record.\n"
            "Try: <i>Sold 10 MCB at ₹85 and 3 wire coils at ₹650</i>",
            parse_mode="HTML",
        )


# ── Record sales ──────────────────────────────────────────────────────────────

async def _record_sales(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    items: list[dict],
    transcript: str,
    sale_date: str,
) -> None:
    if not items:
        await update.message.reply_text("No items found. Please try again.")
        return

    # Enrich each item with catalog data
    enriched = []
    for item in items:
        name  = item.get("product_name", "")
        qty   = item.get("qty")
        price = item.get("selling_price")
        if not name or not qty:
            continue

        matches    = await search_products(name)
        product_id = matches[0]["id"] if matches else None
        catalog_price = float(matches[0]["selling_price"]) if matches else None

        # Use spoken price first, fall back to catalog price
        selling_price = price or catalog_price

        enriched.append({
            "product_name":  name,
            "qty":           qty,
            "unit":          item.get("unit"),
            "product_id":    product_id,
            "selling_price": selling_price,
            "sale_date":     sale_date,
            "raw_input":     transcript,
        })

    if not enriched:
        await update.message.reply_text("No valid items found.")
        return

    # Check if any prices are missing
    missing_price = [e for e in enriched if not e["selling_price"]]

    if missing_price:
        # Store pending and ask for prices
        key = f"voice_{update.message.message_id}"
        _PENDING_SALES[key] = enriched
        context.user_data["pending_sale_key"] = key

        names = ", ".join(e["product_name"] for e in missing_price)
        await update.message.reply_text(
            f"What is the selling price for: <b>{names}</b>?\n\n"
            "Reply with the price(s), e.g.: <i>MCB ₹85, wire ₹650</i>\n"
            "Or type <b>skip</b> to save with ₹0 price.",
            parse_mode="HTML",
        )
        return

    # All prices present — save immediately
    await _save_sales(update, enriched)


async def handle_voice_price_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from the smart text dispatcher when user is supplying missing prices.
    Returns True if it handled the message, False otherwise.
    """
    key = context.user_data.get("pending_sale_key")
    if not key or key not in _PENDING_SALES:
        return False

    text    = update.message.text.strip()
    pending = _PENDING_SALES[key]

    if text.lower() != "skip":
        # Parse "MCB 85, wire 650" or "₹85 for MCB" etc.
        _apply_price_corrections(pending, text)

    context.user_data.pop("pending_sale_key", None)
    _PENDING_SALES.pop(key, None)
    await _save_sales(update, pending)
    return True


async def _save_sales(update: Update, items: list[dict]) -> None:
    recorded, skipped = [], []

    for item in items:
        selling_price = item.get("selling_price") or 0.0
        try:
            await create_sale({
                "sale_date":       item["sale_date"],
                "product_id":      item.get("product_id"),
                "product_name_raw": item["product_name"],
                "qty_sold":        item["qty"],
                "selling_price":   selling_price,
                "source":          "voice",
                "raw_input":       item.get("raw_input", ""),
            })
            unit      = item.get("unit") or ""
            price_str = f" @ ₹{selling_price:,.0f}" if selling_price else " (price not set)"
            recorded.append(f"  • {item['product_name']} × {item['qty']} {unit}{price_str}")
        except Exception as e:
            skipped.append(f"  • {item['product_name']} ({e})")

    date_label = "Today" if items[0]["sale_date"] == date.today().isoformat() else items[0]["sale_date"]
    lines = [f"✅ <b>Sales Recorded ({date_label}):</b>"]
    lines += recorded or ["  None"]
    if skipped:
        lines += ["\n⚠️ <b>Could not save:</b>"] + skipped

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── Edit ──────────────────────────────────────────────────────────────────────

async def _edit_sales(
    update: Update, items: list[dict], transcript: str, sale_date: str
) -> None:
    if not items:
        await update.message.reply_text(
            "I understood this as an <b>edit</b> but couldn't identify which item.\n"
            "Try: <i>change MCB to 8 pieces</i>",
            parse_mode="HTML",
        )
        return

    existing     = await list_sales(sale_date)
    updated, not_found = [], []

    for item in items:
        name    = item.get("product_name", "")
        new_qty = item.get("qty")
        match   = find_best_match(
            name,
            [{"id": s["id"], "name": s.get("product_name_raw") or ""} for s in existing],
            threshold=0.4,
        )
        if not match:
            not_found.append(name)
            continue
        payload = {}
        if new_qty is not None:
            payload["qty_sold"] = new_qty
        if item.get("selling_price"):
            payload["selling_price"] = item["selling_price"]
        if payload:
            await update_sale(match["id"], payload)
            updated.append(f"  • {name} → {new_qty or 'price updated'}")

    lines = [f"✅ <b>Updated ({sale_date}):</b>"]
    lines += updated or ["  Nothing updated"]
    if not_found:
        lines += ["\n⚠️ Not found in sales:"] + [f"  • {n}" for n in not_found]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── Delete ────────────────────────────────────────────────────────────────────

async def _delete_sales(update: Update, items: list[dict], sale_date: str) -> None:
    if not items:
        await update.message.reply_text(
            "I understood this as a <b>delete</b> but couldn't identify which item.\n"
            "Try: <i>remove MCB from today</i>",
            parse_mode="HTML",
        )
        return

    existing      = await list_sales(sale_date)
    deleted, not_found = [], []

    for item in items:
        name  = item.get("product_name", "")
        match = find_best_match(
            name,
            [{"id": s["id"], "name": s.get("product_name_raw") or ""} for s in existing],
            threshold=0.4,
        )
        if not match:
            not_found.append(name)
            continue
        await delete_sale(match["id"])
        deleted.append(f"  • {name}")

    lines = [f"✅ <b>Removed ({sale_date}):</b>"]
    lines += deleted or ["  Nothing removed"]
    if not_found:
        lines += ["\n⚠️ Not found:"] + [f"  • {n}" for n in not_found]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── Price parser ──────────────────────────────────────────────────────────────

def _apply_price_corrections(items: list[dict], text: str) -> None:
    """
    Parse 'MCB 85, wire 650' or '85 for MCB' style price replies.
    Updates items in-place.
    """
    import re
    # Extract number → product name pairs
    # Pattern: word(s) followed by a number, OR number followed by "for" word(s)
    pairs = re.findall(r"([a-zA-Z][a-zA-Z\s\d\.]*?)\s*[:\-@₹]?\s*(\d+(?:\.\d+)?)", text)
    pairs += [(m[1], m[0]) for m in re.findall(r"(\d+(?:\.\d+)?)\s+(?:for|ke liye)?\s+([a-zA-Z][a-zA-Z\s\d\.]*)", text)]

    for raw_name, raw_price in pairs:
        try:
            price = float(raw_price.replace(",", ""))
        except ValueError:
            continue
        match = find_best_match(
            raw_name.strip(),
            [{"id": i, "name": item["product_name"]} for i, item in enumerate(items)],
            threshold=0.3,
        )
        if match:
            items[match["id"]]["selling_price"] = price


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
