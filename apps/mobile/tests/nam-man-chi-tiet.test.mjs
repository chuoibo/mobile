/* The five detail surfaces, pinned against the bodies a real server sent.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * Every wire object below was COPIED out of a live answer from the demo API on
 * 8099, not written from the schema. That distinction is the point of the file:
 * a fixture invented from `openapi.json` proves the author read the schema the
 * same way twice, and this repo has been bitten by exactly that -- a client and
 * a corpus written by one person agreeing with each other and both being wrong
 * about the server.
 *
 * What this file does NOT prove: that any of these render, that anything is
 * reachable by tapping, or that the screens are laid out. Those are the export
 * build and a person with a phone. It proves the five reads parse, that the
 * money identity holds on the split, and that the account number does not leak
 * out of the read path.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { parsePlaceDetail, loiChiTiet, placeDetailUrl, fetchPlaceDetail } from "../dist-test/screens/kham-pha/chi-tiet-dia-diem.js";
import { docWidgetNhom, docChiaBill, docTaiKhoanNhan } from "../dist-test/api.js";
import { khiNao } from "../dist-test/screens/ky-niem/TheWidget.js";
import { ngayGio } from "../dist-test/screens/tai-khoan/TaiKhoanNhan.js";

/* ---------------------------------------------------------------- fixtures */

/** `GET /places/p-tiem-nuong-xom-lao`, trimmed to the fields under test plus
 *  everything `parsePlace` insists on. Prose and reviews are the two fields the
 *  list route does not carry, which is why this route exists at all. */
const CHI_TIET_THAT = {
  id: "p-tiem-nuong-xom-lao",
  name: "Tiệm Nướng Xóm Lào",
  category: "quan-an-local",
  kinds: ["BBQ", "Lào", "Local"],
  rating: 4.7,
  rating_count: 128,
  distance_km: 1.2,
  price_min_vnd: 200000,
  price_max_vnd: 250000,
  address: "12 Đường Hoa Hồng, Phường 4, Đà Lạt",
  open_now: true,
  open_hours: "17:00 - 23:00",
  travel_minutes: 8,
  photo_count: 18,
  traits: ["BBQ", "View đẹp"],
  group_fit: { min_people: 4, max_people: 10, relation: "Bạn bè, đồng nghiệp" },
  flag: null,
  lat: 11.94,
  lng: 108.44,
  match: { score: 96, reason: "Hợp vì ngồi ngoài trời.", source: "ai", verdict: "hop", factors: [] },
  description:
    "Quán nướng sân vườn, bàn than hoa đặt ngoài trời và có mái che khi Đà Lạt trở lạnh.",
  reviews: [
    { author: "Trang", rating: 5.0, body: "Đi bảy đứa vẫn đủ chỗ, thịt ướp đậm vị." },
    { author: "Đức", rating: 4.0, body: "Cuối tuần đông, nên đặt bàn trước." },
  ],
  photos_available: false,
};

/** `GET /contexts/{id}/widget`, exactly as answered. */
const WIDGET_THAT = {
  context_id: "5cacfdee-955f-4743-9cc4-c6a019480c96",
  photo: {
    memory_id: "a7a48773-38b1-4a4b-9275-aefd4e0fe61e",
    image_url:
      "/contexts/5cacfdee-955f-4743-9cc4-c6a019480c96/photos/b70cd980-d2ea-4140-ac66-5ff68bc64b3e",
    caption: null,
    author_id: "46b55e67-932b-5415-a5ee-08fb2641a4ff",
    author_name: "Minh",
    created_at: "2026-08-30T15:13:14.809875Z",
  },
};

/** `POST /bills/{id}/split`, exactly as answered. Four diners, uneven shares. */
const CHIA_THAT = {
  allocation: {
    allocations: {
      "476be708-7bee-851c-b70e-2ba88cfedad7": 162500,
      "74ceeaf8-0823-88a9-91d9-ed10ba5d48a9": 392500,
      "b2331f3e-1d88-8969-bd27-330b62e31747": 117500,
      "ede484c6-bdd6-84b3-94e8-8a178eca1964": 72500,
    },
    exact_shares: {
      "476be708-7bee-851c-b70e-2ba88cfedad7": "162500/1",
      "74ceeaf8-0823-88a9-91d9-ed10ba5d48a9": "392500/1",
      "b2331f3e-1d88-8969-bd27-330b62e31747": "117500/1",
      "ede484c6-bdd6-84b3-94e8-8a178eca1964": "72500/1",
    },
    rounding_gainers: [],
    warnings: [],
  },
  assignment_state: "confirmed",
  suggested_item_keys: [],
  total_amount_vnd: 745000,
};

