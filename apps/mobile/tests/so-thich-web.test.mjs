/* F01.03's controls, read out of the markup react-native-web actually emits.
 *
 * The claims here are all about roles, and a role is the class of thing that
 * compiles perfectly while reaching the DOM as something else or as nothing at
 * all. `aria-state.test.mjs` beside this file exists because
 * `accessibilityState` did exactly that on this stack for two separate screens.
 *
 * Three things this screen can get wrong without any of it showing in a
 * screenshot or in a source read:
 *
 *   1. **Tastes are `checkbox`, budget bands are `radio`.** Swapping the pair
 *      compiles and looks identical. It tells somebody using a screen reader
 *      the opposite of what the screen does: that picking a second taste drops
 *      the first, or that the three budget bands accumulate.
 *   2. **The name of a tile is the word, not the word plus a pictograph.** The
 *      emoji is inside the tile; if it leaks into the accessible name, the
 *      control is announced as a pictograph nobody can pronounce back.
 *   3. **The pre-prompt exists before any permission is asked.** The mockup's
 *      rule is that the benefit is explained first and only then does the OS
 *      dialog open. A switch wired straight to the dialog renders the same.
 *
 * What this does NOT prove: anything about iOS or Android, which read the same
 * props through a different library, and nothing about how the screen looks.
 * The detector and a rendered scan cover the second; only a device covers the
 * first.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CaNhanHoa } from "../dist-test/screens/vao-cua/CaNhanHoa.js";
import { NGAN_SACH, SO_THICH } from "../dist-test/screens/vao-cua/so-thich.js";

/** Every element in `html`, as `{ name, attrs }`. Attribute order is React's,
 *  so these tests compare sets and values, never the serialised string. */
function elements(html) {
  return [...html.matchAll(/<([a-z]+)\s([^>]*?)\/?>/g)].map(([, name, raw]) => ({
    name,
    attrs: Object.fromEntries(
      [...raw.matchAll(/([\w-]+)="([^"]*)"/g)].map(([, key, value]) => [key, value]),
    ),
  }));
}

function withRole(html, role) {
  return elements(html).filter((el) => el.attrs.role === role);
}

function ve(props = {}) {
  return renderToStaticMarkup(
    React.createElement(CaNhanHoa, {
      ten: "Kiệt",
      onXong: () => {},
      onQuayLai: () => {},
      ...props,
    }),
  );
}

test("sở thích là checkbox trong một group, không phải radio", () => {
  const html = ve();

  const o = withRole(html, "checkbox");
  assert.equal(
    o.length,
    SO_THICH.length,
    `có ${SO_THICH.length} sở thích nhưng markup ra ${o.length} checkbox`,
  );

  // Cái bẫy: radiogroup ở đây sẽ nói với trình đọc màn hình rằng chọn cái này
  // là bỏ cái kia, ngược hẳn với việc màn làm.
  const nhom = withRole(html, "group");
  assert.ok(nhom.length >= 1, "khối sở thích không có role=group để gom lại");
  assert.ok(
    nhom.some((g) => (g.attrs["aria-label"] ?? "").includes("Sở thích")),
    `group của sở thích không có tên: ${JSON.stringify(nhom.map((g) => g.attrs["aria-label"]))}`,
  );

  // Chưa bấm gì thì không có cái nào được đánh dấu, và mỗi cái PHẢI khai
  // aria-checked -- thiếu hẳn thuộc tính là lỗi axe aria-required-attr, và nó
  // trông y hệt "chưa chọn".
  for (const el of o) {
    assert.equal(
      el.attrs["aria-checked"],
      "false",
      `checkbox "${el.attrs["aria-label"]}" không khai aria-checked`,
    );
  }
});

