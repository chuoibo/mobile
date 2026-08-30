/** Independent read on M3: when the to-cha shortcut is moved into the sample
 *  counter, what verdict does the filter actually return for text that is
 *  really buried? Confirms the probe's rc=3 comes from an inflated `nhinThay`
 *  and not from a thrown exception or a selector that stopped matching.
 *
 *  Deliberately does NOT use the probe's page machinery -- a hand-built page,
 *  so a bug in the probe cannot produce the answer here too.
 */
import http from "node:http";
import puppeteer from "puppeteer-core";

// Chay:  node tests/qa/qa-tt-0016/do-doc-lap-verdict.mjs <duong-dan-pre-patch> [<duong-dan-M3>]
// Lay ban pre-patch bang: git show c9532cf:apps/mobile/tools/che-chu.mjs > /tmp/prepatch.mjs
import { execFileSync } from "node:child_process";

const CHROME = process.env.PUPPETEER_EXECUTABLE_PATH;
const GOC = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
const MODULES = {
  "ban dang do (post-#261)": `${GOC}/apps/mobile/tools/che-chu.mjs`,
  ...(process.argv[3] ? { "M3 duong tat trong ham dem": process.argv[3] } : {}),
  "doi chung pre-patch": process.argv[2],
};

// A card whose class set the overlay copies exactly -- the rnw atomic-class
// collision, reproduced by hand. The overlay is a SIBLING of the text, not an
// ancestor: the words really are unreadable.
const HTML = `<!doctype html><html><body style="margin:0">
<div class="r-card r-bg r-pad" style="position:relative;padding:40px">
  <span class="r-txt">Tong cong nhom</span>
</div>
<div class="r-card r-bg r-pad" style="position:fixed;left:0;top:0;width:400px;height:120px;background:#123456;z-index:9999"></div>
</body></html>`;

const server = http.createServer((_, res) => {
  res.writeHead(200, { "content-type": "text/html" });
  res.end(HTML);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
});

// Exactly the snippet shape the detector writes: text selector, quoted run,
// coverage percent, occluder selector.
const snippet = 'div.r-card.r-bg.r-pad "Tong cong nhom" is 92% covered by an opaque element (div.r-card.r-bg.r-pad)';

console.log(`snippet: ${snippet}\n`);
console.log("module                        verdict      doc duoc  laLoiThat");
for (const [ten, duong] of Object.entries(MODULES)) {
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle0" });
  const m = await import(duong.startsWith("/") ? `file://${duong}` : duong);
  const kq = await m.phanLoai(page, { snippet });
  console.log(
    `${ten.padEnd(30)}${String(kq.verdict).padEnd(13)}` +
      `${String(kq.diemNhinThay)}/${String(kq.diemDo)}`.padEnd(10) +
      `${m.laLoiThat(kq) ? "GIU canh bao" : "XOA canh bao"}`,
  );
  await page.close();
}
await browser.close();
server.close();
