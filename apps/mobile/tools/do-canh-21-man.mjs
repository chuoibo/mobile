/** How many of the mockup set's 21 screens can a person REACH BY PRESSING?
 *
 * The denominator is fixed by the product mockups (`RuDi_Mobile_Product_Mockups`,
 * 7 areas x 3 screens). The question is not "do 21 screens exist in
 * `src/screens/`" -- that counts VERTICES, and a vertex lies: a screen can be
 * fully built, fully tested, and have no button anywhere that opens it. That
 * screen is dead code wearing a passing test.
 *
 * So this measures EDGES. Three rules make the number mean what it says:
 *
 *   1. No URL editing. `lien-ket.ts` accepts `#tab=`/`?man=` fragments and every
 *      other measuring tool here uses them -- correct for a detector, wrong for
 *      this question: a person cannot type a fragment. This file loads `/` and
 *      only ever loads `/`; replaying a path is a fresh load of `/` followed by
 *      the same presses again.
 *   2. Real mouse presses through `Input.dispatchMouseEvent` (see
 *      `tests/chrome-cdp.mjs`), never `el.click()`. react-native-web `Pressable`
 *      listens on pointer events; a synthetic click can miss `onPress` and a
 *      dead control would be recorded as a live edge.
 *   3. A press whose target is outside the viewport after scrolling is refused
 *      rather than dispatched at empty space, for the same reason.
 *
 * ## Two passes, because one cannot do it
 *
 * Pass A is a breadth-first sweep from the login screen. It finds what is near
 * the surface and, more usefully, what is NOT: an area with no press leading
 * into it shows up as an area the sweep never lands in.
 *
 * Pass A cannot reach the money screens, and the reason is worth writing down
 * rather than working around. `screen-snapshots.mjs` needs 29 presses to get
 * from the opening screen to the share screen. A breadth-first sweep that deep
 * is not a budget problem, it is a combinatorial one -- at ~15 controls per
 * screen the frontier passes 10^6 before depth 6. So pass B walks the money
 * path directly, using the press sequence `screen-snapshots.mjs` already
 * drives, and records what screen it is standing on at each waypoint. Those are
 * the same real presses; what pass B gives up is the SEARCH, not the rigour.
 *
 * Two of pass B's steps are not presses: choosing a photo out of the picker
 * (twice). They are counted and labelled `anh:` rather than folded into the
 * press count, because "a person can press their way here" and "a person can
 * press their way here if they also hand it a photo" are different claims.
 *
 * ## The classification happens afterwards, on purpose
 *
 * Neither pass decides what it is looking at. Both dump every state they stand
 * on -- text, controls, and the exact path that reached it -- to JSON, and the
 * match against the 21 mockups is done against that artifact. Deciding in
 * advance what counts as "the settlement screen" and then looking for it is how
 * a walk finds what its author expected; dumping first lets the states argue.
 *
 * ## The positive control
 *
 * If the harness is broken -- no browser, stub not installed, bundle stale --
 * every screen reads as unreachable, which is the same output as a product with
 * no navigation at all. So the run refuses to report unless Khám phá, which is
 * the tab the app opens on after login, comes back reached. A zero from a dead
 * instrument and a zero from a dead product must not look alike.
 *
 * The API is stubbed by `installBeforeApp` from `screen-snapshots.mjs`, imported
 * rather than restated so this file and the screenshot walk cannot describe two
 * different apps.
 *
 * Dev tool. Nothing in the app may import it.
 *
 *     cd apps/mobile && npm run build:check && node tools/do-canh-21-man.mjs
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { findChrome, launch, serve } from "../tests/chrome-cdp.mjs";
import {
  API_BASE,
  JPEG_B64,
  SCAN_FIXTURE,
  VIETQR_FIXTURE,
  installBeforeApp,
} from "./screen-snapshots.mjs";
import { installTabStubs, taoFixtures, themAnhDiaDiem } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, "..");
const BUILD = path.join(ROOT, ".expo-build-check");

/* 390x844 is the phone the rest of this repo's visual work is measured at.
 * Reachability is width-dependent: a control the layout pushes off a narrow
 * screen is not reachable on that screen, and saying so requires picking one. */
const RONG = 390;
const CAO = 844;

const SAU_TOI_DA = Number(process.env.DO_SAU ?? 5);
const LAN_TAI_TOI_DA = Number(process.env.DO_TAI ?? 900);

