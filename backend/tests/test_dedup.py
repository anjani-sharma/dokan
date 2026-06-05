"""Pure-function tests for src.imports.dedup — no DB needed."""

from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from src.imports.dedup import (
    PHASH_HAMMING_THRESHOLD,
    _hamming_hex,
    _norm_name,
    _within_pct,
    compute_invoice_fingerprint,
    compute_payment_fingerprint,
    compute_phash,
)


def _img(color=(200, 200, 200), size=(64, 64)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class TestInvoiceFingerprint:
    def test_item_order_does_not_matter(self):
        items_a = [
            {"product_name": "LED Bulb 100W", "qty": 10},
            {"product_name": "Copper Wire 2.5mm", "qty": 50},
            {"product_name": "Switch 6A", "qty": 12},
        ]
        items_b = list(reversed(items_a))
        f_a = compute_invoice_fingerprint(1, date(2026, 5, 27), 1234.50, items_a)
        f_b = compute_invoice_fingerprint(1, date(2026, 5, 27), 1234.50, items_b)
        assert f_a == f_b

    def test_name_normalization_absorbs_ocr_noise(self):
        items_a = [{"product_name": "LED Bulb 100W", "qty": 10}]
        items_b = [{"product_name": "led-bulb 100w", "qty": 10}]
        assert compute_invoice_fingerprint(1, date(2026, 5, 27), 100, items_a) == \
               compute_invoice_fingerprint(1, date(2026, 5, 27), 100, items_b)

    def test_total_rounds_to_nearest_rupee(self):
        items = [{"product_name": "x", "qty": 1}]
        # 1000.40 and 1000.49 both round to 1000
        assert compute_invoice_fingerprint(1, date(2026, 5, 27), 1000.40, items) == \
               compute_invoice_fingerprint(1, date(2026, 5, 27), 1000.49, items)
        # ...but 1000.5 rounds to 1001 (banker's would round to 1000; we use round()
        # which is banker's-rounded in Python 3, so 1000.5 → 1000). Just assert
        # something different at +1 rupee.
        a = compute_invoice_fingerprint(1, date(2026, 5, 27), 1000, items)
        b = compute_invoice_fingerprint(1, date(2026, 5, 27), 1001.4, items)
        assert a != b

    def test_supplier_change_breaks_match(self):
        items = [{"product_name": "x", "qty": 1}]
        assert compute_invoice_fingerprint(1, date(2026, 5, 27), 100, items) != \
               compute_invoice_fingerprint(2, date(2026, 5, 27), 100, items)

    def test_date_change_breaks_match(self):
        items = [{"product_name": "x", "qty": 1}]
        assert compute_invoice_fingerprint(1, date(2026, 5, 27), 100, items) != \
               compute_invoice_fingerprint(1, date(2026, 5, 28), 100, items)

    def test_accepts_product_name_raw_alias(self):
        # Worker path uses {"product_name": ...} (OCR contract); HTTP commit
        # path uses {"product_name_raw": ...} (InvoiceItemCreate dump). Both
        # must produce the same fingerprint.
        a = [{"product_name": "LED Bulb 100W", "qty": 10}]
        b = [{"product_name_raw": "LED Bulb 100W", "qty": 10}]
        assert compute_invoice_fingerprint(1, date(2026, 5, 27), 100, a) == \
               compute_invoice_fingerprint(1, date(2026, 5, 27), 100, b)


class TestPaymentFingerprint:
    def test_mode_is_case_insensitive(self):
        assert compute_payment_fingerprint(date(2026, 5, 27), 500, "UPI", "TXN1") == \
               compute_payment_fingerprint(date(2026, 5, 27), 500, "upi", "TXN1")

    def test_ref_strip(self):
        assert compute_payment_fingerprint(date(2026, 5, 27), 500, "upi", " TXN1 ") == \
               compute_payment_fingerprint(date(2026, 5, 27), 500, "upi", "TXN1")

    def test_amount_change_breaks_match(self):
        assert compute_payment_fingerprint(date(2026, 5, 27), 500, "upi", "TXN1") != \
               compute_payment_fingerprint(date(2026, 5, 27), 501, "upi", "TXN1")


class TestWithinPct:
    def test_zero_safe(self):
        assert _within_pct(0, 0, 1)

    def test_within(self):
        assert _within_pct(1000, 1009, 1.0)  # 0.9% diff

    def test_outside(self):
        assert not _within_pct(1000, 1011, 1.0)  # 1.1% diff


class TestNorm:
    def test_strips_non_alnum_and_lowercases(self):
        assert _norm_name(" LED-Bulb 100W. ") == "ledbulb100w"

    def test_handles_empty(self):
        assert _norm_name("") == ""
        assert _norm_name(None) == ""  # type: ignore[arg-type]


class TestPhash:
    def test_returns_16_char_hex(self):
        h = compute_phash(_img())
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_image_same_hash(self):
        bs = _img(color=(123, 45, 67))
        assert compute_phash(bs) == compute_phash(bs)

    def test_different_color_different_hash(self):
        # Solid-color images can collide on phash; force a gradient.
        from PIL import ImageDraw
        def grad(seed):
            img = Image.new("RGB", (64, 64), (0, 0, 0))
            d = ImageDraw.Draw(img)
            for y in range(64):
                d.line([(0, y), (64, y)], fill=(y * 4 % 256, seed, 80))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        h1 = compute_phash(grad(50))
        h2 = compute_phash(grad(200))
        assert h1 != h2


class TestHammingHex:
    def test_zero_for_identical(self):
        assert _hamming_hex("0123456789abcdef", "0123456789abcdef") == 0

    def test_single_bit_diff(self):
        # 0x0...0 vs 0x0...1 differ in exactly one bit.
        assert _hamming_hex("0000000000000000", "0000000000000001") == 1

    def test_all_bits_diff(self):
        assert _hamming_hex("0000000000000000", "ffffffffffffffff") == 64

    def test_threshold_is_sensible(self):
        # The constant is exposed so callers can tune. Sanity-check the value
        # we shipped is in a plausible range for a 64-bit hash.
        assert 0 < PHASH_HAMMING_THRESHOLD <= 32
