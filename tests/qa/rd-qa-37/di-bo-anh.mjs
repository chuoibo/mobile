/** Does the photo frame dial anybody it should not, and what does it show?
 *
 * Items 2 and 3 of rd-qa-37, measured on the rendered DOM rather than on the
 * source -- `rnw-nuot-accessibilitystate` is the standing reason: react-native-web
 * drops attributes that read correctly in the .tsx and are simply absent in the
 * browser, so a source-reading gate can be green while the screen is wrong.
 *
 * The hostile addresses are injected by rewriting the `GET /places` response,
 * which is precisely the threat model `nguon-anh.ts` was written against: the
 * address is a string a *member* wrote, so the server sends it in good faith.
 * Injecting at the API is therefore the honest place to inject -- it does not
 * touch product code and it reproduces the real payload path.
 *
 * Two canaries per run, because "the tracker logged nothing" and "the frame
 * never fetches anything" look identical from outside:
 *
 *   XANH  an address on the API's own origin -> MUST load, MUST hit the tap
 *   DO    an address on the tracker's origin -> MUST NOT hit the tracker
 *
 * If the XANH canary fails the whole run is void and the script says so.
 */
import fs from "node:fs";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const API = process.env.API_URL ?? "http://localhost:9611";
const TRACKER = process.env.TRACKER_URL ?? "http://localhost:9613";
const TRACKER_LOG = process.env.TRACKER_LOG ?? "/tmp/rd-qa-37-tracker.json";
const SHOT = process.env.SHOT_DIR ?? "/tmp/rd-qa-37-shots";

const CA = [
  { id: "canary-xanh", url: `${API}/qa37-anh/that.png`, phaiTai: true,
    vi: "cung goc API -- canary XANH, bat buoc tai duoc" },
  { id: "ngoai-host", url: `${TRACKER}/theo-doi.png`, phaiTai: false,
    vi: "host nguoi khac -- day la vu ro ri that" },
  { id: "protocol-relative", url: `//localhost:9613/pr.png`, phaiTai: false,
    vi: "// mo dau: trong nhu duong dan, thuc te la host khac" },
  { id: "backslash", url: `/\\localhost:9613/bs.png`, phaiTai: false,
    vi: "/\\ -- cung tro thanh host khac trong mot so parser" },
  { id: "prefix-tricked", url: `${API}.localhost:9613/x.png`, phaiTai: false,
    vi: "base la tien to nhung host that la cho khac" },
  { id: "javascript", url: `javascript:fetch('${TRACKER}/js.png')`, phaiTai: false,
    vi: "javascript: -- co chay khong" },
  { id: "data-html", url: `data:text/html,<img src="${TRACKER}/data.png">`, phaiTai: false,
    vi: "data:text/html -- co render va tu dial khong" },
  { id: "url-chet", url: `${API}/qa37-anh/../../khong-ton-tai-404.png`, phaiTai: false,
    vi: "cung goc nhung 404 -- phai ve cho cho va O LAI" },
];

function docTracker() {
  try { return JSON.parse(fs.readFileSync(TRACKER_LOG, "utf8")); } catch { return []; }
}

const browser = await chromium.launch();
const ketQua = [];

for (const ca of CA) {
  fs.writeFileSync(TRACKER_LOG, "[]");
  const truocTracker = docTracker().length;

  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  const yeuCau = [];
  page.on("request", (r) => yeuCau.push(r.url()));
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e).slice(0, 200)));

  // Rewrite every place's photo to the address under test.
  await page.route(`${API}/places*`, async (route) => {
    const res = await route.fetch();
    let body;
    try { body = await res.json(); } catch { return route.fulfill({ response: res }); }
    const list = Array.isArray(body) ? body : body.places ?? body.items ?? [];
    for (const p of list) { p.photo_url = ca.url; p.image_url = ca.url; }
    await route.fulfill({ response: res, json: body });
  });

  await page.goto(`${WEB}/#tab=kham-pha&nguoi=minh`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3500);

  // Force re-renders. Item 2 asks whether a failed load re-fires its request on
  // every parent update; only repeated rendering can answer that.
  for (let i = 0; i < 3; i++) {
    await page.evaluate(() => window.dispatchEvent(new Event("resize")));
    await page.mouse.wheel(0, 250);
    await page.waitForTimeout(600);
  }
  await page.waitForTimeout(1500);

  const dom = await page.evaluate(() => {
    const imgs = Array.from(document.querySelectorAll("img"));
    return {
      soImg: imgs.length,
      src: imgs.map((i) => i.currentSrc || i.getAttribute("src") || "").slice(0, 4),
      daTai: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
      vo: imgs.filter((i) => i.complete && i.naturalWidth === 0).length,
      vaiImage: document.querySelectorAll('[role="img"]').length,
      nhan: Array.from(document.querySelectorAll('[role="img"]'))
        .map((e) => e.getAttribute("aria-label")).filter(Boolean).slice(0, 4),
      iframe: document.querySelectorAll("iframe").length,
    };
  });

  const text = await page.locator("body").innerText();
  await page.screenshot({ path: `${SHOT}/anh-${ca.id}.png` });

  const hits = docTracker().slice(truocTracker);
  const trinhDuyetGoi = yeuCau.filter((u) => u.includes("9613"));

  ketQua.push({
    ca: ca.id,
    vi: ca.vi,
    url: ca.url.slice(0, 70),
    phaiTai: ca.phaiTai,
    trackerNhan: hits.length,
    trackerPaths: hits.map((h) => h.path),
    trinhDuyetGoi9613: trinhDuyetGoi.length,
    imgTrongDOM: dom.soImg,
    imgDaTai: dom.daTai,
    imgVo: dom.vo,
    roleImg: dom.vaiImage,
    nhanA11y: dom.nhan,
    iframe: dom.iframe,
    loRaChu: ["ECONNREFUSED", "404", "Not Found", "[object", "undefined"]
      .filter((s) => text.includes(s)),
    pageErrors: loi.slice(0, 2),
  });

  console.log(`\n=== ${ca.id} ===`);
  console.log(JSON.stringify(ketQua[ketQua.length - 1], null, 1));
  await ctx.close();
}

fs.writeFileSync(`${SHOT}/ket-qua-anh.json`, JSON.stringify(ketQua, null, 2));

const xanh = ketQua.find((r) => r.ca === "canary-xanh");
console.log("\n================ KET LUAN ================");
if (!xanh || xanh.imgDaTai === 0) {
  console.log("VOID: canary XANH khong tai duoc anh nao.");
  console.log("      Moi so 0 ben duoi la vo nghia -- may do co the da chet.");
} else {
  console.log(`canary XANH: ${xanh.imgDaTai} anh tai duoc -> may do CON SONG`);
  const ro = ketQua.filter((r) => !r.phaiTai && (r.trackerNhan > 0 || r.trinhDuyetGoi9613 > 0));
  console.log(ro.length === 0
    ? "khong ca doc hai nao cham toi tracker -> chot chan GIU"
    : `RO RI: ${ro.map((r) => r.ca).join(", ")}`);
}
await browser.close();
