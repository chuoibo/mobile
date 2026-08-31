/** Does the DeXuat screen ever paint a 36-character id where a name goes?
 *
 * ## The question, and why it is asked on the glass
 *
 * A scan of the source (`frontend/co-may-sinh-mac-dinh-id`) found three places
 * still ending in a raw-id fallback, two of them on `DeXuat.tsx` -- the screen
 * where money is confirmed into the ledger:
 *
 *     advancerName = people.find(p => p.id === proposal.advancerId)?.name ?? proposal.advancerId
 *     gainerNames  = proposal.roundingGainers.map(id => people.find(...)?.name ?? id)
 *
 * That scan matched a SHAPE. A shape is not a symptom: a fallback whose
 * condition can never hold paints nothing, and the difference matters, because
 * "a UUID is reaching a user" and "a branch exists that would" are two
 * different reports to make to a leader. So this file does not read the source
 * at all. It drives the real bundle in real Chrome through the real presses,
 * lands on `DeXuat`, and reads `document.body.innerText` off the rendered page.
 *
 * ## Why there are two positive controls
 *
 * A zero with no positive control cannot be told apart from a broken scanner.
 * Both controls are run in the SAME browser, through the SAME reader, so a
 * zero in measurement A means "no id on the glass" rather than "the regex
 * never matches anything".
 *
 *   B. The server names somebody the bill does not know. A fetch shim sitting
 *      OUTSIDE the app rewrites `rounding_gainers` in the `POST /expenses`
 *      reply to an id absent from the roster -- the exact divergence the two
 *      lists have by construction, since one comes from the server and one
 *      from what the organiser typed. Nothing in the app is patched.
 *   C. The advancer is not in the roster. Reached by rendering the real
 *      component with those props through react-native-web's documented server
 *      path and opening the page in the same browser. This is the state the
 *      screen cannot be walked into today; C is what it would look like.
 *
 * D asks WHY A is zero: it removes the advancer from the roster on the
 * previous screen and reads whether the door to `DeXuat` is still open.
 *
 * ## What this does NOT prove
 *
 * That no OTHER screen prints an id (only `DeXuat` is walked). That the fallback
 * is unreachable in production -- D measures one door on one build, and a door
 * held by a single upstream check is a door that a later change can open. That
 * the real server never returns an id outside the participants it was sent;
 * that is a claim about `services/api`, not about this browser.
 *
 * Dev probe. Nothing in the app imports it, it writes only to the OS temp
 * directory, and it is not part of `npm test`.
 *
 *     cd apps/mobile && npm run build:check \
 *       && npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node tests/qa2-111127-hai-cho-de-xuat/probe-in-id-tren-man.mjs
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import {
  API_BASE,
  CHROME,
  JPEG_B64,
  SCAN_FIXTURE,
  TREN_BILL,
  VIETQR_FIXTURE,
  clickAria,
  clickButton,
  closeServer,
  createStaticServer,
  installBeforeApp,
  listen,
  pickMemberOnMatrix,
  visibleText,
  waitForPreview,
  waitForScreen,
} from "../../tools/screen-snapshots.mjs";

const MOBILE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const BUILD_DIR = path.join(MOBILE_ROOT, ".expo-build-check");
const OUT = fs.mkdtempSync(path.join(os.tmpdir(), "de-xuat-id-"));

/** Two ids no name in `nhom-demo.ts` can resolve. Version-4 shaped so they are
 *  indistinguishable from a real one to a reader, which is the whole point. */
const MA_LA_1 = "0f9c8b7a-1d2e-4f30-9a41-5b6c7d8e9f01";
const MA_LA_2 = "1a2b3c4d-5e6f-4071-8293-a4b5c6d7e8f9";

/* ------------------------------------------------------------------ đọc màn */

/** A v4-shaped id, the thing `?? id` actually leaks. */
const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
/** Anything 36 characters long with no space in it, whatever its alphabet.
 *  Wider than UUID_RE on purpose: the question asked was "is there a 36-char
 *  string on screen", and an id that stops being a UUID must not stop being
 *  found. */
const DAI_36_RE = /\S{36,}/g;

function quet(nhan, text) {
  const uuid = [...new Set(text.match(UUID_RE) ?? [])];
  const dai = [...new Set(text.match(DAI_36_RE) ?? [])];
  return { nhan, uuid, dai, soKyTu: text.length };
}

/** The second surface: a string a screen reader speaks but innerText never
 *  carries. Reported apart from the glass, never folded into it. */
async function quetAria(page) {
  const nhan = await page.evaluate(() =>
    [...document.querySelectorAll("[aria-label]")].map((n) => n.getAttribute("aria-label")),
  );
  return [...new Set(nhan.join("\n").match(UUID_RE) ?? [])];
}