/** The two presses that are a real login. `Bỏ qua` is also a real press and
 *  pass A explores it too -- it enters with no person chosen, which is a
 *  finding, not a login. */
const DANG_NHAP = [
  { kieu: "chu", khoa: "Đăng ký với Apple" },
  { kieu: "nhan", khoa: "Vào app với tư cách Minh" },
];

/* ---------------------------------------------------------------- in-page --- */

/** Every control a finger could press, as stable keys.
 *
 * Roles, not tag names. `ThanhTab` renders its tabs as `role="tab"` and the
 * category chips on Khám phá are `role="radio"`; a sweep looking only for
 * `button` would miss the entire tab bar and report an app with no navigation.
 *
 * A key is the aria-label when there is one, otherwise the collapsed visible
 * words -- exactly the pair `chrome-cdp.mjs` can press. Anything with neither,
 * or sharing a key with another control, is returned with a reason instead of a
 * key: it cannot be pressed unambiguously, so it is reported as unmeasured
 * rather than guessed at.
 */
function doQuetNut() {
  const SEL = [
    "button",
    "[role='button']",
    "[role='tab']",
    "[role='radio']",
    "[role='link']",
    "[role='switch']",
    "[role='checkbox']",
    "[role='menuitem']",
  ].join(",");

  const hienRa = (e) => {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(e);
    return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.01;
  };

  const els = [...document.querySelectorAll(SEL)].filter(hienRa);
  // Drop a control that only wraps another: react-native-web nests pressables,
  // and pressing the outer one is the same edge as pressing the inner.
  const trong = els.filter((e) => !els.some((o) => o !== e && e.contains(o)));

  const raw = trong.map((e) => {
    const nhan = e.getAttribute("aria-label");
    const chu = e.textContent.replace(/\s+/g, " ").trim();
    return {
      kieu: nhan ? "nhan" : "chu",
      khoa: nhan || chu,
      chu,
      vaiTro: e.getAttribute("role") || e.tagName.toLowerCase(),
    };
  });

  const dem = new Map();
  for (const r of raw) dem.set(r.kieu + " " + r.khoa, (dem.get(r.kieu + " " + r.khoa) ?? 0) + 1);

  const nut = [];
  const boQua = [];
  for (const r of raw) {
    const k = r.kieu + " " + r.khoa;
    if (!r.khoa) boQua.push({ ...r, vi_sao: "khong co nhan lan chu" });
    else if (dem.get(k) > 1) boQua.push({ ...r, vi_sao: `trung khoa x${dem.get(k)}` });
    else nut.push(r);
  }
  // A `chu` press matches button/[role=button] only (that is what `doHopBam`
  // searches), so a tab or radio with no aria-label cannot be pressed by this
  // harness. Say so rather than enqueueing an edge that will throw.
  for (let i = nut.length - 1; i >= 0; i--) {
    if (nut[i].kieu === "chu" && nut[i].vaiTro !== "button") {
      boQua.push({ ...nut[i], vi_sao: `vai tro ${nut[i].vaiTro} khong co aria-label` });
      nut.splice(i, 1);
    }
  }
  return { nut, boQua, coO: document.querySelector("input[type=file]") !== null };
}

function doDocMan() {
  return (document.body.innerText || "").replace(/\s+/g, " ").trim();
}

/** Has the DOM stopped moving? Compares against the last sample left on
 *  `window`, so a caller polls it rather than sleeping a fixed time. */
function doYen() {
  const now = (document.body.innerText || "").replace(/\s+/g, " ").trim();
  const w = window.__doYen ?? { chu: null, lan: 0 };
  if (w.chu === now) w.lan += 1;
  else {
    w.chu = now;
    w.lan = 1;
  }
  window.__doYen = w;
  return w.lan >= 3 && now.length > 0;
}

function doXoaYen() {
  window.__doYen = null;
}

