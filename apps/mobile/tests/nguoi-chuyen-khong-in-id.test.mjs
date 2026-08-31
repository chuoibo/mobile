/* The "Người chuyển" chip row on `ket-qua-tt` must not print a database id
 * where a name goes.
 *
 * This is the THIRD site with the shape of bug-050923, found by enumerating
 * every `labelFor` call site and asking one question of each: does the id it
 * is handed come from walking THIS BILL's roster, or did a server name it?
 *
 *   - 10 of the 11 call sites walk `roster.participants` themselves, so a miss
 *     is impossible by construction and `labelFor` is the right lookup.
 *   - 1 does not. `KetQuaThanhToan` labels `envelope.senderId`, and an
 *     envelope is built in `api.ts` from the `guest_links` of
 *     `POST /batches/{id}/publish`. The server answers that route in ids.
 *
 * `labelFor` returns the id it was handed when it cannot place one, so that
 * one site prints a UUID on a chip a person is meant to tap to find their own
 * code. It is the same leak, the same cause and the same fallback as the debt
 * panel and the `Máy chủ chia thử` card on `goi-y`.
 *
 * WHAT THIS IS NOT: a live defect on main today. The batch is opened with
 * `expense_version_ids: [expenseVersionId]`, so its obligations come from one
 * bill, and publish resolves names against `proposal.participants` -- the same
 * people. For `form.roster` to be missing a published sender, somebody would
 * have to remove a participant after publishing, and `DotThu` has no control
 * that goes back to `goi-y`. Measured, not assumed: `DotThu`'s props are
 * `obligations, published, gates, onPublish, onShare, onRefresh,
 * onConfirmReceipt, busy` -- there is no `onBack`.
 *
 * So this screen is correct by an accident of navigation three files away, not
 * by anything at the site of the lookup. That is an acquittal path, not a
 * safety property, and it is worth exactly as much as the acquittal path the
 * `Máy chủ chia thử` card had until it was pinned: adding a back control to
 * `DotThu` is an ordinary afternoon's work, and it would reopen this with no
 * test anywhere going red.
 *
 * These cases render the real screen with a sender the bill does not hold and
 * pin the outcome, so the fix is held by a measurement rather than by a
 * missing button.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { KetQuaThanhToan } from "../dist-test/screens/KetQuaThanhToan.js";
import { TEN_CHUA_BIET } from "../dist-test/screens/chat/tin-nhan.js";

/** Markup with tags stripped, which is what a person actually reads. */
function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

/* The real ids off the seeded group, matching `so-du-khong-in-id.test.mjs`. */
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f";
const NGOC = "e3a44e25-4547-508a-8f4d-9b2495c3325f";
/* In the group's ledger, absent from its active membership. */
const LA = "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8";

/** Who is on the bill. */
const ROSTER = {
  participants: [
    { id: MINH, name: "Minh" },
    { id: TRANG, name: "Trang" },
  ],
  advancerId: MINH,
};

/** Who is in the group, including the person the bill does not hold. */
const NHOM = [
  { id: MINH, name: "Minh" },
  { id: TRANG, name: "Trang" },
  { id: NGOC, name: "Ngọc" },
];

const HINH_DANG_UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/** One envelope as `sendPublish` builds it: the server's `sender_id`, and the
 *  name resolved beside it. */
function phongBi(senderId, senderName, amountVnd) {
  return {
    senderId,
    senderName,
    amountVnd,
    url: `https://example.invalid/g/${senderId}`,
    opened: false,
    obligations: [
      { obligationId: `ob-${senderId}`, amountVnd, vietqrPayload: "00020101" },
    ],
  };
}

/* Two envelopes, because the chip row only exists when there is a choice to
 * make. One sender is on the bill and one is not: a fix that labels everybody
 * with the fallback word has to fail the "Trang" case below. */
function manThanhToan(over = {}) {
  return words(
    React.createElement(KetQuaThanhToan, {
      roster: ROSTER,
      nhom: NHOM,
      allocations: { [MINH]: 40000, [TRANG]: 25000 },
      obligations: [],
      envelopes: [
        phongBi(TRANG, "Trang", 25000),
        phongBi(NGOC, "Ngọc", 30000),
      ],
      advancerId: MINH,
      itemCount: 1,
      nguoiDangChon: null,
      onChonNguoi: () => {},
      renderMaQr: () => null,
      onShare: () => {},
      onDone: () => {},
      onBack: () => {},
      ...over,
    }),
  );
}

test("chip Người chuyển không in id ra chỗ đặt tên", () => {
  const read = manThanhToan();
  const lot = read.match(HINH_DANG_UUID);
  assert.equal(lot, null, `id lọt ra chip người chuyển: ${lot?.[0]} trong "${read}"`);
});

test("người máy chủ nêu mà không có trên bill vẫn hiện đúng tên", () => {
  const read = manThanhToan();
  assert.ok(read.includes("Ngọc"), `mất tên Ngọc ở chip người chuyển: ${read}`);
});

/* The chip that was already right has to stay right. A fix that labels
 * everybody with the fallback word passes the first case and ruins the row. */
test("người có trên bill vẫn hiện đúng tên của họ", () => {
  const read = manThanhToan();
  assert.ok(read.includes("Trang"), `hỏng chip vốn đã đúng: ${read}`);
});

/* Eight hex characters are a valid-looking word, so a fix that sliced the id
 * would satisfy the UUID shape above and still print `e3a44e25` at a person. */
test("tám ký tự hex đầu của id cũng không được coi là tên", () => {
  const read = manThanhToan();
  assert.ok(!read.includes(NGOC.slice(0, 8)), `tiền tố id lọt ra chip: ${read}`);
});

test("người không ai biết tên thì nói ra, không in id", () => {
  const read = manThanhToan({
    envelopes: [phongBi(TRANG, "Trang", 25000), phongBi(LA, LA, 30000)],
  });
  assert.equal(read.match(HINH_DANG_UUID), null, `id lọt ra chip: ${read}`);
  assert.ok(read.includes(TEN_CHUA_BIET), `thiếu "${TEN_CHUA_BIET}": ${read}`);
});
