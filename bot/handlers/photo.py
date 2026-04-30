"""
Photo handler with auto-detection and inline confirmation.

Flow:
  1. User sends any photo (no caption needed)
  2. Claude Vision auto-detects invoice vs payment slip
  3. Bot shows a formatted summary + 3 inline buttons: ✅ Save  ✏️ Edit  ❌ Cancel
  4. On ✅ Save → data POSTed to backend
  5. On ✏️ Edit → bot asks user to type a correction
  6. On ❌ Cancel → discarded
"""
import json
import os
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from services.ocr import ocr_document
from services.api_client import upsert_supplier, create_invoice, create_payment
from services.storage import upload_image
from settings import settings

# pending confirmations: {callback_data_prefix: ocr_result_dict}
_PENDING: dict[str, dict] = {}


# ── Incoming photo ────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📷 Photo received, reading document...")

    # Download highest-resolution photo
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    os.makedirs(settings.images_dir, exist_ok=True)
    local_path = os.path.join(settings.images_dir, f"photo_{photo.file_unique_id}.jpg")
    await tg_file.download_to_drive(local_path)

    try:
        data = ocr_document(local_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Could not read the document: {e}")
        _safe_remove(local_path)
        return

    # Upload to R2 (or keep local path) — stored with the invoice/payment record
    prefix = "payments" if data.get("type") == "payment_slip" else "invoices"
    data["_stored_url"] = upload_image(local_path, prefix=prefix)

    doc_type   = data.get("type", "unknown")
    confidence = data.get("confidence", "low")

    if doc_type == "unknown":
        await update.message.reply_text(
            "🤔 I couldn't identify this document.\n"
            f"Reason: {data.get('note', 'unclear image')}\n\n"
            "Please resend with a caption: <b>invoice</b> or <b>payment</b>",
            parse_mode="HTML",
        )
        _safe_remove(local_path)
        return

    # Store OCR result for confirmation callback
    key = photo.file_unique_id
    _PENDING[key] = data
    _PENDING[key]["_local_path"] = local_path  # keep file until confirmed/cancelled

    # Build preview text
    preview = _format_preview(data)
    conf_note = "" if confidence == "high" else f"\n\n⚠️ Confidence: <b>{confidence}</b> — please verify."

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Save",   callback_data=f"save:{key}"),
            InlineKeyboardButton("✏️ Edit",   callback_data=f"edit:{key}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{key}"),
        ]
    ])

    await update.message.reply_text(
        preview + conf_note,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ── Callback handler (button taps) ────────────────────────────────────────────

async def handle_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, key = query.data.split(":", 1)
    data = _PENDING.get(key)

    if not data:
        await query.edit_message_text("⏰ This confirmation has expired. Please resend the photo.")
        return

    if action == "cancel":
        _cleanup(key)
        await query.edit_message_text("❌ Cancelled. Nothing was saved.")
        return

    if action == "edit":
        await query.edit_message_text(
            "✏️ Please type your correction, e.g.:\n"
            "<i>supplier: Ravi Electricals, total: 4500, invoice: INV-099</i>\n\n"
            "Or type <b>cancel</b> to discard.",
            parse_mode="HTML",
        )
        # Store key in user_data so the text handler can pick it up
        context.user_data["editing_photo_key"] = key
        return

    if action == "save":
        await _save_document(query, data, key)


async def handle_photo_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Called from the text handler when the user is correcting an OCR result.
    Returns True if it handled the message, False otherwise.
    """
    key = context.user_data.get("editing_photo_key")
    if not key or key not in _PENDING:
        return False

    text = update.message.text.strip()
    if text.lower() == "cancel":
        _cleanup(key)
        context.user_data.pop("editing_photo_key", None)
        await update.message.reply_text("❌ Cancelled.")
        return True

    # Apply plain-text overrides onto the stored OCR data
    data = _PENDING[key]
    _apply_text_corrections(data, text)

    preview = _format_preview(data)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Save",   callback_data=f"save:{key}"),
            InlineKeyboardButton("✏️ Edit again", callback_data=f"edit:{key}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{key}"),
        ]
    ])
    context.user_data.pop("editing_photo_key", None)
    await update.message.reply_text(
        f"Updated preview:\n\n{preview}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return True


# ── Save logic ────────────────────────────────────────────────────────────────

async def _save_document(query, data: dict, key: str) -> None:
    doc_type = data.get("type")

    try:
        if doc_type == "invoice":
            result = await _save_invoice(data)
            await query.edit_message_text(result, parse_mode="HTML")
        elif doc_type == "payment_slip":
            result = await _save_payment(data)
            await query.edit_message_text(result, parse_mode="HTML")
    except Exception as e:
        err = str(e)
        if "duplicate" in err.lower() or "unique" in err.lower():
            await query.edit_message_text(
                f"⚠️ Invoice <b>{data.get('invoice_number', '')}</b> is already recorded.",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(f"❌ Failed to save: {err}")
    finally:
        _cleanup(key)


async def _save_invoice(data: dict) -> str:
    supplier_name  = data.get("supplier_name") or "Unknown Supplier"
    invoice_number = data.get("invoice_number") or f"INV-{date.today().isoformat()}"
    invoice_date   = data.get("invoice_date")   or date.today().isoformat()
    total_amount   = data.get("total_amount")   or 0
    items_raw      = data.get("items", [])

    supplier_id = await upsert_supplier(supplier_name)

    items_payload = [
        {
            "product_name_raw": item.get("product_name", ""),
            "qty":       item.get("qty")       or 0,
            "unit_cost": item.get("unit_cost") or 0,
        }
        for item in items_raw
        if item.get("product_name")
    ]

    await create_invoice({
        "invoice_number": invoice_number,
        "supplier_id":    supplier_id,
        "invoice_date":   invoice_date,
        "total_amount":   total_amount,
        "notes":          data.get("notes"),
        "image_url":      data.get("_stored_url"),
        "items":          items_payload,
    })

    lines = [
        "✅ <b>Invoice Saved</b>",
        f"Supplier:  {supplier_name}",
        f"Invoice #: {invoice_number}",
        f"Date:      {invoice_date}",
        f"Total:     ₹{float(total_amount):,.2f}",
        f"Items:     {len(items_payload)}",
    ]
    return "\n".join(lines)


async def _save_payment(data: dict) -> str:
    amount       = data.get("amount")       or 0
    payment_mode = data.get("payment_mode") or "other"
    payment_date = data.get("payment_date") or date.today().isoformat()
    txn_ref      = data.get("transaction_ref")
    note         = data.get("note")

    await create_payment({
        "payment_date":    payment_date,
        "amount":          amount,
        "payment_mode":    payment_mode,
        "direction":       "outflow",
        "transaction_ref": txn_ref,
        "image_url":       data.get("_stored_url"),
        "note":            note,
    })

    lines = [
        "✅ <b>Payment Saved</b>",
        f"Amount: ₹{float(amount):,.2f}",
        f"Mode:   {payment_mode}",
        f"Date:   {payment_date}",
    ]
    if txn_ref:
        lines.append(f"Ref:    {txn_ref}")
    return "\n".join(lines)


# ── Formatters ────────────────────────────────────────────────────────────────

def _format_preview(data: dict) -> str:
    doc_type = data.get("type")

    if doc_type == "invoice":
        lines = [
            "🧾 <b>Invoice Detected</b>",
            f"Supplier:  {data.get('supplier_name') or '—'}",
            f"Invoice #: {data.get('invoice_number') or '—'}",
            f"Date:      {data.get('invoice_date') or '—'}",
            f"Total:     ₹{float(data.get('total_amount') or 0):,.2f}",
        ]
        items = data.get("items", [])
        if items:
            lines.append(f"\nItems ({len(items)}):")
            for item in items[:5]:
                cost = f" @ ₹{item['unit_cost']}" if item.get("unit_cost") else ""
                lines.append(f"  • {item['product_name']} × {item.get('qty', '?')}{cost}")
            if len(items) > 5:
                lines.append(f"  … and {len(items) - 5} more")
        if data.get("notes"):
            lines.append(f"\nNotes: {data['notes']}")

    elif doc_type == "payment_slip":
        lines = [
            "💸 <b>Payment Slip Detected</b>",
            f"Mode:   {data.get('payment_mode') or '—'}",
            f"Amount: ₹{float(data.get('amount') or 0):,.2f}",
            f"Date:   {data.get('payment_date') or '—'}",
        ]
        if data.get("transaction_ref"):
            lines.append(f"Ref:    {data['transaction_ref']}")
        if data.get("payee_name"):
            lines.append(f"To:     {data['payee_name']}")
        if data.get("note"):
            lines.append(f"Note:   {data['note']}")
    else:
        lines = ["❓ Unknown document type"]

    return "\n".join(lines)


def _apply_text_corrections(data: dict, text: str) -> None:
    """
    Parse simple 'field: value' corrections from freetext.
    e.g. "supplier: Ravi, total: 4500, date: 2026-04-30"
    """
    for part in text.split(","):
        if ":" not in part:
            continue
        k, _, v = part.partition(":")
        k = k.strip().lower().replace(" ", "_")
        v = v.strip()
        if not v:
            continue
        # Map common aliases
        aliases = {
            "supplier": "supplier_name",
            "total": "total_amount",
            "date": "invoice_date",
            "invoice": "invoice_number",
            "amount": "amount",
            "mode": "payment_mode",
            "ref": "transaction_ref",
        }
        field = aliases.get(k, k)
        # Convert numeric fields
        if field in ("total_amount", "amount"):
            try:
                data[field] = float(v.replace("₹", "").replace(",", ""))
            except ValueError:
                pass
        else:
            data[field] = v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cleanup(key: str) -> None:
    entry = _PENDING.pop(key, None)
    if entry:
        _safe_remove(entry.get("_local_path", ""))


def _safe_remove(path: str) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass
