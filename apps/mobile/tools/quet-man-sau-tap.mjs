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
 * running. It drives the real bundle through a scenario and only then paints
 * `CANARY LAI DA CHAY` in near-invisible grey. A screen's number is refused
 * unless a finding comes back whose snippet contains that marker:
 *
 *   - marker present  -> the detector waited for a full walk before measuring,
 *                        so that step's number describes the screen it names.
 *   - marker missing  -> it measured early. That number would be the opening
 *                        screen wearing another screen's label, so the screen is
 *                        reported as CHUA KET LUAN DUOC and no number is printed
 *                        for it.
 *
 * Counting findings would not do: a page measured too early still scores
 * whatever `MoDau` scores, and `> 0` would pass while proving nothing. The
 * assertion has to name something that can only exist after the walk.
 *
 * ## It runs per screen, and the inference it replaced pointed the wrong way
 *
 * This canary used to run ONCE, on one pinned scenario, and the rest of the
 * table inherited the result: "the LONGEST scenario, so proving the detector
 * waited for it proves it waited for every shorter one too."
 *
 * The scenario pinned was `de-xuat`, at 23 steps. It is not the longest.
 * `dot-thu` is 25, `ket-qua-thanh-toan` 27, `chia-se` 29. So the inference ran
 * backwards over precisely the last three screens of the hero path -- where the
 * money is proposed, collected, turned into a VietQR and shared -- and their
 * `findings= 0` rows rested on nothing.
 *
 * The reason written down for pinning it was that those three "exceed the
 * 30000ms navigation budget of imp detect". Nothing measured that. Measured
 * now, all nine scenarios finish in 2.6-3.4s, `chia-se` the longest at 2.74s --
 * under a tenth of the budget they were excused against. A gate that states a
 * number it never took is guessing in the voice of a measurement.
 *
 * Step count is not time either: a 9-step scenario can hold one slow step. So
 * the inference is gone rather than re-tuned, and every screen now proves the
 * detector waited for ITS OWN walk. The cost is nine more scans, about 25s.
 *
 * What it still does NOT prove, stated plainly: the canary page and the scanned
 * page are two separate loads, so this is "the detector can wait out this walk",
 * not "the detector did wait during that other load". The marker has to sit on
 * a page nobody measures, or it would land in the real findings.
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

import puppeteer from "puppeteer-core";

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
import { laLoiThat, phanLoai } from "./che-chu.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

/** The phone is the primary target, so that is the viewport reported. Stated
 *  rather than defaulted: `line-length` and the viewport-edge rules answer
 *  differently per width, and an unstated width makes two runs incomparable. */
const VIEWPORT = process.env.QUET_VIEWPORT ?? "390x844";

/**
 * The same width, parsed once, for the browser this file drives itself.
 *
 * `VIEWPORT` used to reach only the detector subprocess while the browser below
 * was pinned to a literal 390x844. A run at any other width therefore measured
 * two widths at once: the detector rendered at the requested width and produced
 * findings, and `xetCheChu` then adjudicated those findings against a 390
 * layout. The JSON artifact recorded `viewport: <requested>` for the pair, so
 * the file claimed a width it had only half used.
 *
 * Measured before this was single-sourced, on the ten hero screens: a run at
 * 360x800 returned three `text-occlusion` findings on `ket-qua-thanh-toan`
 * (against two at 390) and every one of them was dismissed as a scroll illusion
 * by a browser looking at a different layout than the one they came from. The
 * verdicts may well have been right; they were not measurements.
 *
 * At the default the parse yields exactly the literal it replaced, so this is a
 * no-op for every run that does not set `QUET_VIEWPORT` -- the point is that
 * runs which DO set it now mean it.
 */
const [VP_W, VP_H] = (() => {
  const m = /^(\d+)x(\d+)$/.exec(VIEWPORT.trim());
  if (!m) throw new Error(`QUET_VIEWPORT "${VIEWPORT}" khong dung dang <rong>x<cao>, vi du 390x844`);
  return [Number(m[1]), Number(m[2])];
})();

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
  /* Đăng nhập, chứ không "Bỏ qua".
   *
   * Đường đi của bản demo mở đầu bằng "mở app -> đăng nhập", và kể từ
   * bug-053800 thì đó không còn là chi tiết trang trí: khoản chi phải ghi vào
   * một nhóm CÓ THẬT, nhóm mở dưới danh nghĩa người đang đăng nhập, nên vào
   * app mà chưa chọn người thì không có nhóm nào để ghi vào. Trước bản vá,
   * đường này vẫn "đi được" vì nó gửi một id nhóm chưa từng tồn tại -- máy chủ
   * trả 422 ở bước chốt, tức là nó chưa bao giờ đi được thật.
   *
   * Canary thứ ba bắt đúng chuyện này: kịch bản cũ dừng ở "Đưa bill vào khung
   * hình" vì màn chia tiền giờ nói "Chưa biết bạn là ai". Số đo bị từ chối
   * thay vì được in ra dưới tên một màn khác. */
const DEN_CHUP_BILL = [
  { cho: "AI đi chơi, chia bill thông minh" },
  /* Nút Apple, không phải nút Google, và lý do là chuyện đo được chứ không phải
   * sở thích: `bamChu` so BẰNG NHAU với `textContent`, còn `NutHang` vẽ chữ ký
   * hiệu Google bằng một `<Text>G</Text>` đứng trước nhãn -- nên textContent của
   * nó là "GĐăng ký với Google" và phép so bằng không bao giờ khớp. Ký hiệu
   * Apple vẽ bằng View nên không góp chữ nào. Hai nút mở cùng một danh sách
   * (`setDangChon(true)`), nên chọn nút khớp được là đủ.
   *
   * Và không phải "Chọn người để vào app": đó là nhãn của hộp thoại, không phải
   * của nút mở nó. */
  { bamChu: "Đăng ký với Apple" },
  { cho: "Vào app với tư cách ai?" },
  { bam: "Vào app với tư cách Minh" },
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
/** F26. Same viewfinder as `chup-bill`, then the screenshot picker rather
 *  than the paper-bill one. The needle is the merchant the stub returns --
 *  text only `KetQuaQuetAnh` prints, and only after the read has landed. */
const DEN_KET_QUA_QUET_ANH = [
  ...DEN_CHUP_BILL,
  { bam: "Ảnh chụp màn hình" },
  { anh: JPEG_B64 },
  { cho: "Quán Bún Chả Hương Liên", ms: 45000 },
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
  {
    step: "ket-qua-quet-anh",
    needle: "Quán Bún Chả Hương Liên",
    kichBan: DEN_KET_QUA_QUET_ANH,
  },
  { step: "ket-qua", needle: "Đã nhận diện 3 món", kichBan: DEN_KET_QUA },
  { step: "goi-y", needle: "Gợi ý chia theo người", kichBan: DEN_GOI_Y },
  { step: "nhap", needle: "Khoản chi mới", kichBan: DEN_NHAP },
  // The needle is the typed sentence, not the button, and that is the whole
  // point of it. `Chia tiền` turns out NOT to be gated on the description, so a
  // `goChu` that silently failed still walked here, still landed on `DeXuat`,
  // and still printed "Đúng rồi, ghi vào sổ" -- the screen was measured with an
  // empty occasion while the log said `needle OK`. Measured: breaking `goChu`
  // moved this screen from 279 rendered chars to 269 and changed no verdict
  // anywhere. `DeXuat` titles itself `Chia {occasion}`, so asking for the
  // occasion asks whether the typing was believed by React.
  { step: "de-xuat", needle: "Chia bữa lẩu tối thứ bảy", kichBan: DEN_DE_XUAT },
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

/** Deliberately buried: an opaque sibling painted over a heading that is fully
 *  in view. Its only job is to survive `che-chu.mjs` as a REAL occlusion.
 *
 *  The adjudicator added below removes `text-occlusion` findings it judges to
 *  be clip artifacts, and the failure mode of any such filter is that it
 *  answers "artifact" to everything -- which turns a buried heading green and
 *  reads exactly like a screen with nothing wrong. `canary xau` cannot catch
 *  that: it trips contrast and size rules, not this one. So the filter gets its
 *  own positive control, and the run refuses to report a table unless this page
 *  still comes back dirty after being adjudicated.
 *
 *  Same shape as `CHE_THAT` in `tests/che-chu.test.mjs`, on purpose: that file
 *  proves the adjudicator can say `that` at all, and this one proves it still
 *  says it here, through this scanner's own detector call and page load. */
const CANARY_CHE = `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>canary che</title><style>
body{background:#fff;color:#1a1a1a;font-family:system-ui,sans-serif;font-size:16px;
  line-height:1.6;margin:0;padding:24px}
h1{font-size:28px;line-height:1.3;margin:0 0 16px}
</style></head><body>
<div style="position:relative">
  <h1>Bua toi o Da Lat</h1>
  <div style="position:absolute;left:0;right:0;top:4px;height:40px;background:#123456"></div>
</div>
<p>Doan van ban nay co do tuong phan cao va co nhip do doc binh thuong.</p>
</body></html>`;

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
export function trangTuLai(indexHtml, kichBan, dauLai = null) {
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
export function serverGiuNhip(root) {
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
 * Split `text-occlusion` findings into real defects and clip artifacts.
 *
 * `quet-tab-url.mjs` has done this since it was written; this file did not, and
 * the two scanners therefore answered the same question two different ways --
 * with the cruder answer landing on the ten screens the demo actually walks
 * through. Measured on `ket-qua-thanh-toan`: the detector reports "Trang" 88%
 * covered and "160.000đ" 100% covered by the footer button, and both adjudicate
 * to `cuon-khuat` -- once scrolled to, 5/5 sampled points show the word itself
 * on top. They are rows below the fold of an inner ScrollView whose boxes still
 * intersect the pinned footer, which is the artifact `che-chu.mjs` exists for.
 *
 * That mattered in both directions. The hero table exited 2 for two words a
 * reader can read perfectly well, and a gate that is red for fake reasons is
 * one people stop reading -- so a genuine occlusion arriving on the money
 * screens would have looked like the same familiar noise.
 *
 * Only `text-occlusion` is routed through here. Every other antipattern is kept
 * verbatim: this adjudicates one rule's known artifact, it is not a filter on
 * findings in general.
 *
 * Returns both halves. The artifacts are printed and persisted rather than
 * dropped, because "we saw it and judged it" and "we never saw it" are
 * different claims and only one of them is true here.
 */
async function xetCheChu(browser, url, needle, findings) {
  const that = [];
  const aoAnh = [];
  const canXet = findings.filter((f) => f.antipattern === "text-occlusion");
  if (canXet.length === 0) return { that: [...findings], aoAnh };

  const page = await browser.newPage();
  try {
    page.setDefaultTimeout(30000);
    await page.goto(url, { waitUntil: "networkidle0" });
    if (needle) {
      await page
        .waitForFunction((n) => (document.body?.innerText ?? "").includes(n), { timeout: 20000 }, needle)
        .catch(() => {});
    }
    for (const f of findings) {
      if (f.antipattern !== "text-occlusion") {
        that.push(f);
        continue;
      }
      const kq = await phanLoai(page, f);
      if (laLoiThat(kq)) that.push(f);
      else aoAnh.push({ f, kq });
    }
  } finally {
    await page.close();
  }
  return { that, aoAnh };
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
  /** Số màn không kết luận được. Khai ở đây chứ không trong `try` vì mã thoát
   *  đọc nó sau `finally`. */
  let khongKetLuan = 0;
  try {
    const port = await listen(server);
    const goc = `http://127.0.0.1:${port}`;

    const tenXau = ghi("__canary-xau.html", CANARY_XAU);
    const tenSach = ghi("__canary-sach.html", CANARY_SACH);
    const tenChe = ghi("__canary-che.html", CANARY_CHE);
    /* Mỗi màn một canary lái, chứ không một canary cho cả bảng.
     *
     * Bản trước ghim canary vào đúng một kịch bản và suy ra phần còn lại: "chạy
     * cái DÀI NHẤT, nên đợi được nó là đợi được mọi cái ngắn hơn". Hai chỗ hỏng.
     *
     * Thứ nhất, kịch bản được ghim là `de-xuat` (23 bước) — KHÔNG phải dài nhất.
     * `dot-thu` 25, `ket-qua-thanh-toan` 27, `chia-se` 29. Nên phép suy luận
     * chạy ngược chiều với đúng ba màn cuối của đường đi hero: chỗ tiền được
     * chốt, thu, dựng thành VietQR và chia sẻ. Ba dòng `findings= 0` đó không có
     * gì đỡ.
     *
     * Thứ hai, lý do viết ra để bào chữa cho việc ghim — ba kịch bản kia "vượt
     * hạn điều hướng 30000ms của imp detect" — chưa từng được đo. Đo rồi: cả
     * chín kịch bản về đích trong 2.6-3.4 giây, `chia-se` dài nhất mất 2.74s.
     * Chưa cái nào tới một phần mười cái hạn ấy. Một cổng khai một con số nó
     * không đo là một cổng đang đoán bằng giọng của phép đo.
     *
     * Số bước cũng không phải thời gian: một kịch bản 9 bước có thể chứa một
     * bước chậm. Nên bản này bỏ hẳn phép suy luận thay vì sửa hằng số của nó —
     * mỗi màn tự chứng minh detector đã đợi hết đường đi CỦA CHÍNH NÓ. Giá là
     * chín lượt quét nữa, khoảng 25 giây.
     *
     * Cái nó vẫn KHÔNG chứng minh, nói thẳng ra ở đây: trang canary và trang
     * quét là hai lượt tải khác nhau, nên đây là "detector đợi được đường đi
     * này", không phải "detector đã đợi trong đúng lượt tải kia". Dấu phải nằm
     * trên trang không bị đo mới không lẫn vào findings thật. */
    for (const { step, kichBan } of MAN_SAU_TAP) {
      ghi(`__quet-${step}.html`, trangTuLai(indexHtml, kichBan));
      ghi(`__canary-lai-${step}.html`, trangTuLai(indexHtml, kichBan, DAU_MAU));
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

    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      headless: true,
      defaultViewport: { width: VP_W, height: VP_H, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    /* Đối chứng DƯƠNG cho bộ phân loại che chữ, chạy trước khi bảng dưới được
     * đọc. Hai canary ở trên không thay được nó: chúng bắt tương phản và cỡ
     * chữ, không đụng tới luật `text-occlusion`. Nếu bộ phân loại trả lời "ảo
     * ảnh" cho mọi thứ thì một tiêu đề bị chôn thật cũng thành xanh, và bảng
     * dưới trông y hệt một đường đi sạch. */
    const che = await quet(`${goc}/${tenChe}`);
    const cheXet = await xetCheChu(browser, `${goc}/${tenChe}`, null, che.findings);
    const cheThat = cheXet.that.filter((f) => f.antipattern === "text-occlusion");
    console.log(
      `  canary che   findings=${che.findings.length} exit=${che.status}, ` +
        `sau khi xet: ${cheThat.length} che that / ${cheXet.aoAnh.length} ao anh  (can che that > 0)`,
    );
    if (che.findings.filter((f) => f.antipattern === "text-occlusion").length === 0) {
      throw new Error(
        "MAY QUET KHONG THAY CHE CHU: trang co tinh chon chu khong ra finding text-occlusion nao. " +
          "Bo phan loai duoi khong the duoc tin, vi khong co gi chung minh luat nay con chay.",
      );
    }
    if (cheThat.length === 0) {
      throw new Error(
        "BO PHAN LOAI CHE CHU DA MU: mot tieu de bi de len that su bi xet thanh ao anh. " +
          "Moi so 0 ve text-occlusion o bang duoi la vo nghia cho toi khi hieu vi sao.",
      );
    }

    console.log(`\n== ${MAN_SAU_TAP.length} man sau tap, tren trang that ==`);
    const bangKe = [];
    const chuaKetLuan = [];
    for (const { step, needle } of MAN_SAU_TAP) {
      const url = `${goc}/__quet-${step}.html`;

      /* Canary lái CỦA MÀN NÀY, chạy trước khi con số của màn này được đọc.
       *
       * Không đếm findings mà tìm dấu: một trang bị đo sớm vẫn ra đúng số điểm
       * của màn mở đầu, nên `> 0` sẽ xanh mà chẳng chứng minh gì. Dấu là thứ
       * chỉ tồn tại sau khi kịch bản chạy hết. */
      const lai = await quet(`${goc}/__canary-lai-${step}.html`);
      const thayDau = lai.findings.some((f) => JSON.stringify(f).includes(DAU_MAU.chu));
      if (!thayDau) {
        /* Trạng thái thứ ba. Không phải ĐẠT, cũng không phải HỎNG.
         *
         * Cái sai ở đây không phải "màn này bẩn" mà "không biết con số này nói
         * về màn nào". In `findings= 0` cho nó là nhập "không biết" vào "sạch",
         * đúng cái nhập mà cả đội đang gỡ khỏi từng cổng một. Nên màn này không
         * có số, không được cộng vào tổng, và cả lượt chạy thoát mã 4.
         *
         * Nói WHERE đường đi dừng, không chỉ nói dấu vắng mặt: detector đo sớm
         * là lỗi thời gian trong file này, còn kịch bản chết ở bước bốn là màn
         * hỏng, và hai thứ đó cần hai bản sửa ngược nhau. Driver đã tự ghi tiến
         * độ lên `window.__lai` sẵn cho việc này. */
        let chan = null;
        try {
          chan = await kiemManHinh(browser, `${goc}/__canary-lai-${step}.html`, DAU_MAU.chu);
        } catch (err) {
          chan = { loiChanDoan: String(err) };
        }
        const buoc = chan?.lai?.buoc ?? [];
        chuaKetLuan.push({
          step,
          laiXong: chan?.lai?.xong ?? null,
          laiLoi: chan?.lai?.loi ?? null,
          soBuocDaQua: buoc.length,
          buoc,
          pageerror: (chan?.loi ?? []).slice(0, 2),
          loiChanDoan: chan?.loiChanDoan ?? null,
        });
        console.log(
          `  ${step.padEnd(10)} CHUA KET LUAN DUOC  (canary lai khong thay dau "${DAU_MAU.chu}")`,
        );
        console.log(
          `      detector do TRUOC khi trang lai xong, nen mot con so o day se la man ` +
            `mo dau doi ten thanh "${step}". Khong bao cao so nao cho man nay.`,
        );
        console.log(
          `      chan doan: lai.xong=${chan?.lai?.xong} lai.loi=${chan?.lai?.loi ?? "-"} ` +
            `buoc da qua (${buoc.length}): ${buoc.join(" | ") || "(khong co)"}`,
        );
        if ((chan?.loi ?? []).length) {
          console.log(`      pageerror: ${chan.loi.slice(0, 2).join(" ; ")}`);
        }
        continue;
      }

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
      const { that, aoAnh } = await xetCheChu(browser, url, needle, findings);
      bad += that.length;
      bangKe.push({
        step,
        findings: that,
        // Kept, not dropped: an artifact we looked at and judged is a different
        // thing from one we never saw, and only the first is true here.
        aoAnh: aoAnh.map(({ f, kq }) => ({ snippet: f.snippet, verdict: kq.verdict, ly: kq.ly })),
        status,
        chars: man.chars,
        els: man.els,
      });
      console.log(
        `  ${step.padEnd(10)} findings=${String(that.length).padStart(2)} exit=${status}` +
          `  (da render: els=${man.els} chars=${man.chars}, needle OK, canary lai OK` +
          `${aoAnh.length ? `, ${aoAnh.length} che-chu ao anh` : ""})`,
      );
      for (const f of that) {
        console.log(`      [${f.severity}] ${f.antipattern}: ${(f.snippet ?? "").slice(0, 150)}`);
      }
      for (const { f, kq } of aoAnh) {
        console.log(`      [bo qua: ${kq.verdict}] ${f.antipattern}: ${(f.snippet ?? "").slice(0, 110)}`);
        console.log(`          ${kq.ly}`);
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
          // The adjudicator's own positive control: how many text-occlusion
          // findings a deliberately-buried heading still had AFTER being
          // judged. A 0 here would mean every 0 below is unfalsifiable.
          canaryChe: cheThat.length,
          // Per screen now, not one flag for the table. `chuaKetLuan` non-empty
          // is what makes the run inconclusive; `man` only ever holds screens
          // whose own drive canary came back with the marker.
          canaryLaiTungMan: Object.fromEntries(bangKe.map((m) => [m.step, true])),
          chuaKetLuan,
          man: bangKe,
          chuaQuet: CHUA_QUET,
        },
        null,
        2,
      ),
    );
    console.log(`\ntong findings tren cac man: ${bad}`);
    if (chuaKetLuan.length > 0) {
      console.log(
        `\n${chuaKetLuan.length}/${MAN_SAU_TAP.length} man CHUA KET LUAN DUOC: ` +
          `${chuaKetLuan.map((m) => m.step).join(", ")}`,
      );
      console.log(
        "DAY KHONG PHAI DAT. Khong man nao HONG, nhung cung khong biet con so cua " +
          "nhung man tren noi ve man nao. Tong o tren chi tinh cac man da ket luan duoc.",
      );
    }
    console.log(`chi tiet: ${path.join(outDir, "ket-qua-sau-tap.json")}`);
    khongKetLuan = chuaKetLuan.length;
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
  /* Ba trạng thái, không phải hai.
   *
   *   0  đạt        — mọi màn có canary lái của chính nó, và sạch.
   *   2  hỏng       — có finding thật trên một màn đã kết luận được.
   *   4  chưa kết luận được — không màn nào hỏng, nhưng ít nhất một màn bị đo
   *                   trước khi đường đi của nó chạy xong, nên số của nó nói về
   *                   màn khác. Đây KHÔNG phải đạt.
   *
   * Hỏng xếp trên chưa-kết-luận: một finding thật đã đủ để dừng, còn phần không
   * biết thì đọc trong log. */
  process.exitCode = bad > 0 ? 2 : khongKetLuan > 0 ? 4 : 0;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