test("mỗi sở thích được đọc lên bằng đúng cái tên, không kèm hình", () => {
  const html = ve();
  const ten = withRole(html, "checkbox").map((el) => el.attrs["aria-label"]);

  assert.deepEqual(
    [...ten].sort(),
    SO_THICH.map((m) => m.nhan).sort(),
    "tên đọc lên của các ô sở thích không khớp bảng",
  );

  for (const m of SO_THICH) {
    const el = withRole(html, "checkbox").find((x) => x.attrs["aria-label"] === m.nhan);
    assert.ok(el, `không thấy ô "${m.nhan}"`);
    assert.ok(
      !el.attrs["aria-label"].includes(m.hinh),
      `tên đọc lên của "${m.nhan}" có lẫn hình ${m.hinh}`,
    );
  }
});

test("ngân sách là radio trong radiogroup, và ba khoảng đều tới được", () => {
  const html = ve();

  const o = withRole(html, "radio");
  assert.equal(
    o.length,
    NGAN_SACH.length,
    `có ${NGAN_SACH.length} khoảng nhưng markup ra ${o.length} radio`,
  );

  const nhom = withRole(html, "radiogroup");
  assert.equal(nhom.length, 1, `phải có đúng 1 radiogroup, thấy ${nhom.length}`);

  // Tên đọc lên phải mang cả khoảng tiền lẫn chữ mô tả: "Vừa phải" một mình
  // không nói được nó là bao nhiêu, và "100K–250K" một mình bỏ mất thứ giúp
  // so ba lựa chọn với nhau.
  for (const k of NGAN_SACH) {
    const el = o.find((x) => (x.attrs["aria-label"] ?? "").includes(k.nhan));
    assert.ok(el, `không thấy khoảng "${k.nhan}" trong markup`);
    assert.ok(
      el.attrs["aria-label"].includes(k.phu),
      `"${k.nhan}" không đọc kèm "${k.phu}": ${el.attrs["aria-label"]}`,
    );
    assert.equal(el.attrs["aria-checked"], "false", `"${k.nhan}" không khai aria-checked`);
  }
});

test("công tắc danh bạ là switch, và chưa bật thì chưa có lời mời quyền nào", () => {
  const html = ve();

  const o = withRole(html, "switch");
  assert.equal(o.length, 1, `phải có đúng 1 switch, thấy ${o.length}`);
  assert.equal(o[0].attrs["aria-checked"], "false");
  assert.ok(
    (o[0].attrs["aria-label"] ?? "").includes("danh bạ"),
    `switch không có tên nói về danh bạ: ${o[0].attrs["aria-label"]}`,
  );

  // Trạng thái mặc định: chưa có panel giải thích, và chưa có câu kết quả nào.
  // Nếu câu kết quả hiện sẵn thì màn đang khai một thứ chưa xảy ra.
  assert.equal(withRole(html, "status").length, 0, "chưa bấm gì mà đã có dòng kết quả");
  assert.ok(
    !html.includes("Bật đồng bộ"),
    "panel giải thích hiện sẵn khi công tắc còn tắt",
  );
});

test("nút chính và hai lối ra đều là nút bấm được, không phải chữ trơ", () => {
  const html = ve();
  const nhan = withRole(html, "button").map((el) => el.attrs["aria-label"] ?? "");

  // "Bỏ qua" là điều kiện nghiệm thu của mockup: bước này không bắt buộc.
  assert.ok(
    nhan.some((n) => n.includes("Bỏ qua")),
    `không có lối bỏ qua trong ${JSON.stringify(nhan)}`,
  );
  assert.ok(
    nhan.some((n) => n.includes("Quay lại")),
    `không có lối quay lại trong ${JSON.stringify(nhan)}`,
  );
  assert.ok(html.includes("Hoàn tất"), "không thấy nút Hoàn tất");
});

test("chào bằng đúng cái tên vừa đặt ở bước trước", () => {
  // Bước đặt tên ngay trước đó là chỗ lát cắt dọc từng chết. Hiện lại cái tên
  // là bằng chứng rẻ nhất cho người dùng rằng nó đã được ghi.
  assert.ok(ve({ ten: "Kiệt" }).includes("Kiệt"));
  assert.ok(ve({ ten: "Trang" }).includes("Trang"));
});
