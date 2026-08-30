/* Đối chứng độc lập cho #261 — cùng MỘT vi phạm, viết bằng những HÌNH DẠNG khác.
 *
 * ## Vì sao có file này khi #261 đã mang theo bảng đột biến của chính nó
 *
 * Bảng của #261 (`apps/mobile/tools/dot-bien-che-chu.mjs`) đúng và tôi đã chạy
 * lại: 7/7 hàng ra đúng màu nó khai. Nhưng mọi hàng ĐỎ của nó neo vào đúng một
 * chuỗi ký tự — chính dòng ternary mà PR vừa sửa:
 *
 *     verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : "that",
 *
 * Một cổng chỉ neo vào một chuỗi thì cái nó chứng minh được là "có ai đụng vào
 * dòng này không". Nó chưa chứng minh được "tính chất còn đúng không". Hai câu
 * đó khác nhau: người hồi sinh lời tha bổng gần như chắc chắn sẽ không gõ lại
 * y hệt dòng cũ — họ sẽ viết nó theo cách của họ.
 *
 * Nên file này viết lại CÙNG một vi phạm — cho một dòng chữ bị chôn hoàn toàn
 * thoát khỏi cổng — bằng bốn hình dạng mà bảng của #261 không neo tới, cộng hai
 * hàng GIỮ TÍNH CHẤT của riêng nó.
 *
 * ## Bốn hình dạng
 *
 *   1. Nhấc `cha` ra vế ngoài cùng. Tương đương ngữ nghĩa với dòng lỗi cũ,
 *      không trùng một ký tự nào với nó.
 *   2. Vẫn tha bổng, nhưng dán nhãn `cuon-khuat` thay vì `to-cha`. Cùng hậu
 *      quả — cả hai đều nằm trong `DA_LOAI_TRU` — chỉ khác tên. Hàng này phân
 *      biệt "cổng đo tính chất" với "cổng so chuỗi verdict".
 *   3. Dời lời tha bổng xuống `laLoiThat`, để `verdict` vẫn là `"that"`. Đây là
 *      đường ghi thứ hai: bản ghi trông đúng, chỉ có phép đếm là mù.
 *   4. `cha` luôn false. Không phải một lỗ — đây là phép kiểm ngược, hỏi xem ca
 *      thứ ba mà #261 mới thêm có THẬT SỰ ghim nhãn `to-cha` không, hay nhãn đó
 *      đã thành đồ trang trí sau khi nó mất quyền tha bổng.
 *
 * Hàng 4 đáng nói riêng. Sau bản vá, `to-cha` và `cuon-khuat` đều bị loại trừ,
 * nên `cha` không còn đổi được con số nào — nó chỉ còn đổi cái nhãn. Nếu không
 * ca nào ghim nhãn ấy thì nửa còn lại của `cha` là code chết mà không ai biết.
 *
 * ## Hai hàng GIỮ TÍNH CHẤT
 *
 * Một bảng toàn đỏ không phân biệt được "cổng phản ứng với đúng thứ sai" và
 * "cổng phản ứng với việc có người sửa file". Hai hàng dưới đổi thật sự nội
 * dung file mà KHÔNG đổi tính chất, nên chúng phải XANH:
 *
 *   - đổi câu chữ chuỗi `ly` ở vế chữ không đọc được — nếu đỏ thì cổng đang
 *     đọc văn bản giải thích chứ không đo hành vi;
 *   - nới ngưỡng đục 0.9 -> 0.85 khi lọc phần tử che — fixture là nền đục hoàn
 *     toàn, mọi ngưỡng dưới 1 phân loại y hệt.
 *
 * ## Chạy
 *
 *     cd apps/mobile && npm ci        # cần node_modules cho puppeteer-core
 *     CHROME_BIN=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome \
 *       node tests/qa/qa-tt-0014/hinh-dang-khac-cua-loi-to-cha.mjs
 *
 * Thoát 0 = cả bảng ra đúng màu mong đợi. Khác 0 = có hàng lệch, đọc dòng LECH.
 *
 * Nền phải XANH trước khi bất kỳ hàng nào có nghĩa; nền đỏ thì script dừng ở
 * mã 2 thay vì in ra một bảng màu vô nghĩa.
 *
 * Cái này KHÔNG chứng minh: rằng ngưỡng 0.6 đặt đúng chỗ, rằng detector bắn
 * đúng nơi cần bắn, hay rằng màn thật nào đang sạch. Nó chỉ chứng minh cổng
 * `che-chu` phản ứng với đúng tính chất "chữ bị chôn thì phải bị đếm", qua
 * nhiều cách viết chứ không qua một cách viết.
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const MOBILE = path.join(REPO, "apps/mobile");
const NGUON = path.join(MOBILE, "tools/che-chu.mjs");
// Cả hai file gate, vì chúng phủ hai nửa khác nhau của vế phán quyết. Chạy
// riêng `che-chu.test.mjs` chính là chuyện đã để lỗ `to-cha` mở suốt #255.
const GATES = [
  path.join(MOBILE, "tests/che-chu.test.mjs"),
  path.join(MOBILE, "tests/che-chu-lo-to-cha.test.mjs"),
];

const CHROME =
  process.env.CHROME_BIN ??
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";

/** Dòng phán quyết sau bản vá #261 — neo của bốn hàng đầu. */
const GOC = 'verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : "that",';

