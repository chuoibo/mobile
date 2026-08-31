/* No name minted in `api.ts` may be a database id.
 *
 * This is the FOURTH site with the shape of bug-050923, and it was found by
 * changing the question. The first three were found by walking `labelFor` call
 * sites, which is a question about screens. Lead's reframing was that the root
 * is not "somebody forgot a lookup on one screen" but "there is a LAYER of ids
 * coming from the server straight to the display" -- so the question becomes
 * which server fields reach a person's eyes without a safe lookup, and that is
 * answered from `api.ts`, not from the screens.
 *
 * Asked that way, the answer is not one site. `api.ts` mints display names
 * itself, in two private helpers that no screen can see and that the `labelFor`
 * enumeration therefore could not reach:
 *
 *   - `nameOf`, inside `openBatch`, builds `Obligation.senderName` and
 *     `Obligation.recipient` from `sender_id` / `recipient_id` of `POST
 *     /batches`.
 *   - `nameFrom`, used by `sendPublish`, builds `Envelope.senderName` from
 *     `guest_links[].sender_id` of `POST /batches/{id}/publish`.
 *
 * Both looked the person up in THIS BILL's roster only, and both ended `?? id`.
 * The server answers those routes against the roster IT holds, so a person who
 * is in the group but not on the bill somebody typed came back as a UUID, and
 * that UUID was rendered as a name in four places:
 *
 *   - `DotThu`          -- "<uuid> gửi Minh", the collection board
 *   - `KetQuaThanhToan` -- "<uuid> trả cho Minh", beside the QR code
 *   - `ChiaSe`          -- the row a person taps to send somebody their link
 *   - the share message ITSELF, which is copied to the clipboard and sent to a
 *     real person: "Phần của <uuid>: 505.094đ".
 *
 * Measured before the fix, against the seeded group's real ids, the obligation
 * row read
 *
 *     e3a44e25-4547-508a-8f4d-9b2495c3325f trả cho Minh
 *
 * which is the same id, in the same sentence shape, as the line the original
 * bug-050923 ticket was filed about. Same leak, different layer.
 *
 * `nameFrom` carried a written argument FOR the `?? id` fallback: that saying
 * "Người nhận" instead would make two different people look like the same one.
 * That argument predates `labelInGroup` (#423) and does not survive it, because
 * `labelInGroup` widens to the group BEFORE it gives up and numbers duplicates
 * across both lists. So the only people who reach the fallback word are people
 * neither list can name -- and for a human reader a raw UUID does not tell two
 * of those apart either. It only looks like it does.
 *
 * These cases pin the boundary rather than the screens, because that is where
 * the names are minted: a fifth screen rendering `senderName` tomorrow inherits
 * the guarantee instead of needing its own test.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { openBatch, publishBatch } from "../dist-test/api.js";
import { DotThu } from "../dist-test/screens/DotThu.js";
import { ChiaSe } from "../dist-test/screens/ChiaSe.js";
import { TEN_CHUA_BIET } from "../dist-test/screens/chat/tin-nhan.js";

/* The seeded group's real ids, matching `so-du-khong-in-id.test.mjs` and
 * `nguoi-chuyen-khong-in-id.test.mjs`. */
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f";
const NGOC = "e3a44e25-4547-508a-8f4d-9b2495c3325f";
/* In the group's ledger, absent from its active membership. */
const LA = "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8";

const HINH_DANG_UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/** Who is on the bill somebody typed: Ngọc is NOT on it. */
const TREN_BILL = [
  { id: MINH, name: "Minh" },
  { id: TRANG, name: "Trang" },
];

/** Who the group has, which is what the server answers against. */
const TRONG_NHOM = [
  { id: MINH, name: "Minh" },
  { id: TRANG, name: "Trang" },
  { id: NGOC, name: "Ngọc" },
];

const PROPOSAL = {
  expenseId: "ex-1",
  contextId: "ctx-1",
  advancerId: MINH,
  participants: TREN_BILL,
  serverProposal: {},
};

/* Separated the way `offline.test.mjs` writes its attempt: a bare digit run
 * that long is what repo-guard exists to ask about. */
const ATTEMPT = { key: "k-1", at: 1_756_600_000_000 };

/** Answer the next call with this body, and put `fetch` back afterwards. */
function mayChuTraLoi(body) {
  const that = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  return () => {
    globalThis.fetch = that;
  };
}

async function moDotThu(senderId) {
  const tra = mayChuTraLoi({
    batch_id: "b-1",
    obligations: [
      { obligation_id: "o-1", sender_id: senderId, recipient_id: MINH, amount_vnd: 505094 },
      { obligation_id: "o-2", sender_id: TRANG, recipient_id: MINH, amount_vnd: 374262 },
    ],
  });
  try {
    return await openBatch(PROPOSAL, "ev-1", true, ATTEMPT, TRONG_NHOM);
  } finally {
    tra();
  }
}

