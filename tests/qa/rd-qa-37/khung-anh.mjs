/** The three things `Anh.tsx` says it does, asked of the rendered DOM.
 *
 *   1. a loadable photo -> a real <img>, filling the frame, and the frame's
 *      geometry identical to what it was with no photo at all
 *   2. a dead URL -> back to the stand-in, and NO new request on re-render
 *   3. a screen reader hears the frame exactly once, not once per layer
 *
 * All three are measured after react-native-web has rendered, never from the
 * .tsx: rnw drops attributes that read correctly in source. Question 3 is the
 * one where that matters most -- the source sets `aria-hidden` on both the
 * stand-in and the <Image>, and only the DOM can say whether they survived.
 */
import fs from "node:fs";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const API = process.env.API_URL ?? "http://localhost:9611";
const SHOT = process.env.SHOT_DIR ?? "/tmp/rd-qa-37-shots";

const browser = await chromium.launch();

/** Render Khám phá with every place photo forced to `url`, and measure. */
async function do1(url, nhan) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  const goi = [];
  page.on("request", (r) => {
    const u = r.url();
    if (/\.png|\.jpg|qa37-anh|khong-ton-tai/.test(u)) goi.push(u);
  });

  if (url !== null) {
    await page.route(`${API}/places*`, async (route) => {
      const res = await route.fetch();
      let body;
      try { body = await res.json(); } catch { return route.fulfill({ response: res }); }
      const list = Array.isArray(body) ? body : body.places ?? body.items ?? [];
      for (const p of list) { p.photo_url = url; p.image_url = url; }
      await route.fulfill({ response: res, json: body });
    });
  }

  await page.goto(`${WEB}/#tab=kham-pha&nguoi=minh`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3500);

  // Geometry of every frame. `role="img"` is what the frame renders as, so it
  // is the thing whose box must not move when a photo arrives.
  const hop = async () => page.evaluate(() =>
    Array.from(document.querySelectorAll('[role="img"]')).map((e) => {
      const r = e.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height), y: Math.round(r.top) };
    }));

  const truoc = await hop();
  const goiSauTai = goi.length;

  // Three forced re-renders. If a failed load re-mounts its <Image>, the
  // request count climbs here and nowhere else.
  for (let i = 0; i < 3; i++) {
    await page.evaluate(() => window.dispatchEvent(new Event("resize")));
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(1200);
  const sau = await hop();

  const a11y = await page.evaluate(() => {
    const frames = Array.from(document.querySelectorAll('[role="img"]'));
    const imgs = Array.from(document.querySelectorAll("img"));
    return {
      soFrame: frames.length,
      coNhan: frames.filter((e) => (e.getAttribute("aria-label") || "").trim()).length,
      // An <img> that is NOT hidden would be announced a second time, under
      // the frame that already announced itself.
      imgLoRa: imgs.filter((i) =>
        i.getAttribute("aria-hidden") !== "true" &&
        i.getAttribute("role") !== "presentation" &&
        i.getAttribute("role") !== "none").length,
      soImg: imgs.length,
      daTai: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
      // Does the photo actually fill the frame it sits in?
      phu: imgs.slice(0, 3).map((i) => getComputedStyle(i).objectFit),
    };
  });

  await page.screenshot({ path: `${SHOT}/khung-${nhan}.png` });
  await ctx.close();

  return {
    nhan,
    url: url === null ? "(khong co anh)" : url.slice(0, 60),
    soFrame: a11y.soFrame,
    frameCoNhan: a11y.coNhan,
    imgKhongAnDi: a11y.imgLoRa,
    soImg: a11y.soImg,
    imgDaTai: a11y.daTai,
    objectFit: a11y.phu,
    hopTruoc: truoc.slice(0, 3),
    hopSau: sau.slice(0, 3),
    goiAnhTongCong: goi.length,
    goiTruocReRender: goiSauTai,
    goiThemSauReRender: goi.length - goiSauTai,
  };
}

const khongAnh = await do1(null, "1-khong-anh");
const coAnh = await do1(`${API}/qa37-anh/that.png`, "2-co-anh");
const chetAnh = await do1(`${API}/qa37-anh-chet/404.png`, "3-url-chet");

const bang = [khongAnh, coAnh, chetAnh];
fs.writeFileSync(`${SHOT}/ket-qua-khung.json`, JSON.stringify(bang, null, 2));
for (const r of bang) { console.log(`\n=== ${r.nhan} ===`); console.log(JSON.stringify(r, null, 1)); }

console.log("\n================ KET LUAN ================");
const nhay = JSON.stringify(khongAnh.hopTruoc) !== JSON.stringify(coAnh.hopTruoc);
console.log(`1. nhay layout khi co anh:      ${nhay ? "CO -- khung doi kich thuoc" : "KHONG"}`);
console.log(`   khong anh: ${JSON.stringify(khongAnh.hopTruoc[0])}`);
console.log(`   co anh   : ${JSON.stringify(coAnh.hopTruoc[0])}`);
console.log(`2. url chet ban lai khi re-render: ${chetAnh.goiThemSauReRender} yeu cau moi ` +
  `(${chetAnh.goiThemSauReRender === 0 ? "DAT" : "KHONG DAT"})`);
console.log(`   img con lai trong DOM: ${chetAnh.soImg}, vo: ${chetAnh.soImg - chetAnh.imgDaTai}`);
console.log(`3. frame co nhan: ${coAnh.frameCoNhan}/${coAnh.soFrame}; ` +
  `img KHONG an di: ${coAnh.imgKhongAnDi} (phai la 0)`);
console.log(`   canary: co anh -> ${coAnh.imgDaTai} img tai duoc ` +
  `(${coAnh.imgDaTai > 0 ? "may do CON SONG" : "VOID -- khong tai duoc gi"})`);
await browser.close();
