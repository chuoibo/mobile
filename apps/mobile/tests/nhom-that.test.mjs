/* Người trong ma trận chia tiền phải là người CÓ THẬT trong nhóm.
 *
 * Lỗi được báo (bug-125301), đo trên chromium 390x844 với DB đã `make demo`:
 * màn "Gợi ý chia theo người" mở ra với nhóm rỗng và cách duy nhất để thêm
 * người là gõ tên vào một ô chữ. Gõ "Hải" không tìm ra Hải; nó đúc một UUID
 * ngẫu nhiên mới. Sau khi ghi vào sổ, bảng `people` có ba hàng tên Hải:
 *
 *     be2389f9-62cb-5b28-8e5f-874768e9fb75   <- Hải thật, uuid5 từ seed_demo_data
 *     e21109db-...                           <- người lạ, do gõ tên sinh ra
 *     8bcb84a6-...                           <- người lạ, do gõ tên sinh ra
 *
 * và 329.667đ rơi vào `8bcb84a6`. Phép chia đúng tuyệt đối -- tổng ba phần
 * bằng đúng 989.000 -- nhưng nó được ghi cho một người không tồn tại, nên tab
 * "Cá nhân" của Hải thật không bao giờ nhúc nhích. Đây là lỗi TIỀN, không phải
 * lỗi giao diện: sổ cái đúng, chủ sở hữu của con số thì sai.
 *
 * Điều kiện để tin file này:
 *
 *   `personId` trong `nhom-demo.ts` chính là hàng trong DB đã seed. Không phải
 *   file này chứng minh điều đó -- `services/api/tests/test_demo_identity_
 *   matches_seed.py` dẫn xuất lại từng ký tự từ `scripts/seed_demo_data.py` và
 *   đỏ nếu một ký tự xê dịch. Nên khẳng định "id này là người thật" ở đây là
 *   bắc cầu qua cổng đó, chứ không phải lời hứa.
 *
 * File này KHÔNG chứng minh: rằng máy chủ chấp nhận các id ấy, rằng màn Cá
 * nhân đọc lại đúng, hay rằng đường đi thật sự chạy end-to-end. Nó chứng minh
 * cái mà một lần render thấy được: màn chia mời người dùng chọn trong nhóm, và
 * id đi ra khỏi màn là id của nhóm chứ không phải id mới đúc.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GoiYChia, VUNG_CUON_MA_TRAN } from "../dist-test/screens/GoiYChia.js";
import { Field } from "../dist-test/ui/Kit.js";
import { DEMO_PEOPLE } from "../dist-test/navigation/nhom-demo.js";
import {
  addMember,
  availableMembers,
  groupMembers,
} from "../dist-test/participants.js";

/* --------------------------------------------------------------- markup --- */

/** Every element in `html`, as `{ name, attrs }`. Attribute order is React's,
 *  so tests compare sets and values, never the serialised string. Same reader
 *  as `aria-state.test.mjs`, on purpose. */
function elements(html) {
  return [...html.matchAll(/<([a-z]+)\s([^>]*?)\/?>/g)].map(([, name, raw]) => ({
    name,
    attrs: Object.fromEntries(
      [...raw.matchAll(/([\w-]+)="([^"]*)"/g)].map(([, key, value]) => [key, value]),
    ),
  }));
}

function labels(html) {
  return elements(html)
    .map((el) => el.attrs["aria-label"])
    .filter((value) => value !== undefined);
}

/* ------------------------------------------------------------- fixtures --- */

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
  lines: [line("mon-0", "Bún bò Huế", 65000), line("mon-1", "Chả giò", 45000)],
  printedTotalVnd: 110000,
  needsReview: false,
  warnings: [],
};

const NHOM = groupMembers(DEMO_PEOPLE);
const HAI = NHOM.find((m) => m.name === "Hải");
const TRANG = NHOM.find((m) => m.name === "Trang");
const MINH = NHOM.find((m) => m.name === "Minh");

const RONG = { participants: [], advancerId: null };

function manChia(roster, assignment = {}) {
  return renderToStaticMarkup(
    React.createElement(GoiYChia, {
      reading: READING,
      roster,
      nhom: NHOM,
      assignment,
      preview: null,
      onBack: () => {},
      onReset: () => {},
      onToggle: () => {},
      onAddMember: () => {},
      onRemovePerson: () => {},
      onSeeResults: () => {},
    }),
  );
}

