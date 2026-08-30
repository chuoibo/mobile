/* F24: bản nháp từ tin nhắn. Đường đi đúng, không bịa tên, lỗi ra tiếng Việt.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/nhap-tu-chat.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { confirmExpense, newAttempt, proposeSplit } from "../dist-test/api.js";
import { napNhapKhoanChiTuChat } from "../dist-test/api.js";
import { TEN_CHUA_BIET } from "../dist-test/screens/chat/tin-nhan.js";
import {
  banNhapDeGhi,
  CAU_CHUA_GHI_KHOAN_CHI,
  CAU_DA_GHI_KHOAN_CHI,
  CHUA_GHI,
  dongChiaTuAllocation,
  tenTuRoster,
  trangTuWire,
} from "../dist-test/screens/chat/nhap-tu-chat.js";
import { TheNhapChiTuChat } from "../dist-test/screens/chat/TheNhapChiTuChat.js";

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

/* ------------------------------------------------------------------ F24 chốt
 *
 * Cho tới bản vá này thẻ nháp chỉ có nút [Đóng]: `trangTuWire` đổi
 * `paid_by_id` và `shared_by` thành TÊN để hiện, rồi vứt mất ID, nên cái nút
 * chốt không có gì để gửi và không tồn tại được. Bốn ca dưới đây neo vào đúng
 * chỗ đó: state phải giữ id, bản gửi phải đúng bằng cái đang hiện trên thẻ, và
 * thẻ phải có một nút ghi thật.
 */

const NHOM_DU = [
  ...MEMBERS,
  {
    id: "m-2",
    contextId: CTX,
    personId: CHIA,
    displayName: "Minh",
    state: "active",
    role: "member",
  },
];

function nhapMau({ tra = TRA, chia = [TRA, CHIA], tien = 400_000 } = {}) {
  return trangTuWire(
    {
      context_id: CTX,
      message_id: MSG,
      detected: true,
      draft: {
        title: "Tiền lẩu",
        amount_vnd: tien,
        paid_by_id: tra,
        shared_by: chia,
        needs_review: false,
      },
      reason: null,
    },
    NHOM_DU,
  );
}

test("state co-nhap giữ ID người trả và người chia, không chỉ giữ tên", () => {
  const trang = nhapMau();
  assert.equal(trang.kind, "co-nhap");
  assert.equal(trang.nguoiTraId, TRA, "mất paid_by_id thì nút chốt không có gì để gửi");
  assert.deepEqual(trang.nguoiChiaIds, [TRA, CHIA], "mất shared_by thì không chia được cho ai");
  // Tên vẫn còn, vì thẻ vẫn phải đọc được.
  assert.equal(trang.tenNguoiTra, "Hà");
  assert.deepEqual(trang.tenNguoiChia, ["Hà", "Minh"]);
});

test("bản gửi đúng bằng cái thẻ đang hiện: không thêm ai, không bớt ai", () => {
  // Máy đọc để người trả RA NGOÀI danh sách chia. App không được "sửa giúp":
  // thêm một id vào participants là dời tiền thật khỏi hàng của người khác,
  // mà thẻ thì vẫn đang hiện danh sách cũ.
  const trang = nhapMau({ tra: TRA, chia: [CHIA] });
  const ban = banNhapDeGhi(trang, NHOM_DU);

  assert.equal(ban.advancerId, TRA);
  assert.deepEqual(ban.participants.map((p) => p.id), [CHIA]);
  assert.equal(
    ban.participants.some((p) => p.id === TRA),
    false,
    "app tự nhét người trả vào danh sách chia là tự quyết một câu hỏi về tiền",
  );
  assert.equal(ban.totalVnd, 400_000);
  assert.equal(ban.occasion, "Tiền lẩu");
  // Cái gửi đi phải khớp cái đang đọc được trên thẻ.
  assert.deepEqual(
    ban.participants.map((p) => p.name),
    trang.tenNguoiChia,
  );
});

test("hàng chia hiện theo đúng thứ tự thẻ đã liệt kê, và không giấu ai", () => {
  const trang = nhapMau();
  const dong = dongChiaTuAllocation(
    { [CHIA]: 150_000, [TRA]: 250_000, [LA]: 1 },
    trang.nguoiChiaIds,
    NHOM_DU,
  );
  assert.deepEqual(
    dong.map((d) => d.ten),
    ["Hà", "Minh", TEN_CHUA_BIET],
    "người máy chủ chia cho mà thẻ không liệt kê vẫn phải hiện ra",
  );
  assert.deepEqual(dong.map((d) => d.soTien), [250_000, 150_000, 1]);
});

