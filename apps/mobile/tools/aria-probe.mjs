/** Read the toggle state off the live DOM, before and after a real press.
 *
 * The unit test renders the same components through react-native-web and
 * asserts on the markup, which is fast and hermetic and runs in `npm test`.
 * This does the one thing that cannot: it drives the shipped bundle in a real
 * Chromium, clicks a real cell, and reads the element back out of the live
 * document. That is how the bug was found and it is how the fix is checked --
 * a rendered attribute is the only evidence that the whole chain, from state
 * through Pressable through the DOM, delivers what it claims.
 *
 * It reuses `screen-snapshots.mjs` for the walk and the fetch stub, so there
 * is one place where "how to reach the split screen" is written down.
 *
 * Dev tool, not shipped code. Nothing in the app may import it.
 *
 *     cd apps/mobile && npm run build:check && node tools/aria-probe.mjs
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import {
  CHROME,
  JPEG_B64,
  SCAN_FIXTURE,
  addPersonOnMatrix,
  clickAria,
  clickButton,
  closeServer,
  createStaticServer,
  installBeforeApp,
  listen,
  waitForPreview,
  waitForScreen,
} from "./screen-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");
const API_BASE = "http://api.build-check.invalid";

const CELL = "Nam, Lẩu thái";

/** Every attribute of the element with this accessible label, as a plain
 *  object. Reading the whole set rather than one attribute is deliberate: the
 *  original report's evidence was that the *entire* attribute list came back
 *  identical after a press, and a probe that only looked at `aria-checked`
 *  could not have said that. */
function attributesOf(page, label) {
  return page.evaluate((needle) => {
    const el = document.querySelector(`[aria-label="${needle}"]`);
    if (!el) return null;
    return Object.fromEntries([...el.attributes].map((a) => [a.name, a.value]));
  }, label);
}

function rolesSummary(page) {
  return page.evaluate(() => {
    const out = {};
    for (const role of ["checkbox", "radio", "radiogroup"]) {
      const els = [...document.querySelectorAll(`[role="${role}"]`)];
      out[role] = {
        count: els.length,
        withAriaChecked: els.filter((e) => e.hasAttribute("aria-checked")).length,
        values: [...new Set(els.map((e) => e.getAttribute("aria-checked")))],
      };
    }
    return out;
  });
}

/** axe-core over the live page. Loaded from whatever copy is already on the
 *  machine (the chrome-devtools plugin ships one), so the probe adds no
 *  dependency to the app. Pass `AXE_CORE` to point it elsewhere. */
async function axeScan(page) {
  const axePath =
    process.env.AXE_CORE ||
    "/home/lakiet/.claude/plugins/cache/claude-plugins-official/chrome-devtools-mcp/1.6.0/node_modules/axe-core/axe.min.js";
  if (!fs.existsSync(axePath)) return { skipped: `axe-core not found at ${axePath}` };
  await page.addScriptTag({ path: axePath });
  return page.evaluate(async () => {
    const result = await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
    });
    return {
      // The pass count is reported for the same reason the detector's rule
      // count is: an empty violations list from a scanner that never ran looks
      // exactly like a clean page.
      rulesPassed: result.passes.length,
      violations: result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.length,
      })),
    };
  });
}

async function main() {
  const buildDir = path.join(MOBILE_ROOT, ".expo-build-check");
  if (!fs.existsSync(path.join(buildDir, "index.html"))) {
    throw new Error(`No bundle at ${buildDir}/index.html. Run: npm run build:check`);
  }
  if (!fs.existsSync(CHROME)) throw new Error(`Chromium not found at ${CHROME}`);

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "aria-probe-"));
  const jpegPath = path.join(tmp, "bill.jpg");
  fs.writeFileSync(jpegPath, Buffer.from(JPEG_B64, "base64"));

  const server = createStaticServer(buildDir);
  let browser = null;
  try {
    const port = await listen(server);
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(30000);
    await page.evaluateOnNewDocument(installBeforeApp, API_BASE, SCAN_FIXTURE);
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });

    await clickAria(page, "Bỏ qua, vào app mà chưa chọn người");
    await waitForScreen(page, "vao-app", "Khám phá");
    await clickAria(page, "Tạo mới");
    await waitForScreen(page, "menu-tao", "Tạo khoản chi");
    await clickAria(page, "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền");
    await waitForScreen(page, "chup-bill", "Chụp bill");

    const chooserP = page.waitForFileChooser({ timeout: 20000 });
    await clickAria(page, "Chọn ảnh bill");
    (await chooserP).accept([jpegPath]);
    await waitForScreen(page, "ket-qua", "Kết quả nhận diện", 45000);

    await clickButton(page, "Tiếp tục");
    await waitForScreen(page, "goi-y", "Gợi ý chia theo người");
    await addPersonOnMatrix(page, "Nam");
    await addPersonOnMatrix(page, "Hà");

    const before = await attributesOf(page, CELL);
    console.log("truoc khi bam :", JSON.stringify(before));
    await clickAria(page, CELL);
    await waitForPreview(page);
    const after = await attributesOf(page, CELL);
    console.log("sau khi bam   :", JSON.stringify(after));

    console.log("cac role      :", JSON.stringify(await rolesSummary(page), null, 2));
    console.log("axe (goi-y)   :", JSON.stringify(await axeScan(page), null, 2));

    const ok =
      before?.["aria-checked"] === "true" &&
      after?.["aria-checked"] === "false" &&
      before.role === "checkbox";
    console.log(ok ? "KET LUAN: aria-checked co that va doi khi bam" : "KET LUAN: VAN HONG");
    if (!ok) process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => {});
    await closeServer(server);
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
