"""Why does the hero path answer "Không đọc được bill", and can anyone tell?

rd-qa-37 measured the same file reading back 6 times out of 11 and could not say
why. rd-be-20 (#209) then wired `sanitize_image` into `/receipts/scan` for a
privacy reason, and the hypothesis was that re-encoding had accidentally fixed
the reliability bug as a side effect.

rd-qa-38 measured it again on the same file and the hypothesis did not survive:
53.3% before the sanitiser and 56.7% after, n=30 each, in one process where the
sanitiser call is the only difference. What the measurement did find is a cause,
and it is not the picture. Across 12 real calls the reader emitted
`quantity_text: ""` -- an empty string, for lines that print no quantity -- 25
times, and 5 of those 12 readings carried at least one. `_read_quantity` treats
a missing key as "one of this item" and an empty string as a malformed quantity,
so one empty string on one line raises INVALID_QUANTITY for the WHOLE receipt.
The other four items are read correctly and thrown away with it.

That code then reaches `scan_receipt`, which has explicit branches for six codes
and one final catch-all for the rest. INVALID_QUANTITY lands in the catch-all,
becomes `422 receipt_unreadable`, and the person is told to check their photo --
about a photo the model read correctly.

Nothing is written down. The server logs one access line, `422 Unprocessable
Content`, which is the same line a malformed `X-Actor-ID` produces. So the one
failure that actually happens on the hero path is also the one nobody can
diagnose from a log.

Everything below is deterministic: the fake reader replays reading shapes
observed from the real model, so no network, no key, and no rate is involved.
The observed shapes are in `docs/claude/2026-08-30/rd-qa-38-do-lai-do-tin-cay.md`.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_receipt_reader
from app.api.main import app
from app.domain.receipt import ReceiptError, read_scanned_document

# Assembled rather than written out: a 32-digit literal trips the repo guard's
# long-number rule. Synthetic, belongs to nobody. Same shape as rd-qa-37 uses.
ACTOR = {
    "X-Actor-ID": "-".join(("1" * 8, "1" * 4, "4" + "1" * 3, "8" + "1" * 3, "1" * 12))
}

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfe\xa7\x9a\xa2\x8c\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _bill(quantity_of_tra_da):
    """The rd-qa-37 bill as the reader actually returns it.

    `quantity_of_tra_da` is the one field that moved between runs. Pass a
    sentinel of None to leave the key out entirely, which is what the reader
    does on the runs that succeed.
    """

    tra_da = {"name": "Trà đá", "unit_price_text": None, "line_total_text": "20.000"}
    if quantity_of_tra_da is not None:
        tra_da["quantity_text"] = quantity_of_tra_da
    return {
        "document_type": "receipt",
        "items": [
            {
                "name": "Cơm tấm sườn bì chả",
                "unit_price_text": None,
                "line_total_text": "65.000",
            },
            {
                "name": "Cơm tấm sườn nướng",
                "unit_price_text": None,
                "line_total_text": "55.000",
            },
            {
                "name": "Canh chua cá lóc",
                "unit_price_text": None,
                "line_total_text": "45.000",
            },
            tra_da,
            {
                "name": "Bia Sài Gòn",
                "unit_price_text": None,
                "line_total_text": "50.000",
            },
        ],
        "total_text": "235.000",
        "confidence": 0.95,
    }


class _Reader:
    """Return a canned reading, or raise a canned code, without a network."""

    def __init__(self, reading=None, error=None):
        self.reading = reading
        self.error = error

    def read(self, image: bytes, mime_type: str) -> dict:
        del image, mime_type
        if self.error is not None:
            raise self.error
        return self.reading


def _client(reader):
    app.dependency_overrides[get_receipt_reader] = lambda: reader
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_receipt_reader, None)


def _scan(reader):
    for client in _client(reader):
        return client.post(
            "/receipts/scan",
            files={"image": ("bill.png", PNG_1x1, "image/png")},
            headers=ACTOR,
        )
    raise AssertionError("unreachable")


# The seven codes with no branch of their own in `scan_receipt`. Six others --
# UNSUPPORTED_IMAGE_TYPE, IMAGE_TOO_LARGE, RECEIPT_TOO_BLURRY,
# RECEIPT_READER_NOT_CONFIGURED, NOT_A_RECEIPT, NOT_A_RECEIPT_PRICE_LIST -- are
# handled by name and are not in this list.
CATCH_ALL_CODES = [
    "EMPTY_IMAGE",
    "INVALID_CONFIDENCE",
    "INVALID_QUANTITY",
    "INVALID_RECEIPT",
    "INVALID_RECEIPT_ITEM",
    "NO_ITEMS_READ",
    "UNREADABLE_AMOUNT",
]


class TestCaiGiThucSuHong:
    """The reading that fails is a reading the model got right."""

    def test_thieu_truong_quantity_thi_doc_duoc(self):
        """No quantity key at all: the receipt reads, and the money is right."""

        result = read_scanned_document(_bill(None))
        assert len(result["items"]) == 5
        assert result["total_vnd"] == 235000

    def test_quantity_rong_khong_con_pha_huy_ca_hoa_don(self):
        """One empty string on ONE line no longer destroys all five.

        This is the observed production failure, not a constructed one: the
        reader emitted `""` on 25 of 60 item-readings across 12 real calls.
        Semantically `""` and a missing key say the same thing -- this line
        prints no quantity -- and the two used to be handled differently.

        Written as characterization while the bug was alive, with the note that
        the day the domain stopped doing this the case would go red and point
        whoever changed it at this file. That is exactly what happened: #220
        (rd-be-22) landed the fix, and the old form -- `pytest.raises`, asserting
        code `INVALID_QUANTITY` -- started failing with DID NOT RAISE. It is
        inverted here into the regression guard for the fixed behaviour: the
        blank line reads, and it takes the other four with it instead of down.
        """

        result = read_scanned_document(_bill(""))
        assert len(result["items"]) == 5

    def test_bon_mon_kia_doc_duoc_van_bi_vut_di(self):
        """The four good lines are collateral, not the cause."""

        chi_bon_mon = _bill("")
        chi_bon_mon["items"] = [
            it for it in chi_bon_mon["items"] if it.get("quantity_text") != ""
        ]
        assert read_scanned_document(chi_bon_mon)["total_vnd"] == 235000

    def test_quantity_rong_nen_doc_nhu_khong_co(self):
        """Blank and absent now mean the same thing, and the money is right.

        Was `xfail(strict=True)` while `_read_quantity` accepted only bare
        digits: `""` and a missing key say the same thing on a bill that prints
        no quantity column, and only one of them was read. #220 (rd-be-22) reads
        blank as absent, so this passes on its own now. The marker came off in
        the same change that proved it -- a strict xfail left on a case that has
        started passing turns XPASS into a hard failure and reds main.
        """

        assert read_scanned_document(_bill(""))["total_vnd"] == 235000


class TestBayMaMotCau:
    """Seven distinct causes, one sentence, no way back to the cause."""

    @pytest.mark.parametrize("code", CATCH_ALL_CODES)
    def test_moi_ma_deu_ra_cung_mot_body(self, code):
        response = _scan(_Reader(error=ReceiptError(code)))
        assert response.status_code == 422
        assert response.json()["code"] == "receipt_unreadable"

    def test_hai_nguyen_nhan_khac_han_nhau_khong_phan_biet_duoc(self):
        """`UNREADABLE_AMOUNT` is a person's problem; `EMPTY_IMAGE` is not.

        One means the model read the item names but not the money -- a person
        can retake that photo usefully, or type the number. The other means
        nothing arrived. On the wire they are the same bytes.
        """

        a = _scan(_Reader(error=ReceiptError("UNREADABLE_AMOUNT")))
        b = _scan(_Reader(error=ReceiptError("EMPTY_IMAGE")))
        assert a.json() == b.json()


class TestKhongAiChanDoanDuoc:
    """Can anyone find out which of the seven it was, after the fact?"""

    def test_ma_loi_co_trong_log(self, caplog):
        """The failing code reaches the log, so the cause is recoverable.

        Was `xfail(strict=True)`: measured on a live server, 5 failing scans
        produced 5 identical `422 Unprocessable Content` access lines and
        nothing else, and a malformed X-Actor-ID produced that same line, so the
        log could not separate a bad header from an unreadable bill. #220
        (rd-be-22) logs the code, which is more than that change promised to do.
        Marker removed for the same reason as the case above.
        """

        with caplog.at_level(logging.DEBUG):
            response = _scan(_Reader(error=ReceiptError("INVALID_QUANTITY")))
        assert response.status_code == 422
        assert "INVALID_QUANTITY" in caplog.text

    def test_log_khong_bao_gio_chua_noi_dung_bill(self, caplog):
        """The guard that has to hold once the code above is fixed.

        Vacuously true today, because nothing is logged at all. It is here so
        that the fix for the case above cannot be "log the reading" -- an image
        of a bill is private data, and so is its transcription. Only the code
        may be written down.
        """

        with caplog.at_level(logging.DEBUG):
            _scan(_Reader(reading=_bill("")))
        for bi_mat in ("Cơm tấm sườn bì chả", "Trà đá", "235.000", "65.000"):
            assert bi_mat not in caplog.text
