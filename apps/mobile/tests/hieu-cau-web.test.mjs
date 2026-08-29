/* Whether the model's reading is actually on screen, in the markup.
 *
 * rd-fe-15 makes one thing non-negotiable: the person has to be shown what the
 * AI took their sentence to mean. The reason is narrow and practical. Someone
 * types "dưới 300k", the model hears 30.000đ, and the screen fills with cheap
 * places or with nothing. Without the reading in front of them the only signal
 * is that the results are odd, and odd results look exactly like a thin
 * catalogue -- so they retype the same sentence and conclude the feature is
 * broken. With "NGÂN SÁCH 30k/người" sitting there, the fix takes one glance.
 *
 * `tim-dia-diem.test.mjs` proves `hieuDuocGi` computes those rows. It cannot
 * prove they were rendered: a component that drops the rows on the floor, or
 * hides them behind a collapsed section, passes every assertion in that file.
 * This one renders through react-native-web -- the same substitution Expo's web
 * build performs -- and reads the emitted markup, which is the form of evidence
 * this repo has already had to learn twice (`accessibilityState` reaching the
 * DOM as nothing, `Field` losing its accessible name).
 *
 * What it proves: the values reach the markup on web, in this renderer. What it
 * does not prove: that iOS and Android draw them, that the panel is readable at
 * a real size, or that the wording is the right wording. The first is a
 * different bridge; the last two are `imp detect` and a person.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CauAiHieu, KhongCoKetQua, TimKhongDuoc } from "../dist-test/screens/kham-pha/CauAiHieu.js";
import { parseUnderstood } from "../dist-test/screens/kham-pha/tim-kiem.js";

/** Markup with tags stripped, which is what a person actually reads. */
function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

const CATS = [{ id: "quan-an-local", label: "Quán ăn local" }];

function understood(over = {}) {
  return parseUnderstood({
    budget_per_person_vnd: 300000,
    group_size: 6,
    max_distance_km: 5,
    categories: ["quan-an-local"],
    traits: ["Ngoài trời"],
    ...over,
  });
}

/* --------------------------------------------- the reading is on screen -- */

test("cả năm điều AI hiểu đều nằm trong markup, không chỉ trong hàm tính", () => {
  const html = words(React.createElement(CauAiHieu, { understood: understood(), categories: CATS }));

  assert.match(html, /AI hiểu câu của bạn/);
  assert.match(html, /300k\/người/);
  assert.match(html, /6 người/);
  assert.match(html, /trong 5km/);
  // The label, not the id. An id on screen is readable but this one has a
  // label, and resolving it is the difference between a reading and a dump.
  assert.match(html, /Quán ăn local/);
  assert.match(html, /Ngoài trời/);
});

test("người đọc được mời sửa lại, chứ không chỉ được thông báo", () => {
  // A reading nobody is invited to correct is a readout. This line is what
  // makes the panel a control, and it is the actionable half of the
  // requirement, so it is pinned separately from the values above.
  const html = words(React.createElement(CauAiHieu, { understood: understood(), categories: CATS }));
  assert.match(html, /Hiểu chưa đúng ý bạn/);
});

test("AI hiểu sai số tiền thì con số sai đó hiện ra, đúng chỗ người ta phát hiện được", () => {
  // The whole scenario the requirement exists for: "dưới 300k" heard as 30k.
  const html = words(
    React.createElement(CauAiHieu, {
      understood: understood({ budget_per_person_vnd: 30000 }),
      categories: CATS,
    }),
  );
  assert.match(html, /30k\/người/);
  assert.equal(/300k\/người/.test(html), false);
});

test("understood rỗng ra một câu giải thích, không phải một cái hộp trống", () => {
  const trong = understood({
    budget_per_person_vnd: null,
    group_size: null,
    max_distance_km: null,
    categories: [],
    traits: [],
  });
  const html = words(React.createElement(CauAiHieu, { understood: trong, categories: CATS }));

  assert.match(html, /không rút được điều kiện cụ thể nào/);
  // Still says a model answered. Silence here would read as "no AI ran", which
  // is a different fact and the one the next card is for.
  assert.match(html, /AI hiểu câu của bạn/);
});

