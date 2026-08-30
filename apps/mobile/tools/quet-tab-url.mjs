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
 * A fifth, and the first that only appears away from the phone. Scanning
 * `ket-qua-thanh-toan` at the detector's default desktop viewport reports
 * `"VIETQR · NAPAS 247" 73% covered`; at 390x844 it reports nothing. Measured
 * across four widths, the caption sits at 704-718 every time and only the
 * scroller moves:
 *
 *     390x844   khung cuộn kết thúc 739   -> chữ nằm trong, sạch
 *     768x900   khung cuộn kết thúc 795   -> sạch
 *     1280x800  khung cuộn kết thúc 695   -> chữ 704-718 rơi xuống dưới, BÁO
 *     1440x900  khung cuộn kết thúc 795   -> sạch
 *
 * So it tracks viewport HEIGHT, not width: 1280x800 is the only one of the four
 * short enough to push that line past the clip. Same artifact, fifth time.
 *
 * The useful half of this is not the false positive, it is that a screen can be
 * clean at one viewport and speak up at another. This scan runs 390x844 only,
 * which is the right default when the phone is the primary target -- but a
 * clean run here is evidence about the phone, and saying more than that would
 * be claiming a width nobody measured.
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

import puppeteer from "puppeteer-core";

import { laLoiThat, phanLoai } from "./che-chu.mjs";
import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, NGUOI, moiMan, installTabStubs, taoFixtures, themAnhDiaDiem } from "./tab-snapshots.mjs";

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
 * The heavy canary's bottom defect, identified by its STYLE rather than its words.
 *
 * The first version of this check looked for the paragraph's text inside the
 * finding and failed on a page the scanner had read perfectly well, because
 * `imp detect` does not quote the page -- it reports the property. A
 * `low-contrast` finding reads `1.2:1 (need 4.5:1) — text #eeeeee on #ffffff`
 * and carries `line: 0` and no selector, so there is no positional field to
 * anchor on and no page text to match.
 *
 * The colour is the anchor instead, and it works because the filler cannot
 * produce it: every other element on that page is #1a1a1a at 16px or 20px, and
 * the filler scanned on its own returns exactly zero findings (measured, not
 * assumed -- `canaryNang(300, false)` is scanned every run for precisely this).
 * So a `low-contrast` naming #eeeeee can only have come from the last element
 * on a 1200-element page.
 */
const MAU_LOI_DAY = "#eeeeee";

/**
 * The same defect as `CANARY_XAU`, buried under a page as big as a real screen.
 *
 * `CANARY_XAU` is three elements. The screens below are 300 to 600, and that
 * gap is the whole reason this exists: a scanner that is awake on a postcard
 * and dies, truncates, or times out on a full page returns `[]` and exit 0 for
 * every screen, and the small canary signs off on all of it. That is the shape
 * of failure this project has already paid for twice -- a canary that proves
 * something true about a page nobody is measuring.
 *
 * So the filler is deliberately *clean*: high contrast, ordinary type, short
 * lines. It must contribute no findings of its own, or the check below cannot
 * tell "the scanner read to the bottom" from "the scanner found the usual mess
 * near the top". The one defect sits after all of it, and the gate does not
 * merely count findings -- it requires the finding carrying `DAY_TRANG`. A
 * scanner that stops early comes back with a number greater than zero and
 * still fails, which is the only version of this check worth having.
 *
 * `coLoi: false` builds the same page without the defect. That half is not
 * decoration either: it is what proves the filler contributes nothing, which
 * is the only reason a #eeeeee finding can be attributed to the last element.
 * Together the pair separates the three states a single scan cannot -- read
 * the whole page, read part of it, or fell over and said nothing.
 */
function canaryNang(soKhoi, coLoi = true) {
  const khoi = Array.from(
    { length: soKhoi },
    (_, i) =>
      `<section><h2>Muc ${i + 1}</h2>` +
      `<p>Doan van ban binh thuong, tuong phan cao, dong ngan va de doc.</p></section>`,
  ).join("");
  return `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>canary nang</title><style>
body{background:#fff;color:#1a1a1a;font-family:system-ui,sans-serif;font-size:16px;
  line-height:1.6;margin:0;padding:24px;max-width:640px}
h2{font-size:20px;line-height:1.3;margin:0 0 8px}
p{margin:0 0 16px}
.faint{color:${MAU_LOI_DAY};background:#fff;font-size:11px}
</style></head><body>
${khoi}
${coLoi ? `<p class="faint">Chu hong nam o day trang canary nang</p>` : ""}
</body></html>`;
}

