/* Anti-drift: the TypeScript app and the Python web layer format money from
 * the same golden file. Run with: node packages/shared/money.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { formatVnd } from "./money.mjs";

const { cases } = JSON.parse(readFileSync(new URL("./money-format.cases.json", import.meta.url)));
assert.ok(cases.length >= 10, "golden corpus is too small to catch anything");

for (const { amount_vnd: amount, display } of cases) {
  assert.equal(formatVnd(amount), display, `${amount} should render as ${display}`);
}

for (const bad of [1.5, -1, "82000", null, undefined, NaN]) {
  assert.throws(() => formatVnd(bad), `${String(bad)} must be refused`);
}

console.log(`money.mjs: ${cases.length} golden cases + 6 refusals, all pass`);

/* parseAmountVnd: the boundary is checked on the digit string, so these cases
 * are about what a double would have silently done to the value.
 */
import { MAX_AMOUNT_VND, parseAmountVnd } from "./money.mjs";

const accepted = [
  ["0", 0],
  ["000", 0],
  ["82000", 82_000],
  ["82.000", 82_000],
  ["82,000", 82_000],
  ["1 000 000", 1_000_000],
  ["  480000  ", 480_000],
  [String(MAX_AMOUNT_VND), MAX_AMOUNT_VND],
  // repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
  ["0000000082000", 82_000],
];
for (const [typed, value] of accepted) {
  const got = parseAmountVnd(typed);
  assert.deepEqual(got, { ok: true, value }, `${typed} should parse to ${value}`);
}

const refused = [
  ["", "empty"],
  ["   ", "empty"],
  ["abc", "not-a-number"],
  ["82k", "not-a-number"],
  ["-5", "not-a-number"],
  ["1.5e3", "not-a-number"],
  ["...", "not-a-number"],
  [String(MAX_AMOUNT_VND + 1), "too-large"],
  // repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
  ["9999999999999", "too-large"],
  // Past Number.MAX_SAFE_INTEGER. `Number` returns ...992 for this and
  // `Number.isInteger` still says true, so the usual guard would pass a value
  // that is not the one the person typed.
  // repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
  ["9007199254740993", "too-large"],
];
for (const [typed, reason] of refused) {
  const got = parseAmountVnd(typed);
  assert.deepEqual(got, { ok: false, reason }, `${typed} should be refused as ${reason}`);
}

// The refusal above is only meaningful if the naive version really does lose it.
// repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
assert.equal(Number("9007199254740993"), 9007199254740992);
// repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
assert.equal(Number.isInteger(Number("9007199254740993")), true);

console.log(
  `money.mjs: parseAmountVnd ${accepted.length} accepted + ${refused.length} refused, all pass`,
);