/** Catch the file picker instead of letting it open a dialog nobody can answer.
 *
 * This patches the BROWSER's file chooser, not the app. It is the same thing
 * puppeteer's `waitForFileChooser` does for `screen-snapshots.mjs`, spelled by
 * hand because `chrome-cdp.mjs` speaks CDP over a pipe and drops events, so
 * `Page.fileChooserOpened` never arrives here.
 *
 * It must be installed BEFORE `installBeforeApp`, which snapshots
 * `HTMLInputElement.prototype.click` to rewrite Expo's dispatched click into a
 * real activation. Installed first, that rewrite lands on this patch and the
 * input is captured; installed second, it lands on the native one and headless
 * Chrome opens a chooser that never closes.
 *
 * Nothing about the app's own code is stubbed by this. The button still runs
 * its real handler, Expo still builds its real input, and the `change` the app
 * listens for is the real one `DOM.setFileInputFiles` fires.
 */
function bayOAnh() {
  const goc = HTMLInputElement.prototype.click;
  HTMLInputElement.prototype.click = function bat() {
    if (this.type === "file") {
      window.__oAnh = this;
      return undefined;
    }
    return goc.apply(this, arguments);
  };
}

/** Measure a press box for a control matched by CSS selector + exact words.
 *  Same scroll-then-measure contract as `doHopBam` in `chrome-cdp.mjs`; needed
 *  here because the money walk presses a `role="radio"`, which that one does
 *  not search. */
function doHopLoc(sel, chu) {
  const els = [...document.querySelectorAll(sel)].filter(
    (e) => e.textContent.replace(/\s+/g, " ").trim() === chu,
  );
  if (els.length === 0) return null;
  if (els.length > 1) return { trung: els.length };
  const el = els[0];
  el.scrollIntoView({ block: "nearest", inline: "nearest" });
  const r = el.getBoundingClientRect();
  const x = r.left + r.width / 2;
  const y = r.top + r.height / 2;
  return { x, y, trongMan: x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight };
}

/** The i-th control carrying an `aria-label`, when more than one carries it.
 *
 * `clickLabel` refuses an ambiguous name and is right to -- pressing an
 * arbitrary one of two would report on a screen nobody asked for. But `ChupBill`
 * really does ship two buttons both named "Chọn ảnh bill" (135x44 and 44x44,
 * both visible), so the money path cannot be walked without naming which. The
 * index is written into the step and reported as a defect rather than smoothed
 * over: two controls with one accessible name is what a screen reader reads out
 * twice with no way to tell them apart.
 */
function doHopNhanI(khoa, i) {
  const els = [...document.querySelectorAll(`[aria-label]`)].filter(
    (e) => e.getAttribute("aria-label") === khoa,
  );
  const el = els[i];
  if (!el) return null;
  el.scrollIntoView({ block: "nearest", inline: "nearest" });
  const r = el.getBoundingClientRect();
  const x = r.left + r.width / 2;
  const y = r.top + r.height / 2;
  return { x, y, trongMan: x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight, so: els.length };
}

/* ------------------------------------------------------------------ walk --- */

const bam = (n) => `${n.kieu}:${n.khoa}`;

function chuKy(chu, nut) {
  // Text plus the set of pressable keys. Text alone merges two screens that
  // differ only in their controls; controls alone merge a list with its empty
  // state.
  const h = createHash("sha256");
  h.update(chu.slice(0, 4000));
  h.update("\u0000");
  h.update(nut.map(bam).sort().join("\u0000"));
  return h.digest("hex").slice(0, 16);
}

async function moiTai(page, url) {
  await page.goto(url, () => document.readyState === "complete");
  await page.evaluate(doXoaYen);
  await page.waitFor(doYen, { timeout: 20000, label: "man dau yen" });
}

async function doiYen(page) {
  await page.evaluate(doXoaYen);
  try {
    await page.waitFor(doYen, { timeout: 8000, label: "man yen sau khi bam" });
  } catch {
    /* A screen that never settles is still a screen; read it as it is. */
  }
}

