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

test("a partly-dangling citation is refused, not quietly trimmed", () => {
  // This test asserted the opposite until QA read the function and pointed out
  // what the opposite meant: the surviving citation carried the expense, so
  // ["m1", "m99"] displayed as fully sourced. If m99 held the number, the
  // person is told the reverse of the truth.
  //
  // Third time today a test has pinned a gap rather than a promise. The shape
  // is always the same -- it describes what the code does, so it passes, and
  // the fact that what the code does is wrong never comes up.
  const { grounded, ungrounded } = review(
    { expenses: [expense({ sourceMessageIds: ["m1", "m99"] })], questions: [] },
    THREAD,
  );
  assert.equal(grounded.length, 0);
  assert.equal(ungrounded.length, 1);
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

/* Three ways a citation can be worthless, all found by QA reading `review()`.
 *
 * ADR-0008 let the bot read the whole thread in exchange for citing its
 * sources. A citation nobody checks is not a citation, and these are the three
 * ways the check was not happening.
 */
test("a dangling id poisons the whole expense, even beside a real one", async () => {
  const { review } = await import("../dist-test/extraction.js");
  // The surviving citation used to carry the expense. If the missing message
  // held the number, the person is told the opposite of the truth.
  const { grounded, ungrounded, blocked } = review(
    {
      expenses: [expense({ sourceMessageIds: ["m1", "m_khong_ton_tai"] })],
      questions: [],
    },
    THREAD,
  );
  assert.equal(grounded.length, 0);
  assert.equal(ungrounded.length, 1);
  assert.equal(blocked, true);
});

test("a citation to a message that never mentions the amount is refused", async () => {
  const { review } = await import("../dist-test/extraction.js");
  const chat = [{ id: "m1", author: "Nam", text: "chào cả nhà" }];
  const { grounded, ungrounded } = review(
    {
      expenses: [
        { totalVnd: 500_000, paidBy: "Nam", label: "ăn trưa", sourceMessageIds: ["m1"] },
      ],
      questions: [],
    },
    chat,
  );
  // Otherwise the screen prints a greeting under "Đọc từ tin nhắn này" and
  // calls it evidence.
  assert.equal(grounded.length, 0);
  assert.equal(ungrounded.length, 1);
});

test("the amounts people actually type are recognised", async () => {
  const { messageMentionsAmount } = await import("../dist-test/extraction.js");
  const yes = [
    ["tao trả 800000 rồi", 800_000],
    ["tao trả 800.000 rồi", 800_000],
    ["tao trả 800,000 rồi", 800_000],
    ["hết 800k nhé", 800_000],
    ["hết 85 nghìn", 85_000],
    ["hết 85 ngàn thôi", 85_000],
    ["khách sạn 1tr2", 1_200_000],
    ["khách sạn 2tr350", 2_350_000],
    ["hết 3 triệu", 3_000_000],
  ];
  for (const [text, amount] of yes) {
    assert.equal(messageMentionsAmount(text, amount), true, `${text} -> ${amount}`);
  }

  const no = [
    ["chào cả nhà", 500_000],
    ["hết 800k nhé", 900_000],
    ["khách sạn 1tr2", 1_000_000],
    ["mai đi chơi nhé", 82_000],
  ];
  for (const [text, amount] of no) {
    assert.equal(messageMentionsAmount(text, amount), false, `${text} -/-> ${amount}`);
  }
});

test("a real citation that does mention the amount still passes", async () => {
  const { review } = await import("../dist-test/extraction.js");
  const { grounded, blocked } = review(
    { expenses: [expense()], questions: [] },
    THREAD,
  );
  assert.equal(grounded.length, 1, "the honest case must not be caught by the guard");
  assert.equal(blocked, false);
});