const BANG = [
  {
    ten: "HÌNH DẠNG KHÁC: cùng lời tha bổng, viết bằng cách nhấc `cha` ra vế ngoài",
    tim: GOC,
    thay: 'verdict: cha ? "to-cha" : tyLe >= 0.6 ? "cuon-khuat" : "that",',
    mong: "DO",
    vi: "tương đương ngữ nghĩa với dòng lỗi cũ, không trùng ký tự nào — cổng vẫn phải thấy",
  },
  {
    ten: "HÌNH DẠNG KHÁC: vẫn tha bổng, dán nhãn 'cuon-khuat' thay vì 'to-cha'",
    tim: GOC,
    thay:
      'verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : cha ? "cuon-khuat" : "that",',
    mong: "DO",
    vi: "cùng hậu quả (bị loại trừ), tên khác — cổng đo tính chất thì vẫn phải đỏ",
  },
  {
    ten: "HÌNH DẠNG KHÁC: tha bổng dời xuống laLoiThat, verdict vẫn là 'that'",
    tim: "  return !DA_LOAI_TRU.has(kq?.verdict);",
    thay: '  return !DA_LOAI_TRU.has(kq?.verdict) && kq?.chan !== "div.khung";',
    mong: "DO",
    vi: "bản ghi trông đúng, chỉ phép đếm mù — đường tha bổng thứ hai",
  },
  {
    ten: "NHÃN: `cha` luôn false (ca thứ ba của #261 có thật sự ghim nhãn to-cha?)",
    tim: "          if (c.contains(el)) { cha = true; break; }",
    thay: "          if (c.contains(el)) { cha = false; break; }",
    mong: "DO",
    vi: "XANH ở đây nghĩa là nhãn to-cha đã thành đồ trang trí và không ca nào gác nó",
  },
  {
    ten: "GIỮ TÍNH CHẤT: đổi câu chữ `ly` ở vế chữ không đọc được",
    tim: '`sau khi cuon toi, chi ${nhinThay}/${tong} diem mau doc duoc; tren cung la ${chan ?? "?"}`',
    thay: '`CHU BI CHON: ${nhinThay}/${tong} diem; tren cung la ${chan ?? "?"}`',
    mong: "XANH",
    vi: "chuỗi giải thích không phải tính chất — đỏ ở đây là cổng đọc văn bản nguồn",
  },
  {
    ten: "GIỮ TÍNH CHẤT: nới ngưỡng đục 0.9 -> 0.85 khi lọc phần tử che",
    tim: "0.9",
    thay: "0.85",
    mong: "XANH",
    vi: "fixture là nền đục hoàn toàn, mọi ngưỡng dưới 1 phân loại y hệt",
  },
];

const goc = fs.readFileSync(NGUON, "utf8");

function chayGate() {
  try {
    execFileSync(process.execPath, ["--test", ...GATES], {
      cwd: MOBILE,
      env: { ...process.env, CHROME_BIN: CHROME, MOBILE_REQUIRE_CHE_CHU: "1" },
      stdio: "pipe",
    });
    return "XANH";
  } catch {
    return "DO";
  }
}

const nen = chayGate();
console.log(`nen (chua dot bien): ${nen}`);
if (nen !== "XANH") {
  console.log("Nen da do -> moi ket qua duoi vo nghia. Dung o ma 2.");
  process.exit(2);
}

let lech = 0;
for (const m of BANG) {
  // Neo phải khớp đúng một lần: `replace(a, b)` vá bản sao ĐẦU TIÊN, nên một
  // neo khớp hai chỗ sẽ sửa nhầm chỗ và in ra một màu không nói về hàng này.
  const soLan = goc.split(m.tim).length - 1;
  if (soLan !== 1) {
    console.log(`BO QUA  ${m.ten}`);
    console.log(`         neo khop ${soLan} lan (can dung 1) — dot bien nay khong tin duoc`);
    lech++;
    continue;
  }
  fs.writeFileSync(NGUON, goc.replace(m.tim, m.thay));
  // Và phải xác nhận file THẬT SỰ đổi: một đột biến no-op in ra XANH trông y
  // hệt "cổng chịu được thay đổi này".
  if (fs.readFileSync(NGUON, "utf8") === goc) {
    console.log(`BO QUA  ${m.ten}\n         file khong doi — dot bien la no-op`);
    lech++;
    fs.writeFileSync(NGUON, goc);
    continue;
  }
  const kq = chayGate();
  fs.writeFileSync(NGUON, goc);
  const ok = kq === m.mong;
  if (!ok) lech++;
  console.log(`${ok ? "OK  " : "LECH"} [${kq.padEnd(4)}] mong ${m.mong.padEnd(4)}  ${m.ten}`);
  console.log(`         vi: ${m.vi}`);
}

fs.writeFileSync(NGUON, goc);
console.log(lech === 0 ? "\nCA BANG DUNG NHU MONG DOI" : `\n${lech} HANG LECH`);
process.exit(lech === 0 ? 0 : 1);
