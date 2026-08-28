/* What the proposal card is allowed to show, and what it must refuse.
 *
 * ADR-0008 traded away §5.1's explicit context snapshot so the bot could read
 * the whole thread. The thing accepted in exchange was that every extracted
 * expense cites the message it came from. These tests are that trade, written
 * down: a number without a checkable source does not reach a person as if it
 * were like any other number.
 *
 * Run from apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import { review } from "../dist-test/extraction.js";

const THREAD = [
  { id: "m1", author: "Nam", text: "tao vừa trả tiền ăn tối 800k nhé" },
  { id: "m2", author: "Hà", text: "ok" },
  { id: "m3", author: "Quyên", text: "xe về 145k tao ứng trước" },
];

const expense = (over = {}) => ({
  totalVnd: 800_000,
  paidBy: "Nam",
  label: "ăn tối",
  sourceMessageIds: ["m1"],
  ...over,
});

test("an expense citing a real message is shown with that message attached", () => {
  const { grounded, ungrounded } = review({ expenses: [expense()], questions: [] }, THREAD);
  assert.equal(ungrounded.length, 0);
  assert.equal(grounded.length, 1);
  assert.deepEqual(
    grounded[0].sources.map((m) => m.id),
    ["m1"],
  );
  // The author's own words, not a summary: a paraphrase would be the bot
  // checking its own reading.
  assert.equal(grounded[0].sources[0].text, "tao vừa trả tiền ăn tối 800k nhé");
});

test("an expense citing nothing is refused, not shown as a normal row", () => {
  const { grounded, ungrounded, blocked } = review(
    { expenses: [expense({ sourceMessageIds: [] })], questions: [] },
    THREAD,
  );
  assert.equal(grounded.length, 0);
  assert.equal(ungrounded.length, 1);
  assert.equal(blocked, true);
});

test("a citation pointing at a message that is not in the thread is refused too", () => {
  // Worse than citing nothing: it looks like provenance while pointing nowhere.
  const { grounded, ungrounded } = review(
    { expenses: [expense({ sourceMessageIds: ["m99"] })], questions: [] },
    THREAD,
  );
  assert.equal(grounded.length, 0);
  assert.equal(ungrounded.length, 1);
});

test("a partly-dangling citation keeps only the messages that exist", () => {
  const { grounded } = review(
    { expenses: [expense({ sourceMessageIds: ["m1", "m99"] })], questions: [] },
    THREAD,
  );
  assert.equal(grounded.length, 1);
  assert.deepEqual(
    grounded[0].sources.map((m) => m.id),
    ["m1"],
  );
});

test("an open question blocks acceptance even when every expense is grounded", () => {
  // §8.3. "I do not know who was there" is not settled, and letting it through
  // would make the question decorative.
  const { grounded, blocked } = review(
    { expenses: [expense()], questions: ["ai có mặt trong bữa ăn tối"] },
    THREAD,
  );
  assert.equal(grounded.length, 1);
  assert.equal(blocked, true);
});

test("nothing to ask and nothing ungrounded means acceptance is possible", () => {
  const { blocked } = review({ expenses: [expense()], questions: [] }, THREAD);
  assert.equal(blocked, false);
});

test("an empty extraction is not an error and is not blocked", () => {
  // "I found no expenses" is an honest answer to a thread about nothing.
  const { grounded, ungrounded, blocked } = review(
    { expenses: [], questions: [] },
    THREAD,
  );
  assert.equal(grounded.length, 0);
  assert.equal(ungrounded.length, 0);
  assert.equal(blocked, false);
});

test("two expenses from two messages stay separate", () => {
  const { grounded } = review(
    {
      expenses: [
        expense(),
        expense({ totalVnd: 145_000, paidBy: "Quyên", label: "xe về", sourceMessageIds: ["m3"] }),
      ],
      questions: [],
    },
    THREAD,
  );
  assert.equal(grounded.length, 2);
  assert.deepEqual(
    grounded.map((item) => item.expense.totalVnd),
    [800_000, 145_000],
  );
  // No total anywhere: the split belongs to the server's allocator, and adding
  // these here would be a second implementation of money.
  assert.equal(typeof review, "function");
});