/**
 * States that exist only after a press, on screens a cold URL already reaches.
 *
 * Khám phá cuts its grid at four and puts the rest behind "Xem tất cả". Both
 * halves are real screens, and the loop above only ever measures the first one:
 * a cold URL always lands collapsed. Left there, this file would report "Khám
 * phá: 0 findings" about a screen with two thirds of its catalogue undrawn --
 * the shape of claim `MAN_KHAC`'s own header warns about, filed under a name
 * that reads like full coverage.
 *
 * `imp detect` brings its own browser and has no hook to press anything, so the
 * page presses its own button: a poller injected after the API stub finds the
 * control by its text and clicks it, exactly as `quet-man-sau-tap.mjs` drives
 * the bill flow. By the time the detector has finished loading, the app is in
 * the expanded state on its own.
 *
 * `bam` is a PREFIX. The label carries a count ("Xem tất cả (6)") that moves
 * with the fixture, and an equality match would break the day a row is added
 * and report it as a missing button rather than a changed number.
 *
 * The needle is the fifth place in sort order, which the collapsed grid cannot
 * be showing. A needle naming any of the first four would read true before the
 * click landed and wave through a press that missed entirely.
 */
const MAN_TUONG_TAC = [
  {
    step: "kham-pha-mo-rong",
    frag: `tab=kham-pha&nguoi=${NGUOI}`,
    bam: "Xem tất cả",
    needle: "Cà Phê Vợt Hẻm 330",
    // Still one. Expanding the grid reveals four more cards and no more
    // photographs -- the fixture gives `photo_url` to the first row only -- so
    // a number above one here means the expanded grid started painting
    // something into frames the server said nothing about.
    anh: 1,
  },
  // rd-fe-33. The comment panel is the only place on the wall with an input,
  // a send button and a list of somebody else's words, and none of it exists
  // until the button is pressed -- so the closed wall this tool used to scan
  // reported zero for a surface it never rendered.
  //
  // `☰` is the comment button's glyph and both photographs carry one; `find`
  // takes the first, which is the photograph that actually has a comment to
  // show. The needle is that comment's author, a name printed by nothing else
  // on the screen, so it cannot read true before the press lands.
  {
    step: "ky-niem-binh-luan",
    frag: `vao=ky-niem&nguoi=${NGUOI}`,
    bam: "☰",
    needle: "Quang Huy",
    // Same wall, comment panel open. The photograph is still on screen behind
    // it, so the count is the same one `ky-niem` is held to.
    anh: 1,
  },
  /* rd-fe-33. Điểm hẹn's answer, which is the whole feature and which no cold
   * URL reaches: the button that asks for it is disabled until two people have
   * been placed, so `ban-do=hen` alone only ever renders the picker.
   *
   * Three presses, and "+" twice is not a typo -- each press adds one person to
   * the first district, and two people is the minimum the request accepts.
   * Both start from Đà Lạt, which makes this one origin rather than two, and
   * that is deliberate: with two DISTINCT areas the answer is invertible and
   * `DiemHen` withholds the result behind the inversion warning, so a
   * two-district selection would scan the warning under this filename.
   *
   * The needle is "Cân bằng nhất", the badge on the winning candidate. It is
   * printed by nothing else on the screen and cannot render before the answer
   * arrives, so a press that missed cannot pass as a result.
   */
  {
    step: "diem-hen-ket-qua",
    frag: `ban-do=hen&nguoi=${NGUOI}`,
    bam: ["+", "+", "Tìm chỗ gặp"],
    needle: "Cân bằng nhất",
  },
];

