/** Bản vá #468 có đóng được nhánh SỐNG mà lượt trước đo được không?
 *
 * ## Nhánh sống đó là gì
 *
 * Lượt trước (qa2-111127) đo trên MÀN, không đọc nguồn: đi bộ bản expo export
 * thật qua đúng các cú bấm của đường demo tới `DeXuat`, rồi để MÁY CHỦ trả về
 * `rounding_gainers` là một id không có trong roster. UUID hiện nguyên trên câu
 * "Chia không hết chẵn ... chịu thêm 1đ lẻ". Đó là phép tái lập duy nhất chứng
 * minh `?? id` ở `DeXuat.tsx` là nhánh SỐNG chứ không phải hình dạng chết.
 *
 * File này chạy LẠI đúng kịch bản đó trên nhánh `frontend/co-may-sinh-mac-dinh-id`
 * (#468) và trả lời ba câu Lead hỏi. Nó là MỘT file chạy được trên CẢ HAI nền:
 *
 *     nền cũ (06ae2d7 / main)  -> phải ĐỎ  (mã thoát 1)
 *     nền vá (#468)            -> phải XANH (mã thoát 0)
 *
 * Một phép đo chỉ chạy trên nền đã vá thì không phân biệt được với một phép đo
 * hỏng. Đó là lý do cùng một file, hai cây, hai mã thoát.
 *
 * ## Sáu phép đo, và cái nào canh cái nào
 *
 *   A  · đường demo thật, không bơm gì. Nền nào cũng phải sạch.
 *   Đ  · ĐỐI CHỨNG DƯƠNG CHO MÁY ĐỌC. Gõ chính một UUID vào ô "dịp" ở màn
 *        trước, rồi đọc `DeXuat`. Không vá gì trong app — người dùng gõ. Nếu
 *        máy đọc không thấy UUID ở đây thì số 0 của B và C không có nghĩa.
 *   B  · KỊCH BẢN CŨ. Shim `fetch` NGOÀI app viết lại `rounding_gainers` trong
 *        câu trả lời `POST /expenses` thành một id lạ. Không chạm code sản phẩm.
 *   C1 · dựng thẳng `DeXuat` với advancerId VÀ gainer nằm ngoài cả roster lẫn
 *        nhóm, `nhom: []`. Trạng thái mà đường demo hôm nay không đi vào được.
 *   C2 · cùng thế, nhưng NHÓM biết người ứng tiền. Đây là cọc chống "bôi Thành
 *        viên lên mọi thứ": bản vá phải ra TÊN THẬT, không phải một chữ chung.
 *   D  · CÁNH CỬA (câu 2). Bỏ người ứng tiền khỏi roster ở màn trước rồi đọc
 *        nút "Chia tiền". Đo xem #468 có đụng vào cái cửa giữ-bằng-một-phép-kiểm
 *        không, hay nó chỉ thêm lớp ở chỗ hiển thị.
 *   E  · ĐỐI CHỨNG ÂM (câu 3). Máy chủ chia tiền cho một người NGOÀI bill —
 *        Σ giữ nguyên, chỉ dời tiền. Đo xem người đó có mặt trên màn không.
 *
 * ## Cái này KHÔNG chứng minh
 *
 * Rằng máy chủ THẬT có bao giờ trả id ngoài roster không: ở đây `POST /expenses`
 * do stub của `tools/screen-snapshots.mjs` trả lời, và shim nói dối thay máy chủ.
 * Câu đó là của `tests/e2e/gainer-thuoc-bill.probe.mjs` (cũng ở #468), cần một
 * máy chủ thật. Cái file này trả lời đúng một câu: NẾU một id lạ tới client thì
 * MÀN có in nó ra không.
 *
 * Cũng không chứng minh màn khác không in id, và không chứng minh `nhom` mà
 * `App.tsx` truyền vào luôn đầy đủ.
 *
 * Probe dev. Không file nào trong app import nó, nó chỉ ghi vào thư mục tạm của
 * hệ điều hành, và nó không nằm trong `npm test`.
 *
 *     cd apps/mobile && npm run build:check \
 *       && npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node tests/qa2-113404-ban-va-468/probe-sau-468.mjs
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
const OUT = fs.mkdtempSync(path.join(os.tmpdir(), "sau-468-"));

/** Nhãn nền, chỉ để in ra cho người đọc. Không phép đo nào rẽ nhánh theo nó. */
const NEN = process.env.QA_NEN ?? "(không đặt tên)";

