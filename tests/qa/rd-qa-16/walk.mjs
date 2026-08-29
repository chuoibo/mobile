/** rd-qa-16: press every tab and every [+] row on a bundle built from PR #138's
 *  own SHA, and assert each press lands on a screen that actually rendered.
 *
 *  The gate in #138 proves tabs.ts is internally consistent. It cannot prove a
 *  press reaches a screen -- that is what this walks. "Blank" is measured as
 *  rendered text length plus element count, not as a screenshot someone looks at.
 */
import { serve } from "./serve.mjs";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const DIST = process.argv[2];
const PORT = 4316;
const BASE = `http://localhost:${PORT}`;
const VIEWPORT = { width: 390, height: 844 };

const TABS = [
  { id: "kham-pha", label: "Khám phá — gợi ý chỗ đi cho nhóm", expect: /Khám phá/ },
  { id: "len-plan", label: "Lên plan — chuyến đi của nhóm", expect: /./ },
  { id: "tin-nhan", label: "Tin nhắn — chat nhóm và AI", expect: /./ },
  { id: "ca-nhan", label: "Cá nhân — hồ sơ và tài chính của bạn", expect: /./ },
];

const CREATE_ROWS = [
  { id: "tao-chuyen", label: "Tạo chuyến", expectBar: true },
  { id: "tao-khoan-chi", label: "Tạo khoản chi", expectBar: false },
  { id: "dang-ky-niem", label: "Đăng kỷ niệm", expectBar: true, expectAlert: true },
  { id: "tao-nhom", label: "Tạo nhóm", expectBar: false },
];

const results = [];
const seenHeads = new Map();
let fails = 0;

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  if (!ok) fails++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
}

/** What "the screen rendered" means, in numbers rather than in a glance.
 *
 *  Raw element count is the wrong oracle: the group screen is a legitimate
 *  screen drawn in 18 nodes, and a threshold tuned to Khám phá's 1561 calls it
 *  dead. What actually separates a live screen from a white one is readable
 *  text plus at least one control a finger can land on -- so that is what is
 *  counted, and `canary-man-trang` below proves the count still goes red.
 */
async function screenState(page) {
  return page.evaluate(() => {
    const bar = document.querySelector('[role="tablist"]');
    const controls = document.querySelectorAll(
      'button,input,[role="button"],[role="tab"],[role="radio"],[role="link"]');
    // The tab bar survives every screen, so body text alone says "alive" even
    // when the content area above it is empty -- which is exactly what a route
    // pointing at a tab that does not exist produces. Measure the content.
    const barText = bar ? bar.innerText.trim().length : 0;
    return {
      textLen: document.body.innerText.trim().length,
      contentLen: document.body.innerText.trim().length - barText,
      controls: controls.length,
      elements: document.querySelectorAll("div,span,button,input,img").length,
      barVisible: !!bar && bar.getClientRects().length > 0,
      alerts: [...document.querySelectorAll('[role="alert"]')].map((n) => n.innerText.trim()),
      head: document.body.innerText.trim().slice(0, 120).replace(/\n/g, " / "),
    };
  });
}

const server = await serve(DIST, PORT);
const browser = await chromium.launch();

async function freshPage() {
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  // about:blank first: AppRoot reads the fragment once at mount, so reusing a
  // page across fragments reports the previous screen while exiting 0.
  await page.goto("about:blank");
  await page.goto(`${BASE}/#nguoi=minh`, { waitUntil: "networkidle" });
  await page.waitForSelector('[role="tablist"]', { timeout: 15000 });
  return { page, ctx, errors };
}