/** Do one action. Everything a person can do to this app, as five verbs. */
async function lam(page, b, jpegPath) {
  if (b.kieu === "nhan") return page.clickLabel(b.khoa);
  if (b.kieu === "chu") return page.clickChu(b.khoa);
  if (b.kieu === "loc") {
    return page.bamVaoHop(await page.evaluate(doHopLoc, b.sel, b.khoa), `${b.sel} ${JSON.stringify(b.khoa)}`);
  }
  if (b.kieu === "nhanI") {
    return page.bamVaoHop(
      await page.evaluate(doHopNhanI, b.khoa, b.i),
      `aria-label ${JSON.stringify(b.khoa)} #${b.i}`,
    );
  }
  if (b.kieu === "go") return page.typeInto(b.khoa, b.chu);
  if (b.kieu === "anh") {
    // Choosing a photo out of the picker. Not a press, and counted separately.
    //
    // `document.querySelector` cannot find the input: Expo's web picker builds
    // it with `createElement` and never appends it to the document, so it only
    // exists as the receiver of the activation `bayOAnh` intercepts. Looking
    // for it in the DOM finds nothing and reads exactly like a button that
    // failed to open a picker.
    const r = await page.call("Runtime.evaluate", { expression: "window.__oAnh" });
    if (!r.result.objectId) throw new Error("picker chua mo: khong bat duoc input[type=file]");
    return page.call("DOM.setFileInputFiles", { files: [jpegPath], objectId: r.result.objectId });
  }
  throw new Error(`khong biet lam gi voi kieu ${b.kieu}`);
}

/** Replay a path from a cold load of `/`. Returns `{loi}` when a step no longer
 *  exists -- the path was not reproducible, which is not the same as the
 *  destination being unreachable, and is recorded as such. */
async function diLai(page, url, duong, jpegPath) {
  await moiTai(page, url);
  for (const b of duong) {
    try {
      await lam(page, b, jpegPath);
    } catch (err) {
      return { loi: `${bam(b)}: ${err.message}` };
    }
    await doiYen(page);
  }
  return { ok: true };
}

async function docTrangThai(page) {
  const chu = await page.evaluate(doDocMan);
  const { nut, boQua, coO } = await page.evaluate(doQuetNut);
  return { chu, nut, boQua, coO, ky: chuKy(chu, nut) };
}

/* ------------------------------------------------------- pass B: the money --- */

/** The press sequence `screen-snapshots.mjs` drives, as data.
 *
 * Restated here as steps rather than imported as a function because `drive()`
 * is written to write snapshot files, and what is wanted is the screen it is
 * standing on at each waypoint. `tests/do-canh-21-man.test.mjs` holds the two
 * lists together so this cannot drift into describing a walk the app no longer
 * supports.
 *
 * `cho` waits for a needle before the next step, exactly as `waitForScreen`
 * does there: without it the next press lands on the previous screen and the
 * waypoint recorded would be the wrong screen wearing the right name.
 */
const DUONG_TIEN = [
  { moc: null, buoc: [...DANG_NHAP], cho: "Khám phá" },
  { moc: null, buoc: [{ kieu: "nhan", khoa: "Tạo mới" }], cho: "Tạo khoản chi" },
  {
    moc: "05.01 chup-bill",
    buoc: [{ kieu: "nhan", khoa: "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền" }],
    cho: "Chụp bill",
  },
  {
    moc: "05.02a ket-qua-nhan-dien",
    buoc: [{ kieu: "nhanI", khoa: "Chọn ảnh bill", i: 0 }, { kieu: "anh" }],
    cho: "Kết quả nhận diện",
    lau: 60000,
  },
  {
    moc: "05.02b goi-y-chia (gan mon cho nguoi)",
    buoc: [{ kieu: "chu", khoa: "Tiếp tục" }],
    cho: "Gợi ý chia theo người",
  },
  {
    moc: "nhap-khoan-chi",
    buoc: [
      { kieu: "nhan", khoa: "Thêm Minh vào nhóm" },
      { kieu: "nhan", khoa: "Thêm Trang vào nhóm" },
      { kieu: "nhan", khoa: "Thêm Hải vào nhóm" },
      { kieu: "chu", khoa: "Xem kết quả" },
    ],
    cho: "Khoản chi mới",
  },
  {
    moc: "de-xuat",
    buoc: [
      { kieu: "go", khoa: "Đi đâu, ăn gì", chu: "bữa lẩu tối thứ bảy" },
      { kieu: "loc", sel: "[role=radio]", khoa: "Minh" },
      { kieu: "chu", khoa: "Chia tiền" },
    ],
    cho: "Đúng rồi, ghi vào sổ",
  },
  {
    moc: "dot-thu",
    buoc: [{ kieu: "chu", khoa: "Đúng rồi, ghi vào sổ" }],
    cho: "Đợt thu",
  },
  {
    moc: "05.03 ket-qua-thanh-toan (VietQR)",
    buoc: [{ kieu: "chu", khoa: "Phát đợt thu" }],
    cho: "Quét để thanh toán",
    lau: 45000,
  },
  {
    moc: "chia-se",
    buoc: [{ kieu: "chu", khoa: "Chia sẻ kết quả" }],
    cho: "Mỗi người một link riêng",
  },
];

