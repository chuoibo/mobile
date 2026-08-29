/* A person the app does not recognise must not be shown their database id.
 *
 * `nguoiTheoAuthor` resolves a name by searching `DEMO_PEOPLE`, the seven
 * hard-coded demo people. Everybody else fell through to
 * `authorId.slice(0, 8)` -- the first eight hex characters of a UUID, printed
 * where a human name goes. On the group-chat screen that reads:
 *
 *     ? 2bb00000
 *     Tao đói rồi, chốt sớm đi.
 *
 * That is not a corner case. The two group flows that are actually built --
 * "Tạo nhóm" (F03/F04) and the friend QR card (F05, `ban` in `lien-ket.ts`)
 * -- both add people who are, by construction, not in `DEMO_PEOPLE`. So the
 * first real person to join a group becomes a hex string in the thread and in
 * the member list, on the one screen whose whole point is that a group is
 * talking to each other.
 *
 * The reason it cannot simply be fixed by looking the name up: the server does
 * not send one. `MembershipResponse` is
 * `id, context_id, person_id, state, role, invited_by_id, joined_at, left_at,
 * created_at` and `MessageResponse` carries `author_id` and no name, and there
 * is no `GET /people/{id}` -- only `PUT`. Until one of those carries a
 * `display_name`, the honest thing on screen is a word that says "we do not
 * know who this is", not an identifier that looks like we do.
 *
 * So what this file pins is narrow and deliberate: no raw id reaches the
 * reader. It does not pin "the right name is shown", because with today's API
 * the client has no way to know it -- that half is filed against the backend
 * lane, and when it lands this test still passes and a new one asserts the
 * name.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { BongBong } from "../dist-test/screens/chat/BongBong.js";
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

const LA = "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8";

function message(over = {}) {
  return {
    id: "5ee4fc1b-4a7d-4c5e-8f6b-e1a9b3c7d5f0",
    context_id: "1aa0be7f-9c3d-4e1a-8b2f-a7c5d9e3f1b6",
    author_id: LA,
    kind: "text",
    body: "Tao đói rồi, chốt sớm đi.",
    image_url: null,
    card: null,
    created_at: "2026-08-29T12:01:00Z",
    cursor: "c2",
    ...over,
  };
}

/* `dauChuoi` is what puts the name row on screen at all -- it marks the first
 * bubble of a run by one person, so the name is not repeated on every line.
 * Leaving it out renders a bubble with no name row, and the two "no id on
 * screen" assertions below then pass on markup that never had a name in it.
 * They did, on the first run of this file. */
function bubble(over = {}, nguoiGui = null) {
  return words(
    React.createElement(BongBong, {
      message: message(over),
      nguoiGui,
      cuaMinh: false,
      dauChuoi: true,
    }),
  );
}

test("tin nhắn của người lạ không in id ra chỗ đặt tên", () => {
  const read = bubble();
  assert.ok(!read.includes(LA.slice(0, 8)), `id lọt ra màn hình: ${read}`);
  assert.ok(!/[0-9a-f]{8}-[0-9a-f]{4}/.test(read), `UUID lọt ra màn hình: ${read}`);
});

test("chỗ đặt tên có một từ người đọc hiểu, không phải một ô trống", () => {
  assert.ok(bubble().includes(TEN_CHUA_BIET), `thiếu "${TEN_CHUA_BIET}"`);
});

/* An id is not the only shape of leak: eight hex characters happen to be a
 * valid-looking word, so a test that only searched for dashes would pass on
 * exactly the string this bug printed. */
test("tám ký tự hex đầu của id cũng không được coi là tên", () => {
  const read = bubble({ author_id: "deadbeef-1a2b-4c3d-8e4f-a5b6c7d8e9f0" });
  assert.ok(!read.includes("deadbeef"), `tiền tố id lọt ra màn hình: ${read}`);
});

test("người app biết tên thì vẫn hiện đúng tên của họ", () => {
  const read = bubble({}, { name: "Trang", initials: "T" });
  assert.ok(read.includes("Trang"), `mất tên thật: ${read}`);
  assert.ok(!read.includes(TEN_CHUA_BIET), `đè lên tên thật: ${read}`);
});

/* Not a name case at all, and worth pinning so a later edit does not make it
 * one: `author_id: null` is how a message says it came from the AI, so the
 * bubble takes the AI header rather than any person row. The `"Ẩn danh"`
 * branch inside `HangNguoi` is therefore unreachable today -- left alone here
 * rather than deleted, because `cuaAi` is the thing that decides it and this
 * file is not where that decision belongs. */
test("tin không có tác giả là tin của AI, không phải một người vô danh", () => {
  const read = bubble({ author_id: null });
  assert.ok(read.includes("Rủ Đi AI"), `mất nhãn AI: ${read}`);
  assert.ok(!read.includes(TEN_CHUA_BIET), `gọi AI là người: ${read}`);
});
