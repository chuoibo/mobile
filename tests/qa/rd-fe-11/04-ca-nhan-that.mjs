/* axe on the screen rd-qa-07 actually measured (`#tab=ca-nhan&nguoi=minh`),
 * plus a short viewport that FORCES a scrollable region into existence so the
 * `scrollable-region-focusable` rule has something to judge. At 390x844 the
 * personal screen fits, so a 0 from that rule there is a vacuous 0. */
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";
const WEB = process.env.WEB_URL;
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];
const b = await chromium.launch();
let bad = 0;
for (const [nhan, vp] of [["390x844 (khung thật)", { width: 390, height: 844 }],
                          ["390x400 (ép ra vùng cuộn)", { width: 390, height: 400 }]]) {
  const p = await (await b.newContext({ viewport: vp, isMobile: true, hasTouch: true })).newPage();
  await p.goto(`${WEB}/index.html#tab=ca-nhan&nguoi=minh`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(4000);
  const cuon = await p.evaluate(() => {
    let n = 0;
    for (const el of document.querySelectorAll("*")) {
      const s = getComputedStyle(el);
      if (/auto|scroll/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 1) n++;
    }
    return { vung: n, doc: document.documentElement.scrollHeight > document.documentElement.clientHeight + 1 };
  });
  const v = (await new AxeBuilder({ p: 0, page: p }).withTags(TAGS).analyze()).violations;
  console.log(`\n${nhan}: ${v.length} vi phạm · vùng cuộn=${cuon.vung} · document cuộn=${cuon.doc}`);
  for (const x of v) console.log(`  ✗ [${x.impact}] ${x.id} — ${x.help} (${x.nodes.length}x) target=${JSON.stringify(x.nodes[0]?.target)}`);
  bad += v.length;
  await p.close();
}
await b.close();
console.log(`\n04-ca-nhan-that: ${bad === 0 ? "PASS" : "FAIL"} (tổng ${bad} vi phạm)`);
process.exit(bad === 0 ? 0 : 1);