/** Serialised into the page, so it can reference nothing outside itself.
 *
 * `chuoiBam` is a LIST of prefixes pressed in order, each one waited for
 * separately. One press was enough while every interactive state on this app
 * was one button away from a cold URL, but Điểm hẹn's result is three: two
 * origins have to be chosen before "Tìm chỗ gặp" stops being disabled. Pressing
 * them in a single pass without re-waiting would click a control that the
 * previous press had not yet caused to render, and the miss would surface as a
 * needle failure naming the wrong cause.
 *
 * Each step waits for a control whose text starts with the prefix AND which is
 * not disabled -- the button here spends its first two presses disabled, and
 * clicking a disabled button succeeds silently while doing nothing.
 */
function tuDongBam(chuoiBam) {
  const buoc = Array.isArray(chuoiBam) ? chuoiBam : [chuoiBam];
  const t0 = Date.now();
  let i = 0;
  (function poll() {
    if (i >= buoc.length) return;
    const el = [...document.querySelectorAll("button, [role='button']")].find((n) => {
      if (n.disabled || n.getAttribute("aria-disabled") === "true") return false;
      return n.textContent.replace(/\s+/g, " ").trim().startsWith(buoc[i]);
    });
    if (el) {
      el.scrollIntoView({ block: "center", inline: "nearest" });
      if (document.scrollingElement) document.scrollingElement.scrollLeft = 0;
      el.click();
      i += 1;
      // Back through the poller rather than straight on to the next prefix:
      // the control the next step wants is usually rendered BY this click.
      setTimeout(poll, 60);
      return;
    }
    // Give up quietly. The needle check downstream is what turns a missed press
    // into a failure, and it reports the screen state rather than the poller's
    // opinion about why.
    if (Date.now() - t0 > 20000) return;
    setTimeout(poll, 60);
  })();
}

/**
 * `index.html`, with the stubs installed ahead of the bundle.
 *
 * The script is injected at the top of `<head>` rather than appended to
 * `<body>`. Expo emits the bundle as a `<script src>` in `<head>`, and a stub
 * that installs after the bundle has already called `fetch` patches nothing:
 * the screen would render its error panel and the needle check below would
 * fail. Order is the whole trick, so it is stated here rather than assumed.
 */
