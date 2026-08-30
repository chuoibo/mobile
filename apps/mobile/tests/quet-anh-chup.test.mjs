/* F26: quét ảnh chụp màn hình. Multipart đúng, lỗi ra tiếng Việt, source dịch đủ.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/quet-anh-chup.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import { quetAnhChupMan } from "../dist-test/api.js";
import { tenNguonQuetAnh } from "../dist-test/screens/quet-anh.js";

const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const ANH = { uri: "file:///tmp/anh.jpg", bytes: 1234 };

const OK = {
  source: "grab",
  merchant: "Quán test",
  total_vnd: 89_000,
  occurred_on: "2026-08-30",
  needs_review: false,
};

function res(body, { status = 200 } = {}) {
  const ok = status >= 200 && status < 300;
  return {
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

async function withFetch(impl, fn) {
  const previous = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = previous;
  }
}

async function batLoi(work) {
  try {
    await work();
  } catch (problem) {
    return problem;
  }
  throw new Error("gọi xong mà không ném lỗi, test này không đo được gì");
}

test("multipart không kèm Content-Type thủ công và không kèm Idempotency-Key", async () => {
  const goi = [];
  await withFetch(async (url, init) => {
    goi.push({ url: String(url), method: init?.method, headers: init?.headers, body: init?.body });
    return res(OK);
  }, () => quetAnhChupMan(ANH, ACTOR));

  assert.equal(goi.length, 1);
  assert.equal(goi[0].method, "POST");
  assert.equal(new URL(goi[0].url).pathname, "/screenshots/scan");
  const ten = Object.keys(goi[0].headers).map((k) => k.toLowerCase());
  assert.equal(ten.includes("content-type"), false, `còn gửi Content-Type: ${ten.join(", ")}`);
  assert.equal(
    goi[0].headers["Idempotency-Key"],
    undefined,
    "đọc không được gửi Idempotency-Key",
  );
  assert.equal(goi[0].headers["X-Actor-ID"], ACTOR);
  assert.ok(goi[0].body instanceof FormData, "body phải là FormData");
  assert.ok(goi[0].body.has("image"), "thiếu field image");
});

const MA_LOI = [
  { code: "image_too_large", status: 413, phaiCo: /8 MB|nặng/ },
  { code: "unsupported_image_type", status: 415, phaiCo: /JPG|PNG|ảnh/ },
  { code: "not_a_transaction", status: 422, phaiCo: /giao dịch/ },
  { code: "screenshot_model_named_a_person", status: 422, phaiCo: /tên người|phiên đăng nhập/ },
  { code: "screenshot_unreadable", status: 422, phaiCo: /Không đọc được|ảnh chụp/ },
  { code: "screenshot_reader_unavailable", status: 502, phaiCo: /không trả lời|Thử lại/ },
  { code: "screenshot_reader_not_configured", status: 503, phaiCo: /chưa cấu hình|máy chủ/ },
];

for (const { code, status, phaiCo } of MA_LOI) {
  test(`mã ${code} ra câu tiếng Việt đúng`, async () => {
    const loi = await withFetch(
      async () => res({ code, detail: "Internal Server Error" }, { status }),
      () => batLoi(() => quetAnhChupMan(ANH, ACTOR)),
    );
    assert.equal(loi.code, code);
    assert.match(loi.message, /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụỳýỷỹỵ]/i);
    assert.match(loi.message, phaiCo);
    assert.equal(loi.message.includes("Internal Server Error"), false);
    assert.equal(loi.message.includes(code), false, `mã máy lọt ra màn: ${loi.message}`);
  });
}

test("source dịch đúng bốn giá trị", () => {
  assert.equal(tenNguonQuetAnh("grab"), "Grab");
  assert.equal(tenNguonQuetAnh("shopeefood"), "ShopeeFood");
  assert.equal(tenNguonQuetAnh("banking"), "Chuyển khoản");
  assert.equal(tenNguonQuetAnh("receipt"), "Hoá đơn");
  assert.notEqual(tenNguonQuetAnh("banking"), tenNguonQuetAnh("receipt"));
  assert.notEqual(tenNguonQuetAnh("grab"), "grab");
});