/** `GET /bank-recipients/{id}`, exactly as answered. */
const TAI_KHOAN_THAT = {
  id: "8f12f5cb-3e23-447f-a5d9-59a646703f45",
  recipient_id: "b2331f3e-1d88-8969-bd27-330b62e31747",
  bank_bin: "970415",
  bank_name: "VietinBank",
  bank_recognised: true,
  // repo-guard: allow=long-number reason=synthetic-placeholder-account-number
  account_number: "0011002200330044",
  account_name: "AN - THU NGHIEM",
  confirmed_at: "2026-08-30T14:50:29.436153Z",
};

/** A fetch that answers one body and records what it was asked. */
function mayChu(body, { status = 200 } = {}) {
  const daGoi = [];
  const doFetch = async (url, init = {}) => {
    daGoi.push({
      url: String(url),
      method: init.method ?? "GET",
      body: init.body ?? null,
      headers: init.headers ?? {},
    });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  };
  return { doFetch, daGoi };
}

/* ------------------------------------------------ 1. GET /places/{place_id} */

test("chi tiết địa điểm: giới thiệu và đánh giá đọc được từ thân thật", () => {
  const place = parsePlaceDetail(CHI_TIET_THAT);
  assert.equal(place.name, "Tiệm Nướng Xóm Lào");
  assert.match(place.description, /^Quán nướng sân vườn/);
  assert.equal(place.reviews.length, 2);
  assert.deepEqual(place.reviews[0], {
    author: "Trang",
    rating: 5,
    body: "Đi bảy đứa vẫn đủ chỗ, thịt ướp đậm vị.",
  });
  // Not inferred from an empty gallery: the server says it out loud.
  assert.equal(place.photosAvailable, false);
  // The shared half still comes from `parsePlace`, so the two screens cannot
  // disagree about what a price band is.
  assert.equal(place.priceMinVnd, 200000);
  assert.equal(place.match.verdict, "hop");
});

test("chi tiết địa điểm: mô tả rỗng đọc thành null chứ không thành chuỗi rỗng", () => {
  assert.equal(parsePlaceDetail({ ...CHI_TIET_THAT, description: "   " }).description, null);
  assert.equal(parsePlaceDetail({ ...CHI_TIET_THAT, description: null }).description, null);
  // Absent entirely -- an older server -- is not an error either.
  const { reviews, ...khongCoDanhGia } = CHI_TIET_THAT;
  assert.deepEqual(parsePlaceDetail(khongCoDanhGia).reviews, []);
});

test("chi tiết địa điểm: điểm đánh giá ngoài 0-5 bị từ chối, không bị cắt", () => {
  assert.throws(
    () => parsePlaceDetail({ ...CHI_TIET_THAT, reviews: [{ author: "X", rating: 9, body: "y" }] }),
    /rating ngoài 0-5/,
  );
});

test("chi tiết địa điểm: id đi vào đường dẫn được mã hoá", () => {
  assert.equal(placeDetailUrl("http://x", "../../etc"), "http://x/places/..%2F..%2Fetc");
  assert.equal(placeDetailUrl("http://x/", "p-1"), "http://x/places/p-1");
});

test("chi tiết địa điểm: mọi cách hỏng đều ra một câu, không ném", async () => {
  const { doFetch } = mayChu(CHI_TIET_THAT);
  const ok = await fetchPlaceDetail("p-1", { base: "http://x", fetchImpl: doFetch });
  assert.equal(ok.kind, "co-du-lieu");
  assert.equal(loiChiTiet(ok), null);

  const chet = await fetchPlaceDetail("p-1", {
    base: "http://x",
    fetchImpl: async () => {
      throw new Error("ECONNREFUSED");
    },
  });
  assert.equal(chet.kind, "khong-noi-duoc");
  assert.match(loiChiTiet(chet), /Không nối được/);

  // A server WITHOUT the route answers FastAPI's own 404; the route's own 404
  // carries a `code`. Two different afternoons, so two different states.
  const thieuRoute = mayChu({ detail: "Not Found" }, { status: 404 });
  const r1 = await fetchPlaceDetail("p-1", { base: "http://x", fetchImpl: thieuRoute.doFetch });
  assert.equal(r1.kind, "chua-co-endpoint");

  const khongCo = mayChu({ code: "place_not_found", detail: "x" }, { status: 404 });
  const r2 = await fetchPlaceDetail("p-1", { base: "http://x", fetchImpl: khongCo.doFetch });
  assert.equal(r2.kind, "khong-co");
});

/* ------------------------------------ 2. GET /contexts/{context_id}/widget */

