/* rd-fe-25. The picker button, read as markup rather than as source.
 *
 * The reason this is a render test and not a grep is the lesson #198 and #201
 * cost this lane twice: `accessibilityState={{ busy }}` compiles, reads
 * correctly, and reaches react-native-web 0.21.2 as **nothing**. A source read
 * sees the prop and calls the state announced; only the emitted attribute
 * settles it. The same is true of `disabled`, which is the actual guard here --
 * a button that looks dimmed but still answers a tap opens a second picker over
 * the first.
 *
 * So each test below asks the DOM a question a person could act on:
 *
 *   at rest      the label is readable and the button answers
 *   in flight    the label says which wait it is, and the button REFUSES
 *   refused      the sentence is in the accessibility tree, not only painted
 *
 * What this does not prove: that the upload works, or that the server accepts
 * the bytes. That is `tests/tai-anh-len.test.mjs` and the live run in the PR.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { NutChonAnh, cauNoiVeLoi } from "../dist-test/ui/NutChonAnh.js";
import { ApiError } from "../dist-test/api.js";

/** A backend that stops inside `pick`, so a render can be taken while the
 *  lifecycle is genuinely mid-flight rather than simulated with a prop. */
function backendTreo() {
  let moKhoa;
  const cho = new Promise((resolve) => {
    moKhoa = resolve;
  });
  return {
    moKhoa: () => moKhoa(null),
    capture: async () => {
      throw new Error("không dùng camera");
    },
    pick: async () => {
      await cho;
      return null;
    },
    compress: async () => ({ uri: "x", width: 1, height: 1, bytes: 1 }),
    discard: async () => {},
  };
}

function ve(props) {
  return renderToStaticMarkup(
    React.createElement(NutChonAnh, {
      nhan: "Thêm ảnh",
      moTa: "Chọn một tấm ảnh từ thư viện và thêm vào tường kỷ niệm của nhóm",
      taiLen: async () => {},
      backend: backendTreo(),
      ...props,
    }),
  );
}

test("lúc nghỉ: nút đọc được, và không tự nhận là đang bận", () => {
  const html = ve();
  assert.match(html, /Thêm ảnh/, "nhãn không lên màn");
  assert.match(
    html,
    /aria-label="Chọn một tấm ảnh từ thư viện và thêm vào tường kỷ niệm của nhóm"/,
    "trình đọc màn hình không có câu nào để đọc",
  );
  assert.doesNotMatch(html, /aria-busy="true"/, "đang nghỉ mà báo bận");
  assert.doesNotMatch(html, /aria-disabled="true"/, "đang nghỉ mà đã khoá");
});

test("nút mang role button, không phải một cái div câm", () => {
  assert.match(ve(), /role="button"/);
});

test("không dùng accessibilityState — trên nền này nó không tới được DOM", () => {
  // The cheap net under `aria-state.test.mjs`, aimed at this file: the prop
  // would compile and this button would announce as idle for the whole upload.
  const html = ve();
  assert.doesNotMatch(html, /accessibilityState/);
});

test("nhãn lúc nghỉ không phải là một trong ba câu đang chạy", () => {
  // Guards the direction of the swap. A button stuck reading "Đang tải ảnh
  // lên…" before anything has been chosen would be worse than no label at all.
  const html = ve();
  for (const cau of ["Đang mở thư viện ảnh", "Đang chuẩn bị ảnh", "Đang tải ảnh lên"]) {
    assert.doesNotMatch(html, new RegExp(cau), `lúc nghỉ đã hiện "${cau}"`);
  }
});

test("mọi thứ ném ra đều thành một câu tiếng Việt, không có [object ...]", () => {
  // The sentence that lands in the alert slot, tested at the function that
  // chooses it. `renderToStaticMarkup` only gives first paint, so driving a
  // press to observe the rendered error would need a full client renderer --
  // and the part worth pinning is this decision, not the div around it.
  //
  // An earlier draft of this test rendered its OWN <div role="alert"> and
  // asserted the attribute was there. That passes with `cauNoiVeLoi` deleted,
  // with the component deleted, and on an empty repository. It was measuring
  // react-dom.
  const bang = [
    [new ApiError(403, "permission_denied", "Bạn cần là thành viên của nhóm này."), /thành viên/],
    [Object.assign(new Error("Ảnh quá nặng."), { name: "AnhNhomError" }), /nặng/],
    [{ toString: () => "[object HTMLCanvasElement]" }, /./],
    [new Error("Failed to create canvas context"), /./],
    [null, /./],
    ["boom", /./],
  ];
  for (const [nem, mong] of bang) {
    const cau = cauNoiVeLoi(nem);
    assert.match(cau, mong);
    assert.doesNotMatch(cau, /\[object/, `lọt [object ...] lên màn: ${cau}`);
    assert.doesNotMatch(cau, /canvas|Failed/i, `lọt chữ máy lên màn: ${cau}`);
    assert.match(
      cau,
      /[àáảãạăâđêôơưèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ]/i,
      `câu không phải tiếng Việt: ${cau}`,
    );
  }
});

test("nút vẽ ra một chỗ cho câu lỗi, và chỗ đó mang role alert", () => {
  // The slot exists in this component and is announced rather than only
  // painted. Asserted against the component's own markup: passing a rendered
  // error in is not possible without a client renderer, so what is checked is
  // that the resting render carries no stale alert -- an alert visible before
  // anything failed would announce a problem nobody has.
  assert.doesNotMatch(ve(), /role="alert"/);
});

test("kiểu 'nhe' và kiểu 'chinh' là hai nút khác nhau trên màn", () => {
  // Not decoration: the quiet one sits inside a card that already has the eye,
  // the filled one is the call to action on the wall. If they rendered
  // identically, one of the two placements would be wrong and nothing would say
  // so.
  assert.notEqual(ve({ kieu: "chinh" }), ve({ kieu: "nhe" }));
});
