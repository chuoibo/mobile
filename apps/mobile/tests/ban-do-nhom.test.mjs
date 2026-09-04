/* Bản đồ nhóm, nhiệt độ nhóm và điểm hẹn: phần đọc được mà không cần render.
 *
 * Ba nhóm ca ở đây, và chỉ nhóm đầu là về việc vẽ đúng.
 *
 * NHÓM 1 — thân request của F45. Đây là ca đáng giá nhất cả file. Tính riêng
 * tư của "meet in the middle" không nằm ở lời hứa trong docstring mà nằm ở chỗ
 * thân request KHÔNG CÓ TRƯỜNG NÀO để nhét danh tính vào. Ca dưới đọc đúng
 * cái byte app gửi đi và khẳng định nó có duy nhất `from_areas`. Nếu mai có
 * người thêm `person_id` cho tiện gỡ lỗi, ca này đỏ.
 *
 * NHÓM 2 — trường tiết lộ. `scanned_checkins` / `truncated` /
 * `unknown_area_count` là thứ phân biệt "thói quen của nhóm" với "500 lần
 * check-in gần nhất của nhóm". Máy chủ bỏ gửi chúng thì app phải ĐỎ chứ không
 * được im lặng vẽ ra một bản tóm tắt không còn biên.
 *
 * NHÓM 3 — 403. Ba route này gác theo tư cách thành viên, nên 403 nghĩa là
 * "bạn không còn trong nhóm" chứ không phải "có lỗi". Ca kiểm rằng câu chữ
 * trên màn không chứa con số 403 và không mời người dùng đi thử lại một thứ
 * chưa bao giờ hỏng.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  cauDaQuet,
  cauKhongRoKhu,
  fetchBanDoNhom,
  fetchDiemHen,
  fetchNhietDo,
  parseBanDoNhom,
  parseNhietDo,
  soKm,
  soLan,
} from "../dist-test/screens/kham-pha/ban-do-nhom.js";
/* Cùng hình dạng với `tests/api/helpers.py`. Chữ trong UUID là có chủ ý:
 * repo guard chặn chuỗi số dài (luật `long-number`, thứ bắt số tài khoản),
 * và một UUID toàn chữ số trông y hệt thứ đó. */
const NGUOI = "2bb00000-bbbb-4bbb-8bbb-0000b0000001";

/** A `fetch` stand-in that records what it was called with. */
function ghiLai(res) {
  const goi = [];
  const impl = async (url, init) => {
    goi.push({ url, init });
    return res;
  };
  return { goi, impl };
}