/* ------------------------------------------------- 1. danh tính là tiền --- */

test("nhóm demo mang đúng id của hàng trong DB, không phải slug", () => {
  // The whole fix rests on this mapping: what the screen calls a member id is
  // the `people` row the API will be asked to allocate against.
  assert.equal(NHOM.length, DEMO_PEOPLE.length);
  for (const person of DEMO_PEOPLE) {
    const member = NHOM.find((m) => m.name === person.name);
    assert.ok(member, `thiếu ${person.name} trong nhóm`);
    assert.equal(member.id, person.personId);
    assert.notEqual(member.id, person.id, "id gửi đi phải là personId, không phải slug");
  }
  // The exact row from the bug report, spelled out so a silent edit to
  // `nhom-demo.ts` cannot quietly re-open this defect.
  assert.equal(HAI.id, "be2389f9-62cb-5b28-8e5f-874768e9fb75");
});

test("thêm người từ nhóm giữ nguyên id của họ, không đúc id mới", () => {
  const roster = addMember(RONG, HAI);
  assert.deepEqual(roster.participants, [{ id: HAI.id, name: "Hải" }]);
});

test("thêm hai lần cùng một người không tạo ra hai người", () => {
  const once = addMember(RONG, HAI);
  const twice = addMember(once, HAI);
  assert.deepEqual(twice.participants, once.participants);
});

test("thêm người không bao giờ dời người đã chọn trả trước", () => {
  const roster = addMember({ participants: [], advancerId: HAI.id }, TRANG);
  assert.equal(roster.advancerId, HAI.id);
});

test("đi lại đúng bước 5 của phiếu lỗi thì ba id là ba người thật", () => {
  // "Bấm 'Thêm', gõ 'Hải', bấm nút 'Thêm'. Lặp cho Trang, Minh." -- the same
  // three people, now chosen instead of typed.
  let roster = RONG;
  for (const member of [HAI, TRANG, MINH]) roster = addMember(roster, member);

  const ids = roster.participants.map((p) => p.id);
  assert.deepEqual(ids, [HAI.id, TRANG.id, MINH.id]);
  // Every id the screen will send belongs to somebody the seeded database has
  // heard of. That is exactly the sentence that was false before the fix.
  const cuaNhom = new Set(DEMO_PEOPLE.map((p) => p.personId));
  for (const id of ids) assert.ok(cuaNhom.has(id), `${id} không phải người trong nhóm`);
});

test("ai đã trong nhóm thì không còn nằm trong danh sách mời thêm", () => {
  const roster = addMember(RONG, HAI);
  const conLai = availableMembers(roster, NHOM);
  assert.equal(conLai.length, NHOM.length - 1);
  assert.ok(!conLai.some((m) => m.id === HAI.id));
});

/* --------------------------------------------- 2. màn hình mời chọn ai --- */

test("nhóm rỗng thì màn chia mời chọn từng người trong nhóm, không bắt gõ tên", () => {
  // The dead end in the report: "Chưa có ai trong nhóm. Thêm người bằng nút +
  // ở trên." followed by a text box. With nobody in the roster there is
  // nothing else to do on this screen, so the group is on screen already.
  const html = manChia(RONG);
  const ten = labels(html);
  for (const member of NHOM) {
    assert.ok(
      ten.includes(`Thêm ${member.name} vào nhóm`),
      `không mời được ${member.name}: ${JSON.stringify(ten)}`,
    );
  }
});

test("màn chia không còn ô gõ tên tự do — gõ tên là cách đúc ra người lạ", () => {
  // Asserted on the source, not only on one render, and the difference
  // matters. The box that caused this bug was behind a press: it appeared
  // only after "Thêm" was tapped, so a static render of the opening state
  // shows no input and would pass while the defect sat one tap away.
  // `renderToStaticMarkup` cannot tap. What can be checked without a browser
  // is that the screen no longer has a text box to reveal.
  const src = readFileSync(new URL("../src/screens/GoiYChia.tsx", import.meta.url), "utf8");
  assert.ok(
    !/\bField\b/.test(src),
    "GoiYChia còn dùng Field: một ô chữ trên màn này là một cách đúc người lạ",
  );
  assert.deepEqual(
    elements(manChia(RONG)).filter((el) => el.name === "input"),
    [],
    "còn một ô nhập trên màn chia",
  );
});

