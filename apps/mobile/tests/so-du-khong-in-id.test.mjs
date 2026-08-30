/* The debt panel on `goi-y` must not print a database id where a name goes.
 *
 * Measured on main @ 880cd6d, on a one-shot stack with the seeded demo group,
 * walking Google -> Minh -> Tạo mới -> Tạo khoản chi -> Chọn ảnh bill ->
 * Tiếp tục -> Thêm Minh -> Thêm Trang. The block "Trước bữa này, nhóm còn nợ
 * nhau" read, all three rows at once:
 *
 *     e3a44e25-4547-508a-8f4d-9b2495c3325f trả Minh 505.094đ
 *     Trang trả Minh 374.262đ
 *     cdadf49b-b6a8-5631-8b9d-aee6a7d532de trả Minh 197.215đ
 *
 * Those two ids are Ngọc and Linh -- `DEMO_PEOPLE` in `navigation/nhom-demo.ts`
 * derives them, and `tests/tin-nhan.test.mjs` re-derives them from the seed. So
 * the app was holding both names the whole time. Two lookups exist on this
 * screen and it was using the narrower one:
 *
 *   - `roster` is who is on THIS BILL. It had Minh and Trang, because those
 *     are the two a person had just tapped in.
 *   - `nhom` is the group's active membership, already a prop of `GoiYChia`
 *     because the "Thêm ... vào nhóm" buttons are built from it. It had all
 *     seven.
 *
 * `/contexts/{id}/balances` answers for the ledger of the whole group, not for
 * the bill being typed, so it names people who are legitimately absent from
 * `roster` -- and `labelFor` returns the id it was handed when it cannot place
 * one. The result is a money row addressed to a UUID, sitting beside a money
 * row addressed to a person, in the same block.
 *
 * The panel below it has the same shape and the same cause: `Máy chủ chia thử`
 * draws `ketQua.allocations`, whose keys come from the server against the
 * roster the SERVER holds -- which is the entire reason that card is worth
 * pressing. It is pinned here too rather than left as the second acquittal
 * path for one bug.
 *
 * What this file pins: no id reaches the reader, and a name the app actually
 * holds is used rather than the fallback word. It renders the whole `GoiYChia`
 * rather than the panel alone, on purpose -- repairing the panel while leaving
 * `nhom` unpassed at the call site is a fix that renders exactly the defect
 * this was filed for.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GoiYChia } from "../dist-test/screens/GoiYChia.js";
/* The word for a person nobody can name is one constant for the whole app, and
 * it already lives here because the chat bubble needed it first. Imported
 * rather than re-declared: the member list and this money row drifting into two
 * different words for one state is the thing that constant exists to stop. */
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

/* The real ids off the seeded group, not invented ones. A test written with
 * `"aaaa-..."` would pass on a fix that special-cased the demo people. */
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f";
const HAI = "be2389f9-62cb-5b28-8e5f-874768e9fb75";
const NGOC = "e3a44e25-4547-508a-8f4d-9b2495c3325f";
const LINH = "cdadf49b-b6a8-5631-8b9d-aee6a7d532de";
/* Nobody: in the ledger of this group, absent from its active membership. A
 * member who left still owes what they owed. */
const LA = "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8";

function line(id, name, amount) {
  return {
    id,
    name,
    quantity: 1,
    lineTotalVnd: amount,
    read: { name, quantity: 1, lineTotalVnd: amount },
  };
}

const READING = {
  lines: [line("mon-0", "Bún bò Huế", 65000)],
  printedTotalVnd: 65000,
  needsReview: false,
  warnings: [],
};

/** Who is on the bill: the two a person tapped in on this screen. */
const ROSTER = {
  participants: [
    { id: MINH, name: "Minh" },
    { id: TRANG, name: "Trang" },
  ],
  advancerId: MINH,
};

/** Who is in the group. `nguoiCoTheChia` in `App.tsx` builds this from
 *  `GET /contexts/{id}/members`, filtered to active. */
const NHOM = [
  { id: MINH, name: "Minh" },
  { id: TRANG, name: "Trang" },
  { id: HAI, name: "Hải" },
  { id: NGOC, name: "Ngọc" },
  { id: LINH, name: "Linh" },
];

