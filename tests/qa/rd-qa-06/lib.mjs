/* rd-qa-06 · shared driving helpers for the SECOND HALF of the vertical slice.
 *
 * Two rules this file exists to enforce, both learned the hard way in rd-qa-05:
 *
 * 1. `locator.fill()` on a react-native-web TextInput does not simulate typing.
 *    It sets the value without the per-character change events the screen
 *    recomputes its total from, and rd-qa-05 measured a total off by ~150
 *    billion dong that was purely the harness's fault. Everything here types
 *    with real keys.
 * 2. The app pushes no history entries, so `goBack()` leaves the app entirely.
 *    Never read a blank page as a product bug without checking `location`.
 */
import { chromium } from "playwright";

export const WEB = process.env.WEB_URL ?? "http://127.0.0.1:8631";
export const API = process.env.API_URL ?? "http://127.0.0.1:8620";

export async function phone() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text().slice(0, 300)); });
  return { browser, context, page, errors };
}

/** Type into a field the way a thumb does: focus, clear, one key at a time. */
export async function typeInto(page, locator, text) {
  await locator.click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Delete");
  if (text !== "") await page.keyboard.type(text, { delay: 15 });
}

export async function text(page) {
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

/** Open the app, skip sign-in, open [+] -> Tạo khoản chi, drop to manual form. */
export async function toManualForm(page) {
  await page.goto(WEB + "/index.html", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  await page.getByRole("button", { name: /Bỏ qua/ }).click();
  await page.waitForTimeout(1000);
  await page.getByRole("button", { name: /Tạo mới/ }).click();
  await page.waitForTimeout(700);
  await page.getByRole("button", { name: /Tạo khoản chi/ }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: /^Huỷ$/ }).click();
  await page.waitForTimeout(1200);
}

export function report(name, failures) {
  console.log(`\n———— ${name} ————`);
  if (failures.length === 0) { console.log("0 vấn đề chặn"); return 0; }
  for (const f of failures) console.log("  ✗ " + f);
  console.log(`${failures.length} vấn đề`);
  return failures.length;
}

/* ---------------------------------------------------------------------------
 * The three predicates every verdict in this harness rests on.
 *
 * They live here, as pure functions over already-collected data, for one
 * reason: `04-selfcheck.mjs` feeds them deliberately corrupted input and
 * requires them to go red. A control that re-implements the check it is
 * validating proves nothing, so the self-check must call THESE, not a copy.
 * ------------------------------------------------------------------------- */

/** Luật tiền 2, đo trên màn: Σ các dòng phân bổ == tổng in ra == số đã gõ. */
export function sumProblems(rows, tongTrenMan, typedVnd) {
  const out = [];
  if (rows.length !== 3) out.push(`chỉ đọc được ${rows.length}/3 dòng phân bổ trên màn`);
  const sum = rows.reduce((a, r) => a + r.amount, 0);
  if (sum !== tongTrenMan) out.push(`LUẬT TIỀN 2 vỡ TRÊN MÀN: Σ ${sum} ≠ Tổng ${tongTrenMan}`);
  if (tongTrenMan !== typedVnd) out.push(`Tổng trên màn ${tongTrenMan} ≠ số đã gõ ${typedVnd}`);
  if (!rows.every((r) => Number.isInteger(r.amount))) out.push("có phân bổ không phải số nguyên đồng");
  return out;
}

/**
 * Trang khách rò gì không.
 *
 * `ownAmount` được kiểm TRƯỚC mọi phủ định. Không có nó thì một trang trắng,
 * một trang 404, hay một trang in tiền ở định dạng khác đều làm mọi dòng
 * `!includes(...)` bên dưới pass một cách rỗng tuếch.
 */
export function leakProblems({ who, plain, html, ownAmount, otherNames, forbiddenAmounts }) {
  const out = [];
  if (!plain.includes(ownAmount))
    out.push(`trang ${who}: KHÔNG thấy số tiền của chính họ (${ownAmount}) — mọi phép kiểm rò rỉ bên dưới thành rỗng`);
  if (who === "?") out.push("không đọc được 'Phần của <tên>' trên trang khách");
  for (const t of forbiddenAmounts)
    if (plain.includes(t)) out.push(`RÒ RỈ: trang khách của ${who} in ra ${t}`);
  for (const o of otherNames)
    if (new RegExp(`\\b${o}\\b`).test(plain)) out.push(`RÒ RỈ: trang khách của ${who} có tên người khác "${o}"`);
  for (const bad of ["group_balance", "group_history", "other_allocations", "invocation_thread"])
    if (html.includes(bad)) out.push(`RÒ RỈ: trang ${who} chứa trường cấm ${bad}`);
  return out;
}

/** Mã QR trên màn: giải mã được, đúng chuỗi máy chủ gửi, đúng số tiền. */
export function qrProblems(decoded, knownPayloads, expectedAmount) {
  const out = [];
  if (!decoded) { out.push("ảnh QR trên màn KHÔNG giải mã được bằng bộ đọc QR (cv2)"); return out; }
  if (!knownPayloads.includes(decoded)) out.push("QR giải mã ra chuỗi KHÁC payload máy chủ gửi về");
  const tag = decoded.match(/54(\d{2})/);
  const val = tag ? decoded.slice(decoded.indexOf(tag[0]) + 4, decoded.indexOf(tag[0]) + 4 + Number(tag[1])) : null;
  if (val !== expectedAmount) out.push(`QR mã hoá số tiền ${val}, màn hình ghi ${expectedAmount}`);
  return out;
}
