/* Tường kỷ niệm: ngày, chặng và tiền — những phần đọc được mà không cần render.
 *
 * Ca đáng giá nhất ở đây là ca NGÀY. `starts_on`/`ends_on` là ngày theo lịch,
 * chưa bao giờ là một thời điểm. Đưa chúng qua `new Date("2030-08-23")` thì
 * spec ECMAScript parse thành nửa đêm UTC, rồi `getDate()` đọc lại theo múi giờ
 * của MÁY — nên một chuyến kết thúc ngày 23 hiện thành ngày 22 trên mọi máy ở
 * phía tây Greenwich. Chạy ở +07 hay ở UTC đều không thấy; chỉ máy ở múi âm mới
 * thấy. Nên ở đây có một ca chạy thẳng dưới `TZ=America/New_York`.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";

import {
  khoangNgay,
  loiKyUc,
  soNgay,
  tienVnd,
  tomTatChang,
} from "../dist-test/screens/ky-niem/ky-uc.js";

/* ------------------------------------------------------------------ ngày --- */

test("khoảng ngày trong cùng một tháng gộp lại, không lặp tháng hai lần", () => {
  assert.equal(khoangNgay("2030-08-21", "2030-08-23"), "21 – 23/08/2030");
});

test("chuyến một ngày in một ngày, không in '23 – 23'", () => {
  assert.equal(khoangNgay("2030-08-23", "2030-08-23"), "23/08/2030");
});

test("khoảng ngày vắt qua tháng và qua năm vẫn đọc được", () => {
  assert.equal(khoangNgay("2030-08-30", "2030-09-02"), "30/08 – 02/09/2030");
  assert.equal(khoangNgay("2030-12-30", "2031-01-02"), "30/12/2030 – 02/01/2031");
});

test("chuỗi ngày sai định dạng trả về rỗng chứ không trả 'NaN/NaN'", () => {
  for (const bad of ["", "hôm qua", "2030-8-3", "2030-08-23T00:00:00Z"]) {
    assert.equal(khoangNgay(bad, "2030-08-23"), "", bad);
  }
});

test("ngày KHÔNG bị dịch bởi múi giờ của máy đọc", () => {
  // Chạy trong tiến trình con ở múi âm nhất còn dùng phổ biến. Nếu hàm này
  // parse ngày lịch thành một thời điểm, chuyến kết thúc 23 sẽ ra 22 ở đây —
  // và ca này là chỗ duy nhất trong bộ test nhìn thấy điều đó.
  const script =
    "import('../dist-test/screens/ky-niem/ky-uc.js')" +
    ".then(m => console.log(m.khoangNgay('2030-08-21','2030-08-23')))";
  const out = execFileSync(process.execPath, ["--input-type=module", "-e", script], {
    cwd: new URL(".", import.meta.url).pathname,
    env: { ...process.env, TZ: "America/New_York" },
    encoding: "utf8",
  }).trim();
  assert.equal(out, "21 – 23/08/2030");
});

test("số ngày đếm cả ngày đầu lẫn ngày cuối", () => {
  assert.equal(soNgay("2030-08-23", "2030-08-23"), 1);
  assert.equal(soNgay("2030-08-21", "2030-08-23"), 3);
  assert.equal(soNgay("2030-12-30", "2031-01-02"), 4);
});

/* ----------------------------------------------------------------- chặng --- */

test("chặng không có tên quán vẫn được kể bằng nhãn của nó", () => {
  // Bỏ chặng không tên đi thì một chuyến ba chặng tự nấu ăn ở nhà sẽ đọc thành
  // một chuyến không đi đâu cả.
  assert.equal(
    tomTatChang([
      { position: 0, at: "17:00", label: "Đi chợ", place_name: null },
      { position: 1, at: "19:00", label: "Nướng sân thượng", place_name: null },
    ]),
    "Đi chợ · Nướng sân thượng",
  );
});

test("tên quán được ưu tiên hơn nhãn chung chung", () => {
  assert.equal(
    tomTatChang([{ position: 0, at: "08:00", label: "Cafe", place_name: "Lưng Chừng" }]),
    "Lưng Chừng",
  );
});

test("quá ba chặng thì rút gọn kèm số còn lại, không cắt cụt im lặng", () => {
  const stops = ["A", "B", "C", "D", "E"].map((n, i) => ({
    position: i,
    at: "08:00",
    label: n,
    place_name: null,
  }));
  assert.equal(tomTatChang(stops), "A · B · C · +2");
});

test("chuyến chưa có chặng nào trả rỗng để màn tự bỏ dòng đó đi", () => {
  assert.equal(tomTatChang([]), "");
});

/* ------------------------------------------------------------------ tiền --- */

test("tiền in kiểu Việt Nam, chấm chứ không phẩy", () => {
  // `Intl` bị từ chối: Hermes không kèm ICU đầy đủ và `toLocaleString` rơi về
  // locale C, ra "860,000đ" trên điện thoại trong khi web vẫn đúng.
  assert.equal(tienVnd(860_000), "860.000đ");
  assert.equal(tienVnd(0), "0đ");
  assert.equal(tienVnd(1_000), "1.000đ");
  assert.equal(tienVnd(12_345_678), "12.345.678đ");
});

/* ------------------------------------------------------------------- lỗi --- */

test("bị từ chối vì không phải thành viên thì nói đúng lý do đó", () => {
  assert.match(loiKyUc(403, "permission_denied"), /thành viên/);
});

test("mỗi mã lỗi ra một câu khác nhau, không gộp thành 'có lỗi'", () => {
  const messages = [loiKyUc(401, ""), loiKyUc(403, ""), loiKyUc(404, ""), loiKyUc(500, "")];
  assert.equal(new Set(messages).size, messages.length);
});
