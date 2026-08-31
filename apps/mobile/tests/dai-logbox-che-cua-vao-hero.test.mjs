/* Dải LogBox của React Native che ĐÚNG nút mở luồng hero trên native.
 *
 * ## Vì sao file này tồn tại
 *
 * Đo trên Expo Go 57 / Android 15 / 1080x2400, màn Khám phá:
 *
 *     dải LogBox      [26,2146] – [1054,2271]
 *     thanh tab       bắt đầu y = 2253
 *     4 nhãn tab      y ≈ 2311            -> DƯỚI dải, bấm được
 *     nút "Tạo mới"   [469,2195] – [611,2337], tâm y = 2266   -> TRONG dải
 *
 * Đúng một nút bị nuốt, và nó là cửa vào luồng tạo khoản chi — nửa đầu của
 * đường hero (chụp bill -> chia tiền -> VietQR). Bấm vào: không lỗi, không
 * log, không điều hướng. Trên màn hình nó giống hệt "tính năng này chưa có",
 * và đó chính là câu một bảng đếm tính năng sẽ chép vào báo cáo.
 *
 * Lỗi này KHÔNG nhìn thấy được trong Chrome: `react-native-web` xuất một
 * LogBox rỗng, nên dải không bao giờ được vẽ ở đó. Mọi số đo giao diện của đội
 * cho tới nay đều đo trong Chrome, nên không có phép đo nào đã từng chạm tới nó.
 *
 * ## File này chứng minh gì
 *
 * Rằng `App.tsx` tắt dải thông báo LogBox ở CẤP MODULE — tức là lời gọi nằm ở
 * thân module, không nằm trong một hàm có thể không bao giờ được gọi.
 * `index.ts` import `./App` rồi mới `registerRootComponent`, nên mã cấp module
 * của `App.tsx` chạy trước khi React vẽ khung hình đầu tiên.
 *
 * Và rằng lời gọi đó an toàn cho bản web: `react-native-web` thật sự xuất một
 * `LogBox` có `ignoreAllLogs`. Câu đó được kiểm bằng cách GỌI hàm thật, không
 * bằng cách đọc tên nó trong nguồn.
 *
 * ## File này KHÔNG chứng minh gì
 *
 * Không chứng minh ngón tay bấm được nút "Tạo mới" trên máy Android sau thay
 * đổi này. Câu đó cần emulator, và lượt viết file này emulator đang bị lane
 * khác dùng (đã ghi trong PR). Thứ thay thế ở đây là hai mảnh chắc chắn hơn
 * lời hứa: toạ độ ĐO ĐƯỢC ở trên, và hành vi của `ignoreAllLogs` đọc thẳng
 * trong nguồn React Native đã cài — `Libraries/LogBox/LogBox.js` dòng 155 tự
 * khai: "this only disables notifications, uncaught errors will still open a
 * full screen LogBox".
 *
 * Nên: mất dải, KHÔNG mất thông tin. Cảnh báo vẫn ra `console` và vẫn nằm
 * trong logcat; sập vẫn mở LogBox toàn màn. Thứ duy nhất biến mất là mảng dev
 * chrome đang ngồi lên cửa vào của luồng hero.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const GOC = dirname(fileURLToPath(import.meta.url));
const DUONG_APP = join(GOC, "..", "App.tsx");
const NGUON = readFileSync(DUONG_APP, "utf8");

/* ------------------------------------------------------------------ nền đo */

/** Xoá comment và chuỗi, giữ nguyên độ dài để vị trí không trôi.
 *
 * Đọc `LogBox.ignoreAllLogs(` bằng regex trần sẽ khớp cả một dòng comment nói
 * VỀ nó — và file này có hẳn một đoạn comment như thế ở ngay trên. Một phép đo
 * đọc được chính lời chú thích của mình là phép đo không đo gì cả.
 */
function locBoChuThichVaChuoi(src) {
  let ra = "";
  let i = 0;
  while (i < src.length) {
    const hai = src.slice(i, i + 2);
    if (hai === "/*") {
      const het = src.indexOf("*/", i + 2);
      const den = het === -1 ? src.length : het + 2;
      for (let k = i; k < den; k++) ra += src[k] === "\n" ? "\n" : " ";
      i = den;
      continue;
    }
    if (hai === "//") {
      let k = i;
      while (k < src.length && src[k] !== "\n") {
        ra += " ";
        k++;
      }
      i = k;
      continue;
    }
    const c = src[i];
    if (c === '"' || c === "'" || c === "`") {
      ra += " ";
      i++;
      while (i < src.length) {
        if (src[i] === "\\") {
          ra += "  ";
          i += 2;
          continue;
        }
        if (src[i] === c) {
          ra += " ";
          i++;
          break;
        }
        ra += src[i] === "\n" ? "\n" : " ";
        i++;
      }
      continue;
    }
    ra += c;
    i++;
  }
  return ra;
}

/** Độ sâu ngoặc nhọn tại mỗi vị trí, tính trên nguồn ĐÃ lọc. */
function doSauTai(sach, viTri) {
  let sau = 0;
  for (let k = 0; k < viTri; k++) {
    if (sach[k] === "{") sau++;
    else if (sach[k] === "}") sau--;
  }
  return sau;
}

