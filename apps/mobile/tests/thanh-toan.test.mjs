/* The settlement screen: the numbers, and nothing but the numbers.
 *
 * This file used to test three things. Two of them -- that a full account
 * number never reached the markup, and that the VietQR card refused to draw
 * when the amount inside the payload disagreed with the amount printed beside
 * it -- were about a payment rail this product no longer has. They are gone
 * with it, and what is left is the claim that was always the important one:
 *
 *   the total on screen is the server's allocation column summed, to the
 *   dong, with nothing this app computed mixed in.
 *
 * A negative case replaces the deleted pair. It is worth keeping because the
 * failure it guards is silent: a screen that still rendered an account number
 * from some leftover field would look completely normal.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { KetQuaThanhToan } from "../dist-test/screens/KetQuaThanhToan.js";

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
      obligations: [{ obligationId: "o1", amountVnd: 312500 }],
      ...overrides,
    },
  ];
}

function screen(props = {}) {
  return renderToStaticMarkup(
    React.createElement(KetQuaThanhToan, {
      roster: ROSTER,
      /* Passed rather than left out. This fixture publishes one envelope, so
       * the sender chip row never renders and the group lookup is never
       * reached -- the screen would work here with no `nhom` at all. Relying
       * on that is relying on the fixture, not on the screen. */
      nhom: ROSTER.participants,
      allocations: ALLOCATIONS,
      obligations: OBLIGATIONS,
      envelopes: envelopes(),
      advancerId: "p2",
      itemCount: 8,
      nguoiDangChon: "p1",
      onChonNguoi: () => {},
      onShare: () => {},
      onDone: () => {},
      onBack: () => {},
      ...props,
    }),
  );
}

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

/* --- what left with the payment rail ------------------------------------ */

test("no bank detail reaches the markup, because there is none to reach it", () => {
  const html = screen();
  for (const gone of ["accountMasked", "vietqr", "qr_payload", "Số tài khoản"]) {
    assert.ok(!html.includes(gone), `${gone} is still on the settlement screen`);
  }
});
