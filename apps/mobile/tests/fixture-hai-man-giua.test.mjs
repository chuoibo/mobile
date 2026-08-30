/** The fixture behind `?man=nhan-dien` and `?man=goi-y-chia` is one bill.
 *
 * `DEMO_READING` + `DEMO_ASSIGNMENT` (the two middle screens) and
 * `DEMO_ALLOCATIONS` + `DEMO_OBLIGATIONS` (the settlement screen) describe the
 * same dinner at two moments. Nothing in the type system says so, and the two
 * halves were written months apart, so the agreement is exactly the kind that
 * rots quietly: change one line total, and the scan pages still render, still
 * exit 0, and still get reported as "the hero path was measured".
 *
 * What rendering-wrong looks like is specific and worth naming, because it is
 * not a crash. `GoiYChia` paints a preview only while
 * `preview.signature === signature(reading, ids, assignment)`, and it prints
 * "..." in every cell otherwise -- deliberately, because a stale dong under a
 * tick is a money error. So a drifted fixture produces a screen that is
 * *plausible*, fully laid out, and mid-flight. A detector would measure it and
 * report contrast and geometry for a state the product only shows for a
 * fraction of a second.
 *
 * This file therefore recomputes the split from the matrix by hand -- an
 * independent fold, not a call into the app's own splitter -- and holds it
 * against the settlement numbers.
 *
 * What it does NOT prove: that the allocator would produce these numbers from
 * this matrix. That is `services/api` domain work and has 41 golden vectors of
 * its own. This checks that the FIXTURE is self-consistent, which is the part
 * that decides whether the scan pages show a settled screen or a stuck one.
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  DEMO_ALLOCATIONS,
  DEMO_ASSIGNMENT,
  DEMO_ITEM_COUNT,
  DEMO_NHOM,
  DEMO_READING,
  DEMO_ROSTER,
  DEMO_SPLIT_PREVIEW,
} from "../dist-test/fixtures/thanh-toan-demo.js";
import { itemsTotalVnd } from "../dist-test/receipt.js";

const TONG = 1125000;

test("bill có đúng số dòng màn thanh toán khoe, và tổng khớp cả ba nguồn", () => {
  assert.equal(DEMO_READING.lines.length, DEMO_ITEM_COUNT);

  const congDong = itemsTotalVnd(DEMO_READING);
  assert.equal(congDong, TONG, "tổng các dòng đã đổi");
  assert.equal(
    DEMO_READING.printedTotalVnd,
    congDong,
    "số in trên giấy phải khớp tổng các dòng, nếu không màn hiện cảnh báo lệch",
  );

  const congPhanBo = Object.values(DEMO_ALLOCATIONS).reduce((a, b) => a + b, 0);
  assert.equal(congPhanBo, congDong, "Σ phân bổ ≠ tổng khoản chi");
});

test("gán món cho người, gấp lại bằng tay, ra đúng bốn con số của màn thanh toán", () => {
  const phanBo = {};
  for (const nguoi of DEMO_ROSTER.participants) phanBo[nguoi.id] = 0;

  for (const line of DEMO_READING.lines) {
    const an = DEMO_ASSIGNMENT[line.id] ?? [];
    assert.ok(an.length > 0, `dòng ${line.id} không ai ăn -- màn sẽ chặn nút chia`);

    // Exact division is a property of this fixture, not of the product: the
    // allocator handles remainders and has golden vectors for it. Asserting it
    // here means a hand-edited line total that no longer divides gets named
    // now, rather than turning into an off-by-one nobody can source later.
    assert.equal(
      line.lineTotalVnd % an.length,
      0,
      `dòng ${line.id}: ${line.lineTotalVnd} không chia hết cho ${an.length} người`,
    );

    for (const id of an) {
      assert.ok(id in phanBo, `dòng ${line.id} gán cho ${id}, không có trong roster`);
      phanBo[id] += line.lineTotalVnd / an.length;
    }
  }

  assert.deepEqual(phanBo, DEMO_ALLOCATIONS);
});

test("ma trận và bill nói về cùng một tập dòng", () => {
  const tuBill = DEMO_READING.lines.map((l) => l.id).sort();
  const tuMaTran = Object.keys(DEMO_ASSIGNMENT).sort();
  assert.deepEqual(tuMaTran, tuBill, "ma trận gán cho dòng không có trên bill, hoặc bỏ sót dòng");
});

test("preview đưa cho màn chính là bộ số của màn thanh toán, không phải bản sao rời", () => {
  assert.deepEqual(DEMO_SPLIT_PREVIEW.allocations, DEMO_ALLOCATIONS);

  // Every division above was exact, so an empty gainer list is the honest
  // answer. If somebody makes a line indivisible, the test above goes red
  // first -- this one stops the list from being left empty afterwards.
  assert.deepEqual(DEMO_SPLIT_PREVIEW.roundingGainers, []);
});

test("mọi người trên bill là thành viên nhóm, và nhóm còn người chưa lên bill", () => {
  const trongNhom = new Set(DEMO_NHOM.map((m) => m.id));
  for (const nguoi of DEMO_ROSTER.participants) {
    assert.ok(trongNhom.has(nguoi.id), `${nguoi.name} ăn bill này mà không ở trong nhóm`);
  }

  // Without this the "Thêm người" picker opens on an empty list, which is a
  // dead end and the least useful state to hand a detector.
  const conLai = DEMO_NHOM.filter((m) => !DEMO_ROSTER.participants.some((p) => p.id === m.id));
  assert.ok(conLai.length > 0, "không còn ai để thêm, ô chọn người sẽ rỗng");
});
