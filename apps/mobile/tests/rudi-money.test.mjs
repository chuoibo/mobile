/* Draft money on the RuDi fixture screens.
 *
 * This is not the product allocator. `src/api.ts` must stay free of split
 * arithmetic (`tests/offline.test.mjs`). What these tests pin is that the
 * draft the screens print uses the SAME rounding the server will use when the
 * expense is confirmed, so the number a person reads does not move by a few
 * đồng at confirm time with nothing on screen to explain it.
 *
 * ## Where the expected numbers come from
 *
 * Not from this file's author. Every vector below was produced by running the
 * server's own allocator over the same expense, and it can be re-derived:
 *
 *     cd services/api && python3 - <<'PY'
 *     import sys; sys.path.insert(0, ".")
 *     from app.domain.allocator import allocate
 *     IDS = ["minh-anh","tuan-kiet","thu-trang","quang-huy",
 *            "lan-anh","minh-khoa","hai-yen","thanh-phuc"]
 *     BILL = [(450_000,[0,1,2,3]), (560_000,[1,3]), (75_000,[0,2,4]),
 *             (45_000,[0,2,3]), (20_000,[0,1,2,3]), (130_000,list(range(8)))]
 *     exp = {"participants": IDS, "total_vnd": sum(a for a,_ in BILL),
 *            "items": [{"item_id": f"i{n}", "amount_vnd": a,
 *                       "shared_by": [IDS[i] for i in who]}
 *                      for n,(a,who) in enumerate(BILL)],
 *            "surcharges": [], "discounts": [], "advancer_id": IDS[0]}
 *     print(allocate(exp)["allocations"])
 *     PY
 *
 * Two people writing the same answer twice is the failure mode `CLAUDE.md`
 * names for the golden corpus itself, so the numbers are copied from the other
 * implementation rather than recomputed by hand here.
 *
 * ## The vector that proves the two rounding rules were different
 *
 * On the default assignment every line divides evenly, so the old per-line
 * rule and the server's whole-expense rule agree and no test could tell them
 * apart. `minh-anh joins "Bò nướng"` is the case where they diverge: 560.000đ
 * over three leaves two đồng, and the old rule handed them to array positions
 * 0 and 1 while the server hands them to the largest remainders, advancer
 * first. The collector's own share differs by exactly one đồng between the two
 * answers -- small enough to never be noticed, which is what made it worth a
 * gate.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  DraftMoneyError,
  collectorReceives,
  draftPicture,
  lineTotal,
  sharesByPerson,
  transfersToCollector,
} from "../dist-test/rudi/money.js";

const IDS = [
  "minh-anh",
  "tuan-kiet",
  "thu-trang",
  "quang-huy",
  "lan-anh",
  "minh-khoa",
  "hai-yen",
  "thanh-phuc",
];

const BILL = [
  { amount: 450_000, personIndexes: [0, 1, 2, 3] },
  { amount: 560_000, personIndexes: [1, 3] },
  { amount: 75_000, personIndexes: [0, 2, 4] },
  { amount: 45_000, personIndexes: [0, 2, 3] },
  { amount: 20_000, personIndexes: [0, 1, 2, 3] },
  { amount: 130_000, personIndexes: [0, 1, 2, 3, 4, 5, 6, 7] },
];

const OTHER = [
  { amount: 2_000_000, personIndexes: [0, 1, 2, 3, 4, 5, 6, 7] },
  { amount: 560_000, personIndexes: [0, 1, 2, 3, 4, 5, 6, 7] },
];

/** `allocate()` over BILL with `advancer_id = "minh-anh"`. */
const SERVER_BILL = [173_750, 413_750, 173_750, 428_750, 41_250, 16_250, 16_250, 16_250];
/** `allocate()` over OTHER with `advancer_id = None`. */
const SERVER_OTHER = [320_000, 320_000, 320_000, 320_000, 320_000, 320_000, 320_000, 320_000];
/** Same call, with `minh-anh` added to the `Bò nướng` line. Gainers: minh-anh, quang-huy. */
const SERVER_BILL_WITH_MINH_ANH = [
  360_417, 320_416, 173_750, 335_417, 41_250, 16_250, 16_250, 16_250,
];

test("bill shares match the server allocator đồng for đồng", () => {
  assert.deepEqual(sharesByPerson(BILL, IDS, 0), SERVER_BILL);
  assert.equal(SERVER_BILL.reduce((sum, n) => sum + n, 0), lineTotal(BILL));
});

test("the divergent case matches too, and it is one đồng away from the old rule", () => {
  const lines = BILL.map((line, index) =>
    index === 1 ? { amount: line.amount, personIndexes: [1, 3, 0] } : line,
  );
  const shares = sharesByPerson(lines, IDS, 0);
  assert.deepEqual(shares, SERVER_BILL_WITH_MINH_ANH);
  // Money law 2 held under the old rule as well, which is why summing was not
  // enough to catch this.
  assert.equal(shares.reduce((sum, n) => sum + n, 0), 1_280_000);
  // The old per-line rule gave the collector 360_416 by handing the two spare
  // đồng to array positions instead of to the largest remainders.
  assert.equal(shares[0], 360_417);
});

