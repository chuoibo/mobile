/* The four tabs in their data-loaded state, addressed the way rd-qa-07 does
 * (`#tab=<tab>&nguoi=minh`). The earlier `?man=` sweep reached the tabs but
 * left Cá nhân in its no-person state, which is a different screen. */
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";
const WEB = process.env.WEB_URL;
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];
const b = await chromium.launch();
let bad = 0;
for (const tab of ["kham-pha", "len-plan", "tin-nhan", "ca-nhan"]) {
  // A fresh page per tab. `#tab=` is read once at boot, so changing only the
  // hash on a live page is a same-document navigation the app never sees --
  // that silently scans the FIRST tab four times and calls it four tabs.
  const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })).newPage();
  await p.goto(`${WEB}/index.html#tab=${tab}&nguoi=minh`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(3000);
  const st = await p.evaluate(() => {
    const tl = document.querySelector('[role="tablist"]');
    return {
      chon: document.querySelector('[role="tab"][aria-selected="true"]')?.getAttribute("aria-label") ?? null,
      con: tl ? [...tl.children].map((c) => c.getAttribute("role") ?? "(khong role)") : null,
    };
  });
  const v = (await new AxeBuilder({ page: p }).withTags(TAGS).analyze()).violations;
  bad += v.length;
  console.log(`${tab.padEnd(9)} ${String(v.length).padStart(2)} vi phạm · con-cua-tablist=${JSON.stringify(st.con)} · dang-chon=${JSON.stringify(st.chon)}`);
  for (const x of v) console.log(`     ✗ [${x.impact}] ${x.id} (${x.nodes.length}x) target=${JSON.stringify(x.nodes[0]?.target)}`);
  if (!st.chon) { bad++; console.log(`     ✗ ${tab}: không xác nhận được tab đã đổi`); }
  await p.close();
}
await b.close();
console.log(`\n05-bon-tab-co-du-lieu: ${bad === 0 ? "PASS" : "FAIL"} (tổng ${bad})`);
process.exit(bad === 0 ? 0 : 1);
