#!/usr/bin/env python3
"""
Phase 3 verification script.
Run with: python test_pipeline.py [--ocr path/to/invoice.jpg] [--payment path/to/slip.jpg]

Tests:
  1. NLP extraction from text transcripts (no audio file needed)
  2. Fuzzy product matcher (no API calls)
  3. Whisper transcription (needs OPENAI_API_KEY + audio file)
  4. Claude OCR for invoice (needs ANTHROPIC_API_KEY + image file)
  5. Claude OCR for payment slip (needs ANTHROPIC_API_KEY + image file)
"""
import argparse
import json
import sys


# ── helpers ──────────────────────────────────────────────────────────────────

def ok(label: str) -> None:
    print(f"  ✓  {label}")


def fail(label: str, detail: str = "") -> None:
    print(f"  ✗  {label}", file=sys.stderr)
    if detail:
        print(f"     {detail}", file=sys.stderr)


def section(title: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


# ── 1. NLP extraction (text → structured JSON) ──────────────────────────────

def test_nlp():
    section("1. NLP — Voice transcript extraction")
    from services.nlp import extract_sales

    test_cases = [
        ("English: simple sale",
         "Sold 10 pieces of MCB 32A and 2 coils of wire 2.5mm today",
         lambda r: r["intent"] == "record_sale" and len(r["items"]) >= 2),

        ("Hinglish: becha",
         "aaj 5 pcs MCB becha aur 3 switch bhi",
         lambda r: r["intent"] == "record_sale" and len(r["items"]) >= 1),

        ("Edit intent",
         "Yesterday I said 10 MCB but it was actually 8 pieces",
         lambda r: r["intent"] in ("edit_sale", "record_sale")),

        ("Query intent",
         "What is today's total?",
         lambda r: r["intent"] == "query"),

        ("Price mentioned",
         "Sold 20 LED bulbs at ₹45 each",
         lambda r: any(i.get("selling_price") for i in r.get("items", []))),
    ]

    passed = 0
    for label, transcript, check in test_cases:
        try:
            result = extract_sales(transcript)
            if check(result):
                ok(label)
                passed += 1
            else:
                fail(label, f"Got: {json.dumps(result, indent=2)[:200]}")
        except Exception as e:
            fail(label, str(e))

    print(f"\n  NLP: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


# ── 2. Fuzzy matcher (no API) ─────────────────────────────────────────────

def test_matcher():
    section("2. Fuzzy product matcher (no API calls)")
    from services.matcher import find_best_match, rank_matches

    catalog = [
        {"id": 1, "name": "MCB 32A Single Pole", "selling_price": "85.00"},
        {"id": 2, "name": "MCB 16A Single Pole", "selling_price": "75.00"},
        {"id": 3, "name": "Wire 2.5mm FRLS", "selling_price": "650.00"},
        {"id": 4, "name": "LED Bulb 9W", "selling_price": "45.00"},
        {"id": 5, "name": "RCCB 25A 30mA", "selling_price": "420.00"},
    ]

    cases = [
        ("MCB 32", 1, 0.5),
        ("2.5mm wire", 3, 0.4),
        ("LED bulb", 4, 0.4),
        ("rccb", 5, 0.3),
        ("completely unrelated item xyz", None, 0.9),
    ]

    passed = 0
    for query, expected_id, threshold in cases:
        result = find_best_match(query, catalog, threshold=threshold)
        result_id = result["id"] if result else None
        if result_id == expected_id:
            ok(f"'{query}' → {result['name'] if result else 'no match'}")
            passed += 1
        else:
            got = result["name"] if result else "no match"
            exp = next((p["name"] for p in catalog if p["id"] == expected_id), "no match")
            fail(f"'{query}'", f"expected '{exp}', got '{got}'")

    print(f"\n  Matcher: {passed}/{len(cases)} passed")
    return passed == len(cases)


# ── 3. JSON parser robustness ────────────────────────────────────────────────

def test_json_parser():
    section("3. Robust JSON parser")
    from services.utils import parse_json_response

    cases = [
        ('Plain JSON', '{"intent":"record_sale","items":[]}', dict),
        ('Fenced JSON', '```json\n{"intent":"query"}\n```', dict),
        ('Leading text', 'Here is the result:\n{"intent":"unknown"}', dict),
        ('Array', '[{"a":1},{"b":2}]', list),
    ]

    passed = 0
    for label, raw, expected_type in cases:
        try:
            result = parse_json_response(raw)
            if isinstance(result, expected_type):
                ok(label)
                passed += 1
            else:
                fail(label, f"Expected {expected_type.__name__}, got {type(result).__name__}")
        except Exception as e:
            fail(label, str(e))

    print(f"\n  JSON parser: {passed}/{len(cases)} passed")
    return passed == len(cases)


# ── 4. Whisper transcription ─────────────────────────────────────────────────

def test_transcription(audio_path: str):
    section(f"4. Whisper transcription — {audio_path}")
    from services.transcriber import transcribe
    try:
        text = transcribe(audio_path)
        if text and len(text) > 3:
            ok(f"Transcript: {text[:100]}")
            return True
        else:
            fail("Transcript too short or empty", repr(text))
            return False
    except Exception as e:
        fail("Transcription failed", str(e))
        return False


# ── 5. Invoice OCR ────────────────────────────────────────────────────────────

def test_ocr_invoice(image_path: str):
    section(f"5. Invoice OCR — {image_path}")
    from services.ocr import ocr_invoice
    try:
        data = ocr_invoice(image_path)
        print(f"  Raw result:\n{json.dumps(data, indent=4, ensure_ascii=False)}")
        checks = [
            ("type == invoice", data.get("type") == "invoice"),
            ("has items list", isinstance(data.get("items"), list)),
            ("no crash on nulls", True),
        ]
        passed = sum(1 for _, v in checks if v)
        for label, result in checks:
            (ok if result else fail)(label)
        print(f"\n  OCR Invoice: {passed}/{len(checks)} checks passed")
        return passed == len(checks)
    except Exception as e:
        fail("OCR failed", str(e))
        return False


# ── 6. Payment slip OCR ───────────────────────────────────────────────────────

def test_ocr_payment(image_path: str):
    section(f"6. Payment slip OCR — {image_path}")
    from services.ocr import ocr_payment_slip
    try:
        data = ocr_payment_slip(image_path)
        print(f"  Raw result:\n{json.dumps(data, indent=4, ensure_ascii=False)}")
        checks = [
            ("type == payment_slip", data.get("type") == "payment_slip"),
            ("has payment_mode", data.get("payment_mode") is not None),
            ("no crash on nulls", True),
        ]
        passed = sum(1 for _, v in checks if v)
        for label, result in checks:
            (ok if result else fail)(label)
        print(f"\n  OCR Payment: {passed}/{len(checks)} checks passed")
        return passed == len(checks)
    except Exception as e:
        fail("OCR failed", str(e))
        return False


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ananta AI pipeline test")
    parser.add_argument("--audio", help="Path to .ogg/.wav voice file for Whisper test")
    parser.add_argument("--ocr", help="Path to invoice image for OCR test")
    parser.add_argument("--payment", help="Path to payment slip image for OCR test")
    args = parser.parse_args()

    results = []

    # Always run — no API keys needed
    results.append(test_json_parser())
    results.append(test_matcher())

    # Needs ANTHROPIC_API_KEY
    results.append(test_nlp())

    # Optional — only if files provided
    if args.audio:
        results.append(test_transcription(args.audio))
    else:
        print("\n  (skipping Whisper test — pass --audio path/to/file.ogg)")

    if args.ocr:
        results.append(test_ocr_invoice(args.ocr))
    else:
        print("  (skipping Invoice OCR test — pass --ocr path/to/invoice.jpg)")

    if args.payment:
        results.append(test_ocr_payment(args.payment))
    else:
        print("  (skipping Payment OCR test — pass --payment path/to/slip.jpg)")

    total = len(results)
    passed = sum(results)
    print(f"\n{'═' * 55}")
    print(f"  TOTAL: {passed}/{total} test groups passed")
    print(f"{'═' * 55}\n")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