test("thiếu danh mục thì id hiện thô, chứ dòng Loại chỗ không biến mất", () => {
  const html = words(
    React.createElement(CauAiHieu, { understood: understood(), categories: [] }),
  );
  assert.match(html, /LOẠI CHỖ/);
  assert.match(html, /quan-an-local/);
});

/* ------------------------------------------- the two kinds of nothing ---- */

test("model trả lời mà không có chỗ nào, và model không trả lời, nói hai câu khác nhau", () => {
  const coHieu = words(React.createElement(KhongCoKetQua, { coCachHieu: true }));
  const khongHieu = words(React.createElement(KhongCoKetQua, { coCachHieu: false }));

  // Answered, nothing fits: point at the reading above, which is loosenable.
  assert.match(coHieu, /Không có chỗ nào hợp câu này/);
  assert.match(coHieu, /Xem lại phần AI hiểu ở trên/);

  // Nothing came back: the brief's own words, because there is no reading to
  // send anyone back to.
  assert.match(khongHieu, /Chưa tìm được, thử nói khác xem/);
  assert.notEqual(coHieu, khongHieu);
});

test("câu bị từ chối không được đoán nguyên nhân hộ máy chủ", () => {
  const html = words(React.createElement(KhongCoKetQua, { coCachHieu: false }));
  // The route returns the same answer whether the model was unreachable or
  // whether `ground_search` refused a reply naming a place that does not
  // exist, and it does not tell the client which. Naming one on screen would
  // be inventing the single fact that was withheld on purpose.
  for (const doan of [/mất mạng/i, /máy chủ lỗi/i, /bịa/i, /không tồn tại/i]) {
    assert.equal(doan.test(html), false, `đoán nguyên nhân: ${doan}`);
  }
  assert.equal(/place_search/.test(html), false);
});

/* ---------------------------------------- machine text stays off screen -- */

test("422 hiện câu tiếng Việt, không hiện thân validation tiếng Anh của FastAPI", () => {
  const html = words(
    React.createElement(TimKhongDuoc, {
      state: { kind: "cau-khong-hop-le", max: 300 },
      baseUrl: "http://api.test.invalid",
    }),
  );
  assert.match(html, /Câu tìm kiếm chưa dùng được/);
  assert.match(html, /ngắn hơn 300 chữ/);
  assert.equal(/String should have/.test(html), false);
  assert.equal(/value_error/.test(html), false);
});

test("404 chỉ đúng route thiếu và work item sở hữu nó, thay vì một chữ Lỗi", () => {
  const html = words(
    React.createElement(TimKhongDuoc, {
      state: { kind: "chua-co-endpoint", url: "http://api.test.invalid/places/search", work: "rd-be-10" },
      baseUrl: "http://api.test.invalid",
    }),
  );
  assert.match(html, /POST \/places\/search/);
  assert.match(html, /rd-be-10/);
  assert.match(html, /Đã thử: http:\/\/api\.test\.invalid\/places\/search/);
});

test("không màn nào in tên biến môi trường ra bundle", () => {
  // `tests/base-url.test.mjs` greps the built bundle for that token to prove
  // Expo substituted the read rather than leaving it to resolve on a device.
  // Printing the name in copy would put it in the bundle and cost that gate
  // its meaning -- the same note `KhamPha.tsx` carries.
  const html = words(
    React.createElement(TimKhongDuoc, {
      state: { kind: "khong-noi-duoc", url: "http://x/places/search", detail: "boom" },
      baseUrl: "http://x",
    }),
  );
  assert.equal(/EXPO_PUBLIC_API_URL/.test(html), false);
});
