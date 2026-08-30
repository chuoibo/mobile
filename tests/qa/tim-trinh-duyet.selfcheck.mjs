/* Does tim-trinh-duyet() answer, and does it answer for the right reason?
 *
 * Run: cd tests/qa && npm run selfcheck
 *
 * The property that matters is not "returns a string". It is the ORDER, because
 * the whole point of replacing the pasted paths was that a scan cannot go stale
 * the way `chromium-1194` did. A resolver that always returned the first thing
 * it found would pass a naive test and still be the old bug.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { existsSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

import { timTrinhDuyet } from "./tim-trinh-duyet.mjs";

/** Run the resolver in a child with a specific environment. */
function voiEnv(env) {
  const src =
    'import("./tests/qa/tim-trinh-duyet.mjs")' +
    ".then((m) => console.log(m.timTrinhDuyet()))" +
    ".catch((e) => { console.error(e.message); process.exit(3); })";
  try {
    return {
      ok: true,
      out: execFileSync(process.execPath, ["-e", src], {
        cwd: new URL("../..", import.meta.url).pathname,
        env: { ...process.env, ...env },
        encoding: "utf8",
      }).trim(),
    };
  } catch (e) {
    return { ok: false, err: (e.stderr || "").trim() };
  }
}

test("tim duoc mot trinh duyet that, chay duoc", () => {
  const p = timTrinhDuyet();
  assert.ok(existsSync(p), `${p} khong ton tai`);
  const v = execFileSync(p, ["--version"], { encoding: "utf8" });
  assert.match(v, /Chrom/i, `khong phai Chromium: ${v}`);
});

test("PUPPETEER_EXECUTABLE_PATH thang moi thu khac", () => {
  const r = voiEnv({ PUPPETEER_EXECUTABLE_PATH: process.execPath });
  assert.ok(r.ok, r.err);
  assert.equal(r.out, process.execPath);
});

test("CHROME_BIN duoc doc khi khong co PUPPETEER_EXECUTABLE_PATH", () => {
  const r = voiEnv({ PUPPETEER_EXECUTABLE_PATH: "", CHROME_BIN: process.execPath });
  assert.ok(r.ok, r.err);
  assert.equal(r.out, process.execPath);
});

test("bien moi truong tro sai thi NEM, khong im lang roi ve mac dinh", () => {
  // The failure this guards: a typo'd override falls through to a working
  // browser, the probe runs against a browser nobody chose, and the run looks
  // clean. Loud is the only safe direction here.
  const r = voiEnv({ PUPPETEER_EXECUTABLE_PATH: "/khong/co/that/chrome" });
  assert.equal(r.ok, false, "phai nem khi duong dan chi dinh khong ton tai");
  assert.match(r.err, /khong ton tai/);
});

test("khong co bien nao thi quet cache, va lay ban MOI nhat", () => {
  const r = voiEnv({ PUPPETEER_EXECUTABLE_PATH: "", CHROME_BIN: "" });
  assert.ok(r.ok, r.err);
  assert.ok(existsSync(r.out), `${r.out} khong ton tai`);

  // The stale build numbers this replaced were 1187 and 1194; the cache also
  // holds 1234. If the scan is doing its job it never picks an older one when a
  // newer is present.
  const m = /chromium[_a-z]*-(\d+)/.exec(r.out);
  if (m) {
    const cache = join(homedir(), ".cache", "ms-playwright");
    const moiNhat = Math.max(
      ...readdirSync(cache)
        .filter((d) => d.startsWith("chromium-"))
        .map((d) => Number(/-(\d+)$/.exec(d)?.[1] ?? 0)),
    );
    assert.equal(Number(m[1]), moiNhat, "lay ban cu trong khi co ban moi hon");
  }
});
