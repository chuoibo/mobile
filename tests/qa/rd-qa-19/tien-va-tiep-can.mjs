/**
 * rd-qa-19, part 2 -- money readability at the boundaries, plus the
 * accessibility pass on the screen the search box actually lives on.
 *
 * The money half renders real budgets through the real component (route
 * intercept, real bundle) rather than calling formatNganSach() directly:
 * a unit call would prove the string and not that the string reaches a screen.
 */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";
import fs from "node:fs";

const WEB = process.env.QA19_WEB ?? "http://127.0.0.1:8548";
const API = process.env.QA19_API ?? "http://127.0.0.1:8547";
const SHOT = "/tmp/qa19-shots";
fs.mkdirSync(SHOT, { recursive: true });

const GROUP = (await (await fetch(`${API}/places`)).json()).group ?? {};
const browser = await chromium.launch();

function bodyFor(budget) {
  return {
    query: "câu thử",
    understood: {
      budget_per_person_vnd: budget,
      group_size: 4,
      max_distance_km: null,
      categories: [],
      traits: [],
    },
    places: [],
    source: "ai",
    group: GROUP,
  };
}

async function moMan(ctx0 = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, ...ctx0 });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/#tab=kham-pha`, { waitUntil: "networkidle" });
  return { ctx, page };
}

async function tim(page, cau = "câu thử") {
  await page.getByLabel("Tìm bằng lời").fill(cau);
  await page.getByRole("button", { name: /Tìm bằng AI|Đang hỏi AI/ }).click();
  await page.waitForFunction(
    () => /AI hiểu câu của bạn|Chưa tìm được|Không tìm được|Kết quả tìm kiếm không đúng dạng|Máy chủ/.test(document.body.innerText),
    { timeout: 60000 },
  );
}

console.log("=".repeat(72));
console.log("TIỀN Ở BIÊN · số nào hiện lên màn cho từng ngân sách");
console.log("=".repeat(72));
const CASES = [300000, 30000, 250500, 1500000, 999, 0, 50000];
for (const vnd of CASES) {
  const { ctx, page } = await moMan();
  await page.route("**/places/search", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(bodyFor(vnd)) }),
  );
  await tim(page);
  const shown = await page.evaluate(() => {
    const t = document.body.innerText.split("\n").map((s) => s.trim());
    const i = t.findIndex((s) => s === "NGÂN SÁCH");
    return i >= 0 ? t[i + 1] : "(không có dòng NGÂN SÁCH)";
  });
  console.log(`  ${String(vnd).padStart(8)} đồng  ->  ${shown}`);
  await ctx.close();
}

console.log("\n" + "=".repeat(72));
console.log("TIẾP CẬN · axe WCAG 2.2 AA trên màn có ô tìm + bảng AI hiểu");
console.log("=".repeat(72));
{
  const { ctx, page } = await moMan();
  await page.route("**/places/search", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(bodyFor(300000)) }),
  );

  // Scan BEFORE search (box idle) and AFTER search (panel rendered): the
  // panel only exists in the second state, so one scan would miss it.
  for (const [nhan, truoc] of [["trước khi tìm", true], ["sau khi tìm (có bảng AI hiểu)", false]]) {
    if (!truoc) await tim(page);
    const res = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    console.log(`\n[${nhan}] violations: ${res.violations.length}`);
    for (const v of res.violations) {
      console.log(`   ${v.impact ?? "?"} · ${v.id} · ${v.help} (${v.nodes.length} node)`);
      for (const n of v.nodes.slice(0, 3)) console.log(`      ${n.html.slice(0, 130)}`);
    }
  }
  await page.screenshot({ path: `${SHOT}/a11y-390.png`, fullPage: true });
  await ctx.close();
}

console.log("\n" + "=".repeat(72));
console.log("BÀN PHÍM · tới ô tìm và bấm Enter mà không cần chuột");
console.log("=".repeat(72));
{
  const { ctx, page } = await moMan();
  await page.route("**/places/search", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(bodyFor(300000)) }),
  );
  const stops = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    const cur = await page.evaluate(() => {
      const a = document.activeElement;
      if (!a) return null;
      const style = getComputedStyle(a);
      return {
        tag: a.tagName,
        label: (a.getAttribute("aria-label") || a.innerText || a.getAttribute("placeholder") || "").trim().slice(0, 40),
        outline: style.outlineStyle + " " + style.outlineWidth,
        boxShadow: style.boxShadow === "none" ? "none" : "có",
      };
    });
    stops.push(cur);
    if (cur?.tag === "INPUT") break;
  }
  stops.forEach((s, i) => console.log(`  Tab ${i + 1}: ${s?.tag} "${s?.label}" outline=${s?.outline} shadow=${s?.boxShadow}`));

  const onInput = stops[stops.length - 1]?.tag === "INPUT";
  console.log(`\n  tới được ô tìm bằng Tab? ${onInput ? "CÓ" : "KHÔNG"}`);
  if (onInput) {
    await page.keyboard.type("quán nướng cho 6 người dưới 300k");
    await page.keyboard.press("Enter");
    const ok = await page
      .waitForFunction(() => document.body.innerText.includes("AI hiểu câu của bạn"), { timeout: 30000 })
      .then(() => true)
      .catch(() => false);
    console.log(`  Enter trong ô có chạy tìm kiếm? ${ok ? "CÓ" : "KHÔNG"}`);
  }
  await ctx.close();
}

await browser.close();
