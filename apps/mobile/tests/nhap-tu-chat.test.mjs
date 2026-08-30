/* F24: bản nháp từ tin nhắn. Đường đi đúng, không bịa tên, lỗi ra tiếng Việt.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/nhap-tu-chat.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import { napNhapKhoanChiTuChat } from "../dist-test/api.js";
import { TEN_CHUA_BIET } from "../dist-test/screens/chat/tin-nhan.js";
import { tenTuRoster, trangTuWire } from "../dist-test/screens/chat/nhap-tu-chat.js";

const CTX = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const MSG = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff";
const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const TRA = "11111111-aaaa-4bbb-8ccc-dddddddddddd";
const CHIA = "22222222-aaaa-4bbb-8ccc-dddddddddddd";
const LA = "deadbeef-dead-4eaf-8eaf-deadbeefdead";

const MEMBERS = [
  {
    id: "m-1",
    contextId: CTX,
    personId: TRA,
    displayName: "Hà",
    state: "active",
    role: "member",
  },
];

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

test("gọi đúng đường POST /contexts/{id}/messages/{id}/expense-draft", async () => {
  const goi = [];
  await withFetch(async (url, init) => {
    goi.push({ url: String(url), method: init?.method, headers: init?.headers });
    return res({
      context_id: CTX,
      message_id: MSG,
      detected: false,
      draft: null,
      reason: "Tin này không nói về tiền.",
    });
  }, () => napNhapKhoanChiTuChat(CTX, MSG, ACTOR));

  assert.equal(goi.length, 1);
  assert.equal(goi[0].method, "POST");
  assert.equal(
    new URL(goi[0].url).pathname,
    `/contexts/${CTX}/messages/${MSG}/expense-draft`,
  );
  assert.equal(goi[0].headers["X-Actor-ID"], ACTOR);
  assert.equal(
    goi[0].headers["Idempotency-Key"],
    undefined,
    "đọc không được gửi Idempotency-Key",
  );
});

test("detected=false hiện đúng reason máy chủ, không tự chế câu", () => {
  const reason = "Tin này kể chuyện đi chơi, không có số tiền.";
  const trang = trangTuWire(
    {
      context_id: CTX,
      message_id: MSG,
      detected: false,
      draft: null,
      reason,
    },
    MEMBERS,
  );
  assert.equal(trang.kind, "khong-thay");
  assert.equal(trang.reason, reason);
  assert.equal(trang.title, undefined, "không được bịa title khi không phát hiện");
});

test("UUID không có trong roster thành TEN_CHUA_BIET, không bịa tên", () => {
  assert.equal(tenTuRoster(LA, MEMBERS), TEN_CHUA_BIET);
  assert.equal(tenTuRoster(TRA, MEMBERS), "Hà");
  assert.notEqual(tenTuRoster(LA, MEMBERS), "Nguyễn Văn A");
  assert.notEqual(tenTuRoster(LA, MEMBERS), LA.slice(0, 8));

  const trang = trangTuWire(
    {
      context_id: CTX,
      message_id: MSG,
      detected: true,
      draft: {
        title: "Lẩu",
        amount_vnd: 300_000,
        paid_by_id: LA,
        shared_by: [LA, CHIA],
        needs_review: true,
      },
      reason: null,
    },
    MEMBERS,
  );
  assert.equal(trang.kind, "co-nhap");
  assert.equal(trang.tenNguoiTra, TEN_CHUA_BIET);
  assert.deepEqual(trang.tenNguoiChia, [TEN_CHUA_BIET, TEN_CHUA_BIET]);
  assert.equal(
    trang.tenNguoiChia.includes("Minh"),
    false,
    "không được bịa tên cho id lạ",
  );
});

const MA_LOI = [
  {
    code: "chat_expense_model_named_a_person",
    status: 422,
    phaiCo: /tên người|danh sách nhóm/,
  },
  {
    code: "chat_expense_unreadable",
    status: 422,
    phaiCo: /Không đọc được|tin nhắn/,
  },
  {
    code: "chat_reader_unavailable",
    status: 502,
    phaiCo: /không trả lời|Thử lại/,
  },
  {
    code: "chat_reader_not_configured",
    status: 503,
    phaiCo: /chưa cấu hình|máy chủ/,
  },
];

for (const { code, status, phaiCo } of MA_LOI) {
  test(`mã ${code} ra câu tiếng Việt đúng`, async () => {
    const loi = await withFetch(
      async () => res({ code, detail: "Internal Server Error" }, { status }),
      () => batLoi(() => napNhapKhoanChiTuChat(CTX, MSG, ACTOR)),
    );
    assert.equal(loi.code, code);
    assert.match(loi.message, /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụỳýỷỹỵ]/i);
    assert.match(loi.message, phaiCo);
    assert.equal(loi.message.includes("Internal Server Error"), false);
    assert.equal(loi.message.includes(code), false, `mã máy lọt ra màn: ${loi.message}`);
  });
}