async function phat(senderId) {
  const tra = mayChuTraLoi({
    guest_links: [
      {
        sender_id: senderId,
        path: "/g/tok-1",
        obligations: [{ obligation_id: "o-1", amount_vnd: 505094, vietqr_payload: "000201" }],
      },
      {
        sender_id: TRANG,
        path: "/g/tok-2",
        obligations: [{ obligation_id: "o-2", amount_vnd: 374262, vietqr_payload: "000201" }],
      },
    ],
  });
  try {
    return await publishBatch(
      "b-1",
      { payerAcknowledged: true },
      MINH,
      ATTEMPT,
      TREN_BILL,
      TRONG_NHOM,
    );
  } finally {
    tra();
  }
}

/** Markup with tags stripped, which is what a person actually reads. */
function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

/* -- the boundary where the names are minted -------------------------------- */

test("openBatch không đặt tên người bằng id máy chủ gửi về", async () => {
  const batch = await moDotThu(NGOC);
  for (const o of batch.obligations) {
    assert.equal(
      HINH_DANG_UUID.test(o.senderName),
      false,
      `senderName là id: ${o.senderName}`,
    );
    assert.equal(
      HINH_DANG_UUID.test(o.recipient),
      false,
      `recipient là id: ${o.recipient}`,
    );
  }
});

test("publishBatch không đặt tên người bằng id máy chủ gửi về", async () => {
  const envelopes = await phat(NGOC);
  for (const e of envelopes) {
    assert.equal(
      HINH_DANG_UUID.test(e.senderName),
      false,
      `senderName là id: ${e.senderName}`,
    );
  }
});

/* A fix that answers TEN_CHUA_BIET for everybody passes every case above and
 * makes the collection board unreadable. Ngọc is in the group, so she has a
 * name and it has to be hers. */
test("người trong nhóm mà không có trên bill vẫn hiện đúng tên", async () => {
  const batch = await moDotThu(NGOC);
  const ngoc = batch.obligations.find((o) => o.senderId === NGOC);
  assert.equal(ngoc.senderName, "Ngọc", `mất tên Ngọc: ${ngoc.senderName}`);

  const envelopes = await phat(NGOC);
  assert.equal(
    envelopes.find((e) => e.senderId === NGOC).senderName,
    "Ngọc",
    "mất tên Ngọc ở phong bì",
  );
});

test("người có trên bill vẫn hiện đúng tên của họ", async () => {
  const batch = await moDotThu(NGOC);
  const trang = batch.obligations.find((o) => o.senderId === TRANG);
  assert.equal(trang.senderName, "Trang", `hỏng tên vốn đã đúng: ${trang.senderName}`);
  assert.equal(trang.recipient, "Minh", `hỏng tên người nhận: ${trang.recipient}`);
});

/* Nobody can name this person. That is allowed to be a word; it is not allowed
 * to be an id, and it is not allowed to be eight hex characters of one -- a
 * slice still looks like something the reader ought to recognise. */
test("người không ai biết tên thì nói ra, không in id", async () => {
  const batch = await moDotThu(LA);
  const la = batch.obligations.find((o) => o.senderId === LA);
  assert.equal(la.senderName, TEN_CHUA_BIET, `không phải "${TEN_CHUA_BIET}": ${la.senderName}`);
  assert.equal(
    la.senderName.includes(LA.slice(0, 8)),
    false,
    `tiền tố id lọt ra: ${la.senderName}`,
  );

  const envelopes = await phat(LA);
  const phongBi = envelopes.find((e) => e.senderId === LA);
  assert.equal(phongBi.senderName, TEN_CHUA_BIET, `phong bì in id: ${phongBi.senderName}`);
});

/* -- and what a person actually sees ---------------------------------------- */

test("bảng đợt thu không in id ở chỗ đặt tên", async () => {
  const batch = await moDotThu(NGOC);
  const read = words(
    React.createElement(DotThu, {
      obligations: batch.obligations,
      published: false,
      gates: { payerAcknowledged: true },
      onPublish: () => {},
      onShare: () => {},
      onRefresh: () => {},
      onConfirmReceipt: () => {},
      busy: false,
    }),
  );
  const lot = read.match(HINH_DANG_UUID);
  assert.equal(lot, null, `id lọt ra bảng đợt thu: ${lot?.[0]} trong "${read}"`);
  assert.ok(read.includes("Ngọc"), `mất tên Ngọc ở bảng đợt thu: ${read}`);
});

test("màn chia sẻ không in id ở chỗ đặt tên", async () => {
  const envelopes = await phat(NGOC);
  const read = words(React.createElement(ChiaSe, { envelopes, onDone: () => {} }));
  const lot = read.match(HINH_DANG_UUID);
  assert.equal(lot, null, `id lọt ra màn chia sẻ: ${lot?.[0]} trong "${read}"`);
  assert.ok(read.includes("Ngọc"), `mất tên Ngọc ở màn chia sẻ: ${read}`);
});
