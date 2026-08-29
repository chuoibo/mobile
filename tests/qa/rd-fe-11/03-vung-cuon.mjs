/* Was the scrollable-region-focusable condition actually present when axe
 * reported 0? A rule that never had a scrollable region to look at returns the
 * same 0 as a rule that looked and found the region reachable. */
import { chromium } from "playwright";
const WEB = process.env.WEB_URL;
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })).newPage();
for (const tab of ["kham-pha", "len-plan", "tin-nhan", "ca-nhan"]) {
  await p.goto(`${WEB}/index.html?man=${tab}`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(1800);
  const r = await p.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll("*")) {
      const s = getComputedStyle(el);
      const scrollableY = /auto|scroll/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 1;
      if (!scrollableY) continue;
      out.push({
        tag: el.tagName.toLowerCase(),
        overflowY: s.overflowY,
        scrollH: el.scrollHeight, clientH: el.clientHeight,
        tabindex: el.getAttribute("tabindex"),
        role: el.getAttribute("role"),
        // axe passes the region when it is focusable OR contains focusable content.
        focusableInside: el.querySelectorAll('a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])').length,
      });
    }
    return out;
  });
  console.log(`${tab}: ${r.length} vùng cuộn dọc thật`);
  for (const x of r) console.log(`   ${JSON.stringify(x)}`);
}
await b.close();
