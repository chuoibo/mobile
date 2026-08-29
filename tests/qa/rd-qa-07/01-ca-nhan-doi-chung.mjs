/* rd-qa-07 · The personal screen against the ledger it claims to read.
 *
 * `finance.py` states its own contract: "Every figure this route answers with
 * is recomputed from the ledger on the request that asks for it, which is
 * invariant 3 stated as an endpoint." This script checks the half of that
 * sentence a backend test cannot see -- that the number the SCREEN prints is
 * the number the ROUTE answered, and not something the client worked out.
 *
 * The check is a comparison, never a recomputation. Nothing here divides,
 * sums or rounds money: it reads the API's own integers, formats them the one
 * way the app formats them, and looks for that exact string on the page. A
 * harness that recomputed the split would just be a second allocator
 * disagreeing with the first.
 */
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://127.0.0.1:8641";
const API = process.env.API_URL ?? "http://127.0.0.1:8640";
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";

/** The app's own formatter, `tienVnd` in src/screens/ca-nhan/tai-chinh.ts. */
function tienVnd(vnd) {
  const negative = vnd < 0;
  const digits = String(Math.abs(vnd));
  let grouped = "";
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) grouped += ".";
    grouped += digits[i];
  }
  return `${negative ? "-" : ""}${grouped}đ`;
}

const failures = [];
const note = (ok, msg) => {
  console.log(`${ok ? "  ok  " : "  FAIL"} ${msg}`);
  if (!ok) failures.push(msg);
};

const fin = await (await fetch(`${API}/people/${MINH}/finance`, {
  headers: { "X-Actor-ID": MINH, "X-Actor-Roles": "member", Accept: "application/json" },
})).json();
console.log(`API  spend=${fin.spend_vnd} settled=${fin.settled_vnd} ` +
  `outstanding=${fin.outstanding_vnd} movements=${fin.movements.length}`);

// The invariant the mockup's layout promises, checked on the wire before the
// screen is even opened -- if this is already broken, the screen is innocent.
note(fin.settled_vnd + fin.outstanding_vnd === fin.spend_vnd,
  `wire: settled + outstanding == spend (${fin.settled_vnd} + ${fin.outstanding_vnd} === ${fin.spend_vnd})`);
note(Number.isInteger(fin.spend_vnd) && Number.isInteger(fin.settled_vnd) &&
  Number.isInteger(fin.outstanding_vnd),
  "wire: every money field is an integer, not 750000.0 (law 1)");

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
});
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text().slice(0, 200)); });

// The URL entry point rd-do-fe-09 shipped precisely so this screen could be
// reached cold by a machine instead of only by tapping.
await page.goto(`${WEB}/index.html#tab=ca-nhan&nguoi=minh`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);

const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
console.log(`\nSCREEN (${body.length} chars): ${body.slice(0, 220)}\n`);

note(body.length > 40, "screen rendered something at all (guards a blank-page false pass)");
note(/Cá nhân|Tài chính|Minh/i.test(body), "screen is the Cá nhân tab, not the opening screen");

// The load-bearing comparison: the API's integers, formatted the app's way,
// must appear verbatim. Assert the positive first -- looking only for absence
// passes vacuously on a white page, which is the trap rd-qa-06 hit.
for (const [label, vnd] of [["spend", fin.spend_vnd], ["settled", fin.settled_vnd],
                            ["outstanding", fin.outstanding_vnd]]) {
  note(body.includes(tienVnd(vnd)),
    `screen prints the server's ${label}: "${tienVnd(vnd)}"`);
}

// Nobody else's money. Minh's screen must not carry Trang's figures.
const trang = await (await fetch(`${API}/people/49871dab-3bf9-5140-acf3-6c9736b31e8f/finance`, {
  headers: { "X-Actor-ID": "49871dab-3bf9-5140-acf3-6c9736b31e8f", "X-Actor-Roles": "member" },
})).json();
// Only a figure that is NOT also one of Minh's own can prove a leak. The first
// run of this check fired on 550.000đ -- Trang's debt, which happens to equal
// Minh's settled total. That was the harness inventing a leak out of an
// arithmetic coincidence, not the screen showing another person's money.
const minhOwn = new Set([fin.spend_vnd, fin.settled_vnd, fin.outstanding_vnd]);
const trangOnly = [trang.spend_vnd, trang.settled_vnd, trang.outstanding_vnd]
  .filter((v) => !minhOwn.has(v));
if (trangOnly.length === 0) {
  console.log("  skip  every figure of Trang's collides with one of Minh's — no leak check possible this run");
} else {
  for (const vnd of trangOnly) {
    note(!body.includes(tienVnd(vnd)),
      `screen does NOT print Trang-only figure "${tienVnd(vnd)}"`);
  }
}

note(errors.length === 0, `no console/page errors (${errors.length}): ${errors.slice(0, 2).join(" | ")}`);

await page.screenshot({ path: "/tmp/rdqa07-ca-nhan.png", fullPage: true });
await browser.close();

console.log(`\n01-ca-nhan-doi-chung: ${failures.length === 0 ? "PASS" : "FAIL"} (${failures.length} failure(s))`);
process.exit(failures.length === 0 ? 0 : 1);