// ---------- 1. the four tabs, pressed in one session like a person would ----
{
  const { page, ctx, errors } = await freshPage();
  for (const t of TABS) {
    await page.getByRole("tab", { name: t.label }).click();
    await page.waitForTimeout(600);
    const s = await screenState(page);
    const alive = s.contentLen > 40 && s.controls >= 1 && s.barVisible;
    seenHeads.set(t.id, s.head);
    check(`tab ${t.id} — màn sống`, alive,
      `noiDung=${s.contentLen} control=${s.controls} bar=${s.barVisible} | ${s.head}`);
    const axe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
    const serious = axe.violations.filter((v) => ["serious", "critical"].includes(v.impact));
    check(`tab ${t.id} — axe serious/critical`, serious.length === 0,
      serious.map((v) => `${v.id}×${v.nodes.length}`).join(", ") || "0 vi phạm");
  }
  check("4 tab — không lỗi console", errors.length === 0, errors.slice(0, 3).join(" | ") || "sạch");
  // Four presses that all render *something* still fail the user if they all
  // render the SAME thing. Distinct opening text is the cheapest proof the
  // press changed screens rather than merely not crashing.
  const heads = [...seenHeads.values()];
  check("4 tab — bốn màn khác nhau, không phải một màn lặp lại",
    new Set(heads).size === 4, `${new Set(heads).size}/4 khác nhau`);

  // CANARY: the oracle above must be able to fail. Wipe the React root and
  // re-measure -- a "màn sống" check that cannot go red proves nothing about
  // the 8 presses it just approved.
  await page.evaluate(() => { document.getElementById("root").innerHTML = ""; });
  const dead = await screenState(page);
  const oracleFires = !(dead.contentLen > 40 && dead.controls >= 1);
  check("canary-man-trang — oracle bắt được màn trắng", oracleFires,
    `noiDung=${dead.contentLen} control=${dead.controls} (phải rớt ngưỡng)`);
  await ctx.close();
}

// ---------- 2. the [+] sheet opens and lists all four rows ----------------
{
  const { page, ctx } = await freshPage();
  await page.getByRole("button", { name: "Tạo mới" }).click();
  await page.waitForTimeout(400);
  for (const r of CREATE_ROWS) {
    const n = await page.getByRole("button", { name: new RegExp("^" + r.label + "\\.") }).count();
    check(`menu [+] — có hàng "${r.label}"`, n === 1, `đếm được ${n}`);
  }
  await ctx.close();
}

// ---------- 3. each [+] row, from a cold app each time -------------------
for (const r of CREATE_ROWS) {
  const { page, ctx, errors } = await freshPage();
  const before = await screenState(page);
  await page.getByRole("button", { name: "Tạo mới" }).click();
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: new RegExp("^" + r.label + "\\.") }).click();
  await page.waitForTimeout(900);
  const s = await screenState(page);

  const alive = s.contentLen > 40 && s.controls >= 1;
  check(`[+] ${r.id} — màn sống`, alive,
    `noiDung=${s.contentLen} control=${s.controls} bar=${s.barVisible} | ${s.head}`);
  check(`[+] ${r.id} — thanh tab ${r.expectBar ? "còn" : "biến mất"}`,
    s.barVisible === r.expectBar, `barVisible=${s.barVisible}`);
  if (r.expectAlert) {
    check(`[+] ${r.id} — nói thẳng là chưa dựng`,
      s.alerts.some((a) => /chưa dựng/.test(a)), JSON.stringify(s.alerts));
  } else {
    check(`[+] ${r.id} — đổi màn thật (khác màn đầu)`,
      s.head !== before.head, `head=${s.head}`);
  }
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
  const serious = axe.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  check(`[+] ${r.id} — axe serious/critical`, serious.length === 0,
    serious.map((v) => `${v.id}×${v.nodes.length}`).join(", ") || "0 vi phạm");
  check(`[+] ${r.id} — không lỗi console`, errors.length === 0,
    errors.slice(0, 2).join(" | ") || "sạch");
  await ctx.close();
}

await browser.close();
server.close();
console.log(`\n=== ${results.length - fails}/${results.length} PASS · ${fails} FAIL ===`);
process.exit(fails ? 1 : 0);