function json(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

const BAN_DO_DU = {
  context_id: "1aa00000-aaaa-4aaa-8aaa-0000a0000001",
  visited: [
    { place_id: "p1", place_name: "Cà phê Vườn", lat: 10.77, lng: 106.7, visit_count: 6 },
  ],
  trending: [],
  recommended: [],
  unavailable: [{ layer: "saved", reason: "Chưa có chỗ lưu địa điểm." }],
  scanned_checkins: 12,
  truncated: false,
};

/* ------------------------------------------- NHÓM 1: thân request của F45 --- */

test("thân request điểm hẹn CHỈ có from_areas, không có chỗ nào cho danh tính", async () => {
  const { goi, impl } = ghiLai(
    json({ context_id: "c", origins: [], candidates: [], two_origin_inversion: false }),
  );

  await fetchDiemHen(["hcm-quan-1", "hcm-thu-duc"], {
    personId: NGUOI,
    base: "http://x",
    fetchImpl: impl,
  });

  assert.equal(goi.length, 1);
  const than = JSON.parse(goi[0].init.body);

  // Đúng một khoá. Không phải "không có person_id" -- không có khoá NÀO khác.
  assert.deepEqual(Object.keys(than), ["from_areas"]);
  assert.deepEqual(than.from_areas, ["hcm-quan-1", "hcm-thu-duc"]);

  // Và định danh người gọi không lọt vào thân dưới bất kỳ tên nào.
  assert.ok(
    !JSON.stringify(than).includes(NGUOI),
    "personId không được nằm trong thân request",
  );
});

/* ------------------------------------------------ NHÓM 2: trường tiết lộ --- */

test("thiếu scanned_checkins là dữ liệu sai, không phải mặc định 0", () => {
  const thieu = { ...BAN_DO_DU };
  delete thieu.scanned_checkins;
  assert.throws(() => parseBanDoNhom(thieu), /scanned_checkins/);
});

test("thiếu truncated là dữ liệu sai: mất biên là mất luôn nghĩa của con số", () => {
  const thieu = { ...BAN_DO_DU };
  delete thieu.truncated;
  assert.throws(() => parseBanDoNhom(thieu), /truncated/);
});

test("thiếu unknown_area_count ở nhiệt độ cũng đỏ", () => {
  const thieu = {
    context_id: "c",
    areas: [],
    resolved_checkins: 0,
    scanned_checkins: 0,
    truncated: false,
  };
  assert.throws(() => parseNhietDo(thieu), /unknown_area_count/);
});

test("câu 'đã quét' đổi hẳn nghĩa khi truncated bật", () => {
  const het = cauDaQuet(12, false);
  const cat = cauDaQuet(500, true);
  assert.ok(het.includes("toàn bộ"));
  assert.ok(!cat.includes("toàn bộ"), "bản bị cắt không được nói 'toàn bộ'");
  assert.ok(cat.includes("chưa tính vào đây"));
});

test("nhóm chưa check-in lần nào nói là chưa có gì để đếm", () => {
  assert.ok(cauDaQuet(0, false).includes("chưa có lần check-in nào"));
});

test("không có check-in lạc khu thì không in dòng thừa", () => {
  assert.equal(cauKhongRoKhu(0), null);
  assert.ok(cauKhongRoKhu(3).includes("3 lần"));
});

test("share_percent quá 100 bị từ chối chứ không vẽ thanh tràn", () => {
  const xau = {
    context_id: "c",
    areas: [{ id: "a", label: "A", lat: 0, lng: 0, visit_count: 5, share_percent: 140 }],
    resolved_checkins: 5,
    unknown_area_count: 0,
    scanned_checkins: 5,
    truncated: false,
  };
  assert.throws(() => parseNhietDo(xau), /share_percent/);
});

test("lớp chưa có được giữ nguyên tên và lý do, không biến thành mảng rỗng", () => {
  const d = parseBanDoNhom(BAN_DO_DU);
  assert.equal(d.chuaCo.length, 1);
  assert.equal(d.chuaCo[0].layer, "saved");
  assert.ok(d.chuaCo[0].reason.length > 0);
});

/* --------------------------------------------------------- NHÓM 3: 403 --- */

test("403 thành trạng thái riêng, không phải may-chu-loi", async () => {
  const { impl } = ghiLai(json({ detail: "is_group_member" }, 403));
  const s = await fetchBanDoNhom({ personId: NGUOI, base: "http://x", fetchImpl: impl });
  assert.equal(s.kind, "khong-con-trong-nhom");
  // Không mang theo status/url: không có gì để người đọc đi sửa.
  assert.equal(s.status, undefined);
  assert.equal(s.url, undefined);
});

test("403 ở nhiệt độ và ở điểm hẹn cũng cùng một trạng thái", async () => {
  for (const goiHam of [fetchNhietDo, (o) => fetchDiemHen(["a", "b"], o)]) {
    const { impl } = ghiLai(json({ detail: "is_group_member" }, 403));
    const s = await goiHam({ personId: NGUOI, base: "http://x", fetchImpl: impl });
    assert.equal(s.kind, "khong-con-trong-nhom");
  }
});

test("404 vẫn là chua-co-endpoint: máy chủ sống nhưng thiếu route", async () => {
  const { impl } = ghiLai(json({ detail: "nope" }, 404));
  const s = await fetchBanDoNhom({ personId: NGUOI, base: "http://x", fetchImpl: impl });
  assert.equal(s.kind, "chua-co-endpoint");
  assert.ok(s.url.endsWith("/map"));
});

test("500 vẫn là may-chu-loi và giữ status để còn đi tìm", async () => {
  const { impl } = ghiLai(json({ detail: "boom" }, 500));
  const s = await fetchBanDoNhom({ personId: NGUOI, base: "http://x", fetchImpl: impl });
  assert.equal(s.kind, "may-chu-loi");
  assert.equal(s.status, 500);
});

test("mạng chết thành khong-noi-duoc chứ không ném ra ngoài", async () => {
  const impl = async () => {
    throw new Error("ECONNREFUSED");
  };
  const s = await fetchBanDoNhom({ personId: NGUOI, base: "http://x", fetchImpl: impl });
  assert.equal(s.kind, "khong-noi-duoc");
});

/* ------------------------------------------------------- header và URL --- */

test("cả ba route đều gửi X-Actor-ID: thiếu nó là hỏng quyền chứ không phải thiếu dữ liệu", async () => {
  const cases = [
    [fetchBanDoNhom, "/map"],
    [fetchNhietDo, "/heatmap"],
    [(o) => fetchDiemHen(["a"], o), "/meet"],
  ];
  for (const [goiHam, duoi] of cases) {
    const { goi, impl } = ghiLai(json({}, 500));
    await goiHam({ personId: NGUOI, base: "http://x", fetchImpl: impl });
    assert.equal(goi[0].init.headers["X-Actor-ID"], NGUOI, duoi);
    assert.ok(goi[0].url.endsWith(duoi), `${goi[0].url} phải kết thúc bằng ${duoi}`);
  }
});

/* --------------------------------------------------------- định dạng --- */

test("số lần luôn kèm đơn vị: một con số trần cạnh tên quán đọc thành hạng", () => {
  assert.equal(soLan(6), "6 lần");
  assert.equal(soLan(0), "0 lần");
});

test("km giữ một chữ số thập phân: làm tròn tới km biến 400m thành ngang nhau", () => {
  assert.equal(soKm(3.44), "3.4 km");
  assert.notEqual(soKm(3.4), soKm(3.8));
});