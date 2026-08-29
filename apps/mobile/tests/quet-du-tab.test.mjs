/* Every tab that claims to be built is a tab the detector has actually seen.
 *
 * "Lên plan" shipped as `kind: "built"` and was never once scanned. Three of
 * the four tabs were in `tab-snapshots.mjs`, the fourth was not, and nothing
 * anywhere said so: the snapshot tool wrote the files it knew about and exited
 * 0, the detector scanned the files it was handed and exited on those, and a
 * report saying "the tabs are clean" was true about three quarters of the bar.
 * A missing screen and a clean screen produce the same green.
 *
 * So the list of scanned screens is checked against `tabs.ts`, which is the
 * file that decides what exists. Adding a fifth tab without adding it here
 * turns this red, which is the only moment anybody would find out.
 *
 * What this proves: the scan list covers the built tabs. What it does not
 * prove: that a scan was run, that it was run on the current bundle, or that
 * it found nothing. Those are `imp detect` and a person reading its output --
 * see ADR-0010 on why a digest is not evidence.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { TABS } from "../dist-test/navigation/tabs.js";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = join(MOBILE_ROOT, "tools/tab-snapshots.mjs");

/**
 * The `SCREENS` rows, read out of the tool's source.
 *
 * Read as text rather than imported on purpose. `tab-snapshots.mjs` runs its
 * own `main()` when loaded, so importing it here would launch Chromium and
 * drive the whole tab suite as a side effect of a unit test. Parsing the
 * literal keeps this file cheap and keeps the tool free to stay a script.
 */
function scannedTabs() {
  const src = readFileSync(TOOL, "utf8");
  const block = /const SCREENS = \[(.*?)\];/s.exec(src);
  // A regex that matches nothing would make every assertion below vacuously
  // true, which is the exact failure this file exists to catch. So the shape
  // of the block is itself an assertion.
  assert.ok(block, `không tìm thấy khối SCREENS trong ${TOOL}`);

  const rows = [...block[1].matchAll(/\btab:\s*"([^"]+)"/g)].map((m) => m[1]);
  assert.ok(rows.length > 0, "khối SCREENS không có dòng nào");
  return rows;
}

test("mọi tab khai là đã dựng đều nằm trong danh sách được chụp và quét", () => {
  const scanned = new Set(scannedTabs());
  const built = TABS.filter((t) => t.destination.kind === "built").map((t) => t.id);

  // Named one by one rather than as a set difference: a failure here should
  // say which tab nobody has ever looked at, not that two lists differ.
  const missing = built.filter((id) => !scanned.has(id));
  assert.deepEqual(
    missing,
    [],
    `tab đã dựng nhưng chưa bao giờ được quét: ${missing.join(", ")}`,
  );
});

test("mọi dòng trong danh sách quét là một tab có thật", () => {
  // The other direction, and it is not symmetric padding. A typo'd step scans
  // nothing while still writing a file named after a screen, so the report
  // carries a row for a tab that does not exist and reads as coverage.
  const ids = new Set(TABS.map((t) => t.id));
  const la = scannedTabs().filter((id) => !ids.has(id));
  assert.deepEqual(la, [], `danh sách quét trỏ tới tab không có thật: ${la.join(", ")}`);
});
