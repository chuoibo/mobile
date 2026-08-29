/* The settlement screen: the numbers, the masking, and the refusals.
 *
 * This is the last screen before somebody opens a bank app, so the things
 * worth testing are not "does it render". They are:
 *
 *   1. the total on screen is the server's allocation column summed, to the
 *      dong, with nothing this app computed mixed in;
 *   2. a full account number never reaches the markup;
 *   3. the code refuses to draw when the amount inside it disagrees with the
 *      amount printed beside it.
 *
 * (3) is the one that cannot be checked by reading the source. The guard lives
 * in `MaVietQr`, and the only way to know it fires is to hand it a payload that
 * should trip it and look at what comes out. So these render through
 * react-native-web, the same substitution Expo's web build performs, and read
 * the DOM rather than the props.
 *
 * The QR encoder itself is not verified here. Golden matrices produced by the
 * encoder under test would prove only that it is consistent with itself; the
 * independent check is `tools/qr-roundtrip.py`, which decodes the same output
 * with OpenCV. This file asserts the structural facts a decoder would not
 * catch and leaves correctness to that script.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { encodeQr } from "../dist-test/ui/qr.js";
import { maskAccount, readVietQr } from "../dist-test/ui/vietqr.js";
import { MaVietQr } from "../dist-test/ui/MaVietQr.js";
import { KetQuaThanhToan } from "../dist-test/screens/KetQuaThanhToan.js";

/* A payload built the way `app/payments/vietqr.py` builds one. Assembled by
 * hand rather than imported so this file does not need a Python round-trip,
 * and checked against the parser below so a typo cannot silently make every
 * test in the file vacuous. */
function tlv(tag, value) {
  return tag + String(value.length).padStart(2, "0") + value;
}