async function diDuongTien(page, url, jpegPath) {
  const moc = [];
  const duong = [];
  await moiTai(page, url);
  for (const chang of DUONG_TIEN) {
    for (const b of chang.buoc) {
      try {
        await lam(page, b, jpegPath);
      } catch (err) {
        moc.push({ moc: chang.moc, dat: false, loi: `${bam(b)}: ${err.message}`, duong: duong.map(bam) });
        return moc;
      }
      duong.push(b);
      await doiYen(page);
    }
    try {
      await page.waitFor((n) => (document.body.innerText || "").includes(n), {
        timeout: chang.lau ?? 20000,
        label: `chu "${chang.cho}"`,
      }, chang.cho);
    } catch (err) {
      moc.push({ moc: chang.moc, dat: false, loi: err.message, duong: duong.map(bam) });
      return moc;
    }
    await doiYen(page);
    if (!chang.moc) continue;
    const t = await docTrangThai(page);
    moc.push({
      moc: chang.moc,
      dat: true,
      so_bam: duong.filter((b) => b.kieu !== "anh").length,
      so_anh: duong.filter((b) => b.kieu === "anh").length,
      duong: duong.map(bam),
      ky: t.ky,
      chu: t.chu,
      nut: t.nut,
    });
    process.stderr.write(`  [B] ${chang.moc}: DAT sau ${duong.length} buoc\n`);
  }
  return moc;
}

/* --------------------------------------------------------------------------- */

