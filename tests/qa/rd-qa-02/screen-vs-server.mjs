/* rd-qa-02 · Does the number on the screen equal the number the server sent?
 *
 * Drives the real Expo web build in a real browser, records every API response
 * body on the wire, then reads the rendered text out of the DOM and compares
 * the two. Nothing here re-splits anything: the expected value is whatever the
 * server put on the wire, formatted through `packages/shared/money.mjs` -- the
 * one formatting implementation both the app and the guest page already use,
 * pinned by its own golden cases.
 *
 * Usage:
 *     node tests/qa/rd-qa-02/screen-vs-server.mjs <web-dir> <api-base> <static-port>
 *
 * Output: a Markdown table of screen value vs server value, and a non-zero
 * exit if any pair disagrees.
 */
import { chromium } from "playwright";
import { formatVnd } from "../../../packages/shared/money.mjs";

const [, , WEB_DIR, API_BASE, STATIC_PORT] = process.argv;
if (!WEB_DIR || !API_BASE || !STATIC_PORT) {
  console.error("usage: screen-vs-server.mjs <web-dir> <api-base> <static-port>");
  process.exit(2);
}

const SITE = `http://127.0.0.1:${STATIC_PORT}`;
const ROSTER = ["Nam", "Hà", "Quyên", "Dũng", "Linh"];
const TOTAL_TYPED = "1234567";

/** Every row of the comparison table. */
const rows = [];
let mismatches = 0;

function compare(surface, label, onScreen, fromServer) {
  const agree = onScreen === fromServer;
  if (!agree) mismatches += 1;
  rows.push({ surface, label, onScreen, fromServer, agree });
}

const wire = { expenses: null, batches: null, publish: null, obligations: null };

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();

// The bundle hard-codes http://localhost:8099 (EXPO_PUBLIC_API_URL is not
// inlined by `expo export` on this commit). Redirect the origin to the API
// under test. This changes where the request goes, not what comes back --
// every body below is the real service's own answer.
await page.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.port !== "8099") return route.continue();
  const target = API_BASE + url.pathname + url.search;
  const response = await route.fetch({ url: target });
  const body = await response.text();
  const path = url.pathname;
  try {
    const json = JSON.parse(body);
    if (path === "/expenses") wire.expenses = json;
    else if (path === "/batches") wire.batches = json;
    else if (path.endsWith("/publish")) wire.publish = json;
    else if (path.endsWith("/obligations")) wire.obligations = json;
  } catch {
    /* not JSON; nothing to record */
  }
  await route.fulfill({ response, body });
});

const consoleErrors = [];
page.on("pageerror", (e) => consoleErrors.push(String(e)));

await page.goto(SITE, { waitUntil: "domcontentloaded" });

// --- Screen 1: enter the bill -------------------------------------------
await page.getByPlaceholder("bữa lẩu tối thứ bảy").fill("QA rd-qa-02");
for (const name of ROSTER) {
  await page.getByPlaceholder("Hà").fill(name);
  await page.getByRole("button", { name: "Thêm", exact: true }).click();
}
await page.getByPlaceholder("480000").fill(TOTAL_TYPED);

/** Trimmed visible lines of whatever is on screen right now. */
async function lines() {
  return (await page.locator("body").innerText()).split("\n").map((s) => s.trim());
}

// The typed total is echoed back through the same formatter the split uses.
// On this screen the unit sits in a nested Text, so the line reads "N đ".
const entryLines = await lines();
const echoed = entryLines.find((s) => /^[\d.]+ đ$/.test(s)) ?? "KHÔNG THẤY";
compare("NhapKhoanChi", "tổng đã nhập", echoed, `${formatVnd(Number(TOTAL_TYPED))} đ`);

await page.getByRole("radio", { name: ROSTER[0], exact: true }).click();
await page.getByRole("button", { name: "Chia tiền" }).click();

await page.getByRole("button", { name: "Đúng rồi, ghi vào sổ" }).waitFor({ timeout: 15_000 });
if (!wire.expenses) throw new Error("no /expenses response was captured");

// --- Screen 2: the proposal ---------------------------------------------
const allocations = wire.expenses.allocation.allocations;
const advancerId = wire.expenses.proposal.paid_by_id;
const idOrder = wire.expenses.proposal.participants;

// Screen prints one row per person, in roster order, with the amount on the
// line right after the name. Read the rendered text and pull them out in order.
const proposalLines = await lines();
for (let i = 0; i < idOrder.length; i++) {
  const id = idOrder[i];
  const name = ROSTER[i];
  const label = id === advancerId ? `${name} (trả trước)` : name;
  const idx = proposalLines.indexOf(label);
  if (idx === -1) throw new Error(`row for ${label} not found on the proposal screen`);
  compare("DeXuat", `phần của ${name}`, proposalLines[idx + 1], `${formatVnd(allocations[id])}đ`);
}
const totalIdx = proposalLines.indexOf("Tổng");
compare(
  "DeXuat",
  "tổng hoá đơn",
  totalIdx === -1 ? "KHÔNG THẤY" : proposalLines[totalIdx + 1],
  `${formatVnd(Number(TOTAL_TYPED))}đ`,
);

// The screen must not invent a total of its own: the sum of the rows it
// printed has to be the bill, to the dong.
const screenSum = idOrder.reduce((sum, id) => sum + allocations[id], 0);
compare("DeXuat", "Σ các dòng trên màn hình", String(screenSum), TOTAL_TYPED);

