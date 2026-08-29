/** Run the detector, as a LIVE page, on the screens you can only reach by tapping.
 *
 * `quet-tab-url.mjs` scans every screen a cold URL can open -- nine of them,
 * derived from the router so the list cannot drift. That is the whole of the
 * coverage, and it stops exactly where the demo's hero path begins. `ChupBill`,
 * `KetQuaNhanDien` and `GoiYChia` have no fragment: you get to them by pressing
 * [+], then "Tạo khoản chi", then handing the viewfinder a photo. So the three
 * screens the entire product exists to demonstrate -- photograph a bill, read
 * the items off it, assign them to people -- had never been through the
 * detector once.
 *
 * Nothing said so, and one thing actively looked like it did. `screen-
 * snapshots.mjs` drives this same walk and writes an HTML file per step, so a
 * directory listing shows `chup-bill.html`, `ket-qua.html`, `goi-y.html` and
 * reads as coverage. It is not, and that file says so itself: those are
 * serialized DOM, "a detector scan, and must not be described as one". The
 * serializer invents `clipped-overflow-container` findings the live page does
 * not have, and the rules that need a real render -- `line-length` counting
 * characters on a laid-out line, `body-text-viewport-edge`, `low-contrast`
 * sampling pixels over a gradient -- never fire at all. Measured on one
 * deliberately sloppy page: 4 findings static, 10 rendered.
 *
 * ## Why this is not just another entry in the scan loop
 *
 * `imp detect <url>` brings its own browser. It navigates, waits, measures, and
 * exits. There is no hook to press a button in the middle, which is precisely
 * why these screens stayed unmeasured while the fragment-reachable ones got
 * covered twice.
 *
 * So the page drives ITSELF. The same inline `<script>` trick `quet-tab-url.mjs`
 * uses to install the API stub ahead of the bundle also carries a scripted
 * walk: wait for this text, click that `aria-label`, hand the file input these
 * JPEG bytes. By the time the detector's browser is done loading, the app has
 * walked to the target screen on its own, and what gets measured is a real
 * render of the real screen -- not a snapshot of one.
 *
 * The stub, the fixtures, the JPEG and the VietQR payload are all imported from
 * `screen-snapshots.mjs` rather than restated, so the screens photographed and
 * the screens scanned cannot describe two different apps.
 *
 * ## The third canary, and why two were not enough
 *
 * `quet-tab-url.mjs` scans one deliberately ugly page and one deliberately
 * clean page every run, and refuses to report anything unless the ugly one
 * comes back dirty. That catches a blind scanner -- the `[]`-and-exit-0 failure
 * that reads exactly like a spotless screen.
 *
 * It cannot catch the failure this file introduces. A self-driving page has a
 * race in it: if the detector measures before the walk finishes, it measures
 * `MoDau`, scores it, and labels the result `goi-y`. Both canaries pass in that
 * world, because both are static pages with nothing to wait for. The number
 * would be real, the screen it names would be wrong, and nothing would say so.
 *
 * So there is a third canary, and it is the one that makes the other two worth
 * running. It drives the real bundle through the LONGEST scenario here, and
 * only then paints `CANARY LAI DA CHAY` in near-invisible grey. The run is
 * refused unless a finding comes back whose snippet contains that marker:
 *
 *   - marker present  -> the detector waited for a full walk before measuring,
 *                        so every step's number describes the screen it names.
 *   - marker missing  -> it measured early. Every number below is the opening
 *                        screen wearing another screen's label, and the run
 *                        aborts instead of reporting them.
 *
 * Counting findings would not do: a page measured too early still scores
 * whatever `MoDau` scores, and `> 0` would pass while proving nothing. The
 * assertion has to name something that can only exist after the walk.
 *
 * ## Coverage is derived, not remembered
 *
 * `STEPS` in `screen-snapshots.mjs` is the list of screens the hero walk
 * reaches, and `tests/di-qua-hay-chup.test.mjs` already forces `drive` and that
 * list to agree. This file takes the same list as its input and requires every
 * name in it to be either scanned here or written down in `CHUA_QUET` with a
 * reason. `tests/quet-man-sau-tap.test.mjs` fails if one is neither.
 *
 * That is the lesson from the layer above, applied one layer down: Kỷ niệm
 * shipped and went unscanned for its whole life because the list of screens and
 * the list of scanned screens were two hand-kept things that agreed only while
 * somebody remembered. `CHUA_QUET` is a record of what is unmeasured, not a
 * dismissal of it -- a named exclusion is evidence of intent, never of coverage.
 *
 * Dev tool, not shipped code. Nothing in the app may import it. The generated
 * pages live inside the build directory and are deleted on the way out; they
 * stub the API, so leaving one behind would put a fake-data page somewhere
 * serveable.
 *
 *     cd apps/mobile && npm run build:check && node tools/quet-man-sau-tap.mjs
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import {
  API_BASE,
  CHROME,
  JPEG_B64,
  SCAN_FIXTURE,
  TREN_BILL,
  VIETQR_FIXTURE,
  closeServer,
  createStaticServer,
  installBeforeApp,
  listen,
} from "./screen-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

/** The phone is the primary target, so that is the viewport reported. Stated
 *  rather than defaulted: `line-length` and the viewport-edge rules answer
 *  differently per width, and an unstated width makes two runs incomparable. */