test("bấm chốt đi đúng POST /expenses rồi POST /expenses/{id}/confirm", async () => {
  const trang = nhapMau();
  const ban = banNhapDeGhi(trang, NHOM_DU);
  const EXP = "cccccccc-dddd-4eee-8fff-aaaaaaaaaaaa";
  const goi = [];

  const deXuat = await withFetch(async (url, init) => {
    goi.push({
      url: String(url),
      method: init?.method,
      headers: init?.headers ?? {},
      body: JSON.parse(init.body),
    });
    if (new URL(String(url)).pathname === "/expenses") {
      return res({
        expense_id: EXP,
        proposal: JSON.parse(init.body),
        allocation: {
          allocations: { [TRA]: 200_000, [CHIA]: 200_000 },
          exact_shares: { [TRA]: "200000", [CHIA]: "200000" },
          rounding_gainers: [],
          warnings: [],
        },
      });
    }
    return res({
      expense_id: EXP,
      expense_version_id: "eeeeeeee-ffff-4aaa-8bbb-cccccccccccc",
      version_number: 1,
      total_amount_vnd: 400_000,
      payer_acknowledgement: "acknowledged",
    });
  }, async () => {
    const dx = await proposeSplit(CTX, ban, newAttempt());
    await confirmExpense(dx, newAttempt());
    return dx;
  });

  assert.equal(goi.length, 2, "chốt phải là hai lần gọi: chia rồi ghi");

  const chia = goi[0];
  assert.equal(chia.method, "POST");
  assert.equal(new URL(chia.url).pathname, "/expenses");
  assert.equal(chia.body.context_id, CTX);
  assert.equal(chia.body.paid_by_id, TRA);
  assert.deepEqual(chia.body.participants, [TRA, CHIA]);
  assert.equal(chia.body.total_amount_vnd, 400_000);
  assert.ok(chia.headers["Idempotency-Key"], "ghi tiền phải có Idempotency-Key");

  const ghi = goi[1];
  assert.equal(new URL(ghi.url).pathname, `/expenses/${EXP}/confirm`);
  assert.equal(ghi.headers["X-Actor-ID"], TRA);
  assert.deepEqual(ghi.body.expected_allocations, { [TRA]: 200_000, [CHIA]: 200_000 });
  assert.equal(ghi.body.acknowledge_as_advancer, true);

  // Con số hiện lên là con số máy chủ trả, không phải phép chia của app.
  const dong = dongChiaTuAllocation(deXuat.allocations, trang.nguoiChiaIds, NHOM_DU);
  assert.deepEqual(dong.map((d) => d.soTien), [200_000, 200_000]);
});

test("thẻ có nút ghi thật, và câu 'chưa ghi' nằm TRÊN nút", () => {
  const markup = renderToStaticMarkup(
    React.createElement(TheNhapChiTuChat, {
      trang: nhapMau(),
      ghi: CHUA_GHI,
      onGhi: () => {},
      onDong: () => {},
    }),
  );
  assert.ok(
    markup.includes("Ghi khoản chi"),
    `thẻ chỉ có [Đóng] thì không có chỗ nào chốt: ${markup.slice(0, 400)}`,
  );
  assert.ok(markup.includes("Đóng"));
  assert.ok(markup.includes(CAU_CHUA_GHI_KHOAN_CHI));
  assert.ok(
    markup.indexOf(CAU_CHUA_GHI_KHOAN_CHI) < markup.indexOf("Ghi khoản chi"),
    "câu điều kiện phải đọc được trước khi tay chạm nút",
  );
  assert.equal(markup.includes(CAU_DA_GHI_KHOAN_CHI), false);
});

test("ghi xong thì thẻ thôi nói 'chưa ghi' và bỏ nút ghi đi", () => {
  const markup = renderToStaticMarkup(
    React.createElement(TheNhapChiTuChat, {
      trang: nhapMau(),
      ghi: { kind: "da-ghi", dong: [{ ten: "Hà", soTien: 200_000 }, { ten: "Minh", soTien: 200_000 }] },
      onGhi: () => {},
      onDong: () => {},
    }),
  );
  assert.equal(
    markup.includes(CAU_CHUA_GHI_KHOAN_CHI),
    false,
    "ghi rồi mà thẻ vẫn nói chưa ghi là nói dối về sổ",
  );
  assert.ok(markup.includes(CAU_DA_GHI_KHOAN_CHI));
  assert.equal(markup.includes("Ghi khoản chi"), false, "ghi hai lần là hai khoản chi");
  assert.ok(markup.includes("200.000"), `số tiền mỗi người phải hiện: ${markup.slice(0, 400)}`);
});

test("chốt hỏng thì giữ nguyên bản nháp và nói bằng tiếng Việt", () => {
  const markup = renderToStaticMarkup(
    React.createElement(TheNhapChiTuChat, {
      trang: nhapMau(),
      ghi: { kind: "ghi-hong", loi: "Khoản chi đã đổi kể từ lúc bạn nhìn." },
      onGhi: () => {},
      onDong: () => {},
    }),
  );
  assert.ok(markup.includes("Khoản chi đã đổi kể từ lúc bạn nhìn."));
  assert.ok(markup.includes("Tiền lẩu"), "mất bản nháp thì không ai quyết được có bấm lại không");
  assert.ok(markup.includes("Ghi lại"));
});

test("câu trên thẻ không có em-dash và không lộ mã máy", () => {
  for (const cau of [CAU_CHUA_GHI_KHOAN_CHI, CAU_DA_GHI_KHOAN_CHI]) {
    assert.equal(cau.includes("—"), false, `còn em-dash: ${cau}`);
    assert.equal(/[a-z]+_[a-z]+/.test(cau), false, `mã máy lọt ra màn: ${cau}`);
  }
});
