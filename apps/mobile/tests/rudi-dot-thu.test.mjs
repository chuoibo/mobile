/* Đợt thu in the RuDi shell (M5 v-b): the bridge module.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/rudi-dot-thu.test.mjs
 *
 * Nothing here adds money or decides a transfer arrived: counts and statuses
 * are the server's, the board keeps ids so the recipient can be told apart,
 * and a refusal code becomes a Vietnamese sentence, never English.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, datTokenPhien } from "../dist-test/api.js";
import {
  cauHangNghiaVu,
  cauTomTatDot,
  cauTrangThaiDot,
  daPhat,
  docBangThu,
  docDotThuCuaNhom,
  loiNhanChiaSe,
  moDotThu,
  nghiaVuToiNhan,
  tomTatBang,
} from "../dist-test/rudi/dot-thu/dot-thu.js";

const AN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const BAN = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const ROSTER = [
  { id: AN, name: "An QA" },
  { id: BAN, name: "Ban QA" },
];

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

test("docDotThuCuaNhom đọc danh sách đợt theo hình dạng máy chủ, số là số máy chủ", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    goi.push({ url: String(url), method: init.method });
    return json(200, {
      context_id: "c-1",
      batches: [
        { batch_id: "b-1", status: "published", created_at: "2026-09-04T01:00:00Z", published_at: "2026-09-04T01:05:00Z", obligation_count: 3, confirmed_count: 1, disputed_count: 0, total_vnd: 500000 },
      ],
    });
  };
  const ds = await docDotThuCuaNhom("c-1", BAN);
  assert.match(goi[0].url, /\/contexts\/c-1\/batches$/);
  assert.equal(goi[0].method, "GET");
  assert.deepEqual(ds, [{ id: "b-1", trangThai: "published", taoLuc: "2026-09-04T01:00:00Z", phatLuc: "2026-09-04T01:05:00Z", soNghiaVu: 3, soDaNhan: 1, soTranhCai: 0, tongVnd: 500000 }]);
  assert.equal(cauTomTatDot(ds[0]), "3 lượt chuyển · 1 đã về · 500.000đ");
  assert.equal(cauTrangThaiDot(ds[0].trangThai), "Đã phát");
  assert.equal(daPhat("frozen"), false);
  assert.equal(daPhat("collecting"), true);
  datTokenPhien(null);
});

test("moDotThu gửi đúng thân của App B (null = mọi khoản chưa vào đợt), Idempotency-Key, và dịch từ chối", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    const body = init.body ? JSON.parse(init.body) : null;
    goi.push({ url: String(url), body, key: init.headers?.["Idempotency-Key"] });
    if (goi.length === 1) {
      return json(201, { batch_id: "b-2", batch_version_id: "v", status: "frozen", obligations: [{ obligation_id: "o-1", sender_id: AN, recipient_id: BAN, amount_vnd: 75000, due_at: "x", source_expense_version_ids: [] }] });
    }
    return json(409, { code: "no_unbatched_allocations", detail: "nothing to batch" });
  };
  const attempt = { key: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", at: Date.UTC(2026, 8, 4) };
  const dot = await moDotThu({ contextId: "c-1", actorId: BAN, expenseVersionIds: null, attempt });
  assert.equal(goi[0].body.context_id, "c-1");
  assert.equal(goi[0].body.expense_version_ids, null);
  assert.equal(goi[0].body.due_at, new Date(attempt.at + 7 * 24 * 60 * 60 * 1000).toISOString());
  assert.equal(goi[0].key, attempt.key);
  assert.deepEqual(dot.nghiaVu, [{ id: "o-1", senderId: AN, recipientId: BAN, amountVnd: 75000, trangThai: "outstanding", tranhCai: false }]);
  await assert.rejects(
    () => moDotThu({ contextId: "c-1", actorId: BAN, expenseVersionIds: null, attempt }),
    (e) => e instanceof ApiError && e.message.startsWith("Sổ chưa có khoản nào để thu"),
  );
  datTokenPhien(null);
});

test("docBangThu giữ id người nhận và gấp «đang thắc mắc» như App B; nghiaVuToiNhan chỉ trả phần tôi được nhận và chưa về", async () => {
  datTokenPhien("token-thu");
  globalThis.fetch = async () =>
    json(200, {
      batch_id: "b-1",
      disputed_count: 1,
      payment_reported_count: 0,
      obligations: [
        { obligation_id: "o-1", sender_id: AN, recipient_id: BAN, amount_vnd: 75000, obligation_status: "outstanding", disputed: false },
        { obligation_id: "o-2", sender_id: AN, recipient_id: BAN, amount_vnd: 10000, obligation_status: "outstanding", disputed: true },
        { obligation_id: "o-3", sender_id: BAN, recipient_id: AN, amount_vnd: 5000, obligation_status: "confirmed", disputed: false },
      ],
    });
  const bang = await docBangThu("c-1", "b-1", BAN);
  assert.equal(bang.soTranhCai, 1);
  assert.deepEqual(bang.nghiaVu.map((n) => n.trangThai), ["outstanding", "disputed", "confirmed"]);
  assert.deepEqual(nghiaVuToiNhan(bang.nghiaVu, BAN).map((n) => n.id), ["o-1"]);
  assert.deepEqual(nghiaVuToiNhan(bang.nghiaVu, AN), []);
  assert.equal(cauHangNghiaVu(bang.nghiaVu[0], ROSTER), "An QA → Ban QA");
  assert.deepEqual(tomTatBang(bang.nghiaVu), { daVe: 1, tong: 3, nguoiXong: 1, nguoiGui: 2 });
  datTokenPhien(null);
});

test("loiNhanChiaSe: lời nhắn của App B, tiền theo định dạng vỏ RuDi, link là link máy chủ trả", () => {
  const cau = loiNhanChiaSe({ senderId: AN, senderName: "An QA", amountVnd: 75000, url: "http://x/g/tok", opened: false, obligations: [] });
  assert.equal(cau, "Phần của An QA: 75.000đ\nhttp://x/g/tok\n\nLink này dành cho An QA; ai có link đều xem được phần của An QA.");
});