const VIEWPORT = process.env.QUET_VIEWPORT ?? "390x844";

/** The wrapper, not a bare `node`: the plugin's docs print a path that does not
 *  exist under a plugin install, and the system node is often too old. */
const IMP = process.env.IMP_BIN ?? path.join(os.homedir(), ".claude/skills/impeccable-pipeline/scripts/imp");

/** The words the drive canary paints. Read by a human in the log, and by
 *  `kiemManHinh` as a needle; NOT by the assertion -- see `DAU_MAU`. */
export const DAU_LAI = "CANARY LAI DA CHAY";

/**
 * The colour pair the assertion actually looks for, and why it is a colour.
 *
 * The first version of this canary asserted that some finding's JSON contained
 * the words above. It could never pass, and it never had: the detector reports
 * the *style* it measured, not the text it measured it on, so a marker painted
 * perfectly comes back as
 *
 *     [warning] low-contrast: 1.2:1 (need 4.5:1) — text #eeeeee on #ffffff
 *
 * with the sentence nowhere in it. That fails closed, which is the safe
 * direction, but it means the whole file could never report a number -- the
 * walk finished, the marker rendered, and the run aborted anyway.
 *
 * So the marker is a colour pair instead, chosen for three properties:
 * contrast low enough that `low-contrast` fires on it (1.16:1), a hex that
 * appears nowhere in the app's warm cream palette so no real screen can forge
 * it, and a value the detector prints verbatim into the finding. It still
 * cannot exist before the walk ends, which is the only thing the canary was
 * ever asserting.
 */
export const DAU_MAU = { chu: "#e3e4e5", nen: "#fcfdfe" };

/**
 * The walk, as data.
 *
 * Each screen names the presses that reach it and the text that proves it
 * arrived. The needle is text only the LOADED screen prints -- never a frame
 * the shell draws in every state, because a screen stuck on its error panel is
 * quiet, short, scores zero findings and would otherwise pass as clean.
 */
/**
 * The walk is written as one growing chain rather than nine copied lists.
 *
 * Each screen's scenario is the previous screen's scenario plus the presses
 * that leave it. Spelled out per entry, the shared prefix appeared nine times
 * and every one of them was a place where a copy could quietly disagree with
 * the others -- and a scenario that walks somewhere slightly different still
 * produces a number, still names the screen it meant to reach, and says
 * nothing. Chaining makes that class of drift unrepresentable.
 */