/** Mọi lời gọi `LogBox.ignoreAllLogs(` kèm độ sâu ngoặc nhọn của nó. */
function loiGoiTatDai(src) {
  const sach = locBoChuThichVaChuoi(src);
  const ra = [];
  const re = /LogBox\s*\.\s*ignoreAllLogs\s*\(/g;
  let m;
  while ((m = re.exec(sach)) !== null) {
    ra.push({ viTri: m.index, doSau: doSauTai(sach, m.index) });
  }
  return ra;
}

test("nền: App.tsx đọc được và phép lọc không nuốt mất mã thật", () => {
  assert.ok(NGUON.length > 10_000, "App.tsx quá ngắn — đọc nhầm file?");
  const sach = locBoChuThichVaChuoi(NGUON);
  assert.equal(sach.length, NGUON.length, "phép lọc làm trôi vị trí");
  assert.match(sach, /export default function/, "phép lọc nuốt mất mã thật");
});

test("nền: phép lọc thật sự bỏ qua lời gọi nằm trong comment", () => {
  const gia = 'const a = 1;\n/* LogBox.ignoreAllLogs(); */\n// LogBox.ignoreAllLogs();\n';
  assert.deepEqual(loiGoiTatDai(gia), [], "comment bị đọc thành lời gọi thật");
});

/* -------------------------------------------------- an toàn cho bản web */

test("react-native-web xuất LogBox thật, và ignoreAllLogs gọi được", async () => {
  const rnw = await import("react-native-web");
  const LogBox = rnw.LogBox ?? rnw.default?.LogBox;
  assert.ok(LogBox, "react-native-web không xuất LogBox — import trong App.tsx sẽ hỏng bản web");
  assert.equal(
    typeof LogBox.ignoreAllLogs,
    "function",
    "LogBox của react-native-web không có ignoreAllLogs",
  );
  // Gọi thật. Nếu nó ném thì bản web sẽ trắng màn ngay ở dòng import.
  assert.equal(LogBox.ignoreAllLogs(), undefined);
});

/* ------------------------------------------------------------ phép đo chính */

test("App.tsx tắt dải thông báo LogBox ở cấp module", () => {
  const goi = loiGoiTatDai(NGUON);

  assert.notDeepEqual(
    goi,
    [],
    "App.tsx không tắt dải thông báo LogBox.\n\n" +
      "Trên Expo Go / Android, dải đó phủ [26,2146]–[1054,2271], còn nút mở " +
      'luồng hero ("Tạo mới") có tâm ở y=2266 — nằm TRONG dải. Bấm vào không ' +
      "có gì xảy ra, và trên màn hình nó không phân biệt được với một tính " +
      "năng chưa tồn tại.",
  );

  const capModule = goi.filter((g) => g.doSau === 0);
  assert.notDeepEqual(
    capModule,
    [],
    "Có gọi `LogBox.ignoreAllLogs()` nhưng lời gọi nằm trong một khối, không " +
      "ở thân module. Một lời gọi chôn trong hàm chỉ chạy nếu hàm đó được gọi; " +
      "dải LogBox thì xuất hiện ngay từ cảnh báo đầu tiên.",
  );
});

/** Xoá comment nhưng GIỮ chuỗi, để còn đọc được tên module trong `from "..."`. */
function locBoChuThich(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

const NHAP_LOGBOX = /import\s*\{[\s\S]*?\bLogBox\b[\s\S]*?\}\s*from\s*["']react-native["']/;

test("App.tsx import LogBox từ chính react-native", () => {
  assert.match(
    locBoChuThich(NGUON),
    NHAP_LOGBOX,
    "LogBox được gọi nhưng không được import từ `react-native` — bản dựng sẽ hỏng.",
  );
});

test("canary: bỏ LogBox khỏi danh sách import thì phép đo phải ĐỎ", () => {
  const daBo = locBoChuThich(NGUON).replace(/^\s*LogBox,\s*$/m, "");
  assert.ok(
    !NHAP_LOGBOX.test(daBo),
    "Gỡ LogBox khỏi import mà thước vẫn thấy nó được import.",
  );
});

/* ---------------------------------------------------------------- canary */

test("canary: bỏ lời gọi khỏi bản sao nguồn thì phép đo phải ĐỎ", () => {
  const daBo = NGUON.replace(/LogBox\s*\.\s*ignoreAllLogs\s*\([^)]*\)\s*;?/g, "");
  assert.deepEqual(
    loiGoiTatDai(daBo),
    [],
    "Gỡ lời gọi mà thước vẫn thấy nó — thước này không đo cái nó khai là đang đo.",
  );
});

test("canary: chôn lời gọi vào trong một hàm thì phép đo cấp module phải ĐỎ", () => {
  const choniInHam = "function noop() {\n  LogBox.ignoreAllLogs();\n}\n";
  const goi = loiGoiTatDai(choniInHam);
  assert.equal(goi.length, 1, "không thấy lời gọi trong bản dựng thử");
  assert.equal(
    goi.filter((g) => g.doSau === 0).length,
    0,
    "lời gọi nằm trong thân hàm mà vẫn được xếp là cấp module — " +
      "thước không phân biệt được 'chạy khi nạp' với 'chạy nếu ai đó gọi'.",
  );
});
