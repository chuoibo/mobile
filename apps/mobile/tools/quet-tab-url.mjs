/** Run the anti-pattern detector against the four tabs as a LIVE page.
 *
 * `tab-snapshots.mjs` already drives these screens, but what it produces is a
 * serialized DOM written to disk. Scanning those files is not the same
 * measurement and is known to be worse in both directions here: the act of
 * snapshotting invents `clipped-overflow-container` findings that the live
 * page does not have, while several rules never fire at all because they need
 * a real render. `imp detect` says so itself -- `line-length` counts characters
 * on a laid-out line, `body-text-viewport-edge` and `text-occlusion` measure
 * computed geometry, and `low-contrast` over a gradient has to sample pixels.
 * Measured on one deliberately sloppy page: 4 findings static, 10 rendered.
 *
 * So the detector needs a URL that serves the real screen. The obstacle was
 * never the fragment -- `lien-ket.ts` has handled `#tab=` for a while -- it was
 * the data. All four tabs call the API on mount, `build:check` inlines an
 * address that resolves nowhere, and a detector drives its own browser, so
 * there is nowhere to hang `page.evaluateOnNewDocument`. A cold URL therefore
 * renders four error panels, and a scan of four error panels reports back as
 * a scan of four tabs.
 *
 * This file removes that obstacle the only way that keeps one source of truth:
 * it writes the SAME stub function and the SAME fixtures `tab-snapshots.mjs`
 * uses into an inline `<script>` ahead of the bundle, as a generated page per
 * tab. Nothing is duplicated by hand, so the screens photographed and the
 * screens scanned cannot drift apart.
 *
 * Dev tool, not shipped code. Nothing in the app may import it. The generated
 * pages live inside the build directory and are deleted on the way out; they
 * are not a demo mode and there is no route from one into the product.
 *
 *     cd apps/mobile && npm run build:check && node tools/quet-tab-url.mjs
 *
 * ## Why this file scans two canaries it does not care about
 *
 * A detector that cannot see returns `[]` and exits 0, which is byte-identical
 * to a clean screen. That failure has actually happened on this machine: with
 * Chrome missing, URL scanning reported every page spotless while the same
 * pages scanned as files reported four findings each. So each run also scans
 * one page built to be ugly and one built to be clean, and REFUSES to report a
 * result unless the ugly one comes back dirty and the clean one comes back
 * clean. A green from this tool means the scanner was demonstrably awake for
 * that green.
 *
 * The needle check is the second half of the same idea, aimed at the app
 * rather than the scanner: a screen stuck on its error panel is quiet, short,
 * and scores zero findings. Every tab must print text that only the loaded
 * screen prints before its number is allowed to count.
 *
 * ## `text-occlusion` under a pinned button is almost always a false positive
 *
 * Read this before "fixing" one. The rule compares raw bounding boxes and does
 * not subtract the clip of a scroll container, so ANY content that has scrolled
 * past the bottom of a scroller reports as covered by whatever is pinned below
 * it -- the tab bar, or a screen's own "Đóng" button. Four of these have now
 * been measured on this project and four out of four were the same artifact:
 *
 *     ca-nhan   "Giao dịch gần đây"    41%   khung cuộn kết thúc 777, chữ 800-823
 *     ban-be    "Phạm Hoàng Anh Thư"  100%   khung cuộn kết thúc 764, chữ 784-802
 *     ban-be    "Bạn bè từ 22/08"     100%   cùng khung, cùng nút "Đóng" 780-828
 *     dia-diem  "Hợp vì ngân sách..."  96%   khung cuộn kết thúc 702, chữ 709-733
 *
 * In every one the text is BELOW its scroller's bottom edge, is clipped rather
 * than painted, and scrolls into view perfectly well above the button. Nothing
 * was wrong on any of the four screens.
 *
 * So measure before touching layout: `node tools/do-hinh-hoc.mjs <man> "<chữ>"`
 * prints the text box, every scroll container, and every button box. If the
 * text's `top` is past the scroller's `bottom`, it is this artifact and the
 * correct action is to leave the screen alone. No detector ignore is added for
 * it either -- the ignore config is shared with other lanes, and silencing a
 * rule project-wide to quiet four known-benign hits would also silence the
 * real occlusions it is there to catch.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, NGUOI, moiMan, installTabStubs, taoFixtures } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

/** The phone is the primary target, so that is the viewport the numbers are
 *  reported at. Passed to the detector explicitly rather than left to default:
 *  line-length and viewport-edge rules answer differently per width, and an
 *  unstated width makes two runs incomparable. */
