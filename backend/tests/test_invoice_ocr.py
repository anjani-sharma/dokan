"""
Smoke test for `POST /invoices/ocr` — uses a stubbed OCR function so the test
neither hits Anthropic nor needs a real image.
"""
import io
import sys
import types

import pytest


@pytest.fixture
def stub_ocr(monkeypatch):
    """Inject a fake `services.ocr.ocr_document` and `services.storage` into
    sys.modules so the router's lazy import resolves to our stub."""
    fake_ocr = types.ModuleType("services.ocr")

    def ocr_document(path: str) -> dict:
        return {
            "type": "invoice",
            "confidence": "high",
            "supplier_name": "Acme Wires",
            "invoice_number": "AC-2026-007",
            "invoice_date": "2026-05-10",
            "items": [
                {"product_name": "MCB", "qty": 4, "unit": "pcs", "unit_cost": 220.0},
            ],
            "total_amount": 880.0,
            "notes": None,
        }
    fake_ocr.ocr_document = ocr_document

    fake_services = types.ModuleType("services")
    fake_storage = types.ModuleType("services.storage")
    fake_storage.upload_image = lambda p: p  # no R2 in tests
    fake_services.ocr = fake_ocr
    fake_services.storage = fake_storage

    monkeypatch.setitem(sys.modules, "services", fake_services)
    monkeypatch.setitem(sys.modules, "services.ocr", fake_ocr)
    monkeypatch.setitem(sys.modules, "services.storage", fake_storage)
    yield


async def test_ocr_endpoint_returns_extracted_fields(client, stub_ocr):
    files = {"file": ("receipt.jpg", io.BytesIO(b"fakebytes"), "image/jpeg")}
    r = await client.post("/invoices/ocr", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "invoice"
    assert body["supplier_name"] == "Acme Wires"
    assert body["invoice_number"] == "AC-2026-007"
    assert body["total_amount"] == 880.0
    assert body["items"][0]["product_name"] == "MCB"
    assert "image_path" in body


async def test_ocr_endpoint_rejects_unsupported_format(client, stub_ocr):
    files = {"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post("/invoices/ocr", files=files)
    assert r.status_code == 400