/** Ba id không danh sách nào trong `nhom-demo.ts` gọi tên được. Hình dạng v4 để
 *  người đọc không phân biệt được với id thật — đó chính là điểm của phép đo. */
const MA_LA_1 = "0f9c8b7a-1d2e-4f30-9a41-5b6c7d8e9f01";
const MA_LA_2 = "1a2b3c4d-5e6f-4071-8293-a4b5c6d7e8f9";
const MA_LA_3 = "2b3c4d5e-6f70-4182-93a4-b5c6d7e8f90a";

/** Chữ `labelInGroup` dùng khi không danh sách nào gọi tên được. Viết thẳng ra
 *  chứ không import từ `src/`: đang đo cái MÀN in ra, không đo hằng số. */
const TEN_CHUA_BIET = "Thành viên";

/* ------------------------------------------------------------------ đọc màn */

const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
/** Bất cứ chuỗi 36 ký tự không dấu cách nào, bảng chữ nào cũng tính. Rộng hơn
 *  UUID_RE có chủ ý: câu hỏi là "trên màn có chuỗi 36 ký tự không", và một id
 *  thôi không còn là UUID thì không được thôi bị bắt. */
const DAI_36_RE = /\S{36,}/g;

function quet(nhan, text) {
  const uuid = [...new Set(text.match(UUID_RE) ?? [])];
  const dai = [...new Set(text.match(DAI_36_RE) ?? [])];
  return { nhan, uuid, dai, soKyTu: text.length };
}

function inKetQua(kq) {
  const sach = kq.uuid.length === 0 && kq.dai.length === 0;
  console.log(
    `  ${sach ? "SẠCH" : "CÓ ID"}  ${kq.nhan}: uuid=${kq.uuid.length} chuoi36=${kq.dai.length} ` +
      `(${kq.soKyTu} ký tự trên màn)`,
  );
  for (const m of kq.uuid) console.log(`         uuid: ${m}`);
  for (const m of kq.dai) if (!kq.uuid.includes(m)) console.log(`         36+ : ${m}`);
  return sach;
}

/** "N người sẽ cần gửi tiền cho X" — con số màn tự khai, không phải con số tôi tính. */
function soNguoiGui(text) {
  const m = text.match(/(\d+)\s+người sẽ cần gửi tiền/);
  return m ? Number(m[1]) : null;
}

/* --------------------------------------------------------------- đi tới màn */

async function goVaoO(page, placeholder, value) {
  const sel = `input[placeholder="${placeholder}"]`;
  await page.waitForSelector(sel, { visible: true, timeout: 15000 });
  await page.click(sel, { clickCount: 3 });
  await page.type(sel, value, { delay: 10 });
}

/** Các cú bấm từ màn mở đầu tới `Khoản chi mới`, đúng những cú
 *  `tools/screen-snapshots.mjs` đi. Chép lại chứ không import vì `drive` chụp
 *  ảnh rồi đi tiếp qua `de-xuat`; đường đi thì y hệt. */
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

/** `Khoản chi mới` -> `DeXuat`, dịp do người gọi chọn, người ứng tiền là
 *  `TREN_BILL[0]`. Hai cái kim chứ không một: "Đúng rồi, ghi vào sổ" sống sót cả
 *  khi dịp rỗng, và tiêu đề là chữ duy nhất chứng minh lần render này dùng đúng
 *  bản nháp vừa gõ. */