function inKetQua(kq) {
  const ok = kq.uuid.length === 0 && kq.dai.length === 0;
  console.log(
    `  ${ok ? "SẠCH" : "CÓ ID"}  ${kq.nhan}: uuid=${kq.uuid.length} chuoi36=${kq.dai.length} ` +
      `(${kq.soKyTu} ký tự trên màn)`,
  );
  for (const m of kq.uuid) console.log(`         uuid: ${m}`);
  for (const m of kq.dai) if (!kq.uuid.includes(m)) console.log(`         36+ : ${m}`);
  return ok;
}

/* --------------------------------------------------------------- đi tới màn */

async function goVaoO(page, placeholder, value) {
  const sel = `input[placeholder="${placeholder}"]`;
  await page.waitForSelector(sel, { visible: true, timeout: 15000 });
  await page.click(sel, { clickCount: 3 });
  await page.type(sel, value, { delay: 15 });
}

/** The presses from the opening screen to `Khoản chi mới`, exactly the ones
 *  `tools/screen-snapshots.mjs` walks. Copied rather than imported because
 *  `drive` snapshots and continues past `de-xuat`; the walk itself is the same. */
async function diToiNhap(page, jpegPath) {
  await waitForScreen(page, "mo-dau", "AI đi chơi, chia bill thông minh");
  await page.evaluate(() => {
    const el = [...document.querySelectorAll("button, [role='button']")].find(
      (n) => (n.textContent || "").replace(/\s+/g, " ").trim() === "Đăng ký với Apple",
    );
    if (!el) throw new Error('khong thay nut "Đăng ký với Apple"');
    el.click();
  });
  await page.waitForFunction(
    () => document.body.innerText.includes("Vào app với tư cách ai?"),
    { timeout: 15000 },
  );
  await clickAria(page, "Vào app với tư cách Minh");
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
  for (const ten of TREN_BILL) await pickMemberOnMatrix(page, ten);
  await waitForPreview(page);

  await clickButton(page, "Xem kết quả");
  await waitForScreen(page, "nhap", "Khoản chi mới");
}

/** `Khoản chi mới` -> `DeXuat`, with the occasion typed and an advancer picked. */
async function nhapSangDeXuat(page) {
  await goVaoO(page, "bữa lẩu tối thứ bảy", "bữa lẩu tối thứ bảy");
  await page.waitForFunction(
    (who) =>
      [...document.querySelectorAll('[role="radio"]')].some((r) => r.textContent.trim() === who),
    {},
    TREN_BILL[0],
  );
  await page.evaluate((who) => {
    const r = [...document.querySelectorAll('[role="radio"]')].find(
      (n) => n.textContent.trim() === who,
    );
    if (!r) throw new Error(`no radio for "${who}"`);
    r.click();
  }, TREN_BILL[0]);
  await page.waitForFunction(() => {
    const b = [...document.querySelectorAll("button")].find(
      (n) => n.textContent.trim() === "Chia tiền",
    );
    return b && !b.disabled;
  });
  await clickButton(page, "Chia tiền");
  // Two needles, not one. "Đúng rồi, ghi vào sổ" also survives an empty
  // occasion, and the title is the only text proving this render used the
  // draft that was typed rather than a stale one.
  await waitForScreen(page, "de-xuat", "Đúng rồi, ghi vào sổ");
  await waitForScreen(page, "de-xuat", "Chia bữa lẩu tối thứ bảy");
}

/* ------------------------------------------------------------------ trình duyệt */

async function moTrinhDuyet() {
  return puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
}

/** The shim for control B. Registered AFTER `installBeforeApp`, so the fetch it
 *  wraps is the stub -- it is a lie told by the SERVER, with no app code
 *  touched. Returns the reply untouched when `maLa` is null. */
async function catNgangExpenses(page, maLa) {
  await page.evaluateOnNewDocument(
    (id, base) => {
      if (!id) return;
      const truoc = window.fetch;
      window.fetch = async function catNgang(input, init = {}) {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input?.url ?? "";
        const method = (init.method || input?.method || "GET").toUpperCase();
        const reply = await truoc.call(this, input, init);
        if (method !== "POST" || !url.startsWith(base) || url.slice(base.length).split("?")[0] !== "/expenses") {
          return reply;
        }
        const body = await reply.clone().json();
        if (body?.allocation) body.allocation.rounding_gainers = [id];
        window.__catNgang = (window.__catNgang ?? 0) + 1;
        return new Response(JSON.stringify(body), {
          status: reply.status,
          headers: { "Content-Type": "application/json" },
        });
      };
    },
    maLa,
    API_BASE,
  );
}