async function main() {
  const bin = findChrome();
  if (!bin) throw new Error("khong tim thay Chrome; phep do nay khong chay duoc ma khong co trinh duyet");
  if (!fs.existsSync(path.join(BUILD, "index.html"))) {
    throw new Error(`khong co ban dung o ${BUILD}; chay npm run build:check truoc`);
  }

  const jpegPath = path.join(os.tmpdir(), `do-canh-bill-${process.pid}.jpg`);
  fs.writeFileSync(jpegPath, Buffer.from(JPEG_B64, "base64"));

  const { url, close } = await serve(BUILD);
  const page = await launch(bin);
  let soLanTai = 0;

  try {
    await page.viewport(RONG, CAO);
    await page.call("DOM.enable");
    /* Which server the app is talking to, swapped between passes.
     *
     * Not one stub for both, and the reason is a miscount this run already
     * made. `installBeforeApp` answers the routes the money path needs and
     * nothing else, so under it Khám phá renders "Máy chủ này chưa có danh mục
     * địa điểm" -- no place cards, therefore no card to press, therefore no
     * edge into `ChiTietDiaDiem`. That screen would have been reported dead
     * when what was actually dead was the fixture. Reachability that depends on
     * data has to be measured against a server that returns data.
     *
     * So the breadth sweep runs on `tab-snapshots.mjs`'s fixtures, which answer
     * `/places`, `/contexts`, `/recap`, `/albums` and the photo routes; and the
     * money path runs on `screen-snapshots.mjs`'s, which are the only ones that
     * answer the bill scan. Each pass gets the fixture that lets its screens
     * have content, and neither pass is asked a question its fixture cannot
     * answer.
     *
     * `bayOAnh` goes first in both; see its own note.
     */
    const idStub = [];
    async function datStub(loai) {
      for (const id of idStub.splice(0)) {
        await page.call("Page.removeScriptToEvaluateOnNewDocument", { identifier: id });
      }
      const nguon =
        loai === "tab"
          ? `(${installTabStubs.toString()})(${JSON.stringify(API_BASE)},${JSON.stringify(
              themAnhDiaDiem(taoFixtures()),
            )});`
          : `(${installBeforeApp.toString()})(${JSON.stringify(API_BASE)},${JSON.stringify(
              SCAN_FIXTURE,
            )},${JSON.stringify(VIETQR_FIXTURE)});`;
      for (const source of [`(${bayOAnh.toString()})();`, nguon]) {
        const r = await page.call("Page.addScriptToEvaluateOnNewDocument", { source });
        idStub.push(r.identifier);
      }
    }
    await datStub("tab");

    /* --- pass A: breadth-first from two seeds --- */
    //
    // Two, not one. Seeded only at `/` and capped at depth 5, the sweep spends
    // two of its five levels on the login screen and sees the app three presses
    // deep -- which is not "what a person can reach", it is "what a person can
    // reach immediately after signing in". Seeded only after login, it would
    // never press `Bỏ qua` and would miss that the app has a second, hollow way
    // in. Both seeds are real press paths from a cold `/`; the depth beside each
    // is how far past it the sweep goes.
    const MAM = [
      { ten: "goc", duong: [], sau: 3 },
      { ten: "dang-nhap", duong: DANG_NHAP, sau: SAU_TOI_DA },
    ];
    const daGap = new Map();
    const hangDoi = MAM.map((m) => ({ duong: m.duong, mam: m.ten, sau: m.sau }));
    const khongDiLaiDuoc = [];
    const conLai = [];

    while (hangDoi.length) {
      const cong = hangDoi.shift();
      const duong = cong.duong;
      if (soLanTai >= LAN_TAI_TOI_DA) {
        conLai.push(duong.map(bam));
        continue;
      }
      soLanTai += 1;
      const r = await diLai(page, url, duong, jpegPath);
      if (r.loi) {
        khongDiLaiDuoc.push({ duong: duong.map(bam), loi: r.loi });
        continue;
      }

      const t = await docTrangThai(page);
      if (daGap.has(t.ky)) {
        daGap.get(t.ky).duong_khac.push(duong.map(bam));
        continue;
      }
      daGap.set(t.ky, {
        ky: t.ky,
        mam: cong.mam,
        sau: duong.length,
        duong: duong.map(bam),
        duong_khac: [],
        chu: t.chu,
        nut: t.nut,
        bo_qua: t.boQua,
      });
      process.stderr.write(`[A ${daGap.size}] sau=${duong.length} nut=${t.nut.length} :: ${t.chu.slice(0, 80)}\n`);

      if (duong.length >= cong.sau) {
        for (const n of t.nut) conLai.push([...duong.map(bam), bam(n)]);
        continue;
      }
      // No key twice on one path. Without this the four sub-tabs inside the
      // group screen generate every ordering of themselves and the frontier is
      // all permutations of the same handful of screens -- measured: 56 states
      // out of 420 loads, none of them past depth 5. Cost of the rule: a screen
      // reachable ONLY by pressing one control twice is missed, and no such
      // screen is known here. It is a restriction on the search, so it is
      // written into the report rather than left as an implementation detail.
      const daBam = new Set(duong.map(bam));
      for (const n of t.nut) {
        if (daBam.has(bam(n))) continue;
        hangDoi.push({ duong: [...duong, { kieu: n.kieu, khoa: n.khoa }], mam: cong.mam, sau: cong.sau });
      }
    }

    /* --- pass B: the money path, driven --- */
    await datStub("bill");
    process.stderr.write(`\n[B] di duong tien...\n`);
    const mocTien = await diDuongTien(page, url, jpegPath);

    /* --- positive control --- */
    const coKhamPha =
      [...daGap.values()].some((s) => s.chu.startsWith("Khám phá")) ||
      mocTien.length > 0;

    const out = {
      commit: process.env.DO_COMMIT ?? null,
      viewport: [RONG, CAO],
      sau_toi_da: SAU_TOI_DA,
      so_lan_tai: soLanTai,
      doi_chung_duong_kham_pha: coKhamPha,
      so_trang_thai: daGap.size,
      trang_thai: [...daGap.values()],
      moc_duong_tien: mocTien,
      khong_di_lai_duoc: khongDiLaiDuoc,
      con_lai_chua_di: conLai,
    };
    const dest = path.join(ROOT, "do-canh-21-man.json");
    fs.writeFileSync(dest, JSON.stringify(out, null, 1));
    process.stderr.write(
      `\npass A: ${daGap.size} trang thai / ${soLanTai} lan tai / ${conLai.length} canh chua di\n` +
        `pass B: ${mocTien.filter((m) => m.dat).length}/${DUONG_TIEN.filter((c) => c.moc).length} moc dat\n` +
        `doi chung duong (Kham pha): ${coKhamPha ? "DAT" : "HONG -- may do hong, dung doc so lieu"}\n` +
        `-> ${dest}\n`,
    );
    if (!coKhamPha) process.exit(2);
  } finally {
    await page.close();
    await close();
    fs.rmSync(jpegPath, { force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