async function nhapSangDeXuat(page, dip = "bữa lẩu tối thứ bảy") {
  await goVaoO(page, "bữa lẩu tối thứ bảy", dip);
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
  await waitForScreen(page, "de-xuat", "Đúng rồi, ghi vào sổ");
  await waitForScreen(page, "de-xuat", `Chia ${dip}`);
}

/* ------------------------------------------------------------- trình duyệt */

async function moTrinhDuyet() {
  return puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
}

/** Shim cho B và E. Đăng ký SAU `installBeforeApp` nên cái `fetch` nó bọc chính
 *  là stub — lời nói dối do MÁY CHỦ nói, không dòng code sản phẩm nào bị chạm.
 *
 *  `kieu`:
 *    "gainer" — viết lại `rounding_gainers` thành `[maLa]` (kịch bản cũ).
 *    "chia"   — dời TOÀN BỘ phần của một người trên bill (không phải người ứng
 *               tiền) sang `maLa`. Σ phân bổ giữ nguyên đúng bằng tổng, nên đây
 *               là một câu trả lời HỢP LỆ theo hợp đồng tiền, không phải rác.
 *    null     — trả nguyên văn.
 */
async function catNgangExpenses(page, kieu, maLa) {
  await page.evaluateOnNewDocument(
    (kieu, maLa, base) => {
      if (!kieu) return;
      const truoc = window.fetch;
      window.fetch = async function catNgang(input, init = {}) {
        const url =
          typeof input === "string" ? input : input instanceof URL ? input.href : input?.url ?? "";
        const method = (init.method || input?.method || "GET").toUpperCase();
        const reply = await truoc.call(this, input, init);
        if (
          method !== "POST" ||
          !url.startsWith(base) ||
          url.slice(base.length).split("?")[0] !== "/expenses"
        ) {
          return reply;
        }
        const body = await reply.clone().json();
        const alloc = body?.allocation;
        if (alloc) {
          if (kieu === "gainer") {
            alloc.rounding_gainers = [maLa];
          } else if (kieu === "chia") {
            const payer = body?.proposal?.paid_by_id;
            const nanNhan = Object.keys(alloc.allocations).find((id) => id !== payer);
            if (nanNhan) {
              alloc.allocations[maLa] = alloc.allocations[nanNhan];
              alloc.allocations[nanNhan] = 0;
              window.__doiCho = { tu: nanNhan, sang: maLa, tien: alloc.allocations[maLa] };
            }
          }
        }
        window.__catNgang = (window.__catNgang ?? 0) + 1;
        return new Response(JSON.stringify(body), {
          status: reply.status,
          headers: { "Content-Type": "application/json" },
        });
      };
    },
    kieu,
    maLa,
    API_BASE,
  );
}

async function moTrang(browser, port, kieu = null, maLa = null) {
  const page = await browser.newPage();
  page.setDefaultTimeout(30000);
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  await page.evaluateOnNewDocument(installBeforeApp, API_BASE, SCAN_FIXTURE, VIETQR_FIXTURE);
  await catNgangExpenses(page, kieu, maLa);
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });
  return { page, loi };
}

/** Dựng thẳng một màn `DeXuat` với props tự chọn, mở trong CÙNG trình duyệt,
 *  đọc bằng CÙNG máy đọc. Trạng thái đường demo không đi vào được. */
async function dungThang(browser, nhan, props, tenFile) {
  const raFile = path.join(OUT, tenFile);
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
  const server = createStaticServer(OUT);
  const port = await listen(server);
  const page = await browser.newPage();
  try {
    await page.goto(`http://127.0.0.1:${port}/${tenFile}`, { waitUntil: "load" });
    const text = await visibleText(page);
    fs.writeFileSync(path.join(OUT, `${tenFile}.txt`), text);
    await page.screenshot({ path: path.join(OUT, `${tenFile}.png`), fullPage: true });
    return { text, kq: quet(nhan, text) };
  } finally {
    await page.close();
    await closeServer(server);
  }
}

