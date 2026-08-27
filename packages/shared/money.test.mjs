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