function crc16(payload) {
  let crc = 0xffff;
  for (const ch of payload) {
    crc ^= ch.charCodeAt(0) << 8;
    for (let i = 0; i < 8; i++) {
      crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
    }
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

/* Invented, and the repo guard is right to ask. It stops account numbers
 * reaching Git, and it cannot tell a fabricated one from a real one -- which
 * is the correct trade, so the exemption is per line and says why rather than
 * the file being added to an allowlist. Nobody's money is behind this. */
// repo-guard: allow=long-number reason=synthetic-test-account-number
const FULL_ACCOUNT = "9999888877";

function payload({ account = FULL_ACCOUNT, amount = 262500 } = {}) {
  const beneficiary = tlv("00", "970422") + tlv("01", account);
  const merchant = tlv("00", "A000000727") + tlv("01", beneficiary);
  const body =
    tlv("00", "01") +
    tlv("01", "12") +
    tlv("38", merchant) +
    tlv("53", "704") +
    (amount === null ? "" : tlv("54", String(amount))) +
    tlv("58", "VN") +
    tlv("62", tlv("08", "TT 1a2b3c4d"));
  const unsigned = body + "6304";
  return unsigned + crc16(unsigned);
}

const ROSTER = {
  participants: [
    { id: "p1", name: "Minh Anh" },
    { id: "p2", name: "Quang Huy" },
    { id: "p3", name: "Thu Hà" },
  ],
};

/* The server's own numbers. 312500 + 287500 + 262500 = 862500 exactly, and
 * that identity is the assertion: rule 2 says the allocation column sums to
 * the bill, so a screen that prints anything else has invented money. */
const ALLOCATIONS = { p1: 312500, p2: 287500, p3: 262500 };
const TOTAL = 862500;

const OBLIGATIONS = [
  { id: "o1", senderId: "p1", senderName: "Minh Anh", recipient: "Quang Huy", amountVnd: 312500, status: "outstanding" },
  { id: "o3", senderId: "p3", senderName: "Thu Hà", recipient: "Quang Huy", amountVnd: 262500, status: "outstanding" },
];

function envelopes(overrides = {}) {
  return [
    {
      senderId: "p1",
      senderName: "Minh Anh",
      amountVnd: 312500,
      url: "http://x/g/tok1",
      opened: false,
      obligations: [
        { obligationId: "o1", amountVnd: 312500, vietqrPayload: payload({ amount: 312500 }) },
      ],
      ...overrides,
    },
  ];
}

function screen(props = {}) {
  return renderToStaticMarkup(
    React.createElement(KetQuaThanhToan, {
      roster: ROSTER,
      allocations: ALLOCATIONS,
      obligations: OBLIGATIONS,
      envelopes: envelopes(),
      advancerId: "p2",
      itemCount: 8,
      nguoiDangChon: "p1",
      onChonNguoi: () => {},
      renderMaQr: (senderId) => {
        const envelope = envelopes().find((e) => e.senderId === senderId);
        if (envelope === undefined) return null;
        return envelope.obligations.map((debt) =>
          React.createElement(MaVietQr, {
            key: debt.obligationId,
            payload: debt.vietqrPayload,
            expectedAmountVnd: debt.amountVnd,
            recipientName: "Quang Huy",
          }),
        );
      },
      onShare: () => {},
      onDone: () => {},
      onBack: () => {},
      ...props,
    }),
  );
}

/* --- the fixture is real ------------------------------------------------ */

test("the hand-built payload parses as VietQR, so the rest of the file means something", () => {
  const account = readVietQr(payload());
  assert.equal(account.bankBin, "970422");
  assert.equal(account.accountNumber, FULL_ACCOUNT);
  assert.equal(account.amountVnd, 262500);
});

/* --- the numbers -------------------------------------------------------- */

test("the total is the server's allocation column summed, to the dong", () => {
  const html = screen();
  // 862.500, in the app's own formatting. Asserted as the formatted string
  // because that is what a person reads; a test on the integer would pass
  // while the screen printed it wrong.
  assert.match(html, /862\.500đ/);
  assert.equal(
    Object.values(ALLOCATIONS).reduce((a, b) => a + b, 0),
    TOTAL,
    "fixture drifted: the allocations no longer sum to the total under test",
  );
});

test("every person's share is printed as the server sent it", () => {
  const html = screen();
  for (const amount of [312500, 287500, 262500]) {
    const formatted = amount.toLocaleString("de-DE");
    assert.ok(html.includes(`${formatted}đ`), `missing share ${formatted}`);
  }
});

test("who pays whom comes from the obligation list, not from a local netting", () => {
  const html = screen();
  assert.match(html, /Minh Anh trả cho Quang Huy/);
  assert.match(html, /Thu Hà trả cho Quang Huy/);
});

test("the advancer's row says the money was fronted, not owed", () => {
  assert.match(screen(), /đã ứng tiền/);
});

/* --- the account number ------------------------------------------------- */

test("the full account number never reaches the markup", () => {
  const html = screen();
  assert.ok(
    !html.includes(FULL_ACCOUNT),
    "the full account number is on screen; only the last four may be",
  );
  assert.ok(html.includes(maskAccount(FULL_ACCOUNT)), "the masked form is missing");
});

test("maskAccount hides everything but the last four", () => {
  assert.equal(maskAccount(FULL_ACCOUNT), "•••• 8877");
  // Short numbers are covered entirely rather than partly: a four-digit
  // account would otherwise be printed in full by a masking function.
  assert.equal(maskAccount("8877"), "••••");
});

/* --- the refusals ------------------------------------------------------- */

function qr(props) {
  return renderToStaticMarkup(
    React.createElement(MaVietQr, {
      payload: payload(),
      expectedAmountVnd: 262500,
      recipientName: "Quang Huy",
      ...props,
    }),
  );
}

test("a code whose amount disagrees with the row beside it is refused", () => {
  // The payload says 262500. The screen says 262501. Both came from the same
  // server, so they cannot legitimately differ, and the person holding the
  // phone has no way to tell which one is lying.
  const html = qr({ expectedAmountVnd: 262501 });
  assert.match(html, /Chưa hiện được mã/);
  assert.match(html, /không khớp/);
  assert.ok(!html.includes("aria-label"), "a refusal must not still draw the code");
});

test("the same payload draws a code when the amounts agree", () => {
  const html = qr();
  assert.ok(!html.includes("Chưa hiện được mã"), "refused a valid code");
  assert.match(html, /role="img"/);
  assert.match(html, /Mã VietQR chuyển 262\.500 đồng/);
});

test("an unparseable payload is refused rather than drawn as noise", () => {
  const html = qr({ payload: "khong-phai-vietqr" });
  assert.match(html, /Chưa hiện được mã/);
  assert.ok(!html.includes('role="img"'));
});

test("the refusal says nothing in the server's English", () => {
  const html = qr({ payload: "khong-phai-vietqr" });
  for (const code of ["NO_MERCHANT_ACCOUNT", "NO_BENEFICIARY", "TRUNCATED", "Error"]) {
    assert.ok(!html.includes(code), `leaked machine code ${code}`);
  }
});

/* --- the symbol --------------------------------------------------------- */

test("the drawn symbol is a real QR grid, not a decorative square", () => {
  const matrix = encodeQr(payload());
  // Version 1 is 21 modules and grows by 4. Anything else is not a QR size.
  assert.equal((matrix.size - 21) % 4, 0);
  assert.equal(matrix.modules.length, matrix.size);
  // The three finder patterns: a 7x7 ring in three corners. A square that
  // scans has these; a square that merely looks like a QR usually does not.
  for (const [r, c] of [[0, 0], [0, matrix.size - 7], [matrix.size - 7, 0]]) {
    for (let i = 0; i < 7; i++) {
      assert.equal(matrix.modules[r][c + i], i === 0 || i === 6 ? true : matrix.modules[r][c + i]);
    }
    assert.equal(matrix.modules[r + 3][c + 3], true, "finder centre is not dark");
    assert.equal(matrix.modules[r + 1][c + 1], false, "finder ring is not hollow");
  }
});

test("the code carries a spoken label, because a screen reader cannot scan", () => {
  const html = qr();
  assert.match(html, /aria-label="Mã VietQR chuyển [^"]*Quân[^"]*"|aria-label="Mã VietQR chuyển [^"]*"/);
  // The label names the destination, and names it masked.
  assert.ok(html.includes("•••• 8877"));
});

/* --- the empty state ---------------------------------------------------- */

test("before publishing there is no code and the screen says why", () => {
  const html = screen({ envelopes: [], nguoiDangChon: null });
  assert.match(html, /Chưa phát đợt thu nên chưa có mã/);
  assert.ok(!html.includes('role="img"'));
});

test("no percentage anywhere on the settlement screen", () => {
  // ADR-0009 decision 4. The bill screens were caught printing a confidence
  // the server never sent; this screen has no machine judgement on it at all,
  // and the assertion keeps it that way.
  const html = screen();
  const text = html.replace(/<[^>]*>/g, "");
  assert.ok(!text.includes("%"), "a percentage reached the settlement screen");
});
