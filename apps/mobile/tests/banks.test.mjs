/* Two copies of the bank directory, and whether they still agree.
 *
 * The guest page names banks from `services/api/app/web/banks.py`. The app
 * names them from `packages/shared/banks.json`, because a React Native bundle
 * cannot import Python. That is two hand-maintained copies of the same table,
 * which is exactly the drift `theme.ts` was written to avoid for colours.
 *
 * The consequence of drift here is specific and bad: one surface says "MB Bank"
 * and the other says "Techcombank" for the same BIN, so a person sees one name
 * in the app, a different name on the link they were sent, and has no way to
 * know which app to open. A transfer to the wrong bank does not bounce
 * politely.
 *
 * So the JSON is checked against the Python by parsing the Python. Not by
 * importing it -- there is no interpreter in this test run -- but by reading
 * the literal out of the source file. That is fragile if somebody rewrites
 * `BANKS` as a comprehension, and this test failing loudly is the correct
 * response to that: it means the copies can no longer be compared, which is
 * the thing that has to be noticed.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { bankDisplayName } from "../dist-test/ui/vietqr.js";

const MOBILE = dirname(dirname(fileURLToPath(import.meta.url)));
const REPO = dirname(dirname(MOBILE));

const JSON_TABLE = JSON.parse(
  readFileSync(join(REPO, "packages", "shared", "banks.json"), "utf8"),
).banks;

/** Pull the `BANKS = { ... }` literal out of the Python source. */
function pythonTable() {
  const source = readFileSync(
    join(REPO, "services", "api", "app", "web", "banks.py"),
    "utf8",
  );
  const block = source.match(/^BANKS = \{$([\s\S]*?)^\}$/m);
  assert.ok(
    block !== null,
    "could not find a `BANKS = {` literal in banks.py; the two directories can " +
      "no longer be compared, which is the thing this test exists to notice",
  );
  const table = {};
  for (const line of block[1].split("\n")) {
    const row = line.match(/^\s*"(\d+)":\s*"([^"]+)",?\s*$/);
    if (row !== null) table[row[1]] = row[2];
  }
  return table;
}

test("the app's bank directory matches the guest page's, entry for entry", () => {
  const python = pythonTable();
  assert.ok(Object.keys(python).length > 10, "parsed suspiciously few banks");
  assert.deepEqual(
    JSON_TABLE,
    python,
    "banks.json and banks.py disagree; the app and the guest page would name " +
      "the same BIN differently",
  );
});

test("a known BIN gets its name", () => {
  assert.equal(bankDisplayName("970422"), "MB Bank");
  assert.equal(bankDisplayName("970436"), "Vietcombank");
});

test("an unknown BIN keeps the code and is labelled as one", () => {
  // Same rule as `bank_display_name` in Python: inventing a name sends
  // somebody confidently into the wrong app.
  assert.equal(bankDisplayName("999999"), "Mã ngân hàng 999999");
});
