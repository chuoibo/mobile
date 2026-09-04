/* ADR-0015: the product says who owes whom and stops. No screen in the RuDi
 * shell may carry a bank detail, a QR rail, or a "mark paid" that pretends a
 * transfer happened. Replaces the App B `thanh-toan.test.mjs` claim «no bank
 * detail in markup» at the source level, since the shell's screens render on
 * the emulator rather than in this runner.
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const RUDI = fileURLToPath(new URL("../src/rudi", import.meta.url));

function files(dir) {
  const out = [];
  for (const m of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, m.name);
    if (m.isDirectory()) out.push(...files(p));
    else if (/\.tsx?$/.test(m.name)) out.push(p);
  }
  return out;
}

const CAM = [/số tài khoản/i, /\bSTK\b/, /VietQR/i, /napas/i, /\bBIN\b/, /bank_account/i, /bankAccount/i, /\bIBAN\b/];

test("không màn nào của vỏ RuDi mang chi tiết ngân hàng hay đường QR thanh toán", () => {
  const dinh = [];
  for (const f of files(RUDI)) {
    const src = readFileSync(f, "utf8");
    for (const re of CAM) {
      const m = src.match(re);
      if (m) dinh.push(`${f.slice(RUDI.length + 1)}: ${m[0]}`);
    }
  }
  assert.deepEqual(dinh, [], `chi tiết thanh toán lọt vào vỏ RuDi:\n${dinh.join("\n")}`);
});
