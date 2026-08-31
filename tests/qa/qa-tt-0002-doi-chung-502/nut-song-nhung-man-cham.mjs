/* Đối chứng cho #502: cú bấm ĐÃ ĂN, nút vẫn còn đó, màn đích tới CHẬM.
 *
 * PR #502 dạy máy lái bấm lại khi màn đích không tới. Lập luận an toàn của nó,
 * viết ngay trong `quet-man-sau-tap.mjs`:
 *
 *     "If the press landed, the screen moved on and the finder no longer
 *      matches, so nothing is pressed twice -- that is what keeps this from
 *      double-submitting a save."
 *
 * Câu đó chỉ đúng khi cái nút BIẾN MẤT sau khi bấm trúng. Thanh tab, nút "Lưu"
 * còn nguyên trên màn, nút toggle — đều còn đó sau khi cú bấm đã ăn. Với chúng,
 * `bamDuoc()` vẫn trả về element (nó chỉ kiểm `disabled` và `aria-disabled`,
 * không kiểm còn-gắn-DOM hay còn-nhìn-thấy), nên điều kiện chặn bấm lại KHÔNG
 * thành lập.
 *
 * Ba hàng của #502 đều dùng trang mà cú bấm đặt chữ đích NGAY LẬP TỨC, nên
 * `cho()` giải quyết ở vòng poll đầu và không hàng nào chạm tới mốc 2500ms.
 * Tức hàng "NÚT TỐT: bam_lai rỗng" chứng minh "màn tới trong 2500ms", không
 * chứng minh "bấm trúng thì không bấm lại".
 *
 * Hàng thiếu, dựng ở đây:
 *
 *   A. CHẬM  — nút ăn cú đầu, đặt chữ đích sau 4000ms, nút vẫn còn và vẫn bấm
 *              được. Nếu lập luận trên đúng: `bam_lai` rỗng, handler chạy 1 lần.
 *   B. NHANH — hệt hàng A nhưng đặt chữ đích sau 200ms. Đây là đối chứng âm:
 *              nó phải ra 1 lần bấm, để phân biệt "máy lái luôn bấm đúp" với
 *              "máy lái bấm đúp khi màn chậm".
 *
 * Handler đếm số lần nó THẬT SỰ chạy (`window.__dem`) và ghi lại từng lần gửi
 * (`window.__gui`) — đo cú gửi, không đo lời khai của máy lái về cú gửi.
 *
 * Chạy (từ gốc repo, cần Chrome):
 *     node tests/qa/qa-tt-0002-doi-chung-502/nut-song-nhung-man-cham.mjs
 */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const day = dirname(fileURLToPath(import.meta.url));
const mobile = resolve(day, "..", "..", "..", "apps", "mobile");
const { findChrome, launch, serve } = await import(
  new URL(`file://${join(mobile, "tests", "chrome-cdp.mjs")}`).href
);
const { laiTrongTrang } = await import(
  new URL(`file://${join(mobile, "tools", "quet-man-sau-tap.mjs")}`).href
);

const NHAN = "Lưu";
const DICH = "Đã lưu xong";

/** Trang một nút "Lưu": cú bấm nào cũng ĂN, và nút KHÔNG biến mất.
 *
 *  Đây là hình dạng của một nút lưu thật: bấm là gửi, gửi xong màn mới hiện,
 *  và trong lúc chờ thì cái nút vẫn nằm đó. `tre` là độ trễ tới màn đích.
 *
 *  `bienMat` dựng đúng ca mà lập luận của #502 cho là an toàn: nút TỰ GỠ khi
 *  màn đích tới (điều hướng thay màn). Nó vẫn không cứu được, vì cái nút chỉ
 *  biến mất LÚC màn đích tới — còn cửa sổ đang-bay trước đó thì nút vẫn nằm
 *  nguyên đó, và cửa sổ ấy chính là thứ dài quá 2500ms. */
function trangLuu(tre, kichBan, bienMat = false) {
  return (
    "<!doctype html><html><head><meta charset=utf-8>" +
    `<script>(${laiTrongTrang.toString()})(${JSON.stringify(kichBan)},null);<\/script>` +
    "</head><body>" +
    `<button id=n>${NHAN}</button><div id=d></div>` +
    "<script>window.__dem=0;window.__gui=[];" +
    "document.getElementById('n').addEventListener('click',function(){" +
    "window.__dem++;window.__gui.push(Date.now());" +
    // Cú bấm ĂN ngay: nó khởi động việc gửi. Màn đích chỉ tới sau `tre`.
    "setTimeout(function(){document.getElementById('d').textContent=" +
    JSON.stringify(DICH) +
    ";" +
    (bienMat ? "var b=document.getElementById('n');if(b)b.remove();" : "") +
    "}," +
    String(tre) +
    ");});<\/script>" +
    "</body></html>"
  );
}

const chromeBin = findChrome();
if (!chromeBin) {
  console.error("KHONG CO CHROME - probe nay khong chay duoc, dung doc la xanh");
  process.exit(2);
}

const thuMuc = mkdtempSync(join(tmpdir(), "nut-song-"));
const server = await serve(thuMuc);
const page = await launch(chromeBin);

async function chay(ten, tre, bienMat = false) {
  const kichBan = [{ bamChu: NHAN }, { cho: DICH, ms: 20000 }];
  writeFileSync(join(thuMuc, ten), trangLuu(tre, kichBan, bienMat));
  await page.viewport(390, 844);
  await page.goto(server.url + ten);
  await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
    timeout: 120000,
    label: `may lai tren ${ten}`,
  });
  return page.evaluate(() => ({
    xong: window.__lai.xong,
    loi: window.__lai.loi,
    bam_lai: window.__lai.bam_lai || [],
    dem: window.__dem,
    gui: window.__gui,
  }));
}

let hong = 0;
for (const [ten, tre, nhan, bienMat] of [
  ["cham.html", 4000, "A. CHAM  (man dich toi sau 4000ms, nut o lai)", false],
  ["nhanh.html", 200, "B. NHANH (man dich toi sau  200ms, nut o lai)", false],
  ["bien-mat.html", 4000, "C. CHAM + NUT TU GO khi man dich toi", true],
]) {
  const r = await chay(ten, tre, bienMat);
  const khoang = r.gui.length > 1 ? r.gui[1] - r.gui[0] : 0;
  console.log(`\n=== ${nhan} ===`);
  console.log(`  may lai xong      : ${r.xong}  loi=${r.loi}`);
  console.log(`  handler CHAY      : ${r.dem} lan` + (khoang ? `  (cach nhau ${khoang}ms)` : ""));
  console.log(`  __lai.bam_lai     : ${JSON.stringify(r.bam_lai)}`);
  // Cú bấm đã ăn thì không được gửi lần hai — bất kể màn đích tới nhanh hay chậm.
  if (r.dem !== 1) {
    console.log(`  >>> GUI ${r.dem} LAN cho MOT cu bam. Nut "Luu" bi gui ${r.dem} lan.`);
    hong += 1;
  } else {
    console.log("  >>> dung 1 lan gui.");
  }
}

await page.close();
await server.close();
rmSync(thuMuc, { recursive: true, force: true });

console.log(`\n${hong === 0 ? "KHONG tim thay cu gui thua" : `CO ${hong}/3 hang gui THUA`}`);
process.exit(hong === 0 ? 0 : 1);
