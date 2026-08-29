/* rd-fe-11 · axe trên vỏ tab, cả bốn tab, vì lỗi nằm ở vỏ dùng chung.
 *
 * rd-qa-07 đo trên main @ aaefbfa và thấy `aria-required-children` (critical,
 * WCAG 1.3.1) trên CẢ BỐN tab: `role="tablist"` đang chứa nút [+] mang
 * `role="button"`. Không phải lỗi của một màn — `ThanhTab` là vỏ dùng chung,
 * nên một lần sửa gỡ cả bốn, và một lần đo phải nhìn cả bốn để nói được điều đó.
 *
 * Ca đầu tiên là ĐỐI CHỨNG, cùng cách rd-qa-06/05-a11y.mjs và rd-fe-10/02 làm:
 * trồng một <img> thiếu alt và một nút không tên vào chính trang đang đo, rồi
 * đòi axe phải báo NHIỀU HƠN. Không có nó thì một mảng rỗng vì axe chết đọc y
 * hệt một mảng rỗng vì trang sạch, và cái thứ hai là điều đang được khẳng định.
 *
 * Cách chạy — cần một bản export web và một máy chủ tĩnh trỏ vào nó:
 *
 *     cd apps/mobile
 *     npx expo export --platform web --output-dir /tmp/w
 *     (cd /tmp/w && python3 -m http.server 8651 --bind 127.0.0.1 &)
 *     cd tests/qa/rd-fe-11 && WEB_URL=http://127.0.0.1:8651 node 01-tablist-axe.mjs
 *
 * `node_modules` ở đây là symlink sang rd-fe-10 (playwright + @axe-core/playwright).
 *
 * Chứng minh: DOM mà Chromium 390x844 nhận được từ bản export đã liệt kê, ở
 * bốn URL đã liệt kê. KHÔNG chứng minh: iOS/Android (cầu accessibility khác),
 * và không chứng minh trình đọc màn hình thật đọc ra câu gì.
 */
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://127.0.0.1:8651";
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];
const TABS = ["kham-pha", "len-plan", "tin-nhan", "ca-nhan"];

const browser = await chromium.launch();
const page = await (
  await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  })
).newPage();
page.setDefaultTimeout(20000);

const failures = [];

async function mo(tab) {
  await page.goto(`${WEB}/index.html?man=${tab}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  // Assert the URL actually moved the app. Without this, a spelling the router
  // ignores gives four scans of the SAME default tab, reported as four tabs --
  // a clean number that describes one screen and claims to describe four.
  const dang_chon = await page.evaluate(() =>
    document.querySelector('[role="tab"][aria-selected="true"]')?.getAttribute("aria-label") ?? null,
  );
  if (!dang_chon) {
    failures.push(`${tab}: không tab nào khai aria-selected=true — không xác nhận được màn đã đổi`);
  }
  console.log(`  → ${tab}: tab đang chọn = ${JSON.stringify(dang_chon)}`);
  return dang_chon;
}

async function quet(nhan) {
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const nang = r.violations.filter((v) => ["critical", "serious"].includes(v.impact));
  console.log(`\n${nhan}: ${r.violations.length} vi phạm (${nang.length} critical/serious)`);
  for (const v of r.violations) {
    console.log(`  ✗ [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} nút)`);
    console.log(`      target: ${JSON.stringify(v.nodes[0]?.target ?? [])}`);
    console.log(`      why   : ${(v.nodes[0]?.failureSummary ?? "").split("\n").slice(1).join(" ").trim().slice(0, 200)}`);
  }
  return { tong: r.violations.length, nang };
}

/* ---- ĐỐI CHỨNG: axe còn sống không -------------------------------------- */

await mo("kham-pha");
const truoc = await quet("đối chứng · Khám phá nguyên bản");
await page.evaluate(() => {
  const img = document.createElement("img");
  // SVG chứ không phải base64: repo guard chặn data-uri base64, và axe chỉ cần
  // một <img> KHÔNG có alt.
  img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1' height='1'%3E%3C/svg%3E";
  document.body.appendChild(img);
  document.body.appendChild(document.createElement("button"));
});
const trong = await quet("đối chứng · ĐÃ TRỒNG image-alt + button-name");
if (trong.tong <= truoc.tong) {
  failures.push(
    `ĐỐI CHỨNG HỎNG: trồng hai lỗi mà axe vẫn báo ${trong.tong} ≤ ${truoc.tong} — ` +
      "mọi con số bên dưới là giả",
  );
} else {
  console.log(`\n✓ đối chứng đạt: ${truoc.tong} → ${trong.tong}. axe còn sống.`);
}

/* ---- bốn tab thật -------------------------------------------------------- */

const bang = [];
for (const tab of TABS) {
  await mo(tab);
  const r = await quet(`tab · ${tab}`);
  bang.push([tab, r.nang.map((v) => `${v.id}(${v.impact})`).join(", ") || "—"]);
  for (const v of r.nang) failures.push(`${tab}: [${v.impact}] ${v.id} — ${v.help}`);
}

/* ---- vỏ tab vẫn còn sống sau khi tách nút [+] ---------------------------- */

await mo("ca-nhan");
const cau_truc = await page.evaluate(() => {
  const tablists = [...document.querySelectorAll('[role="tablist"]')];
  const owned = (root) => {
    const out = [];
    const visit = (el) => {
      for (const child of el.children) {
        const role = child.getAttribute("role");
        if (role) out.push(role);
        else visit(child);
      }
    };
    visit(root);
    return out;
  };
  return {
    soTablist: tablists.length,
    conCuaTablist: tablists.map(owned),
    soTab: document.querySelectorAll('[role="tab"]').length,
    coNutTao: Boolean(document.querySelector('[aria-label="Tạo mới"]')),
    diemDung: [...document.querySelectorAll('[tabindex="0"]')].map((el) => el.getAttribute("role")),
  };
});
console.log("\ncấu trúc vỏ tab (đo trên tab ca-nhan):");
console.log("  " + JSON.stringify(cau_truc));

if (cau_truc.soTablist !== 1) failures.push(`có ${cau_truc.soTablist} role=tablist, phải đúng 1`);
if (cau_truc.soTab !== 4) failures.push(`có ${cau_truc.soTab} role=tab, phải đúng 4`);
if (!cau_truc.coNutTao) failures.push("nút [+] Tạo mới biến mất khỏi thanh");
for (const con of cau_truc.conCuaTablist) {
  const lac = [...new Set(con.filter((r) => r !== "tab"))];
  if (lac.length) failures.push(`tablist còn chứa role lạ: ${lac.join(", ")}`);
}

await browser.close();

console.log("\n———— rd-fe-11 · axe vỏ tab ————");
for (const [tab, v] of bang) console.log(`  ${tab.padEnd(10)} ${v}`);
if (failures.length === 0) {
  console.log("\n0 vi phạm critical/serious trên cả bốn tab");
  process.exit(0);
}
for (const f of failures) console.log("  ✗ " + f);
console.log(`\n${failures.length} vấn đề`);
process.exit(1);
