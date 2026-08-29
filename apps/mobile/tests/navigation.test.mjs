/* The shell's acceptance criteria, as assertions rather than as taps.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * rd-do-fe-02 asks for three things: five tab slots that each reach a screen,
 * a [+] that opens a menu of four, and an opening screen that does not pretend
 * to have signed anybody in. The first two are structural and are checked
 * here. What this file cannot check is that any of it *renders* -- that is the
 * `expo export` build plus the screenshots in the PR, and the split is the
 * point: a green run here is not a claim about pixels.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  CREATE_ACTIONS,
  DEFAULT_TAB,
  TABS,
  tabById,
  unreachableTabs,
} from "../dist-test/navigation/tabs.js";
import { DEMO_PEOPLE, personById } from "../dist-test/navigation/nhom-demo.js";

/* ------------------------------------------------------------------ tabs --- */

test("bốn tab điều hướng, cộng nút [+] ở giữa là năm ô", () => {
  // The bar draws five slots; four of them are destinations and the middle
  // one is an action. Asserting four here is what keeps [+] from quietly
  // becoming a fifth tab that can be "selected" onto a blank screen.
  assert.equal(TABS.length, 4);
  assert.deepEqual(
    TABS.map((t) => t.label),
    ["Khám phá", "Lên plan", "Tin nhắn", "Cá nhân"],
  );
});

test("mỗi tab tới được một màn — không ô nào rơi vào khoảng trắng", () => {
  assert.deepEqual(unreachableTabs(), []);
  for (const tab of TABS) {
    assert.ok(tab.destination.screen, `${tab.id} không có màn`);
    assert.equal(typeof tab.destination.screen, "string");
  }
});

test("id tab không trùng nhau", () => {
  const ids = TABS.map((t) => t.id);
  assert.equal(new Set(ids).size, ids.length);
});

test("tab mặc định là một tab có thật", () => {
  assert.ok(tabById(DEFAULT_TAB), `${DEFAULT_TAB} không nằm trong TABS`);
});

test("tabById trả null cho id lạ, không ném và không đoán", () => {
  assert.equal(tabById("khong-co-tab-nay"), null);
});

test("mỗi tab có nhãn cho trình đọc màn hình, dài hơn nhãn hiển thị", () => {
  for (const tab of TABS) {
    assert.ok(tab.a11yLabel.length > tab.label.length, `${tab.id} thiếu mô tả`);
  }
});

test("màn còn là vỏ thì khai ra chủ và việc sẽ dựng nó", () => {
  // The honesty rule, enforced rather than trusted: a placeholder must name
  // who builds the real screen, so a tab cannot go stale as an anonymous stub.
  for (const tab of TABS) {
    if (tab.destination.kind !== "shell") continue;
    assert.ok(tab.destination.owner, `${tab.id} không nói ai dựng`);
    assert.ok(tab.destination.work, `${tab.id} không nói việc nào dựng`);
  }
});

/* ------------------------------------------------------------ menu [+] --- */

test("nút [+] mở đúng bốn mục", () => {
  assert.equal(CREATE_ACTIONS.length, 4);
  assert.deepEqual(
    CREATE_ACTIONS.map((a) => a.label),
    ["Tạo chuyến", "Tạo khoản chi", "Kỷ niệm nhóm", "Tạo nhóm"],
  );
});

test("mỗi mục có một dòng giải thích, không phải bốn động từ trần", () => {
  for (const a of CREATE_ACTIONS) {
    assert.ok(a.hint.trim(), `${a.id} không có gợi ý`);
  }
});

test("cả bốn mục đã nối sau khi gộp #130 và #131", () => {
  // This is the assertion that keeps the menu honest. If a later change wires
  // up another action, this test fails and forces the flag to be updated
  // rather than letting shells quietly keep claiming to work -- or letting a
  // working feature keep wearing the "vỏ" mark.
  //
  // Resolution of the #130 x #131 merge conflict. Each PR flipped a
  // different action to built and each rewrote this list to three; the union
  // is four. Written by QA to answer "does the combination hold", not shipped
  // as the authors' resolution.
  const built = CREATE_ACTIONS.filter((a) => a.built);
  assert.deepEqual(built.map((a) => a.id), [
    "tao-chuyen",
    "tao-khoan-chi",
    "dang-ky-niem",
    "tao-nhom",
  ]);
});

/* ------------------------------------------------------------ nhóm demo --- */

test("nhóm demo có người, và mỗi người có tên lẫn chữ tắt", () => {
  assert.ok(DEMO_PEOPLE.length >= 2);
  for (const p of DEMO_PEOPLE) {
    assert.ok(p.name.trim(), `${p.id} không có tên`);
    assert.ok(p.initials.trim(), `${p.id} không có chữ tắt`);
  }
});

test("id người trong nhóm demo không trùng nhau", () => {
  const ids = DEMO_PEOPLE.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length);
});

test("id vẫn là slug, còn id thật đi riêng ở personId", () => {
  // Hai trường, không phải một. `id` là slug vì một UUID độn số không đọc
  // được ở chỗ gọi, và vì bản thân repo guard đọc dãy số dài như số tài
  // khoản. `personId` là hàng thật trong database đã gieo, và màn Cá nhân là
  // màn đầu tiên cần tới nó — đúng như ghi chú cũ trong nhom-demo.ts đoán.
  for (const p of DEMO_PEOPLE) {
    assert.doesNotMatch(p.id, /^[0-9a-f]{8}-[0-9a-f]{4}-/i, `${p.id} trông như UUID`);
    assert.match(
      p.personId,
      /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      `${p.id} thiếu personId dạng uuid5`,
    );
  }
});

test("personId không trùng nhau — hai người chung id là hai người chung ví tiền", () => {
  const ids = DEMO_PEOPLE.map((p) => p.personId);
  assert.equal(new Set(ids).size, ids.length);
});

test("personById trả null cho người không có", () => {
  assert.equal(personById("khong-ai"), null);
  assert.ok(personById(DEMO_PEOPLE[0].id));
});
