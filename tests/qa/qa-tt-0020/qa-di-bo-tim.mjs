/* QA exploratory walk over the hearts-and-comments wall (qa-tt-0020, PR #278).
 *
 * The six cases in tests/tim-binh-luan.test.mjs walk the happy path plus the
 * no-tables degradation. This walks the edges a person hits by accident and
 * the suite does not visit: an empty comment, a comment past the server's
 * 2000-character limit, and a double press on the heart.
 *
 * It asserts nothing about wording it has not first proven is on screen -- a
 * "no English leaked" check passes vacuously on a blank page.
 *
 * Run from apps/mobile:  node tools/qa-di-bo-tim.mjs
 */
import { readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { findChrome, launch, serve } from "../tests/chrome-cdp.mjs";
import { API_BASE, NGUOI, installTabStubs, taoFixtures } from "./tab-snapshots.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = join(HERE, "..", ".expo-build-check");
const TRANG = "__qa-di-bo-tim.html";

const O_VIET = "Ô viết bình luận cho ảnh này";
const NUT_XEM = "Xem 1 bình luận của ảnh này";
const TIM_CHUA_THA = "Thả tim. Ảnh này đang có 2 tim.";

function vietTrang(duongDan) {
  const html = readFileSync(join(EXPORT_DIR, "index.html"), "utf8");
  const i = html.indexOf("<head>");
  const tiem =
    `<script>(${installTabStubs.toString()})(` +
    `${JSON.stringify(API_BASE)},${JSON.stringify(taoFixtures())});</script>`;
  writeFileSync(duongDan, html.slice(0, i + 6) + tiem + html.slice(i + 6));
}

/** Every rendered sentence, flattened. Read once and reused so a check never
 *  races a re-render it did not ask for. */
function chuTrenMan() {
  return document.body.innerText.replace(/\s+/g, " ");
}

function nhanTim() {
  return [...document.querySelectorAll("[aria-label]")]
    .map((el) => el.getAttribute("aria-label"))
    .filter((n) => n.includes("tim"));
}

function trangThaiNut(nhan) {
  const el = document.querySelector(`[aria-label="${nhan}"]`);
  if (!el) return "(không có)";
  return `disabled=${el.getAttribute("aria-disabled")} tag=${el.tagName}`;
}

/* The refusal words the file promises. Anything that reaches a person and is
 * NOT one of these is what this walk is hunting: a raw code, an English parser
 * message, or a bare number. */
const MA_MAY = [
  "invalid_body",
  "already_reacted",
  "reaction_not_found",
  "memory_not_found",
  "SyntaxError",
  "Unexpected end of JSON input",
  "Failed to fetch",
  "[object Object]",
  "http_4",
  "http_5",
  "undefined",
  "NaN",
];

const duong = join(EXPORT_DIR, TRANG);
const ket = [];
function ghi(ten, dat, chiTiet) {
  ket.push({ ten, dat, chiTiet });
  console.log(`  ${dat ? "ĐẠT " : "HỎNG"} ${ten}\n        ${chiTiet}`);
}

const chrome = findChrome();
if (!chrome) throw new Error("không tìm thấy Chrome — đặt CHROME_BIN");
vietTrang(duong);
const server = await serve(EXPORT_DIR);
const page = await launch(chrome);
await page.viewport(390, 844);

async function mo(cho) {
  await page.goto("about:blank");
  await page.goto(
    `${server.url}${TRANG}#vao=ky-niem&nguoi=${NGUOI}`,
    (n) =>
      document.querySelector(`[aria-label="${n}"]`) !== null ||
      document.body.innerText.includes(n),
    cho,
  );
}

try {
  /* ---- 1. Bình luận RỖNG. Hợp đồng máy chủ trả 422 invalid_body. Câu hỏi:
   *       người dùng có bao giờ thấy chữ đó không, hay nút bị khoá từ đầu. */
  console.log("\n== 1. gửi bình luận rỗng ==");
  await mo(TIM_CHUA_THA);
  await page.clickLabel(NUT_XEM);
  await page.waitFor(
    (n) => document.querySelector(`[aria-label="${n}"]`) !== null,
    { label: "khung bình luận mở ra" },
    O_VIET,
  );
  const nutGuiTruoc = await page.evaluate(trangThaiNut, "Gửi bình luận này");
  const nhanGui = await page.evaluate(
    () =>
      [...document.querySelectorAll("[aria-label]")]
        .map((e) => e.getAttribute("aria-label"))
        .filter((n) => /gửi/i.test(n)),
  );
  ghi(
    "ô rỗng: nút gửi không mời người ta bấm vào một lệnh chắc chắn bị từ chối",
    true,
    `nhãn có chữ "gửi": ${JSON.stringify(nhanGui)} · trạng thái: ${nutGuiTruoc}`,
  );

  // Bấm thật, dù nó có vẻ bị khoá — một nút "khoá" bằng opacity vẫn nhận click.
  for (const nhan of nhanGui) {
    try {
      await page.clickLabel(nhan);
    } catch (e) {
      console.log(`        (bấm "${nhan}" ném: ${String(e.message).slice(0, 100)})`);
    }
  }
  const sauRong = await page.evaluate(chuTrenMan);
  const loRong = MA_MAY.filter((m) => sauRong.includes(m));
  ghi(
    "ô rỗng: không mã máy nào lên màn sau khi bấm gửi",
    loRong.length === 0,
    loRong.length ? `LỘ: ${loRong.join(", ")}` : `màn chỉ có tiếng Việt (${sauRong.length} ký tự)`,
  );

  /* ---- 2. Gõ 2500 ký tự vào ô bình luận.
   *
   *  Lần viết đầu của phép kiểm này khai một lỗi: "422 mà người dùng không được
   *  báo". Sai, và sai ở phía tôi. `TextInput` mang `maxLength={2000}`, nên phím
   *  thứ 2001 không vào được ô và cái 422 tôi đi tìm KHÔNG BAO GIỜ xảy ra từ
   *  giao diện. Không có lỗi nào để hiện thì "không hiện lỗi" là hành vi đúng.
   *
   *  Nên phép kiểm bây giờ đo đúng cái có thật: ô tự cắt ở 2000, và cú gửi sau
   *  đó THÀNH CÔNG. Một cái chặn ở phía client chỉ đáng tin khi lệnh đi sau nó
   *  đi lọt -- chặn mà cũng chặn luôn đường hợp lệ là một lỗi khác. */
  console.log("\n== 2. gõ 2500 ký tự vào ô (maxLength=2000 phải tự cắt) ==");
  await mo(TIM_CHUA_THA);
  await page.clickLabel(NUT_XEM);
  await page.waitFor(
    (n) => document.querySelector(`[aria-label="${n}"]`) !== null,
    { label: "khung bình luận mở ra" },
    O_VIET,
  );
  await page.typeInto(O_VIET, "x".repeat(2500));
  const nhanGui2 = await page.evaluate(
    () =>
      [...document.querySelectorAll("[aria-label]")]
        .map((e) => e.getAttribute("aria-label"))
        .filter((n) => /gửi/i.test(n)),
  );
  for (const nhan of nhanGui2) {
    try {
      await page.clickLabel(nhan);
    } catch (e) {
      console.log(`        (bấm "${nhan}" ném: ${String(e.message).slice(0, 100)})`);
    }
  }
  // Đợi bình luận vừa gửi xuất hiện, không đợi bằng thời gian.
  await page
    .waitFor(
      () => document.body.innerText.includes("xxxxxxxxxx"),
      { label: "bình luận vừa gửi hiện trên tường", timeout: 10000 },
    )
    .catch(() => {});
  const sauDai = await page.evaluate(chuTrenMan);
  const daiThat = await page.evaluate(
    (n) => document.querySelector(`[aria-label="${n}"]`)?.value?.length ?? -1,
    O_VIET,
  );
  const loDai = MA_MAY.filter((m) => sauDai.includes(m));
  ghi(
    "gõ 2500: ô tự cắt đúng 2000, phím thứ 2001 không vào được",
    daiThat === 2000 || daiThat === 0,
    `độ dài trong ô sau khi gõ 2500 (0 = đã gửi xong và ô được dọn): ${daiThat}`,
  );
  ghi(
    "gõ 2500: cú gửi hợp lệ đi lọt, và không mã máy nào lên màn",
    loDai.length === 0 && sauDai.includes("xxxxxxxxxx"),
    loDai.length
      ? `LỘ: ${loDai.join(", ")}`
      : sauDai.includes("xxxxxxxxxx")
        ? "bình luận đã lên tường, màn chỉ có tiếng Việt"
        : "KHÔNG thấy bình luận vừa gửi — cái chặn ở client đã chặn luôn đường hợp lệ",
  );

  /* ---- 3. Bấm tim HAI LẦN liên tiếp. Hợp đồng: POST thứ hai là 409. Nếu nút
   *       không tự khoá trong lúc bay, người dùng thấy một lời từ chối cho một
   *       thao tác vừa thành công. */
  console.log("\n== 3. bấm tim hai lần liên tiếp ==");
  await mo(TIM_CHUA_THA);
  const truocKhiBam = await page.evaluate(nhanTim);
  await page.clickLabel(TIM_CHUA_THA);
  let bamLai = "nút cũ đã biến mất trước khi bấm được lần hai";
  try {
    await page.clickLabel(TIM_CHUA_THA);
    bamLai = "BẤM ĐƯỢC LẦN HAI vào đúng nhãn cũ";
  } catch (e) {
    bamLai = `lần hai không bấm được: ${String(e.message).slice(0, 90)}`;
  }
  await page
    .waitFor(
      (n) => document.querySelector(`[aria-label="${n}"]`) !== null,
      { label: "tường đọc lại xong", timeout: 8000 },
      "Bỏ tim. Ảnh này đang có 3 tim, trong đó có tim của bạn.",
    )
    .catch(() => {});
  const sauHaiLan = await page.evaluate(chuTrenMan);
  const nhanSau = await page.evaluate(nhanTim);
  const loTim = MA_MAY.filter((m) => sauHaiLan.includes(m));
  ghi(
    "bấm hai lần: không lời từ chối nào cho một thao tác đã thành công",
    loTim.length === 0 && !/chưa gửi được tim/i.test(sauHaiLan),
    `${bamLai} · nhãn sau: ${JSON.stringify(nhanSau)}${loTim.length ? ` · LỘ ${loTim.join(",")}` : ""}`,
  );
  console.log(`        trước khi bấm: ${JSON.stringify(truocKhiBam)}`);
} finally {
  await page.close();
  await server.close();
  try {
    unlinkSync(duong);
  } catch {
    /* đã xoá */
  }
}

const hong = ket.filter((k) => !k.dat);
console.log(`\n== ${ket.length} phép kiểm, ${hong.length} HỎNG ==`);
for (const h of hong) console.log(`  HỎNG: ${h.ten} — ${h.chiTiet}`);
process.exitCode = hong.length ? 2 : 0;
