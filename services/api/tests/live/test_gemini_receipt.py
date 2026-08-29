"""The only test that proves a real model reads a real receipt.

Everything else about ``/receipts/scan`` runs against a fake reader, which
proves orchestration and proves nothing about vision. This file calls Gemini
for real, over the network, and costs money. It is therefore opt-in:

    cd services/api
    set -a; . /path/to/repo/.env; set +a
    MOBILE_LIVE_GEMINI=1 python -m pytest tests/live -q

Skipped is not green. A skip here means the hero claim of this product is
unverified in that run.

The fixture is the receipt photographed inside screen 1 of the product mockup,
cropped at runtime from a file that lives OUTSIDE the repository. No bill image
is committed: a real one is user data, and even this one is a binary the repo
guard would have to allowlist for no benefit. Point ``MOBILE_RECEIPT_IMAGE`` at
a real photo to check the same assertions against real paper.

Ground truth comes from screen 2 and screen 4 of the same mockup: eight items,
printed total 1.125.000.

The eight printed line totals on that receipt sum to 974.000, not 1.125.000 --
the drawn receipt does not add up. That makes it the right fixture for the rule
this product must never break: report both numbers, reconcile neither. The
assertions below therefore pin the two legible facts (item count and the printed
Tổng cộng) and pin the *disagreement*, not the line sum, which is the part a
future model revision is most likely to read differently.
"""

from __future__ import annotations

import io
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.api.vision_gemini import GeminiReceiptReader  # noqa: E402
from app.domain.receipt import read_receipt  # noqa: E402

pytestmark = pytest.mark.live

MOCKUP = pathlib.Path(
    os.environ.get(
        "MOBILE_RECEIPT_MOCKUP",
        "/home/lakiet/mobile/product/features/04-chia-bill-thong-minh.png",
    )
)
# The receipt inside screen 1 of the 1055x1491 mockup sheet, with margin, then
# enlarged: the source region is only 216x305 px and a model reads it far more
# reliably at print scale.
CROP_BOX = (52, 445, 268, 750)
UPSCALE = 6

EXPECTED_ITEMS = 8
EXPECTED_TOTAL_VND = 1_125_000


def receipt_image_bytes() -> bytes:
    override = os.environ.get("MOBILE_RECEIPT_IMAGE")
    if override:
        path = pathlib.Path(override)
        if not path.is_file():
            pytest.skip(f"MOBILE_RECEIPT_IMAGE does not exist: {path}")
        return path.read_bytes()

    pillow = pytest.importorskip("PIL.Image", reason="Pillow crops the mockup fixture")
    if not MOCKUP.is_file():
        pytest.skip(f"mockup not found: {MOCKUP}")
    with pillow.open(MOCKUP) as sheet:
        crop = sheet.convert("RGB").crop(CROP_BOX)
        crop = crop.resize(
            (crop.width * UPSCALE, crop.height * UPSCALE), pillow.LANCZOS
        )
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def reading() -> dict:
    """One live call, shared by every assertion below."""
    if os.environ.get("MOBILE_LIVE_GEMINI") != "1":
        pytest.skip("live Gemini test is opt-in: set MOBILE_LIVE_GEMINI=1")
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not set")
    raw = GeminiReceiptReader().read(receipt_image_bytes(), "image/png")
    return read_receipt(raw)


class TestTheModelReadsTheReceipt:
    def test_it_finds_eight_items(self, reading):
        assert len(reading["items"]) == EXPECTED_ITEMS

    def test_it_reads_the_printed_total(self, reading):
        assert reading["total_vnd"] == EXPECTED_TOTAL_VND

    def test_every_item_has_a_non_empty_name(self, reading):
        assert all(item["name"].strip() for item in reading["items"])

    def test_every_amount_is_integer_dong(self, reading):
        for item in reading["items"]:
            assert type(item["line_total_vnd"]) is int
        assert type(reading["total_vnd"]) is int

    def test_confidence_is_a_real_number_in_range(self, reading):
        assert 0 <= reading["confidence"] <= 100


class TestTheDisagreementIsReportedNotHidden:
    def test_the_line_items_do_not_sum_to_the_printed_total(self, reading):
        """True of this receipt as printed. If it ever becomes false, the
        product started reconciling and this test is the alarm."""
        assert reading["items_total_vnd"] != reading["total_vnd"]

    def test_the_disagreement_is_flagged(self, reading):
        assert reading["totals_agree"] is False

    def test_both_numbers_are_present(self, reading):
        assert reading["items_total_vnd"] > 0
        assert reading["total_vnd"] == EXPECTED_TOTAL_VND


class TestNothingSensitiveComesBack:
    def test_the_reading_carries_no_api_key(self, reading):
        key = os.environ["GEMINI_API_KEY"]
        assert key not in repr(reading)

    def test_the_reading_carries_no_image_bytes(self, reading):
        assert "image" not in reading