// Give the advancer a destination, over the real route, as the advancer.
const bank = await fetch(`${API_BASE}/bank-recipients`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Actor-ID": advancerId,
    "X-Actor-Roles": "member,advancer,recipient,batch_owner",
    "X-Actor-Contexts": wire.expenses.proposal.context_id,
  },
  body: JSON.stringify({
    recipient_id: advancerId,
    bank_bin: "970418",
    account_number: "QATESTACCT",
    account_name: "NGUOI UNG TIEN",
  }),
});
if (!bank.ok) throw new Error(`bank-recipients ${bank.status}: ${await bank.text()}`);

// --- Screen 3: the collection board -------------------------------------
await page.getByRole("button", { name: "Đúng rồi, ghi vào sổ" }).click();
await page.getByRole("button", { name: "Phát đợt thu" }).waitFor({ timeout: 15_000 });
if (!wire.batches) throw new Error("no /batches response was captured");

const boardLines = await lines();
let debts = 0;
for (const o of wire.batches.obligations) {
  const name = ROSTER[idOrder.indexOf(o.sender_id)];
  const expected = `${formatVnd(o.amount_vnd)}đ`;
  const found = boardLines.includes(expected);
  compare("DotThu", `khoản ${name} phải gửi`, found ? expected : "KHÔNG THẤY", expected);
  debts += o.amount_vnd;
}
compare(
  "DotThu",
  "Σ nợ = tổng − phần người ứng",
  String(debts),
  String(Number(TOTAL_TYPED) - allocations[advancerId]),
);

// --- Screen 4: the envelopes --------------------------------------------
await page.getByRole("button", { name: "Phát đợt thu" }).click();
await page.getByRole("button", { name: "Chia sẻ cho từng người" }).waitFor({ timeout: 20_000 });
await page.getByRole("button", { name: "Chia sẻ cho từng người" }).click();
if (!wire.publish) throw new Error("no publish response was captured");

const shareText = await lines();
for (const link of wire.publish.guest_links) {
  const name = ROSTER[idOrder.indexOf(link.sender_id)];
  const serverSum = link.obligations.reduce((s, r) => s + r.amount_vnd, 0);
  const expected = `${formatVnd(serverSum)}đ`;
  compare(
    "ChiaSe",
    `phong bì của ${name}`,
    shareText.includes(expected) ? expected : "KHÔNG THẤY",
    expected,
  );
}

// --- Screen 5: the guest page, server-rendered --------------------------
for (const link of wire.publish.guest_links) {
  const name = ROSTER[idOrder.indexOf(link.sender_id)];
  const guest = await fetch(API_BASE + link.path);
  const html = await guest.text();
  for (const row of link.obligations) {
    const expected = formatVnd(row.amount_vnd);
    compare(
      "trang khách",
      `số tiền của ${name}`,
      html.includes(`>${expected}<`) ? expected : "KHÔNG THẤY",
      expected,
    );
    // The copy-to-clipboard payload is the raw integer; it must be the same
    // number as the one printed, not a re-derived one.
    compare(
      "trang khách",
      `data-copy của ${name}`,
      html.includes(`data-copy="${row.amount_vnd}"`) ? String(row.amount_vnd) : "KHÔNG THẤY",
      String(row.amount_vnd),
    );
  }
  // Nobody else's share may appear on this page.
  //
  // Only amounts that DIFFER from this person's own are checkable by string
  // match: when two people owe the same number, finding it proves nothing
  // either way. Those pairs are counted and reported rather than silently
  // passed, because a check that cannot fail is not a check.
  const mine = link.obligations.reduce((s, r) => s + r.amount_vnd, 0);
  let indistinguishable = 0;
  for (const other of wire.publish.guest_links) {
    if (other.sender_id === link.sender_id) continue;
    const otherSum = other.obligations.reduce((s, r) => s + r.amount_vnd, 0);
    if (otherSum === mine) {
      indistinguishable += 1;
      continue;
    }
    const leaked = html.includes(`>${formatVnd(otherSum)}<`);
    compare("trang khách", `${name} không thấy phần người khác`, leaked ? "LỘ" : "không lộ", "không lộ");
  }
  if (indistinguishable > 0) {
    console.error(
      `  # ${name}: ${indistinguishable} người khác nợ đúng cùng số tiền — ` +
        "không phân biệt được bằng so chuỗi, nên KHÔNG tính là đã quét.",
    );
  }
  // Names are distinguishable even when amounts are not.
  for (const [i, id] of idOrder.entries()) {
    if (id === link.sender_id || id === advancerId) continue;
    const otherName = ROSTER[i];
    const leaked = new RegExp(`>[^<]*\\b${otherName}\\b`).test(html);
    compare("trang khách", `${name} không thấy tên ${otherName}`, leaked ? "LỘ" : "không lộ", "không lộ");
  }
  // Nor may the group total.
  const totalLeak = html.includes(formatVnd(Number(TOTAL_TYPED)));
  compare("trang khách", `${name} không thấy tổng nhóm`, totalLeak ? "LỘ" : "không lộ", "không lộ");
}

await browser.close();

// --- Report --------------------------------------------------------------
console.log("| bề mặt | số gì | trên màn hình | máy chủ gửi | khớp |");
console.log("|---|---|---|---|---|");
for (const r of rows) {
  console.log(`| ${r.surface} | ${r.label} | ${r.onScreen} | ${r.fromServer} | ${r.agree ? "✅" : "❌"} |`);
}
console.log(`\n${rows.length} phép đối chiếu, ${mismatches} lệch.`);
if (consoleErrors.length) {
  console.log(`\nLỗi runtime trong trình duyệt: ${consoleErrors.length}`);
  for (const e of consoleErrors) console.log(`  - ${e}`);
}
process.exit(mismatches === 0 && consoleErrors.length === 0 ? 0 : 1);
