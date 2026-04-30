import anthropic

from settings import settings
from services.utils import parse_json_response, with_retry

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SALES_PROMPT = """\
You are a bookkeeping assistant for an electrical materials shop in India.
The shopkeeper sends daily sales reports in Hindi, Hinglish, or English.

Common electrical items: MCB, RCCB, wire (2.5mm, 4mm, 6mm), switch, socket,
conduit pipe, earthing wire, energy meter, LED bulb, fan capacitor, cable.

Common Hindi/Hinglish words to recognise:
  becha / beche = sold
  pcs / pice / piece = pieces
  coil / koyil = coil
  box / bax = box
  kal = yesterday  aaj = today

From the transcript below, identify the INTENT and extract items.

Return a JSON object with exactly these keys:
  "intent": one of "record_sale" | "edit_sale" | "delete_sale" | "query" | "unknown"
  "items": array — each object has:
    "product_name": string (clean English name)
    "qty": number (required)
    "unit": string or null  (piece/pcs/coil/box/meter/kg/roll)
    "selling_price": number or null
    "edit_note": string or null  (only for edit_sale)
  "date_hint": "today" | "yesterday" | null

Rules:
- If intent is not "record_sale", items may be an empty array.
- Never invent data. If qty is unclear, omit the item.
- Return ONLY the JSON object — no explanation, no markdown fences.

Transcript:
{transcript}
"""


def extract_sales(transcript: str) -> dict:
    """Parse a voice/text transcript into structured sales intent."""

    def _call():
        msg = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[
                {
                    "role": "user",
                    "content": _SALES_PROMPT.format(transcript=transcript),
                }
            ],
        )
        return parse_json_response(msg.content[0].text)

    result = with_retry(_call, retries=2)

    # Normalise — ensure required keys exist
    result.setdefault("intent", "unknown")
    result.setdefault("items", [])
    result.setdefault("date_hint", None)

    # Remove items missing qty
    result["items"] = [
        item for item in result["items"]
        if item.get("qty") and float(item["qty"]) > 0
    ]

    return result
