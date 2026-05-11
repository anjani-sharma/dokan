"""
Auto-detecting OCR for invoices and payment slips.

One call to Claude Vision figures out document type AND extracts data.
No caption keyword required from the user.
"""
import base64

import anthropic

from settings import settings
from services.utils import parse_json_response, with_retry

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_UNIFIED_PROMPT = """\
You are a bookkeeping assistant for an electrical materials shop in India.
Carefully look at this image and do two things:

STEP 1 — Identify the document type:
  - "invoice"       : a purchase bill/invoice from a supplier listing items bought
  - "payment_slip"  : a payment receipt, bank deposit slip, GPay/UPI screenshot,
                      or any proof of payment
  - "unknown"       : if you genuinely cannot tell

STEP 2 — Extract all readable fields based on the type.

Return a single JSON object. Choose the matching structure:

If invoice:
{
  "type": "invoice",
  "confidence": "high" | "medium" | "low",
  "supplier_name": string or null,
  "invoice_number": string or null,
  "invoice_date": "YYYY-MM-DD" or null,
  "items": [
    {
      "product_name": string,
      "qty": number or null,
      "unit": string or null,
      "unit_cost": number or null
    }
  ],
  "total_amount": number or null,
  "notes": string or null
}

If payment_slip:
{
  "type": "payment_slip",
  "confidence": "high" | "medium" | "low",
  "payment_mode": "cash" | "bank_deposit" | "gpay" | "upi" | "other",
  "amount": number or null,
  "transaction_ref": string or null,
  "payment_date": "YYYY-MM-DD" or null,
  "payee_name": string or null,
  "note": string or null
}

If unknown:
{
  "type": "unknown",
  "confidence": "low",
  "note": "brief reason why you could not identify the document"
}

Rules:
- Convert dates to YYYY-MM-DD (e.g. 30/04/26 → 2026-04-30).
- Strip commas from numbers (1,200 → 1200). Use decimal point for paise.
- Detect payment_mode from logos/UI: Google Pay/GPay → gpay, NEFT/RTGS/DD → bank_deposit,
  any UPI app (PhonePe, Paytm, BHIM) → upi, hand-written cash receipt → cash.
- If a field is unclear or missing, use null — never guess.
- Return ONLY the JSON object, no markdown, no explanation.

Vocabulary for invoices (important — the shop reads these in reverse):
- The shop is the BUYER, so the party whose name is on the letterhead /
  at the top of the bill is the "supplier" or "vendor". Put their name in
  "supplier_name".
- Handwritten Indian shop invoices often label the recipient "Customer: <name>"
  — that name is the SHOP itself, not a customer in our system. Do NOT
  include "Customer: ..." in the notes. Refer to the other party only as
  the vendor/supplier in any prose.
- When summarising in the notes field, use "Vendor" or "Supplier", never
  "Customer".
"""


def _encode_image(image_path: str) -> tuple[str, str]:
    """Return (base64_data, media_type)."""
    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    # Detect format from file extension
    ext = image_path.rsplit(".", 1)[-1].lower()
    media_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "webp": "image/webp",
    }.get(ext, "image/jpeg")
    return data, media_type


def ocr_document(image_path: str) -> dict:
    """
    Auto-detect and extract data from any shop document photo.
    Returns a dict with 'type' = 'invoice' | 'payment_slip' | 'unknown'.
    """
    def _call():
        image_data, media_type = _encode_image(image_path)
        msg = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": _UNIFIED_PROMPT},
                    ],
                }
            ],
        )
        result = parse_json_response(msg.content[0].text)
        result.setdefault("type", "unknown")
        result.setdefault("confidence", "low")
        if result["type"] == "invoice":
            result.setdefault("items", [])
            result["items"] = [i for i in result["items"] if i.get("product_name")]
        return result

    return with_retry(_call, retries=2)


# Keep old names as thin wrappers for any code that still calls them directly
def ocr_invoice(image_path: str) -> dict:
    return ocr_document(image_path)

def ocr_payment_slip(image_path: str) -> dict:
    return ocr_document(image_path)