/** The measured reply, ids and dong as they were reported. */
const SO_DU = {
  netByPerson: {},
  transfers: [
    { fromId: NGOC, toId: MINH, amountVnd: 505094 },
    { fromId: TRANG, toId: MINH, amountVnd: 374262 },
    { fromId: LINH, toId: MINH, amountVnd: 197215 },
  ],
  provenMinimal: true,
};

function manGoiY(over = {}) {
  return words(
    React.createElement(GoiYChia, {
      reading: READING,
      roster: ROSTER,
      nhom: NHOM,
      assignment: { "mon-0": [MINH, TRANG] },
      preview: null,
      bill: null,
      soDu: SO_DU,
      onBack: () => {},
      onReset: () => {},
      onToggle: () => {},
      onAddMember: () => {},
      onRemovePerson: () => {},
      onSeeResults: () => {},
      ...over,
    }),
  );
}

/** Any UUID at all, wherever it sits. Written as a shape rather than as the
 *  three ids above so a fix that resolves Ngọc and leaves Linh cannot pass. */
const HINH_DANG_UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

test("khối nợ cũ không in id ra chỗ đặt tên", () => {
  const read = manGoiY();
  const lot = read.match(HINH_DANG_UUID);
  assert.equal(lot, null, `id lọt ra màn hình: ${lot?.[0]} trong "${read}"`);
});

test("người trong nhóm mà không có trên bill vẫn hiện đúng tên", () => {
  const read = manGoiY();
  assert.ok(read.includes("Ngọc"), `mất tên Ngọc: ${read}`);
  assert.ok(read.includes("Linh"), `mất tên Linh: ${read}`);
});

/* The row that was already right has to stay right. A fix that labels everyone
 * with the fallback word passes the first test and destroys the screen. */
test("người có trên bill vẫn hiện đúng tên của họ", () => {
  const read = manGoiY();
  assert.ok(read.includes("Trang trả Minh"), `hỏng dòng vốn đã đúng: ${read}`);
});

test("người không ai biết tên thì nói ra, không in id", () => {
  const read = manGoiY({
    soDu: { ...SO_DU, transfers: [{ fromId: LA, toId: MINH, amountVnd: 12000 }] },
  });
  assert.equal(read.match(HINH_DANG_UUID), null, `id lọt ra màn hình: ${read}`);
  assert.ok(read.includes(TEN_CHUA_BIET), `thiếu "${TEN_CHUA_BIET}": ${read}`);
});

/* Eight hex characters are a valid-looking word, so a fix that sliced the id
 * would satisfy the UUID shape above and print `e3a44e25` at a person. Same
 * trap `ten-nguoi-la.test.mjs` pins for the chat bubble. */
test("tám ký tự hex đầu của id cũng không được coi là tên", () => {
  const read = manGoiY();
  for (const id of [NGOC, LINH]) {
    assert.ok(!read.includes(id.slice(0, 8)), `tiền tố id lọt ra màn hình: ${read}`);
  }
});

/* `labelFor` numbers people who share a display name so two of them can be
 * told apart. Widening the lookup to the group must not lose that, and the
 * numbering has to count across BOTH lists -- a Nam on the bill and a Nam who
 * is only in the group are two people, and one unnumbered "Nam" on a money row
 * is the ambiguity that rule exists to remove. */
test("hai người trùng tên vẫn được đánh số, kể cả khi một người không có trên bill", () => {
  /* All hex letters. A padded literal like `1111...` is a 32-digit run and the
   * repo guard blocks it on sight, unable to tell a test id from an account
   * number -- the same reason `nhom-demo.ts` derives its ids through uuid5. */
  const NAM_A = "aaaaaaaa-bbbb-5ccc-8ddd-eeeeeeeeeeee";
  const NAM_B = "bbbbbbbb-cccc-5ddd-8eee-ffffffffffff";
  const read = manGoiY({
    roster: { participants: [{ id: NAM_A, name: "Nam" }], advancerId: NAM_A },
    nhom: [
      { id: NAM_A, name: "Nam" },
      { id: NAM_B, name: "Nam" },
    ],
    assignment: { "mon-0": [NAM_A] },
    soDu: {
      netByPerson: {},
      transfers: [{ fromId: NAM_B, toId: NAM_A, amountVnd: 50000 }],
      provenMinimal: false,
    },
  });
  assert.ok(read.includes("Nam #2 trả Nam #1"), `mất số phân biệt hai người trùng tên: ${read}`);
});