test("widget: sáu trường, và ảnh null là câu trả lời chứ không phải lỗi", async () => {
  const { doFetch, daGoi } = mayChu(WIDGET_THAT);
  globalThis.fetch = doFetch;
  const w = await docWidgetNhom(WIDGET_THAT.context_id, WIDGET_THAT.photo.author_id);
  assert.equal(w.authorName, "Minh");
  assert.equal(w.caption, null);
  assert.equal(w.imageUrl, WIDGET_THAT.photo.image_url);
  // Members-only, so the read must carry who is asking and which group.
  assert.equal(daGoi[0].method, "GET");
  assert.equal(daGoi[0].headers["X-Actor-ID"], WIDGET_THAT.photo.author_id);
  assert.equal(daGoi[0].headers["X-Actor-Contexts"], WIDGET_THAT.context_id);

  const trong = mayChu({ context_id: WIDGET_THAT.context_id, photo: null });
  globalThis.fetch = trong.doFetch;
  assert.equal(await docWidgetNhom(WIDGET_THAT.context_id, "ai-do"), null);
});

test("widget: mốc thời gian chỉ tương đối trong hai ngày", () => {
  const now = new Date("2026-08-30T20:00:00+07:00");
  assert.equal(khiNao("2026-08-30T09:00:00Z", now), "hôm nay");
  assert.equal(khiNao("2026-08-29T09:00:00Z", now), "hôm qua");
  assert.equal(khiNao("2026-08-20T09:00:00Z", now), "20/8");
  assert.equal(khiNao("khong-phai-ngay", now), "");
});

/* ------------------------------------------- 3. POST /bills/{bill_id}/split */

test("chia bill: tổng phân bổ đúng bằng tổng hoá đơn", async () => {
  const { doFetch, daGoi } = mayChu(CHIA_THAT);
  globalThis.fetch = doFetch;
  const s = await docChiaBill("bill-1", "nguoi-1", "nhom-1", { key: "k", at: 0 });

  // Money law 2, on the wire the app will actually draw from.
  const tong = Object.values(s.allocations).reduce((a, b) => a + b, 0);
  assert.equal(tong, s.totalAmountVnd);
  assert.equal(tong, 745000);
  // Money law 1: every figure an integer đồng, none of them produced here.
  for (const v of Object.values(s.allocations)) assert.ok(Number.isInteger(v));
  assert.equal(Object.keys(s.exactShares).length, 4);
  assert.equal(s.assignmentState, "confirmed");
});

test("chia bill: thân yêu cầu không mang danh tính ai cả", async () => {
  const { doFetch, daGoi } = mayChu(CHIA_THAT);
  globalThis.fetch = doFetch;
  await docChiaBill("bill-1", "nguoi-1", "nhom-1", { key: "k", at: 0 });

  // The whole guarantee: the person is the actor header, and the body has no
  // field in which a caller could name somebody else. `for_ledger` is left at
  // its server-side default so this call cannot write.
  assert.deepEqual(JSON.parse(daGoi[0].body), {});
  assert.equal(daGoi[0].headers["X-Actor-ID"], "nguoi-1");
  assert.equal(daGoi[0].headers["Idempotency-Key"], "k");
});

/* ------------------------------------- 5. GET /bank-recipients/{recipient_id} */

test("tài khoản nhận: đọc lại được, và số về tới màn hình đã che", async () => {
  const { doFetch, daGoi } = mayChu(TAI_KHOAN_THAT);
  globalThis.fetch = doFetch;
  const r = await docTaiKhoanNhan(TAI_KHOAN_THAT.recipient_id, TAI_KHOAN_THAT.recipient_id);

  assert.equal(r.bankName, "VietinBank");
  assert.equal(r.bankRecognised, true);
  assert.equal(r.confirmedAt, "2026-08-30T14:50:29.436153Z");
  // The number must not survive the read path in full. This is the assertion
  // that would catch somebody "helpfully" passing `account_number` through.
  assert.ok(!JSON.stringify(r).includes(TAI_KHOAN_THAT.account_number));
  assert.match(r.accountMasked, /^•+/);
  assert.equal(daGoi[0].method, "GET");
});

test("tài khoản nhận: chưa có tài khoản là null, không phải lỗi", async () => {
  const { doFetch } = mayChu({ code: "bank_recipient_not_found", detail: "x" }, { status: 404 });
  globalThis.fetch = doFetch;
  assert.equal(await docTaiKhoanNhan("ai-do", "ai-do"), null);
});

test("tài khoản nhận: 403 vẫn ném, chỉ 404 mới là 'chưa có'", async () => {
  const { doFetch } = mayChu({ code: "permission_denied", detail: "is_own_account" }, { status: 403 });
  globalThis.fetch = doFetch;
  await assert.rejects(() => docTaiKhoanNhan("nguoi-khac", "toi"));
});

test("tài khoản nhận: mốc lưu đọc được là giờ và ngày", () => {
  assert.match(ngayGio("2026-08-30T14:50:29.436153Z"), /^\d{2}:\d{2} ngày \d+\/\d+$/);
  assert.equal(ngayGio("khong-phai-ngay"), "");
});