const DEN_CHUP_BILL = [
  { cho: "AI đi chơi, chia bill thông minh" },
  { bam: "Bỏ qua, vào app mà chưa chọn người" },
  { cho: "Khám phá" },
  { bam: "Tạo mới" },
  { cho: "Tạo khoản chi" },
  { bam: "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền" },
  { cho: "Đưa bill vào khung hình" },
];
const DEN_KET_QUA = [
  ...DEN_CHUP_BILL,
  { bam: "Chọn ảnh bill" },
  { anh: JPEG_B64 },
  { cho: "Đã nhận diện 3 món", ms: 45000 },
];
const DEN_GOI_Y = [...DEN_KET_QUA, { bamChu: "Tiếp tục" }, { cho: "Gợi ý chia theo người" }];
/**
 * `Xem kết quả` is disabled until every đồng on the bill has an eater, so the
 * roster has to exist before the walk can leave this screen at all. Adding the
 * three names on the bill puts each of them on every item, which covers 100%
 * and satisfies `blockingProblem`.
 */
const DEN_NHAP = [
  ...DEN_GOI_Y,
  ...TREN_BILL.map((ten) => ({ themNguoi: ten })),
  { bamChu: "Xem kết quả" },
  { cho: "Khoản chi mới" },
];
/** The description is the one field the bill cannot fill in for you; the
 *  amount arrives already totalled from the reading. */
const DEN_DE_XUAT = [
  ...DEN_NHAP,
  { go: { oNhap: "bữa lẩu tối thứ bảy", chu: "bữa lẩu tối thứ bảy" } },
  { chonRadio: TREN_BILL[0] },
  { bamChu: "Chia tiền" },
  { cho: "Đúng rồi, ghi vào sổ" },
];
const DEN_DOT_THU = [...DEN_DE_XUAT, { bamChu: "Đúng rồi, ghi vào sổ" }, { cho: "Phát đợt thu" }];
/** Publishing is the moment the codes come into existence, so the app leaves
 *  the batch and lands on the settlement screen carrying the VietQR. */
const DEN_KET_QUA_THANH_TOAN = [
  ...DEN_DOT_THU,
  { bamChu: "Phát đợt thu" },
  { cho: "Quét để thanh toán", ms: 30000 },
];

export const MAN_SAU_TAP = [
  {
    step: "mo-dau",
    // Nothing pressed yet. The needle is the tagline, not the wordmark: "Rủ Đi"
    // is also the shell's header, so it would be found one screen too late.
    needle: "AI đi chơi, chia bill thông minh",
    kichBan: [{ cho: "AI đi chơi, chia bill thông minh" }],
  },
  { step: "chup-bill", needle: "Đưa bill vào khung hình", kichBan: DEN_CHUP_BILL },
  { step: "ket-qua", needle: "Đã nhận diện 3 món", kichBan: DEN_KET_QUA },
  { step: "goi-y", needle: "Gợi ý chia theo người", kichBan: DEN_GOI_Y },
  { step: "nhap", needle: "Khoản chi mới", kichBan: DEN_NHAP },
  { step: "de-xuat", needle: "Đúng rồi, ghi vào sổ", kichBan: DEN_DE_XUAT },
  // Not "Đợt thu": `ChiaSe` prints that too, so it would also read true one
  // screen too late. "Phát đợt thu" is the button only this screen carries.
  { step: "dot-thu", needle: "Phát đợt thu", kichBan: DEN_DOT_THU },
  {
    step: "ket-qua-thanh-toan",
    needle: "Quét để thanh toán",
    kichBan: DEN_KET_QUA_THANH_TOAN,
  },
  {
    step: "chia-se",
    needle: "Mỗi người một link riêng",
    kichBan: [
      ...DEN_KET_QUA_THANH_TOAN,
      { bamChu: "Chia sẻ kết quả" },
      { cho: "Mỗi người một link riêng" },
    ],
  },
];

