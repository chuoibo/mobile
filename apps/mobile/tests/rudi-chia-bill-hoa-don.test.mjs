/* Chia hóa đơn in the RuDi shell (M5): the bridge module.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-chia-bill-hoa-don.test.mjs
 *
 * What matters most: nothing here divides -- the allocations the screen
 * draws are the server's; the expense is proposed with the bill's items and
 * confirmed under its own Attempt; a name never falls back to an id; a new
 * line never reuses an id.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datTokenPhien } from "../dist-test/api.js";
import {
  cauSauKhiScanHong,
  cauTongMon,
  ghiVaoSo,
  hangKetQua,
  hoaDonTrong,
  nguoiThamGia,
  tenCua,
  themMon,
} from "../dist-test/rudi/chia-bill/hoa-don.js";
import { removeLine, renameLine, setLineTotal } from "../dist-test/receipt.js";

const ROSTER = [
  { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", name: "An QA" },
  { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", name: "Ban QA" },
];

function hoaDonHaiMon() {
  let r = themMon(hoaDonTrong());
  r = renameLine(r, "mon-0", "Bun bo");
  r = setLineTotal(r, "mon-0", "150000").reading;
  r = themMon(r);
  r = renameLine(r, "mon-1", "Nuoc");
  r = setLineTotal(r, "mon-1", "50000").reading;
  return r;
}

test("themMon không dùng lại id sau khi bỏ một món", () => {
  let r = hoaDonHaiMon();
  r = removeLine(r, "mon-0");
  r = themMon(r);
  assert.deepEqual(r.lines.map((l) => l.id), ["mon-1", "mon-2"]);
});

test("cauTongMon cộng thành tiền (cộng, không chia) và in tiền dạng Việt", () => {
  assert.equal(cauTongMon(hoaDonHaiMon()), "2 món · 200.000đ");
  assert.equal(cauTongMon(hoaDonTrong()), "0 món · 0đ");
});

test("nguoiThamGia là những người có mặt trong ít nhất một món, theo thứ tự nhóm", () => {
  const r = hoaDonHaiMon();
  const a = { "mon-0": [ROSTER[1].id, ROSTER[0].id], "mon-1": [ROSTER[1].id] };
  assert.deepEqual(nguoiThamGia(r, a, ROSTER).map((p) => p.name), ["An QA", "Ban QA"]);
  assert.deepEqual(nguoiThamGia(r, { "mon-0": [], "mon-1": [] }, ROSTER), []);
});

test("tenCua không bao giờ trả id", () => {
  assert.equal(tenCua(ROSTER, ROSTER[0].id), "An QA");
  assert.equal(tenCua(ROSTER, "cccccccc-cccc-4ccc-8ccc-cccccccccccc"), "Thành viên");
});

test("hangKetQua vẽ đúng số máy chủ đưa, ghi ai nhận lẻ đồng, xếp theo tên", () => {
  const hang = hangKetQua(
    { allocations: { [ROSTER[1].id]: 125000, [ROSTER[0].id]: 75000 }, exactShares: {}, roundingGainers: [ROSTER[1].id], warnings: [], assignmentState: "confirmed", suggestedItemKeys: [], totalAmountVnd: 200000 },
    ROSTER,
  );
  assert.deepEqual(hang.map((h) => [h.ten, h.tien, h.lamTron]), [["An QA", "75.000đ", false], ["Ban QA", "125.000đ", true]]);
});

test("ghiVaoSo đề xuất với items của bill rồi chốt, mỗi lần một Attempt riêng, kèm expected_allocations", async () => {
  datTokenPhien("token-thu");
  const goi = [];
  globalThis.fetch = async (url, init = {}) => {
    const body = init.body ? JSON.parse(init.body) : null;
    goi.push({ url: String(url), method: init.method, body, key: init.headers?.["Idempotency-Key"] });
    if (String(url).endsWith("/expenses")) {
      return new Response(
        JSON.stringify({ expense_id: "e-1", proposal: body, allocation: { allocations: { [ROSTER[0].id]: 75000, [ROSTER[1].id]: 125000 }, rounding_gainers: [], warnings: [] } }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(JSON.stringify({ expense_version_id: "v-1", payer_acknowledgement: "acknowledged" }), { status: 201, headers: { "Content-Type": "application/json" } });
  };
  const r = hoaDonHaiMon();
  const a = { "mon-0": [ROSTER[0].id, ROSTER[1].id], "mon-1": [ROSTER[1].id] };
  const attempts = {};
  const kq = await ghiVaoSo({ reading: r, assignment: a, roster: ROSTER, contextId: "c-1", payerId: ROSTER[1].id, occasion: "Toi", attempts });
  assert.equal(kq.expenseVersionId, "v-1");
  assert.equal(goi[0].method, "POST");
  assert.match(goi[0].url, /\/expenses$/);
  assert.equal(goi[0].body.total_amount_vnd, 200000);
  assert.equal(goi[0].body.paid_by_id, ROSTER[1].id);
  assert.deepEqual(goi[0].body.items.map((i) => [i.label, i.amount_vnd, i.shared_by.length]), [["Bun bo", 150000, 2], ["Nuoc", 50000, 1]]);
  assert.match(goi[1].url, /\/expenses\/e-1\/confirm$/);
  assert.deepEqual(goi[1].body.expected_allocations, { [ROSTER[0].id]: 75000, [ROSTER[1].id]: 125000 });
  assert.notEqual(goi[0].key, goi[1].key, "hai lời gọi, hai Attempt");
  assert.equal(Object.keys(attempts).length, 2);
  datTokenPhien(null);
});

test("cauSauKhiScanHong nối câu máy chủ với lối ra nhập tay", () => {
  assert.equal(cauSauKhiScanHong("Máy chủ chưa cấu hình trình đọc bill."), "Máy chủ chưa cấu hình trình đọc bill. Bạn có thể nhập món bằng tay.");
});