async function moTrang(browser, port, maLa) {
  const page = await browser.newPage();
  page.setDefaultTimeout(30000);
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  await page.evaluateOnNewDocument(installBeforeApp, API_BASE, SCAN_FIXTURE, VIETQR_FIXTURE);
  await catNgangExpenses(page, maLa);
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });
  return { page, loi };
}

/* ------------------------------------------------------------------- phép đo */

async function main() {
  if (!fs.existsSync(path.join(BUILD_DIR, "index.html"))) {
    throw new Error(`Chưa có bundle ở ${BUILD_DIR}. Chạy: cd apps/mobile && npm run build:check`);
  }
  if (!fs.existsSync(CHROME)) throw new Error(`Không thấy Chrome ở ${CHROME}`);
  console.log(`Chrome: ${CHROME}`);
  console.log(`Bundle: ${BUILD_DIR}\nHiện vật: ${OUT}\n`);

  const jpegPath = path.join(OUT, "bill.jpg");
  fs.writeFileSync(jpegPath, Buffer.from(JPEG_B64, "base64"));

  const server = createStaticServer(BUILD_DIR);
  const port = await listen(server);
  const browser = await moTrinhDuyet();
  const sai = [];

  try {
    /* A. Đường demo thật -------------------------------------------------- */
    console.log("A. ĐƯỜNG DEMO THẬT — đi bộ tới DeXuat, đọc chữ trên màn");
    {
      const { page, loi } = await moTrang(browser, port, null);
      await diToiNhap(page, jpegPath);
      await nhapSangDeXuat(page);
      const text = await visibleText(page);
      fs.writeFileSync(path.join(OUT, "A-de-xuat.txt"), text);
      await page.screenshot({ path: path.join(OUT, "A-de-xuat.png"), fullPage: true });
      const kq = quet("A · DeXuat, roster đủ", text);
      const sach = inKetQua(kq);
      const aria = await quetAria(page);
      console.log(`         aria-label mang uuid: ${aria.length}`);
      // Printed so the reader can see the branch was even on screen: a rounding
      // card that never rendered is not evidence that its fallback is quiet.
      console.log(`         thẻ "chia không hết chẵn" có mặt: ${text.includes("Chia không hết chẵn")}`);
      if (loi.length) console.log(`         lỗi trang: ${loi.join(" | ")}`);
      if (!sach) sai.push("A: có id trên màn ở đường demo");
      await page.close();
    }

    /* B. Đối chứng dương — máy chủ gọi tên người bill không biết ----------- */
    console.log("\nB. ĐỐI CHỨNG DƯƠNG 1 — máy chủ trả rounding_gainers là id lạ");
    {
      const { page, loi } = await moTrang(browser, port, MA_LA_1);
      await diToiNhap(page, jpegPath);
      await nhapSangDeXuat(page);
      const text = await visibleText(page);
      fs.writeFileSync(path.join(OUT, "B-de-xuat.txt"), text);
      await page.screenshot({ path: path.join(OUT, "B-de-xuat.png"), fullPage: true });
      const catNgang = await page.evaluate(() => window.__catNgang ?? 0);
      console.log(`         số lần cắt ngang /expenses: ${catNgang}`);
      const kq = quet("B · DeXuat, gainer lạ", text);
      inKetQua(kq);
      if (loi.length) console.log(`         lỗi trang: ${loi.join(" | ")}`);
      if (catNgang === 0) sai.push("B: shim không cắt được /expenses — đối chứng vô nghĩa");
      else if (!kq.uuid.includes(MA_LA_1)) {
        sai.push("B: id lạ KHÔNG hiện ra — hoặc nhánh chết, hoặc máy đọc hỏng");
      }
      await page.close();
    }

    /* D. Cánh cửa — vì sao A ra 0 ----------------------------------------- */
    console.log("\nD. CÁNH CỬA — bỏ người ứng tiền khỏi roster rồi thử bấm Chia tiền");
    {
      const { page } = await moTrang(browser, port, null);
      await diToiNhap(page, jpegPath);
      await goVaoO(page, "bữa lẩu tối thứ bảy", "bữa lẩu tối thứ bảy");
      await page.evaluate((who) => {
        const r = [...document.querySelectorAll('[role="radio"]')].find(
          (n) => n.textContent.trim() === who,
        );
        if (!r) throw new Error(`no radio for "${who}"`);
        r.click();
      }, TREN_BILL[0]);
      const truoc = await page.evaluate(() => {
        const b = [...document.querySelectorAll("button")].find(
          (n) => n.textContent.trim() === "Chia tiền",
        );
        return { co: !!b, disabled: b?.disabled ?? null };
      });
      console.log(`         sau khi chọn ${TREN_BILL[0]} làm người ứng tiền: Chia tiền disabled=${truoc.disabled}`);

      // "Bỏ" is per-row; press the one belonging to the advancer.
      const boDuoc = await page.evaluate((who) => {
        const nut = [...document.querySelectorAll("button, [role='button']")].filter(
          (n) => (n.getAttribute("aria-label") || n.textContent || "").trim() === "Bỏ",
        );
        // The rows render in roster order and the advancer is the first name
        // put on the bill, so its "Bỏ" is the first one.
        if (!nut.length) return false;
        nut[0].click();
        return true;
      }, TREN_BILL[0]);
      await new Promise((r) => setTimeout(r, 400));
      const sauKhiBo = await page.evaluate((who) => {
        const b = [...document.querySelectorAll("button")].find(
          (n) => n.textContent.trim() === "Chia tiền",
        );
        const radios = [...document.querySelectorAll('[role="radio"]')].map((r) => ({
          ten: r.textContent.trim(),
          chon: r.getAttribute("aria-checked"),
        }));
        return {
          disabled: b?.disabled ?? null,
          conTrongDs: (document.body.innerText || "").includes(who),
          radios,
        };
      }, TREN_BILL[0]);
      console.log(`         bấm được "Bỏ": ${boDuoc}`);
      console.log(`         sau khi bỏ ${TREN_BILL[0]}: Chia tiền disabled=${sauKhiBo.disabled}`);
      console.log(`         radio còn lại: ${JSON.stringify(sauKhiBo.radios)}`);
      fs.writeFileSync(path.join(OUT, "D-nhap.txt"), await visibleText(page));
      await page.screenshot({ path: path.join(OUT, "D-nhap.png"), fullPage: true });
      if (sauKhiBo.disabled !== true) {
        sai.push("D: bỏ người ứng tiền mà nút Chia tiền vẫn bấm được — cửa MỞ");
      }
      await page.close();
    }

    /* C. Đối chứng dương 2 — advancer ngoài roster ------------------------- */
    console.log("\nC. ĐỐI CHỨNG DƯƠNG 2 — dựng chính DeXuat với advancerId ngoài roster");
    {
      const props = {
        proposal: {
          participants: [
            { id: "8c1d0e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f", name: "Trang" },
            { id: "9d2e1f30-4b5c-4d6e-8f70-8b9c0d1e2f3a", name: "Hải" },
          ],
          allocations: {
            "8c1d0e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f": 100001,
            "9d2e1f30-4b5c-4d6e-8f70-8b9c0d1e2f3a": 100000,
          },
          roundingGainers: [MA_LA_2],
          totalVnd: 300001,
          advancerId: MA_LA_1,
          occasion: "bữa lẩu tối thứ bảy",
        },
      };
      const raFile = path.join(OUT, "index.html");
      const log = execFileSync(
        process.execPath,
        [
          path.join(MOBILE_ROOT, "tools", "man-ra-html.mjs"),
          path.join(MOBILE_ROOT, "dist-test", "screens", "DeXuat.js"),
          "DeXuat",
          raFile,
          JSON.stringify(props),
        ],
        { cwd: MOBILE_ROOT, encoding: "utf8" },
      );
      console.log(`         ${log.trim()}`);

      const server2 = createStaticServer(OUT);
      const port2 = await listen(server2);
      const page = await browser.newPage();
      try {
        await page.goto(`http://127.0.0.1:${port2}/index.html`, { waitUntil: "load" });
        const text = await visibleText(page);
        fs.writeFileSync(path.join(OUT, "C-de-xuat.txt"), text);
        await page.screenshot({ path: path.join(OUT, "C-de-xuat.png"), fullPage: true });
        const kq = quet("C · DeXuat, advancer ngoài roster", text);
        inKetQua(kq);
        if (!kq.uuid.includes(MA_LA_1)) sai.push("C: advancerId lạ không hiện — máy đọc hỏng");
        if (!kq.uuid.includes(MA_LA_2)) sai.push("C: gainer lạ không hiện — máy đọc hỏng");
      } finally {
        await page.close();
        await closeServer(server2);
      }
    }
  } finally {
    await browser.close();
    await closeServer(server);
  }

  console.log(`\nHiện vật (ngoài repo): ${OUT}`);
  if (sai.length) {
    console.log("\nKẾT LUẬN: phép đo KHÔNG đứng vững");
    for (const s of sai) console.log(`  - ${s}`);
    process.exit(1);
  }
  console.log("\nKẾT LUẬN: đối chứng dương ĐỎ đúng chỗ, đường demo SẠCH — xem bảng trên.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
