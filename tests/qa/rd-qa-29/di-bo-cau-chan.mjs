/* Walk to the exact moment the empty-bill blocking sentence appears, and read
 * both halves of its promise off the SAME rendered markup.
 *
 * Why a walk and not a unit render. The claim under test is "the sentence names
 * a control that is on screen". A source read cannot check that, and a
 * server-rendered snapshot cannot either: `react-native-web` decides at runtime
 * which controls exist. Only a real browser on the real bundle sees both the
 * sentence and the buttons at once.
 *
 * The walk stops at "Gợi ý chia theo người" WITHOUT adding anybody. That empty
 * state is the only state the sentence fires in, and it is also the state every
 * snapshot tool skips past on its way to a populated matrix.
 *
 * Run it against two bundles built from two commits and diff the two JSON
 * blobs: that is the before/after. It imports the driving helpers from the
 * app's own snapshot tool, so the instrument is held constant while the product
 * varies.
 *
 *     cd apps/mobile
 *     cp <this file> ./di-bo-cau-chan.mjs
 *     npm run build:check
 *     PUPPETEER_EXECUTABLE_PATH=<chrome> node di-bo-cau-chan.mjs <nhan>
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import {
  CHROME,
  JPEG_B64,
  SCAN_FIXTURE,
  listen,
  closeServer,
  createStaticServer,
  installBeforeApp,
  waitForScreen,
  clickAria,
  clickButton,
} from "./tools/screen-snapshots.mjs";

const NHAN = process.argv[2] ?? "khong-ten";
const API_BASE = "http://api.build-check.invalid";

const jpeg = path.join(os.tmpdir(), `di-bo-cau-chan-${NHAN}.jpg`);
fs.writeFileSync(jpeg, Buffer.from(JPEG_B64, "base64"));

const server = createStaticServer(".expo-build-check");
const port = await listen(server);
const browser = await puppeteer.launch({
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || CHROME,
  headless: true,
  args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
// Phone, not desktop. The sentence wraps differently at 390pt and that is the
// width the demo runs at.
await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
await page.evaluateOnNewDocument(installBeforeApp, API_BASE, SCAN_FIXTURE);
await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle0" });

await clickAria(page, "Bỏ qua, vào app mà chưa chọn người");
await waitForScreen(page, "vao-app", "Khám phá");
await clickAria(page, "Tạo mới");
await waitForScreen(page, "menu-tao", "Tạo khoản chi");
await clickAria(page, "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền");
await waitForScreen(page, "chup-bill", "Chụp bill");

const chooser = page.waitForFileChooser({ timeout: 20000 });
await clickAria(page, "Chọn ảnh bill");
(await chooser).accept([jpeg]);
await waitForScreen(page, "ket-qua", "Kết quả nhận diện", 45000);

await clickButton(page, "Tiếp tục");
await waitForScreen(page, "goi-y", "Gợi ý chia theo người");
// STOP. Adding anyone here destroys the state under test.

const doc = await page.evaluate(() => {
  const txt = document.body.innerText;
  const cau = txt
    .split("\n")
    .map((s) => s.trim())
    .find((s) => s.startsWith("Chưa "));
  const nut = [...document.querySelectorAll("button,[role='button'],[aria-label]")];
  const cong = nut
    .filter((b) => (b.innerText ?? "").trim() === "+")
    .map((b) => b.getAttribute("aria-label") ?? "(không nhãn)");

  // Scroll containers, measured before anything is called clipped. A shorter
  // visible box is not a missing row: the dish list scrolls, and a longer
  // blocking sentence costs it height.
  const hopCuon = [...document.querySelectorAll("div")]
    .filter((d) => d.scrollHeight > d.clientHeight + 4 && d.clientHeight > 40)
    .map((d) => ({ cao: d.clientHeight, caoThat: d.scrollHeight }));

  return {
    cau: cau ?? "(KHÔNG THẤY câu chặn nào)",
    soNutCong: cong.length,
    nhanNutCong: cong,
    nutDangCo: nut.map((b) => b.getAttribute("aria-label")).filter(Boolean),
    monTrenDom: ["Lẩu thái", "Cơm rang", "Nước sâm"].filter((m) => txt.includes(m)),
    hopCuon,
    emDashTrenMan: (txt.match(/—/g) ?? []).length,
  };
});

console.log(JSON.stringify(doc, null, 1));
await page.screenshot({ path: path.join(os.tmpdir(), `di-bo-cau-chan-${NHAN}.png`), fullPage: true });

await browser.close();
await closeServer(server);
