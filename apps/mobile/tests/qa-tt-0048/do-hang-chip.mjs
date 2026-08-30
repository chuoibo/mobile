/** QA probe qa-tt-0048 -- PR #382 adds a fifth chip to the chat tablist.
 *
 *  Two questions the unit tests cannot answer, both measured on a real render:
 *    1. do five chips still fit 320px / 390px, with a 44px touch target?
 *    2. is any label clipped, and how many lines does it wrap to?
 *
 *  Run it against an export built FROM THE TREE UNDER TEST -- a stale
 *  `.expo-build-check` measures a different product (that is bug-010019, #386):
 *
 *    cd apps/mobile && npm run build:check && node tests/qa-tt-0048/do-hang-chip.mjs
 */
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { findChrome, launch, serve } from "../chrome-cdp.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", "..", ".expo-build-check");

const server = await serve(EXPORT_DIR);
const page = await launch(findChrome());
console.log(`do tren: ${EXPORT_DIR}`);

for (const [w, h] of [[320, 720], [390, 844]]) {
  await page.viewport(w, h);
  // The about:blank hop is load-bearing: AppRoot reads `#tab=` once, at mount.
  await page.goto("about:blank", () => true);
  await page.goto(
    `${server.url}/index.html#tab=tin-nhan&nguoi=minh`,
    (label) => !!document.querySelector(`[aria-label="${label}"]`),
    "Ô nhập tin nhắn",
  );

  const r = await page.evaluate(() => {
    const list = document.querySelector('[role="tablist"]');
    if (!list) return { loi: "khong thay tablist" };
    const tabs = [...list.querySelectorAll('[role="tab"]')].map((t) => {
      const b = t.getBoundingClientRect();
      const el = t.querySelector("div,span") || t;
      const cs = getComputedStyle(el);
      return {
        nhan: (t.textContent || "").trim(),
        right: Math.round(b.right), w: Math.round(b.width), h: Math.round(b.height),
        scrollW: el.scrollWidth, clientW: el.clientWidth,
        scrollH: el.scrollHeight, clientH: el.clientHeight,
        lineH: parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2,
      };
    });
    return { scrollW: list.scrollWidth, clientW: list.clientWidth, vw: innerWidth, tabs };
  });
  if (r.loi) { console.log(`${w}px: ${r.loi}`); continue; }

  console.log(`\n=== ${w}x${h} === tablist scrollWidth=${r.scrollW} clientWidth=${r.clientW}`);
  for (const t of r.tabs) {
    const ngoai = t.right > r.vw + 0.5;
    const cat = t.scrollW > t.clientW + 0.5 || t.scrollH > t.clientH + 0.5;
    console.log(
      `  ${ngoai ? "NGOAI MAN" : "trong man"} ${cat ? "BI CAT" : "du cho"} ` +
      `${t.nhan.padEnd(13)} ${t.w}x${t.h} right=${t.right} ~${Math.round(t.scrollH / t.lineH)} dong`,
    );
  }
  console.log(`  -> ${r.tabs.filter((t) => t.right > r.vw + 0.5).length} chip tran ra ngoai`);
  console.log(`  -> ${r.tabs.filter((t) => t.h < 44).length}/${r.tabs.length} chip cao < 44px`);
}

await page.close();
await server.close();
