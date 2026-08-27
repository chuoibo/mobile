"""VietQR payload construction."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from app.payments.vietqr import (  # noqa: E402
    VietQRError,
    build_payload,
    crc16_ccitt_false,
    parse_tlv,
)


class Crc(unittest.TestCase):
    def test_standard_check_value(self):
        """CRC-16/CCITT-FALSE is defined by CRC("123456789") == 0x29B1.

        Pinning the variant matters: CCITT, XMODEM and KERMIT all differ, and
        picking the wrong one yields a QR every banking app quietly rejects.
        """
        self.assertEqual(crc16_ccitt_false("123456789"), "29B1")

    def test_empty_input_is_the_init_value(self):
        self.assertEqual(crc16_ccitt_false(""), "FFFF")


class Payload(unittest.TestCase):
    def build(self, **overrides):
        args = {"bank_bin": "970415", "account_number": "113366668888"}
        args.update(overrides)
        return build_payload(**args)

    def test_structure_parses_back(self):
        payload = self.build(amount_vnd=82000, note="Bua lau")
        fields = parse_tlv(payload)
        self.assertEqual(fields["00"], "01")
        self.assertEqual(fields["01"], "12")  # dynamic: carries an amount
        self.assertEqual(fields["53"], "704")
        self.assertEqual(fields["54"], "82000")
        self.assertEqual(fields["58"], "VN")

        merchant = parse_tlv(fields["38"])
        self.assertEqual(merchant["00"], "A000000727")
        self.assertEqual(merchant["02"], "QRIBFTTA")
        beneficiary = parse_tlv(merchant["01"])
        self.assertEqual(beneficiary["00"], "970415")
        self.assertEqual(beneficiary["01"], "113366668888")
        self.assertEqual(parse_tlv(fields["62"])["08"], "Bua lau")

    def test_crc_covers_its_own_header(self):
        payload = self.build(amount_vnd=1000)
        body, crc = payload[:-4], payload[-4:]
        self.assertTrue(body.endswith("6304"))
        self.assertEqual(crc16_ccitt_false(body), crc)

    def test_no_amount_means_static_code(self):
        fields = parse_tlv(self.build())
        self.assertEqual(fields["01"], "11")
        self.assertNotIn("54", fields)

    def test_changing_any_field_changes_the_crc(self):
        crcs = {
            self.build(amount_vnd=82000)[-4:],
            self.build(amount_vnd=82001)[-4:],
            self.build(amount_vnd=82000, note="x")[-4:],
            self.build(amount_vnd=82000, account_number="113366668889")[-4:],
        }
        self.assertEqual(len(crcs), 4)

    def test_amount_is_integer_dong_only(self):
        for bad, code in ((0, "NON_POSITIVE_AMOUNT"), (-1, "NON_POSITIVE_AMOUNT"), (1.5, "AMOUNT_NOT_INTEGER"), (True, "AMOUNT_NOT_INTEGER")):
            with self.subTest(bad=bad):
                with self.assertRaises(VietQRError) as caught:
                    self.build(amount_vnd=bad)
                self.assertEqual(caught.exception.code, code)

    def test_rejects_malformed_bank_bin(self):
        for bad in ("97041", "9704155", "97041a"):
            with self.subTest(bad=bad):
                with self.assertRaises(VietQRError) as caught:
                    self.build(bank_bin=bad)
                self.assertEqual(caught.exception.code, "INVALID_BANK_BIN")


class KnownLimits(unittest.TestCase):
    def test_no_real_bank_vector_is_asserted_here(self):
        """Honest gap, recorded rather than hidden.

        The CRC variant and the TLV nesting are verified. What is NOT verified
        is that a real Vietnamese banking app accepts this string, because that
        needs a real bank account and a real phone. Until someone scans one,
        treat this module as structurally correct and behaviourally unproven.
        """
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
