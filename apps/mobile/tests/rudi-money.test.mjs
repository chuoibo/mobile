/* Draft money on the RuDi fixture screens.
 *
 * This is not the product allocator. `src/api.ts` must stay free of split
 * arithmetic (`tests/offline.test.mjs`). These tests pin the one story
 * settlement and finance are allowed to print: integer dong, line sums, and
 * one picture for both screens.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  DraftMoneyError,
  collectorReceives,
  dongQuotient,
  draftPicture,
  lineTotal,
  sharesByPerson,
  splitLine,
  transfersToCollector,
} from "../dist-test/rudi/money.js";

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

test("splitLine sums to the line and stays integer", () => {
  for (const amount of [1, 3, 7, 100, 450_000, 560_000, 75_000]) {
    for (const people of [1, 2, 3, 4, 8]) {
      const parts = splitLine(amount, people);
      assert.equal(parts.length, people);
      let sum = 0;
      for (const part of parts) {
        assert.equal(Number.isInteger(part), true, `share ${part} is not integer`);
        sum += part;
      }
      assert.equal(sum, amount);
    }
  }
});

test("dongQuotient refuses float and a zero person count", () => {
  assert.throws(() => dongQuotient(10.5, 2), DraftMoneyError);
  assert.throws(() => dongQuotient(10, 0), DraftMoneyError);
  assert.equal(dongQuotient(10, 3), 3);
});

test("canonical Xóm Lèo bill is 1_280_000 and the trip is 3_840_000", () => {
  const picture = draftPicture({
    billLines: BILL,
    otherLines: OTHER,
    personCount: 8,
    collectorIndex: 0,
  });
  assert.equal(picture.billTotal, 1_280_000);
  assert.equal(picture.otherTotal, 2_560_000);
  assert.equal(picture.tripTotal, 3_840_000);
  assert.equal(lineTotal(BILL), picture.billTotal);
  const shareSum = picture.shares.reduce((sum, n) => sum + n, 0);
  assert.equal(shareSum, picture.billTotal);
  assert.equal(picture.spent.reduce((sum, n) => sum + n, 0), picture.tripTotal);
});

test("settlement and personal spend move together when an assignment changes", () => {
  const before = draftPicture({
    billLines: BILL,
    otherLines: OTHER,
    personCount: 8,
    collectorIndex: 0,
  });
  const afterLines = BILL.map((line, index) =>
    index === 1 ? { amount: line.amount, personIndexes: [0, 1, 3] } : line,
  );
  const after = draftPicture({
    billLines: afterLines,
    otherLines: OTHER,
    personCount: 8,
    collectorIndex: 0,
  });
  assert.equal(after.billTotal, before.billTotal);
  assert.equal(after.tripTotal, before.tripTotal);
  assert.notEqual(after.shares[0], before.shares[0]);
  assert.notEqual(after.spent[0], before.spent[0]);
  assert.notEqual(after.collectorReceives, before.collectorReceives);
  assert.equal(after.spent[0] - after.shares[0], after.otherShares[0]);
  assert.equal(after.spent[0] - after.shares[0], before.spent[0] - before.shares[0]);
  assert.equal(after.collectorReceives, collectorReceives(after.shares, 0));
  const transferSum = after.transfers.reduce((sum, row) => sum + row.amount, 0);
  assert.equal(transferSum, after.collectorReceives);
});

test("collector does not appear as a transfer and remainder stays on the first people", () => {
  const shares = sharesByPerson([{ amount: 100, personIndexes: [0, 1, 2] }], 3);
  assert.deepEqual(shares, [34, 33, 33]);
  const transfers = transfersToCollector(shares, 0);
  assert.deepEqual(transfers, [
    { fromIndex: 1, amount: 33 },
    { fromIndex: 2, amount: 33 },
  ]);
  assert.equal(collectorReceives(shares, 0), 66);
});