const VIEWPORT = process.env.QUET_VIEWPORT ?? "390x844";

/** The wrapper, not a bare `node`: the plugin's own docs print a path that does
 *  not exist under a plugin install, and the system node is often too old to
 *  load the detector at all. Overridable for a machine that puts it elsewhere. */
const IMP = process.env.IMP_BIN ?? path.join(os.homedir(), ".claude/skills/impeccable-pipeline/scripts/imp");

/** Deliberately ugly: invisible text, unreadable text, and a line long enough
 *  to trip the measured rules. Its only job is to come back dirty. */
const CANARY_XAU = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>canary xau</title><style>
body{background:#fff;font-family:Arial;margin:0}
.faint{color:#eee;background:#fff;font-size:11px}
.tiny{font-size:7px;color:#ddd}
.cram{width:1400px}
button{background:#fafafa;color:#f0f0f0;border:none;padding:1px 2px;font-size:9px}
</style></head><body><div class="cram">
<p class="faint">Chu nay gan nhu vo hinh tren nen trang</p>
<p class="tiny">Chu sieu nho khong ai doc noi</p>
<button>Bam</button>
</div></body></html>`;

/** Deliberately plain: high contrast, ordinary rhythm, a real tap target. Its
 *  only job is to come back clean, so a tool that finds faults everywhere is
 *  caught as loudly as one that finds them nowhere. */
const CANARY_SACH = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>canary sach</title><style>
body{background:#fff;color:#1a1a1a;font-family:system-ui,sans-serif;font-size:16px;
  line-height:1.6;margin:0;padding:24px;max-width:640px}
h1{font-size:28px;line-height:1.3;margin:0 0 16px}
p{margin:0 0 16px}
button{background:#1a4fd6;color:#fff;border:none;border-radius:8px;padding:12px 20px;
  font-size:16px;min-height:44px}
</style></head><body>
<h1>Trang doi chung sach</h1>
<p>Doan van ban nay co do tuong phan cao va co nhip do doc binh thuong.</p>
<button>Tiep tuc</button>
</body></html>`;

/**
 * `index.html`, with the stubs installed ahead of the bundle.
 *
 * The script is injected at the top of `<head>` rather than appended to
 * `<body>`. Expo emits the bundle as a `<script src>` in `<head>`, and a stub
 * that installs after the bundle has already called `fetch` patches nothing:
 * the screen would render its error panel and the needle check below would
 * fail. Order is the whole trick, so it is stated here rather than assumed.
 */
function trangCoStub(indexHtml, fixtures) {
  const tiem =
    `<script>(${installTabStubs.toString()})(` +
    `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
  const i = indexHtml.indexOf("<head>");
  if (i === -1) throw new Error("index.html khong co <head> de chen stub");
  return indexHtml.slice(0, i + "<head>".length) + tiem + indexHtml.slice(i + "<head>".length);
}

/**
 * Confirm the URL really serves HTML before anybody scans it.
 *
 * A 404 body is short, plain, and has no anti-patterns in it, so a mistyped
 * path scores zero and exits 0 -- the same output as a flawless screen. This
 * turns that into a stop.
 */
async function kiemHttp(url) {
  const res = await fetch(url);
  const ct = res.headers.get("content-type") ?? "";
  const body = await res.text();
  if (!res.ok || !ct.includes("text/html")) {
    throw new Error(
      `${url} khong tra ve HTML (status ${res.status}, content-type "${ct}"). ` +
        `Mot trang 404 quet ra 0 finding va exit 0, y het mot man sach.`,
    );
  }
  return body.length;
}

/**
 * Run the detector on one URL and return its findings.
 *
 * `spawn`, deliberately not `spawnSync`. The static server above lives in THIS
 * process, and `spawnSync` blocks the event loop until the child exits -- so
 * the detector's browser asks for the page, nobody answers, and it gives up.
 * What comes back then is `[]` and exit 0, with the real reason on stderr:
 *
 *     Error: Navigation timeout of 30000 ms exceeded
 *
 * which is to say the blocking call turns every screen into a clean screen.
 * That is not a hypothetical: this file scored four spotless tabs that way
 * before the canary below refused the result. Stderr is therefore surfaced on
 * an empty read rather than dropped, because the difference between "nothing
 * wrong" and "never loaded" only exists there.
 */
function quet(url) {
  return new Promise((resolve, reject) => {
    const child = spawn(IMP, ["detect", "--json", "--viewport", VIEWPORT, url], {
      env: {
        ...process.env,
        // Preflight prints "url scanning: available" even when it is not, and a
        // detector that cannot launch Chrome returns [] and exits 0. Pinning the
        // binary is what makes the canaries below able to fail.
        PUPPETEER_EXECUTABLE_PATH: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      },
    });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", (e) => reject(new Error(`khong chay duoc ${IMP}: ${e.message}`)));
    child.on("close", (status) => {
      let findings;
      try {
        findings = JSON.parse(out);
      } catch {
        reject(
          new Error(
            `imp detect khong tra JSON cho ${url} (exit ${status}).\n` +
              `stdout: ${out.slice(0, 400)}\nstderr: ${err.slice(0, 400)}`,
          ),
        );
        return;
      }
      if (!Array.isArray(findings)) {
        reject(new Error(`imp detect tra ve khong phai mang cho ${url}`));
        return;
      }
      if (findings.length === 0 && err.trim()) {
        reject(
          new Error(
            `imp detect tra ve 0 finding cho ${url} NHUNG co loi tren stderr, ` +
              `nen day khong phai mot man sach:\n${err.trim().slice(0, 400)}`,
          ),
        );
        return;
      }
      resolve({ findings, status });
    });
  });
}

/**
 * Load the page and confirm the loaded screen is really on it.
 *
 * Returns the rendered text length too, because "the needle is present" and
 * "the screen actually drew" are different claims and the second one is the
 * one a reader of the report will assume.
 */
async function kiemManHinh(browser, url, needle) {
  const page = await browser.newPage();
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  try {
    page.setDefaultTimeout(30000);
    await page.goto(url, { waitUntil: "networkidle0" });
    await page.waitForFunction(
      (n) => (document.body?.innerText ?? "").includes(n),
      { timeout: 20000 },
      needle,
    ).catch(() => {});
    const r = await page.evaluate(() => ({
      text: (document.body.innerText || "").replace(/\s+/g, " ").trim(),
      els: document.querySelectorAll("*").length,
    }));
    return { co: r.text.includes(needle), chars: r.text.length, els: r.els, loi };
  } finally {
    await page.close();
  }
}

async function main() {
  const buildDir = path.join(MOBILE_ROOT, ".expo-build-check");
  const indexPath = path.join(buildDir, "index.html");
  if (!fs.existsSync(indexPath)) {
    throw new Error(`Khong co bundle o ${indexPath}. Chay: cd apps/mobile && npm run build:check`);
  }
  if (!fs.existsSync(CHROME)) throw new Error(`Khong tim thay Chromium o ${CHROME}`);
  if (!fs.existsSync(IMP)) {
    throw new Error(`Khong tim thay imp o ${IMP}. Dat IMP_BIN neu no nam cho khac.`);
  }

  const fixtures = taoFixtures();
  const indexHtml = fs.readFileSync(indexPath, "utf8");
  const viet = [];
  const ghi = (ten, noiDung) => {
    const p = path.join(buildDir, ten);
    fs.writeFileSync(p, noiDung);
    viet.push(p);
    return ten;
  };

  const server = createStaticServer(buildDir);
  let browser = null;
  let bad = 0;
  try {
    const port = await listen(server);
    const goc = `http://127.0.0.1:${port}`;

    const tenXau = ghi("__canary-xau.html", CANARY_XAU);
    const tenSach = ghi("__canary-sach.html", CANARY_SACH);
    const trang = fs.readFileSync(indexPath, "utf8") === indexHtml ? trangCoStub(indexHtml, fixtures) : null;
    if (trang === null) throw new Error("index.html doi giua chung");
    for (const { step } of moiMan()) ghi(`__quet-${step}.html`, trang);

    // The canaries decide whether any number below is allowed to mean anything.
    console.log(`== doi chung may quet (viewport ${VIEWPORT}) ==`);
    console.log(`  goc = ${goc}`);
    console.log(`  xau  ${await kiemHttp(`${goc}/${tenXau}`)} bytes HTML`);
    console.log(`  sach ${await kiemHttp(`${goc}/${tenSach}`)} bytes HTML`);
    const xau = await quet(`${goc}/${tenXau}`);
    const sach = await quet(`${goc}/${tenSach}`);
    console.log(`  canary xau   findings=${xau.findings.length} exit=${xau.status}  (can > 0)`);
    console.log(`  canary sach  findings=${sach.findings.length} exit=${sach.status}  (can = 0)`);
    if (xau.findings.length === 0) {
      throw new Error(
        "MAY QUET MU: trang co tinh xau khong ra finding nao. " +
          "Mot so 0 tren man that luc nay khong chung minh gi. " +
          "Thuong la thieu Chrome cho puppeteer -- dat PUPPETEER_EXECUTABLE_PATH.",
      );
    }
    if (sach.findings.length !== 0) {
      throw new Error(
        `MAY QUET BAN OAN: trang sach ra ${sach.findings.length} finding. ` +
          "Ket qua duoi khong dang tin cho toi khi hieu vi sao.",
      );
    }

    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    console.log(`\n== nam man, tren trang that ==`);
    const bangKe = [];
    for (const { step, frag, needle } of moiMan()) {
      const url = `${goc}/__quet-${step}.html#${frag}`;

      const man = await kiemManHinh(browser, url, needle);
      if (!man.co) {
        throw new Error(
          `${step}: khong thay "${needle}" tren trang da render. Man dang o trang thai loi ` +
            `hoac stub thieu route, nen mot so 0 o day se la so 0 cua panel loi. ` +
            `(els=${man.els} chars=${man.chars}${man.loi.length ? ` loi=${man.loi[0].slice(0, 120)}` : ""})`,
        );
      }

      const { findings, status } = await quet(url);
      bad += findings.length;
      bangKe.push({ step, findings, status, chars: man.chars, els: man.els });
      console.log(
        `  ${step.padEnd(10)} findings=${String(findings.length).padStart(2)} exit=${status}` +
          `  (da render: els=${man.els} chars=${man.chars}, needle OK)`,
      );
      for (const f of findings) {
        console.log(`      [${f.severity}] ${f.antipattern}: ${(f.snippet ?? "").slice(0, 150)}`);
      }
    }

    const outDir = path.join(MOBILE_ROOT, ".tab-scan");
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(
      path.join(outDir, "ket-qua.json"),
      JSON.stringify({ viewport: VIEWPORT, canaryXau: xau.findings.length, man: bangKe }, null, 2),
    );
    console.log(`\ntong findings tren cac man: ${bad}`);
    console.log(`chi tiet: ${path.join(outDir, "ket-qua.json")}`);
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
    // The generated pages are scan scaffolding, not build output. Leaving them
    // behind would put a page that stubs the API inside a directory somebody
    // could serve.
    for (const p of viet) {
      try {
        fs.unlinkSync(p);
      } catch (err) {
        if (err.code !== "ENOENT") throw err;
      }
    }
  }
  process.exitCode = bad > 0 ? 2 : 0;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