/**
 * Screens the hero walk reaches that this file does NOT scan, each with the
 * reason it is excused.
 *
 * Empty, and that is the point of it existing. `tests/quet-man-sau-tap.test.mjs`
 * reads `STEPS` out of `screen-snapshots.mjs` and requires every name to be
 * scanned here or excused here, so a screen added to the walk later cannot
 * become unmeasured without somebody writing the sentence saying why.
 *
 * The five names that used to sit here -- `nhap`, `de-xuat`, `dot-thu`,
 * `ket-qua-thanh-toan`, `chia-se` -- were the back half of the hero path, and
 * the reason given for all five was one missing capability: the walk could not
 * type. `goChu` is that capability. A named exclusion is evidence of intent,
 * never of coverage, and five of them in a row was a queue, not a decision.
 */
export const CHUA_QUET = {};

/** Deliberately ugly: invisible text, unreadable text, a line long enough to
 *  trip the measured rules. Its only job is to come back dirty. */
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
 *  job is to come back clean, so a tool that finds faults everywhere is caught
 *  as loudly as one that finds them nowhere. */
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
 * The in-page driver.
 *
 * Serialized into the generated page with `.toString()`, so it closes over
 * nothing: every value it needs arrives as an argument. It records its own
 * progress on `window.__lai` so a failed walk can say which press it died on
 * rather than surfacing three screens later as a missing needle.
 */