function propsDeXuat({ advancerId, roundingGainers, nhom }) {
  return {
    proposal: {
      participants: [
        { id: "8c1d0e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f", name: "Trang" },
        { id: "9d2e1f30-4b5c-4d6e-8f70-8b9c0d1e2f3a", name: "Hải" },
      ],
      allocations: {
        "8c1d0e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f": 100001,
        "9d2e1f30-4b5c-4d6e-8f70-8b9c0d1e2f3a": 100000,
      },
      roundingGainers,
      totalVnd: 300001,
      advancerId,
      occasion: "bữa lẩu tối thứ bảy",
    },
    nhom,
  };
}

/* ------------------------------------------------------------------- phép đo */

async function main() {
  if (!fs.existsSync(path.join(BUILD_DIR, "index.html"))) {
    throw new Error(`Chưa có bundle ở ${BUILD_DIR}. Chạy: cd apps/mobile && npm run build:check`);
  }
  if (!fs.existsSync(CHROME)) throw new Error(`Không thấy Chrome ở ${CHROME}`);
  console.log(`Nền:    ${NEN}`);
  console.log(`Chrome: ${CHROME}`);
  console.log(`Bundle: ${BUILD_DIR}\nHiện vật: ${OUT}\n`);

  const jpegPath = path.join(OUT, "bill.jpg");
  fs.writeFileSync(jpegPath, Buffer.from(JPEG_B64, "base64"));

  const server = createStaticServer(BUILD_DIR);
  const port = await listen(server);
  const browser = await moTrinhDuyet();

  /** Vi phạm HỢP ĐỒNG SAU VÁ: nền cũ đỏ ở đây, nền vá phải trống. */
  const sai = [];
  /** Phép đo tự khai là mù. Nền nào cũng phải trống, nếu không thì mọi số 0 vô nghĩa. */
  const mu = [];

  try {
    /* A ------------------------------------------------------------------ */
    console.log("A. ĐƯỜNG DEMO THẬT — không bơm gì");
    let soNguoiA = null;
    {
      const { page, loi } = await moTrang(browser, port);
      await diToiNhap(page, jpegPath);
      await nhapSangDeXuat(page);
      const text = await visibleText(page);
      fs.writeFileSync(path.join(OUT, "A-de-xuat.txt"), text);
      await page.screenshot({ path: path.join(OUT, "A-de-xuat.png"), fullPage: true });
      const sach = inKetQua(quet("A · roster đủ", text));
      soNguoiA = soNguoiGui(text);
      console.log(`         "N người sẽ cần gửi tiền" = ${soNguoiA}`);
      console.log(`         thẻ "Chia không hết chẵn" có mặt: ${text.includes("Chia không hết chẵn")}`);
      if (loi.length) console.log(`         lỗi trang: ${loi.join(" | ")}`);
      if (!sach) sai.push("A: đường demo có id trên màn");
      if (soNguoiA === null) mu.push("A: không đọc được câu 'N người sẽ cần gửi tiền' — E vô nghĩa");
      await page.close();
    }

    /* Đ ------------------------------------------------------------------ */
    console.log("\nĐ. ĐỐI CHỨNG DƯƠNG CHO MÁY ĐỌC — gõ chính một UUID vào ô 'dịp'");
    {
      const { page, loi } = await moTrang(browser, port);
      await diToiNhap(page, jpegPath);
      await nhapSangDeXuat(page, MA_LA_3);
      const text = await visibleText(page);
      fs.writeFileSync(path.join(OUT, "D-doc-duoc.txt"), text);
      await page.screenshot({ path: path.join(OUT, "D-doc-duoc.png"), fullPage: true });
      const kq = quet("Đ · dịp là UUID", text);
      inKetQua(kq);
      if (loi.length) console.log(`         lỗi trang: ${loi.join(" | ")}`);
      if (!kq.uuid.includes(MA_LA_3)) {
        mu.push("Đ: máy đọc KHÔNG thấy UUID người dùng tự gõ — mọi số 0 dưới đây vô nghĩa");
      }
      await page.close();
    }

    /* B ------------------------------------------------------------------ */
    console.log("\nB. KỊCH BẢN CŨ — máy chủ trả rounding_gainers là id lạ");
    {
      const { page, loi } = await moTrang(browser, port, "gainer", MA_LA_1);
      await diToiNhap(page, jpegPath);
      await nhapSangDeXuat(page);
      const text = await visibleText(page);
      fs.writeFileSync(path.join(OUT, "B-de-xuat.txt"), text);
      await page.screenshot({ path: path.join(OUT, "B-de-xuat.png"), fullPage: true });
      const catNgang = await page.evaluate(() => window.__catNgang ?? 0);
      const coThe = text.includes("Chia không hết chẵn");
      const kq = quet("B · gainer lạ", text);
      inKetQua(kq);
      console.log(`         số lần cắt ngang /expenses: ${catNgang}`);
      console.log(`         thẻ "Chia không hết chẵn" có mặt: ${coThe}`);
      const cauLe = (text.match(/Chia không hết chẵn\.[^\n]*/) ?? [""])[0];
      console.log(`         câu 1đ lẻ: ${JSON.stringify(cauLe)}`);
      if (loi.length) console.log(`         lỗi trang: ${loi.join(" | ")}`);
      if (catNgang === 0) mu.push("B: shim không cắt được /expenses — phép đo vô nghĩa");
      if (!coThe) mu.push("B: thẻ 1đ lẻ KHÔNG render — nhánh không được đi qua, phép đo vô nghĩa");
      if (kq.uuid.includes(MA_LA_1)) sai.push("B: id lạ từ máy chủ VẪN hiện nguyên trên màn");
      if (coThe && !cauLe.includes(TEN_CHUA_BIET)) {
        sai.push(`B: câu 1đ lẻ không nói "${TEN_CHUA_BIET}" — không rõ nó đặt tên người lạ bằng gì`);
      }
      await page.close();
    }

    /* C1 ----------------------------------------------------------------- */
    console.log("\nC1. DỰNG THẲNG — advancer VÀ gainer ngoài cả bill lẫn nhóm, nhom=[]");
    {
      const { text, kq } = await dungThang(
        browser,
        "C1 · cả hai id lạ, nhóm rỗng",
        propsDeXuat({ advancerId: MA_LA_1, roundingGainers: [MA_LA_2], nhom: [] }),
        "c1.html",
      );
      inKetQua(kq);
      const soChuaBiet = (text.match(new RegExp(TEN_CHUA_BIET, "g")) ?? []).length;
      console.log(`         số lần "${TEN_CHUA_BIET}" trên màn: ${soChuaBiet}`);
      if (kq.uuid.length) sai.push(`C1: ${kq.uuid.length} id lạ vẫn hiện nguyên`);
      if (!kq.uuid.length && soChuaBiet === 0) {
        sai.push("C1: không id, cũng không có chữ nào gọi tên người lạ — màn nói gì?");
      }
    }

    /* C2 ----------------------------------------------------------------- */
    console.log("\nC2. CỌC CHỐNG BÔI CHỮ CHUNG — NHÓM biết người ứng tiền, bill thì không");
    {
      const { text, kq } = await dungThang(
        browser,
        "C2 · nhóm biết advancer",
        propsDeXuat({
          advancerId: MA_LA_1,
          roundingGainers: [MA_LA_2],
          nhom: [{ id: MA_LA_1, name: "Ngọc" }],
        }),
        "c2.html",
      );
      inKetQua(kq);
      const coTen = text.includes("Ngọc đã trả trước");
      console.log(`         "Ngọc đã trả trước" trên màn: ${coTen}`);
      console.log(`         gainer (không ai biết) ra chữ gì: ` +
        JSON.stringify((text.match(/Chia không hết chẵn\.[^\n]*/) ?? [""])[0]));
      if (kq.uuid.length) sai.push(`C2: ${kq.uuid.length} id lạ vẫn hiện nguyên`);
      if (!coTen) sai.push("C2: nhóm BIẾT người ứng tiền mà màn không gọi đúng tên họ");
    }

    /* D ------------------------------------------------------------------ */
    console.log("\nD. CÁNH CỬA — bỏ người ứng tiền khỏi roster rồi đọc nút 'Chia tiền'");
    {
      const { page } = await moTrang(browser, port);
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
        return b?.disabled ?? null;
      });
      console.log(`         sau khi chọn ${TREN_BILL[0]} làm người ứng tiền: disabled=${truoc}`);
      const boDuoc = await page.evaluate(() => {
        const nut = [...document.querySelectorAll("button, [role='button']")].filter(
          (n) => (n.getAttribute("aria-label") || n.textContent || "").trim() === "Bỏ",
        );
        if (!nut.length) return false;
        nut[0].click();
        return true;
      });
      await new Promise((r) => setTimeout(r, 400));
      const sauKhiBo = await page.evaluate(() => {
        const b = [...document.querySelectorAll("button")].find(
          (n) => n.textContent.trim() === "Chia tiền",
        );
        return b?.disabled ?? null;
      });
      console.log(`         bấm được "Bỏ": ${boDuoc}`);
      console.log(`         sau khi bỏ ${TREN_BILL[0]}: disabled=${sauKhiBo}`);
      fs.writeFileSync(path.join(OUT, "D-cua.txt"), await visibleText(page));
      if (!boDuoc) mu.push("D: không tìm được nút Bỏ — phép đo cửa vô nghĩa");
      if (sauKhiBo !== true) sai.push("D: bỏ người ứng tiền mà nút Chia tiền vẫn bấm được");
      await page.close();
    }

    /* E ------------------------------------------------------------------ */
    console.log("\nE. ĐỐI CHỨNG ÂM — máy chủ chia tiền cho một người NGOÀI bill (Σ giữ nguyên)");
    {
      const { page, loi } = await moTrang(browser, port, "chia", MA_LA_2);
      await diToiNhap(page, jpegPath);
      await nhapSangDeXuat(page);
      const text = await visibleText(page);
      fs.writeFileSync(path.join(OUT, "E-de-xuat.txt"), text);
      await page.screenshot({ path: path.join(OUT, "E-de-xuat.png"), fullPage: true });
      const doiCho = await page.evaluate(() => window.__doiCho ?? null);
      const kq = quet("E · tiền cho người ngoài bill", text);
      inKetQua(kq);
      const soNguoiE = soNguoiGui(text);
      console.log(`         máy chủ dời tiền: ${JSON.stringify(doiCho)}`);
      console.log(`         "N người sẽ cần gửi tiền": A=${soNguoiA} -> E=${soNguoiE}`);
      console.log(`         id người được chia tiền có trên màn: ${text.includes(MA_LA_2)}`);
      console.log(`         số dòng "0đ" trên màn: ${(text.match(/(^|\s)0đ/g) ?? []).length}`);
      if (loi.length) console.log(`         lỗi trang: ${loi.join(" | ")}`);
      if (!doiCho) mu.push("E: shim không dời được tiền — đối chứng âm vô nghĩa");
      // KHÔNG đẩy vào `sai`: E là đối chứng ÂM, nó tả một đường #468 không bịt.
      // Nó phải cho ra CÙNG một kết quả ở cả hai nền; so sánh nằm ngoài file này.
      await page.close();
    }
  } finally {
    await browser.close();
    await closeServer(server);
  }

  console.log(`\nHiện vật (ngoài repo): ${OUT}`);
  if (mu.length) {
    console.log("\nKẾT LUẬN: PHÉP ĐO TỰ KHAI LÀ MÙ — không đọc số nào ở trên");
    for (const s of mu) console.log(`  - ${s}`);
    process.exit(2);
  }
  if (sai.length) {
    console.log(`\nKẾT LUẬN [${NEN}]: CHƯA ĐẠT hợp đồng sau vá`);
    for (const s of sai) console.log(`  - ${s}`);
    process.exit(1);
  }
  console.log(`\nKẾT LUẬN [${NEN}]: ĐẠT hợp đồng sau vá — không id nào ra tới màn ở A/B/C1/C2, cửa D vẫn đóng.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(2);
});