test("the answer does not depend on the order people were tapped in", () => {
  const orders = [
    [1, 3, 0],
    [0, 1, 3],
    [3, 0, 1],
    [3, 1, 0],
  ];
  for (const order of orders) {
    const lines = BILL.map((line, index) =>
      index === 1 ? { amount: line.amount, personIndexes: order } : line,
    );
    assert.deepEqual(
      sharesByPerson(lines, IDS, 0),
      SERVER_BILL_WITH_MINH_ANH,
      `order ${order.join(",")} changed the split`,
    );
  }
});

test("advancer absorbs the rounding on a tie, and loses the tie-break when absent", () => {
  // Mirrors `tests/domain/golden/01_even_split.json` G02 and G03.
  const line = [{ amount: 100_000, personIndexes: [0, 1, 2] }];
  assert.deepEqual(sharesByPerson(line, ["a", "b", "c"], 1), [33_333, 33_334, 33_333]);
  assert.deepEqual(sharesByPerson(line, ["a", "b", "c"], null), [33_334, 33_333, 33_333]);
});

test("tie-break reads id bytes, not array position", () => {
  const line = [{ amount: 100, personIndexes: [0, 1, 2] }];
  // Positions unchanged, ids reordered: the extra đồng follows the id.
  assert.deepEqual(sharesByPerson(line, ["c", "a", "b"], null), [33, 34, 33]);
  assert.deepEqual(sharesByPerson(line, ["a", "b", "c"], null), [34, 33, 33]);
});

test("canonical Xóm Lèo bill is 1_280_000 and the trip is 3_840_000", () => {
  const picture = draftPicture({
    billLines: BILL,
    otherLines: OTHER,
    personIds: IDS,
    collectorIndex: 0,
  });
  assert.equal(picture.billTotal, 1_280_000);
  assert.equal(picture.otherTotal, 2_560_000);
  assert.equal(picture.tripTotal, 3_840_000);
  assert.deepEqual(picture.shares, SERVER_BILL);
  assert.deepEqual(picture.otherShares, SERVER_OTHER);
  assert.equal(
    picture.shares.reduce((sum, n) => sum + n, 0),
    picture.billTotal,
  );
  assert.equal(
    picture.spent.reduce((sum, n) => sum + n, 0),
    picture.tripTotal,
  );
});

test("settlement and personal spend move together when an assignment changes", () => {
  const before = draftPicture({
    billLines: BILL,
    otherLines: OTHER,
    personIds: IDS,
    collectorIndex: 0,
  });
  const after = draftPicture({
    billLines: BILL.map((line, index) =>
      index === 1 ? { amount: line.amount, personIndexes: [1, 3, 0] } : line,
    ),
    otherLines: OTHER,
    personIds: IDS,
    collectorIndex: 0,
  });
  assert.equal(after.billTotal, before.billTotal);
  assert.equal(after.tripTotal, before.tripTotal);
  assert.notEqual(after.shares[0], before.shares[0]);
  assert.notEqual(after.spent[0], before.spent[0]);
  assert.notEqual(after.collectorReceives, before.collectorReceives);
  // The other bucket is untouched by a bill assignment.
  assert.equal(after.spent[0] - after.shares[0], after.otherShares[0]);
  assert.equal(after.spent[0] - after.shares[0], before.spent[0] - before.shares[0]);
  assert.equal(after.collectorReceives, 1_280_000 - 360_417);
  const transferSum = after.transfers.reduce((sum, row) => sum + row.amount, 0);
  assert.equal(transferSum, after.collectorReceives);
});

test("collector does not appear as a transfer", () => {
  const shares = sharesByPerson([{ amount: 100, personIndexes: [0, 1, 2] }], ["a", "b", "c"], 0);
  assert.deepEqual(shares, [34, 33, 33]);
  assert.deepEqual(transfersToCollector(shares, 0), [
    { fromIndex: 1, amount: 33 },
    { fromIndex: 2, amount: 33 },
  ]);
  assert.equal(collectorReceives(shares, 0), 66);
});

test("refuses the inputs that would make the draft quietly wrong", () => {
  const roster = ["a", "b", "c"];
  assert.throws(
    () => sharesByPerson([{ amount: 10.5, personIndexes: [0] }], roster, 0),
    DraftMoneyError,
  );
  assert.throws(
    () => sharesByPerson([{ amount: -1, personIndexes: [0] }], roster, 0),
    DraftMoneyError,
  );
  assert.throws(() => sharesByPerson([{ amount: 10, personIndexes: [] }], roster, 0), DraftMoneyError);
  assert.throws(() => sharesByPerson([{ amount: 10, personIndexes: [3] }], roster, 0), DraftMoneyError);
  assert.throws(() => sharesByPerson([{ amount: 10, personIndexes: [0] }], roster, 9), DraftMoneyError);
  assert.throws(() => sharesByPerson([{ amount: 10, personIndexes: [0] }], [], 0), DraftMoneyError);
  // A person named twice on one line eats one share, not two.
  assert.deepEqual(sharesByPerson([{ amount: 100, personIndexes: [0, 0, 1] }], roster, null), [
    50, 50, 0,
  ]);
});