export function laiTrongTrang(kichBan, dauLai) {
  window.__lai = { xong: false, loi: null, buoc: [] };
  const chu = () => (document.body ? document.body.innerText || "" : "");

  // Hold the page "busy" until the walk is done.
  //
  // This is what makes a self-driving page measurable at all. The detector
  // navigates with `waitUntil: "networkidle0"` and then settles ~700ms, so
  // without this it measures whatever is on screen a moment after load -- the
  // opening screen -- and labels it with the target screen's name. The third
  // canary caught exactly that: it drove the longest scenario, painted its
  // marker at the end, and the detector reported two findings and no marker.
  //
  // `networkidle0` means zero in-flight requests for 500ms, so one request that
  // never gets answered keeps the page from ever looking idle. The walk aborts
  // it on the way out -- success or failure -- and the connection closing is
  // what lets the detector proceed. The server deliberately never responds to
  // `/__giu`; see `serverGiuNhip`.
  const neo = new AbortController();
  fetch("/__giu?lai=1", { signal: neo.signal }).catch(() => {});

  function cho(text, ms) {
    return new Promise((res, rej) => {
      const t0 = Date.now();
      (function poll() {
        if (chu().includes(text)) return res();
        if (Date.now() - t0 > ms) return rej(new Error('het gio cho "' + text + '"'));
        setTimeout(poll, 40);
      })();
    });
  }

  /**
   * A press target is only usable once it is also ENABLED.
   *
   * `Xem kết quả` and `Chia tiền` both ship disabled until their screen is
   * satisfied, and clicking a disabled button is silent -- no error, no
   * navigation. Without this check the walk pressed too early, moved on, and
   * died on the NEXT `cho` with a timeout naming the wrong screen. Treating a
   * disabled button as "not there yet" turns that into an ordinary wait.
   */
  function bamDuoc(el) {
    if (!el) return null;
    if (el.disabled) return null;
    if (el.getAttribute && el.getAttribute("aria-disabled") === "true") return null;
    return el;
  }

  function choDom(tim, moTa, ms) {
    return new Promise((res, rej) => {
      const t0 = Date.now();
      (function poll() {
        if (tim()) return res();
        if (Date.now() - t0 > ms) return rej(new Error("khong thay " + moTa));
        setTimeout(poll, 40);
      })();
    });
  }

  /**
   * Type into a react-native-web `TextInput`.
   *
   * Assigning `el.value` is not enough and fails in the most misleading way
   * available: the box visibly fills, and React never hears about it. React
   * keeps its own record of the last value it wrote to the node and drops any
   * `input` event whose value already matches, so state stays empty, the
   * button stays disabled, and the screen looks typed-into. Going through the
   * prototype's setter writes past that tracker, which is why the event that
   * follows is believed.
   */
  function goChu(placeholder, giaTri, ms) {
    return new Promise((res, rej) => {
      const t0 = Date.now();
      (function poll() {
        const el = [...document.querySelectorAll("input, textarea")].find(
          (n) => (n.getAttribute("placeholder") || "") === placeholder,
        );
        if (el) {
          const dat = Object.getOwnPropertyDescriptor(
            Object.getPrototypeOf(el),
            "value",
          );
          el.focus();
          if (dat && dat.set) dat.set.call(el, giaTri);
          else el.value = giaTri;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          return res();
        }
        if (Date.now() - t0 > ms) return rej(new Error('khong thay o nhap "' + placeholder + '"'));
        setTimeout(poll, 40);
      })();
    });
  }

  function timBam(tim, moTa, ms) {
    return new Promise((res, rej) => {
      const t0 = Date.now();
      (function poll() {
        const el = tim();
        if (el) {
          // `inline: "nearest"`, and the document's horizontal scroll put back:
          // centring on a 445px-wide document at a 390px viewport scrolls the
          // page under the pointer and the click lands on the background.
          el.scrollIntoView({ block: "center", inline: "nearest" });
          if (document.scrollingElement) document.scrollingElement.scrollLeft = 0;
          el.click();
          return res();
        }
        if (Date.now() - t0 > ms) return rej(new Error("khong thay " + moTa));
        setTimeout(poll, 40);
      })();
    });
  }

  function nap(b64) {
    // The viewfinder's picker is a hidden <input type=file>. A page cannot open
    // the native chooser the way CDP can, but it can hand the input the same
    // bytes: rebuild the JPEG into a File and fire the change React listens for.
    return new Promise((res, rej) => {
      const t0 = Date.now();
      (function poll() {
        const el = [...document.querySelectorAll("input[type=file]")].pop();
        if (el) {
          const bin = atob(b64);
          const buf = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
          const dt = new DataTransfer();
          dt.items.add(new File([buf], "bill.jpg", { type: "image/jpeg" }));
          el.files = dt.files;
          el.dispatchEvent(new Event("change", { bubbles: true }));
          return res();
        }
        if (Date.now() - t0 > 20000) return rej(new Error("khong thay input[type=file]"));
        setTimeout(poll, 40);
      })();
    });
  }

  (async () => {
    for (const b of kichBan) {
      if (b.cho) await cho(b.cho, b.ms || 20000);
      if (b.bam) {
        await timBam(
          () => bamDuoc(document.querySelector('[aria-label="' + b.bam + '"]')),
          'nut "' + b.bam + '"',
          20000,
        );
      }
      if (b.bamChu) {
        await timBam(
          () =>
            bamDuoc(
              [...document.querySelectorAll("button, [role='button']")].find(
                (n) => n.textContent.replace(/\s+/g, " ").trim() === b.bamChu,
              ),
            ),
          'nut chu "' + b.bamChu + '" (bam duoc)',
          25000,
        );
      }
      if (b.themNguoi) {
        await timBam(
          () => bamDuoc(document.querySelector('[aria-label="Thêm ' + b.themNguoi + ' vào nhóm"]')),
          'nut moi "' + b.themNguoi + '"',
          20000,
        );
        // Not `innerText.includes(name)`: the name is already on screen in the
        // invite list before the press, so that reads true before the click
        // lands and would wave through a press that missed. Joining moves the
        // member out of the invite list and into the avatar row, so the honest
        // signal is the invite button going away AND the avatar arriving.
        await choDom(
          () =>
            document.querySelector('[aria-label="Thêm ' + b.themNguoi + ' vào nhóm"]') === null &&
            document.querySelector('[aria-label="' + b.themNguoi + '"]') !== null,
          '"' + b.themNguoi + '" vao nhom',
          20000,
        );
      }
      if (b.chonRadio) {
        await timBam(
          () =>
            bamDuoc(
              [...document.querySelectorAll('[role="radio"]')].find(
                (n) => n.textContent.replace(/\s+/g, " ").trim() === b.chonRadio,
              ),
            ),
          'radio "' + b.chonRadio + '"',
          20000,
        );
      }
      if (b.go) await goChu(b.go.oNhap, b.go.chu, 20000);
      if (b.anh) await nap(b.anh);
      window.__lai.buoc.push(JSON.stringify(b).slice(0, 60));
    }
    if (dauLai) {
      // The drive canary's whole point: this only exists once the walk above
      // has finished, so a detector that reports it waited.
      const d = document.createElement("div");
      d.setAttribute(
        "style",
        // z-index is 6 digits, not the int32 maximum. The repo guard's
        // long-number rule reads 10 consecutive digits as a possible account
        // number and is right to; nothing on these pages stacks above 6.
        "position:fixed;inset:0;z-index:999999;background:" + dauLai.nen +
          ";font-family:Arial",
      );
      d.innerHTML =
        '<p style="color:' + dauLai.chu + ";background:" + dauLai.nen +
        ';font-size:11px">' +
        dauLai.chu +
        " chu nay gan nhu vo hinh tren nen trang</p>";
      document.body.appendChild(d);
    }
    window.__lai.xong = true;
  })()
    .catch((e) => {
      window.__lai.loi = String(e && e.message ? e.message : e);
    })
    // Released last, and in `finally` on purpose: a walk that died still has to
    // let the page go idle, or the detector's `goto` sits there until it times
    // out and the real reason never reaches anybody.
    .finally(() => neo.abort());
}