test("người đã thêm hiện ra, và phần nhóm còn lại vẫn tới được", () => {
  // Mounted with somebody already on the bill -- the state returning from
  // "Sửa lại" lands in. Here the matrix is the point, so the picker is folded
  // away behind the "+" rather than sitting above the table; what has to hold
  // is that the rest of the group is still reachable and named.
  //
  // Not covered here: that the list stays open while somebody adds three
  // people in a row. That is internal state, and `renderToStaticMarkup`
  // cannot press a button. The browser pass is what measures it.
  const ten = labels(manChia(addMember(RONG, HAI)));
  assert.ok(ten.includes("Hải"), "không thấy Hải trong dải người đã thêm");
  assert.ok(
    !ten.includes("Thêm Hải vào nhóm"),
    "vẫn mời thêm Hải lần nữa dù Hải đã ở trong nhóm",
  );
  assert.ok(
    ten.includes("Thêm người từ nhóm"),
    `không còn lối nào tới phần nhóm chưa thêm: ${JSON.stringify(ten)}`,
  );
});

test("cả nhóm đã có mặt thì không còn nút mời thêm rỗng", () => {
  let roster = RONG;
  for (const member of NHOM) roster = addMember(roster, member);
  const ten = labels(manChia(roster));
  assert.ok(
    !ten.includes("Thêm người từ nhóm"),
    "còn nút '+' dù không còn ai để mời — bấm vào sẽ mở ra một danh sách rỗng",
  );
});

/* ------------------------------------------------ 3. ba lỗi nhỏ cùng màn --- */

test("vùng cuộn của ma trận có điểm dừng bàn phím", () => {
  // axe `scrollable-region-focusable` (serious, WCAG 2.1.1) fired here and on
  // none of the other four screens. With nobody in the roster the matrix has
  // no checkbox in it at all, so the region holds nothing focusable and no key
  // scrolls it -- the dishes below the fold cannot be read.
  const vung = elements(manChia(RONG)).filter((el) => el.attrs.id === VUNG_CUON_MA_TRAN);
  assert.equal(vung.length, 1, "không tìm thấy vùng cuộn ma trận");
  assert.equal(vung[0].attrs.tabindex, "0");
});

test("ô nhập trong Kit có tên khả truy cập, không chỉ có placeholder", () => {
  // Reported as: aria-label=null, no label[for], no aria-labelledby, so a
  // screen reader read only the placeholder -- and a placeholder is one
  // example name, not a label.
  const html = renderToStaticMarkup(
    React.createElement(Field, {
      label: "Tổng tiền",
      value: "",
      onChangeText: () => {},
      placeholder: "480000",
    }),
  );
  const input = elements(html).find((el) => el.name === "input");
  assert.ok(input, "Field không render ra input");
  assert.equal(input.attrs["aria-label"], "Tổng tiền");
});

test("Enter trong ô nhập gửi đi được, không bắt buộc phải bấm nút", () => {
  // Reported as: typing a name then pressing Enter did nothing. The box that
  // defect was found in is gone, but `Field` is shared by every form here, so
  // the capability is asserted on `Field` rather than on the screen.
  let gui = 0;
  const html = renderToStaticMarkup(
    React.createElement(Field, {
      label: "Tổng tiền",
      value: "",
      onChangeText: () => {},
      onSubmitEditing: () => { gui += 1; },
    }),
  );
  const input = elements(html).find((el) => el.name === "input");
  assert.ok(input, "Field không render ra input");
  // `renderToStaticMarkup` cannot press a key, so what is asserted here is the
  // shape react-native-web needs to deliver one: a submit-capable input rather
  // than a bare text box. The press itself is covered by the browser pass.
  //
  // Read case-insensitively. React serialises this one as `enterKeyHint`, HTML
  // attribute names are case-insensitive, and pinning React's spelling would
  // make this test fail on a rename that changes nothing a browser sees.
  const hint = Object.entries(input.attrs)
    .find(([key]) => key.toLowerCase() === "enterkeyhint");
  assert.ok(hint, `input không khai enterKeyHint: ${JSON.stringify(input.attrs)}`);
  assert.equal(hint[1], "done");
  assert.equal(gui, 0);
});
