/** Exactly what react-native-web emitted for the photo, attribute by attribute.
 *
 * `khung-anh.mjs` counted 12 <img> that its filter did not consider hidden. A
 * count is not a finding: rnw renders `Image` as a wrapper plus an inner
 * element, and which of the two carries the hiding attribute decides whether a
 * screen reader announces the frame once or twice. So this dumps the real
 * attributes and asks the browser's own accessibility tree, rather than
 * inferring from the .tsx -- see `rnw-nuot-accessibilitystate`.
 */
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const API = process.env.API_URL ?? "http://localhost:9611";

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();

await page.route(`${API}/places*`, async (route) => {
  const res = await route.fetch();
  let body;
  try { body = await res.json(); } catch { return route.fulfill({ response: res }); }
  const list = Array.isArray(body) ? body : body.places ?? body.items ?? [];
  for (const p of list) { p.photo_url = `${API}/qa37-anh/that.png`; p.image_url = p.photo_url; }
  await route.fulfill({ response: res, json: body });
});

await page.goto(`${WEB}/#tab=kham-pha&nguoi=minh`, { waitUntil: "networkidle" });
await page.waitForTimeout(3500);

const chiTiet = await page.evaluate(() => {
  const attrs = (e) => Object.fromEntries(Array.from(e.attributes).map((a) => [a.name, a.value]));
  const imgs = Array.from(document.querySelectorAll("img")).slice(0, 2);
  return imgs.map((i) => ({
    img: attrs(i),
    cha: i.parentElement ? { tag: i.parentElement.tagName, ...attrs(i.parentElement) } : null,
    ong: i.parentElement?.parentElement
      ? { tag: i.parentElement.parentElement.tagName, ...attrs(i.parentElement.parentElement) }
      : null,
  }));
});
console.log("=== DOM that cua <img> dau tien ===");
console.log(JSON.stringify(chiTiet, null, 1));

// `page.accessibility` was removed in recent Playwright, so the tree is
// reconstructed the way a screen reader builds it: a node is announced only if
// nothing between it and <body> is aria-hidden, and it carries a name.
const noi = await page.evaluate(() => {
  const anTu = (e) => {
    for (let n = e; n && n !== document.body; n = n.parentElement) {
      if (n.getAttribute("aria-hidden") === "true") return true;
    }
    return false;
  };
  const ten = (e) =>
    (e.getAttribute("aria-label") || "").trim() ||
    (e.tagName === "IMG" ? (e.getAttribute("alt") || "").trim() : "");

  const ra = [];
  for (const e of document.querySelectorAll('[role="img"], img')) {
    if (anTu(e)) continue;
    const t = ten(e);
    if (t) ra.push({ tag: e.tagName, role: e.getAttribute("role"), name: t });
  }
  return ra;
});

console.log("\n=== node anh SE duoc doc len ===");
console.log(`tong: ${noi.length}`);
for (const n of noi.slice(0, 6)) console.log(`  <${n.tag}> role=${n.role} name="${n.name}"`);

const dem = {};
for (const n of noi) dem[n.name] = (dem[n.name] || 0) + 1;
const lap = Object.entries(dem).filter(([, c]) => c > 1);
console.log("\n=== ten bi doc HON MOT LAN ===");
console.log(lap.length ? JSON.stringify(lap, null, 1) : "(khong co -- moi khung doc dung mot lan)");

// The positive canary for this measurement: the <img> really did load, so the
// "announced once" answer is about a frame with a photo in it, not an empty one.
const tai = await page.evaluate(() =>
  Array.from(document.querySelectorAll("img")).filter((i) => i.complete && i.naturalWidth > 0).length);
console.log(`\ncanary: ${tai} <img> da tai that -> ${tai > 0 ? "do tren khung CO anh" : "VOID"}`);

await browser.close();