function trangCoStub(indexHtml, fixtures, bam = null) {
  const tiem =
    `<script>(${installTabStubs.toString()})(` +
    `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>` +
    // After the stub, so the list it feeds exists to be pressed; the poller
    // waits for the control rather than assuming it is there yet.
    (bam ? `<script>(${tuDongBam.toString()})(${JSON.stringify(bam)});</script>` : "");
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
/**
 * Split a screen's findings into real defects and measuring artifacts.
 *
 * Only `text-occlusion` is adjudicated -- it is the one rule here that decides
 * on raw box overlap, so it is the one rule that can be wrong about a page it
 * measured correctly. Every other finding passes through untouched: a filter
 * that grew to cover more rules would eventually be the thing deciding what
 * counts as a defect, which is the detector's job.
 *
 * A screen with no occlusion findings never opens a page, so the common case
 * costs nothing.
 */
async function loc(browser, url, needle, findings) {
  const che = findings.filter((f) => f.antipattern === "text-occlusion");
  if (!che.length) return { that: findings, aoAnh: [] };

  const page = await browser.newPage();
  try {
    page.setDefaultTimeout(30000);
    await page.goto(url, { waitUntil: "networkidle0" });
    await page
      .waitForFunction((n) => (document.body?.innerText ?? "").includes(n), { timeout: 20000 }, needle)
      .catch(() => {});

    const that = [];
    const aoAnh = [];
    for (const f of findings) {
      if (f.antipattern !== "text-occlusion") {
        that.push(f);
        continue;
      }
      const kq = await phanLoai(page, f);
      if (laLoiThat(kq)) that.push(f);
      else aoAnh.push({ f, kq });
    }
    return { that, aoAnh };
  } finally {
    await page.close();
  }
}

/** Element count for one page, so the heavy canary's weight is measured rather
 *  than asserted from the number of blocks it was built with. */
async function demEls(browser, url) {
  const page = await browser.newPage();
  try {
    await page.goto(url, { waitUntil: "networkidle0" });
    return await page.evaluate(() => document.querySelectorAll("*").length);
  } finally {
    await page.close();
  }
}

/**
 * How many of these frames a person actually sees a photograph in, from pixels.
 *
 * The column this feeds used to be `imgs.filter((i) => i.naturalWidth > 0)
 * .length`, and it was a lie on every row it appeared in. react-native-web
 * renders `<Image>` as TWO nodes: an `<img>` pinned at `opacity: 0` whose only
 * job is to decode and fire `onLoad`, and a wrapper `<div>` that paints the
 * picture through an inline `background-image`. The stub in `tab-snapshots.mjs`
 * answered the `<img>`, so `naturalWidth` came back 480 while the div dialled
 * the API host on the real network and got `requestfailed` /
 * `decodedBodySize: 0`. Every place card drew its category ramp under a column
 * reading "1 anh giai ma duoc".
 *
 * The obvious repair -- re-request the URL and see if it decodes -- is wrong
 * here, and measurably so. `installTabStubs` patches
 * `HTMLImageElement.prototype.src`, so a fresh `new Image()` created to test an
 * address gets the stub's answer rather than the painter's. Run with the
 * painter's supply deliberately removed, that version still counted the frame:
 * the check was asking the faker whether the faker had faked it.
 *
 * So this measures the composite instead. Shoot the frame, take the picture
 * away, shoot again: if no pixel moved, nothing was being shown there. The same
 * discriminator `soi-tuong-phan-anh.mjs` uses, and it cannot be fooled by any
 * amount of patching further up, because it looks at what was drawn.
 */
async function demAnhVeDuoc(page, khung) {
  let n = 0;
  for (let i = 0; i < khung.length; i += 1) {
    const o = khung[i];
    const clip = {
      x: Math.max(0, o.x), y: Math.max(0, o.y),
      width: Math.min(o.width, 2000), height: Math.min(o.height, 2000),
    };
    if (clip.width < 1 || clip.height < 1) continue;
    const co = await page.screenshot({ encoding: "base64", clip });
    await page.evaluate((k) => {
      const el = document.querySelector(`[data-khung-anh="${k}"]`);
      el.dataset.khungNen = el.style.backgroundImage;
      el.style.backgroundImage = "none";
      if (el.tagName === "IMG") el.style.visibility = "hidden";
    }, i);
    const khong = await page.screenshot({ encoding: "base64", clip });
    await page.evaluate((k) => {
      const el = document.querySelector(`[data-khung-anh="${k}"]`);
      el.style.backgroundImage = el.dataset.khungNen || "";
      if (el.tagName === "IMG") el.style.visibility = "";
    }, i);
    if (co !== khong) n += 1;
  }
  return n;
}

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
    const r = await page.evaluate(async () => {
      const imgs = [...document.querySelectorAll("img")];
      await Promise.all(imgs.map((i) => (i.complete ? null : i.decode().catch(() => {}))));

      /* Candidate photo frames. Whether any of them actually SHOWS a picture is
       * decided outside, from pixels -- see `demAnhVeDuoc`. */
      const khung = [];
      const them = (el) => {
        const b = el.getBoundingClientRect();
        if (b.width <= 0 || b.height <= 0) return;
        const st = getComputedStyle(el);
        if (st.visibility === "hidden" || st.display === "none" || Number(st.opacity) === 0) return;
        if (
          khung.some(
            (o) =>
              Math.abs(o.x - b.x) < 1 && Math.abs(o.y - b.y) < 1 &&
              Math.abs(o.width - b.width) < 1 && Math.abs(o.height - b.height) < 1,
          )
        ) return;
        el.setAttribute("data-khung-anh", String(khung.length));
        khung.push({ x: b.x, y: b.y, width: b.width, height: b.height });
      };

      for (const i of imgs) {
        if (i.naturalWidth > 0) them(i);
      }
      // Inline only: that is where react-native-web puts a dynamic image URL,
      // and walking every element's computed style would cost a full style
      // resolution on a page with thousands of nodes.
      for (const e of document.querySelectorAll("[style*='background-image']")) them(e);

      return {
        text: (document.body.innerText || "").replace(/\s+/g, " ").trim(),
        els: document.querySelectorAll("*").length,
        khung,
      };
    });
    const anh = await demAnhVeDuoc(page, r.khung);
    return { co: r.text.includes(needle), chars: r.text.length, els: r.els, anh, loi };
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

  // Khám phá is the first screen of the demo and its cards are photographs.
  // Without this the six cards all draw the stand-in, and every number this
  // tool prints for `kham-pha` is a number about a screen the demo never shows.
  const fixtures = themAnhDiaDiem(taoFixtures());
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
    // 300 sections is roughly 1200 elements, comfortably past the biggest
    // screen below. The margin is checked rather than assumed -- see the
    // assertion after the screen loop.
    const tenNang = ghi("__canary-nang.html", canaryNang(300));
    const tenNangSach = ghi("__canary-nang-sach.html", canaryNang(300, false));
    const trang = fs.readFileSync(indexPath, "utf8") === indexHtml ? trangCoStub(indexHtml, fixtures) : null;
    if (trang === null) throw new Error("index.html doi giua chung");
    for (const { step } of moiMan()) ghi(`__quet-${step}.html`, trang);
    for (const { step, bam } of MAN_TUONG_TAC) {
      ghi(`__quet-${step}.html`, trangCoStub(indexHtml, fixtures, bam));
    }

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

    // The heavy canary. Counting findings is not the test -- reaching the
    // bottom is. See `canaryNang`.
    console.log(`  nang ${await kiemHttp(`${goc}/${tenNang}`)} bytes HTML`);
    console.log(`  nang-sach ${await kiemHttp(`${goc}/${tenNangSach}`)} bytes HTML`);

    // Clean half first: it is what licenses the attribution in the dirty half.
    const nangSach = await quet(`${goc}/${tenNangSach}`);
    console.log(
      `  canary nang sach  findings=${nangSach.findings.length} exit=${nangSach.status}  (can = 0)`,
    );
    if (nangSach.findings.length !== 0) {
      throw new Error(
        `CANARY NANG SACH RA ${nangSach.findings.length} FINDING: phan lot cua trang nang ` +
          "dang tu sinh loi, nen mot finding tren ban day khong con quy duoc cho phan tu cuoi trang. " +
          "Sua phan lot cho sach roi hay tin ket qua nao ben duoi.",
      );
    }

    const nang = await quet(`${goc}/${tenNang}`);
    const chamDay = nang.findings.some(
      (f) => f.antipattern === "low-contrast" && (f.snippet ?? "").includes(MAU_LOI_DAY),
    );
    console.log(
      `  canary nang       findings=${nang.findings.length} exit=${nang.status}` +
        `  cham day trang=${chamDay ? "co" : "KHONG"}  (can: cham day)`,
    );
    if (!chamDay) {
      throw new Error(
        "MAY QUET KHONG DOC TOI DAY TRANG: loi duy nhat cua canary nang la mot phan tu " +
          `${MAU_LOI_DAY} o cuoi trang 1200 phan tu, va khong finding low-contrast nao nhac toi mau do. ` +
          "Phan lot vua quet ra 0 finding nen no khong the che mat, nghia la may quet " +
          "chay duoc tren trang nho nhung khong tron ven tren trang co that. " +
          "Moi so 0 duoi day se la so 0 cua mot luot quet bi cat ngan.",
      );
    }

    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    // Counted, not spelled out. The heading said "nam man" while the loop
    // below printed nine, because a screen was added to the list and the
    // sentence describing the list was not -- the same class of drift this
    // whole file exists to catch, sitting in its own output.
    console.log(
      `\n== ${moiMan().length} man tu URL + ${MAN_TUONG_TAC.length} man sau khi bam, tren trang that ==`,
    );
    const bangKe = [];
    for (const { step, frag, needle, anh } of [...moiMan(), ...MAN_TUONG_TAC]) {
      const url = `${goc}/__quet-${step}.html#${frag}`;

      const man = await kiemManHinh(browser, url, needle);
      if (!man.co) {
        throw new Error(
          `${step}: khong thay "${needle}" tren trang da render. Man dang o trang thai loi ` +
            `hoac stub thieu route, nen mot so 0 o day se la so 0 cua panel loi. ` +
            `(els=${man.els} chars=${man.chars}${man.loi.length ? ` loi=${man.loi[0].slice(0, 120)}` : ""})`,
        );
      }
      /* The needle proves TEXT arrived. On a screen whose subject is a
       * photograph it proves nothing about the photograph, and this run has
       * already shipped that gap once: `ky-niem`'s needle is recap text that
       * paints whether or not a single image loaded, so two `/photos/... 404`s
       * and a wall of grey stand-ins scored `findings=0 ... needle OK` for as
       * long as wall photographs have been permission-checked.
       *
       * A count rather than a boolean, because "some image appeared" is also
       * true of a wall serving bytes for every row, and that erases the
       * stand-in half the fixture is built to show. Rows without `anh` are
       * screens with nothing to decode and are not asked the question. */
      if (typeof anh === "number" && man.anh !== anh) {
        const viSao =
          man.anh < anh
            ? `Thieu anh: so findings duoi day se la so cua mot man KHONG co anh, ghi duoi ` +
              `ten mot man co anh. Kiem route /contexts/{id}/photos/{id} trong installTabStubs.`
            : `Thua anh: khung "cho san" da bien mat khoi man, nen mot nua trang thai ma ` +
              `fixture dung ra phai bay ra dang khong duoc quet. Kiem \`anhTheoId\`.`;
        throw new Error(
          `${step}: can ${anh} anh giai ma duoc, dang co ${man.anh}. ${viSao} ` +
            `(els=${man.els} chars=${man.chars})`,
        );
      }

      const { findings, status } = await quet(url);

      // `text-occlusion` compares raw bounding boxes, so every row that has
      // scrolled past its container's clip edge reports as "covered" by
      // whatever is pinned at those coordinates. Four of the five findings on
      // this app's screens were that, and acting on them would have moved
      // layouts nobody could see a problem with. Each one is re-measured in a
      // real render -- scrolled to, then hit-tested -- and only the ones still
      // buried count. The rest are printed, never dropped in silence.
      const { that, aoAnh } = await loc(browser, url, needle, findings);
      bad += that.length;
      // `anh` rides along into the JSON so a reader of `ket-qua.json` can tell a
      // measured photo surface from one that scored 0 with nothing on it. That
      // distinction is invisible in a findings count, which is how it was
      // missed the first time.
      bangKe.push({
        step,
        findings: that,
        aoAnh,
        status,
        chars: man.chars,
        els: man.els,
        anh: man.anh,
      });
      console.log(
        `  ${step.padEnd(10)} findings=${String(that.length).padStart(2)} exit=${status}` +
          `  (da render: els=${man.els} chars=${man.chars}, needle OK` +
          `${typeof anh === "number" ? `, ${man.anh} anh giai ma duoc` : ""})`,
      );
      for (const f of that) {
        console.log(`      [${f.severity}] ${f.antipattern}: ${(f.snippet ?? "").slice(0, 150)}`);
      }
      for (const { f, kq } of aoAnh) {
        console.log(
          `      [bo qua: ${kq.verdict}] ${f.antipattern}: ${(f.snippet ?? "").slice(0, 110)}`,
        );
        console.log(`          ${kq.ly}`);
      }
    }

    // The heavy canary only vouches for the screens it actually outweighs. If
    // a screen grows past it, the guarantee lapses silently -- the run still
    // prints a clean table, and the one number proving the scanner reads whole
    // pages was measured on a page smaller than the page being judged. Say so
    // instead of inheriting a conclusion this canary did not earn.
    const nangNhat = bangKe.reduce((m, r) => (r.els > m.els ? r : m), { step: "-", els: 0 });
    const elsNang = await demEls(browser, `${goc}/${tenNang}`);
    console.log(
      `\ncanary nang ${elsNang} els vs man nang nhat ${nangNhat.step} ${nangNhat.els} els`,
    );
    if (elsNang < nangNhat.els) {
      throw new Error(
        `CANARY NHE HON MAN NANG NHAT: canary ${elsNang} els < ${nangNhat.step} ${nangNhat.els} els. ` +
          "Bang tren dang thua huong mot ket luan do tren trang nho hon chinh no. " +
          "Tang so khoi trong canaryNang() cho vuot qua.",
      );
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
