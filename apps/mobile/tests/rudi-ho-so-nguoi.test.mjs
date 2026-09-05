/* Hồ sơ người khác và tường của họ (M8).
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-ho-so-nguoi.test.mjs
 *
 * Điều đáng gác nhất: `GET /people/{id}/posts` trả 200 kèm danh sách RỖNG cho
 * cả «người ấy chưa đăng gì» lẫn «không có bài nào dành cho bạn». Màn không
 * được nói câu thứ nhất, vì app không biết điều đó. Kèm theo: hai lời gọi đi
 * với bearer của người đọc, và mỗi bài hiện mức người đọc bằng đúng chữ mà ô
 * soạn bài đưa ra.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien } from "../dist-test/api.js";
import {
  cauLucNao,
  cauNgayVao,
  cauQuanHe,
  cauTuongRong,
  docHoSoNguoi,
  docTuongCua,
  dongPhuBai,
  nhanMuc,
} from "../dist-test/rudi/nguoi/ho-so-nguoi.js";

const HO_SO = {
  id: "7ba00000-bbbb-4bbb-8bbb-0000b0000007",
  display_name: "Bảo Châu",
  bio: "Thích cà phê muộn",
  city: "Đà Lạt",
  created_at: "2026-09-01T10:00:00Z",
  relation: "friend",
};

function gaLoi(status, code) {
  return async () => ({
    ok: false,
    status,
    headers: { get: () => "application/json" },
    json: async () => ({ code, detail: "x" }),
    text: async () => "",
  });
}

function gaJson(than, ghi) {
  return async (url, init) => {
    if (ghi) ghi.push({ url: String(url), init });
    return {
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => than,
      text: async () => JSON.stringify(than),
    };
  };
}

test("tường rỗng không khẳng định người ấy chưa đăng gì", () => {
  for (const quanHe of ["friend", "groupmate"]) {
    const cau = cauTuongRong(quanHe);
    assert.match(cau, /bạn đọc được/);
    assert.ok(!/chưa đăng bài nào/i.test(cau), `«${cau}» khẳng định quá tay`);
  }
  // Với chính mình thì khẳng định được: mình luôn đọc được mọi bài mình viết.
  assert.match(cauTuongRong("self"), /Bạn chưa đăng bài nào/);
});

test("quan hệ nói bằng ngôi thứ hai, không lộ cách máy chủ suy ra", () => {
  assert.equal(cauQuanHe("self"), "Hồ sơ của bạn");
  assert.equal(cauQuanHe("friend"), "Bạn bè");
  assert.equal(cauQuanHe("groupmate"), "Cùng nhóm");
});

test("mỗi bài hiện mức người đọc bằng chữ của ô soạn bài", () => {
  assert.equal(nhanMuc("only_me"), "Chỉ mình tôi");
  assert.equal(nhanMuc("friends"), "Bạn bè");
  assert.equal(nhanMuc("group"), "Một nhóm");
  assert.equal(nhanMuc("public"), "Công khai");
  const bay = new Date("2026-09-05T12:00:00Z");
  const dong = dongPhuBai(
    { id: "b1", author_id: "p1", audience: "public", context_id: null, body: "x", image_url: null, created_at: "2026-09-05T11:30:00Z" },
    bay,
  );
  assert.equal(dong, "30 phút trước · Công khai");
});

test("thời gian thô dần theo khoảng cách, không in đồng hồ chính xác", () => {
  const bay = new Date("2026-09-05T12:00:00Z");
  assert.equal(cauLucNao("2026-09-05T11:59:40Z", bay), "Vừa xong");
  assert.equal(cauLucNao("2026-09-05T09:00:00Z", bay), "3 giờ trước");
  assert.equal(cauLucNao("2026-09-03T12:00:00Z", bay), "2 ngày trước");
  assert.equal(cauLucNao("khong-phai-ngay", bay), "");
});

test("ngày tham gia in theo tháng, không in ngày", () => {
  assert.equal(cauNgayVao("2026-09-01T10:00:00Z"), "Tham gia từ tháng 9/2026");
  assert.equal(cauNgayVao("rac"), "");
});

test("hai lời gọi đi với bearer của người đọc, đúng đường dẫn", async () => {
  datTokenPhien("token-cua-nguoi-doc");
  const ghi = [];
  const goc = globalThis.fetch;
  globalThis.fetch = gaJson({ ...HO_SO }, ghi);
  try {
    await docHoSoNguoi(HO_SO.id, "p-nguoi-doc");
  } finally {
    globalThis.fetch = goc;
  }
  assert.match(ghi[0].url, /\/people\/7ba00000-bbbb-4bbb-8bbb-0000b0000007$/);
  assert.equal(ghi[0].init.headers.Authorization, "Bearer token-cua-nguoi-doc");

  const ghi2 = [];
  globalThis.fetch = gaJson({ person_id: HO_SO.id, posts: [] }, ghi2);
  try {
    const bai = await docTuongCua(HO_SO.id, "p-nguoi-doc");
    assert.deepEqual(bai, []);
  } finally {
    globalThis.fetch = goc;
  }
  assert.match(ghi2[0].url, /\/people\/[0-9a-f-]+\/posts\?limit=50$/);
});

test("hồ sơ không xem được nói ra nước đi tiếp, không nói id có tồn tại hay không", async () => {
  const goc = globalThis.fetch;
  globalThis.fetch = gaLoi(403, "person_not_visible");
  try {
    await docHoSoNguoi(HO_SO.id, "p-nguoi-doc");
    assert.fail("phải ném");
  } catch (error) {
    assert.match(error.message, /bạn bè hoặc người cùng nhóm/);
    assert.ok(!/không tồn tại|tồn tại/i.test(error.message));
  } finally {
    globalThis.fetch = goc;
  }
});