/**
 * `index.html`, with the stub and the walk installed ahead of the bundle.
 *
 * Injected at the top of `<head>`, not appended to `<body>`. Expo emits the
 * bundle as a `<script src>` in `<head>`, and a stub installed after the bundle
 * has already called `fetch` patches nothing -- the screen renders its error
 * panel and the needle check fails. Order is the whole trick.
 */
function trangTuLai(indexHtml, kichBan, dauLai = null) {
  const tiem =
    `<script>(${installBeforeApp.toString()})(` +
    `${JSON.stringify(API_BASE)},${JSON.stringify(SCAN_FIXTURE)},${JSON.stringify(VIETQR_FIXTURE)});` +
    `(${laiTrongTrang.toString()})(${JSON.stringify(kichBan)},${JSON.stringify(dauLai)});<\/script>`;
  const i = indexHtml.indexOf("<head>");
  if (i === -1) throw new Error("index.html khong co <head> de chen stub");
  return indexHtml.slice(0, i + "<head>".length) + tiem + indexHtml.slice(i + "<head>".length);
}

/**
 * The static server, plus one route that is never answered.
 *
 * `/__giu` is the other half of the anchor the injected walk opens: the page
 * requests it and does not get a reply, so the page never reaches
 * `networkidle0` until the walk aborts the request itself. Answering it -- even
 * with a 404 -- would defeat the whole mechanism, so the handler returns
 * without touching `res` and that is deliberate rather than a missing branch.
 *
 * The held responses are tracked so shutdown can destroy them; an unanswered
 * request holds its socket open, and `server.close()` waits for open sockets.
 */
function serverGiuNhip(root) {
  const server = createStaticServer(root);
  const tinh = server.listeners("request").slice();
  server.removeAllListeners("request");
  const treo = new Set();
  server.on("request", (req, res) => {
    if ((req.url ?? "").startsWith("/__giu")) {
      treo.add(res);
      res.on("close", () => treo.delete(res));
      return;
    }
    for (const l of tinh) l(req, res);
  });
  server.__treo = treo;
  return server;
}

/**
 * Confirm the URL really serves HTML before anybody scans it. A 404 body is
 * short, plain, has no anti-patterns, and so scores zero and exits 0 -- the
 * same output as a flawless screen.
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
 * Run the detector on one URL.
 *
 * `spawn`, deliberately not `spawnSync`: the static server lives in THIS
 * process, and blocking the event loop means the detector's browser asks for
 * the page, nobody answers, and it gives up -- returning `[]` and exit 0, with
 * the real reason ("Navigation timeout") only on stderr. That is why an empty
 * read with anything on stderr is refused rather than reported as clean.
 */
function quet(url) {
  return new Promise((resolve, reject) => {
    const child = spawn(IMP, ["detect", "--json", "--viewport", VIEWPORT, url], {
      env: {
        ...process.env,
        // Preflight prints "url scanning: available" even when it is not, and a
        // detector that cannot launch Chrome returns [] and exits 0. Pinning the
        // binary is what lets the canaries fail.
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
 * Load the page in our own browser and confirm the walk landed.
 *
 * Separate from the detector's own navigation on purpose: this is what turns
 * "the scan returned a number" into "the scan returned a number about THIS
 * screen". Returns the rendered size too, because "the needle is present" and
 * "the screen actually drew" are different claims.
 */
async function kiemManHinh(browser, url, needle) {
  const page = await browser.newPage();
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  try {
    page.setDefaultTimeout(60000);
    await page.goto(url, { waitUntil: "networkidle0" });
    await page
      .waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), {
        timeout: 60000,
      })
      .catch(() => {});
    const r = await page.evaluate(
      (n) => ({
        co: (document.body.innerText || "").includes(n),
        chars: (document.body.innerText || "").replace(/\s+/g, " ").trim().length,
        els: document.querySelectorAll("*").length,
        lai: window.__lai ?? null,
      }),
      needle,
    );
    return { ...r, loi };
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

  const indexHtml = fs.readFileSync(indexPath, "utf8");
  const viet = [];
  const ghi = (ten, noiDung) => {
    const p = path.join(buildDir, ten);
    fs.writeFileSync(p, noiDung);
    viet.push(p);
    return ten;
  };

  const server = serverGiuNhip(buildDir);
  let browser = null;
  let bad = 0;
  try {
    const port = await listen(server);
    const goc = `http://127.0.0.1:${port}`;

    const tenXau = ghi("__canary-xau.html", CANARY_XAU);
    const tenSach = ghi("__canary-sach.html", CANARY_SACH);
    // The drive canary runs the LONGEST scenario here, so proving the detector
    // waited for it proves it waited for every shorter one too.
    const sauNhat = MAN_SAU_TAP.reduce((a, b) => (b.kichBan.length > a.kichBan.length ? b : a));
    const tenLai = ghi("__canary-lai.html", trangTuLai(indexHtml, sauNhat.kichBan, DAU_MAU));
    for (const { step, kichBan } of MAN_SAU_TAP) {
      ghi(`__quet-${step}.html`, trangTuLai(indexHtml, kichBan));
    }

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
        "MAY QUET MU: trang co tinh xau khong ra finding nao. Mot so 0 tren man that " +
          "luc nay khong chung minh gi. Thuong la thieu Chrome cho puppeteer -- " +
          "dat PUPPETEER_EXECUTABLE_PATH.",
      );
    }
    if (sach.findings.length !== 0) {
      throw new Error(
        `MAY QUET BAN OAN: trang sach ra ${sach.findings.length} finding. ` +
          "Ket qua duoi khong dang tin cho toi khi hieu vi sao.",
      );
    }

    // The third canary. Not a count -- a marker, because a page measured too
    // early still scores whatever the opening screen scores.
    const lai = await quet(`${goc}/${tenLai}`);
    const thayDau = lai.findings.some((f) => JSON.stringify(f).includes(DAU_MAU.chu));
    console.log(
      `  canary lai   findings=${lai.findings.length} exit=${lai.status}` +
        `  (can chua "${DAU_MAU.chu}": ${thayDau ? "CO" : "KHONG"})`,
    );
    for (const f of lai.findings) {
      console.log(`      [${f.severity}] ${f.antipattern}: ${(f.snippet ?? "").slice(0, 120)}`);
    }
    if (!thayDau) {
      // Say WHERE the walk stopped, not just that the marker is missing.
      //
      // Both causes print the same line otherwise, and they need opposite
      // fixes: a detector that measured too early is a timing problem in this
      // file, while a walk that died on press four is a broken screen. The
      // driver already records its own progress on `window.__lai` for exactly
      // this, so the diagnosis costs one page load.
      let chan = null;
      try {
        const tam = await puppeteer.launch({
          executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
          headless: true,
          defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
          args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        });
        try {
          chan = await kiemManHinh(tam, `${goc}/${tenLai}`, DAU_MAU.chu);
        } finally {
          await tam.close();
        }
      } catch (err) {
        chan = { loiChanDoan: String(err) };
      }
      throw new Error(
        `MAY QUET DO SOM: canary lai chay het kich ban "${sauNhat.step}" roi moi ve dau ` +
          `"${DAU_MAU.chu}", va detector khong thay dau do. Nghia la no do TRUOC khi trang ` +
          `lai xong, nen moi con so duoi day se la man mo dau doi ten thanh man khac. ` +
          `Khong bao cao so nao het.\n` +
          `  chan doan: lai.xong=${chan?.lai?.xong} lai.loi=${chan?.lai?.loi ?? "-"}\n` +
          `  buoc da qua (${chan?.lai?.buoc?.length ?? 0}): ${(chan?.lai?.buoc ?? []).join(" | ")}\n` +
          `  pageerror: ${(chan?.loi ?? []).slice(0, 2).join(" ; ") || "(khong co)"}`,
      );
    }

    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    console.log(`\n== ${MAN_SAU_TAP.length} man sau tap, tren trang that ==`);
    const bangKe = [];
    for (const { step, needle } of MAN_SAU_TAP) {
      const url = `${goc}/__quet-${step}.html`;

      const man = await kiemManHinh(browser, url, needle);
      if (!man.co) {
        throw new Error(
          `${step}: khong thay "${needle}" tren trang da render. Kich ban lai hong hoac ` +
            `man dang o trang thai loi, nen mot so 0 o day se la so 0 cua panel loi. ` +
            `(els=${man.els} chars=${man.chars} lai.loi=${man.lai?.loi ?? "-"} ` +
            `buoc=${man.lai?.buoc?.length ?? 0}` +
            `${man.loi.length ? ` pageerror=${man.loi[0].slice(0, 120)}` : ""})`,
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

    const chuaQuet = Object.keys(CHUA_QUET);
    console.log(`\n${chuaQuet.length} man CHUA quet lan nao: ${chuaQuet.join(", ")}`);

    const outDir = path.join(MOBILE_ROOT, ".tab-scan");
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(
      path.join(outDir, "ket-qua-sau-tap.json"),
      JSON.stringify(
        {
          viewport: VIEWPORT,
          canaryXau: xau.findings.length,
          canaryLaiThayDau: thayDau,
          man: bangKe,
          chuaQuet: CHUA_QUET,
        },
        null,
        2,
      ),
    );
    console.log(`\ntong findings tren cac man: ${bad}`);
    console.log(`chi tiet: ${path.join(outDir, "ket-qua-sau-tap.json")}`);
  } finally {
    if (browser) await browser.close();
    // Any `/__giu` still held open owns a socket, and `server.close()` waits on
    // open sockets, so shutdown would hang here rather than finish.
    for (const res of server.__treo) res.destroy();
    await closeServer(server);
    // Scan scaffolding, not build output. Leaving one behind would put a page
    // that stubs the API inside a directory somebody could serve.
    //
    // `QUET_GIU=1` keeps them, for one job only: measuring the geometry behind
    // a `text-occlusion` finding, which needs the same page the detector saw
    // rather than a second walk that might lay out differently. Opt-in, and
    // loud, because the thing it leaves behind serves fake data.
    // Not `return` -- this is a `finally`, and returning from one discards any
    // exception still travelling through it, so a failed run would exit 0 with
    // its reason deleted.
    const giu = process.env.QUET_GIU === "1";
    if (giu) {
      console.log(`\nQUET_GIU=1: giu lai ${viet.length} trang tam trong .expo-build-check/`);
      console.log("  CHUNG STUB API VA CHUA DU LIEU GIA -- xoa tay sau khi do xong.");
    }
    for (const p of giu ? [] : viet) {
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
