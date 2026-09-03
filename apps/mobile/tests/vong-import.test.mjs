/* Vòng import, và vì sao nó không phải chuyện thẩm mỹ.
 *
 * ## Nó đã ăn một cú bấm
 *
 * Đưa chín module về gọi chung một chỗ dựng header sinh ra:
 *
 *     Require cycle: src/api.ts -> src/participants.ts
 *                    -> src/screens/chat/tin-nhan.ts -> src/api.ts
 *
 * React Native in cảnh báo đó ra LogBox, và LogBox là một DẢI thật nằm đè lên
 * đáy màn hình. Trên máy ảo ngày 2026-09-03 nó phủ đúng nút «Rủ Đi thôi!»:
 * Maestro báo `Tap on "Rủ Đi thôi!"... COMPLETED`, màn hình không đổi, rồi
 * assert kế tiếp đỏ. Ảnh chụp lúc đỏ cho thấy màn chào còn nguyên và cái dải
 * vàng nằm ngay trên nút.
 *
 * Và đó mới là triệu chứng nhẹ. Cái nặng là ngữ nghĩa: module nào bị nạp giữa
 * vòng sẽ thấy hàm nó import là `undefined`. Với vòng cụ thể trên, thứ có thể
 * thành `undefined` là chỗ dựng header danh tính — tức crash trên đúng đường mà
 * bản vá sinh ra nó được viết để chữa.
 *
 * ## Vì sao là danh sách ghim chứ không phải «cấm hết»
 *
 * Cây này có sẵn hai vòng, cả hai đều có trước và không thuộc phạm vi lượt sửa
 * này. Bắt chúng đỏ ngay bây giờ chỉ dẫn tới việc ai đó tắt cả ca. Ghim lại thì
 * cổng trả lời được câu duy nhất đáng hỏi khi review: **lượt này có thêm vòng
 * nào không.** Gỡ được vòng nào thì xoá dòng đó — danh sách thừa cũng đỏ.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

/** Vòng đã có trước lượt gỡ 2026-09-03. Không được dài thêm. */
const VONG_DA_BIET = [
  "src/api.ts -> src/screens/DotThu.tsx -> src/api.ts",
  "src/screens/kham-pha/BanDoNhom.tsx -> src/screens/kham-pha/DiemHen.tsx" +
    " -> src/screens/kham-pha/BanDoNhom.tsx",
];

function nguon(dir) {
  const ra = [];
  for (const muc of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, muc.name);
    if (muc.isDirectory()) ra.push(...nguon(p));
    else if (/\.tsx?$/.test(muc.name) && !muc.name.includes(".test.")) ra.push(p);
  }
  return ra.sort();
}

/** `./x` -> file thật. Thử đúng những đuôi Metro thử. */
function giaiDuong(tuFile, duong) {
  const goc = resolve(dirname(tuFile), duong);
  for (const hau of [".ts", ".tsx", "/index.ts", "/index.tsx"]) {
    try {
      readFileSync(goc + hau);
      return goc + hau;
    } catch {
      /* thử đuôi tiếp theo */
    }
  }
  return null;
}

function doThi() {
  const canh = new Map();
  for (const f of nguon(SRC)) {
    const than = readFileSync(f, "utf8");
    const toi = new Set();
    // `from "..."` phủ cả `import ... from` lẫn `export ... from`. Bỏ
    // `import type`: nó biến mất khi biên dịch nên không nằm trong vòng lúc
    // chạy — đúng cách Metro nhìn.
    for (const m of than.matchAll(/(?<!\btype\s)\bfrom\s+["'](\.[^"']+)["']/g)) {
      const d = giaiDuong(f, m[1]);
      if (d !== null) toi.add(d);
    }
    canh.set(f, [...toi].sort());
  }
  return canh;
}

function timVong(canh) {
  const dang = new Set();
  const xong = new Set();
  const ra = [];
  const ten = (f) => `src/${relative(SRC, f)}`;
  const di = (n, duong) => {
    if (dang.has(n)) {
      const i = duong.indexOf(n);
      ra.push([...duong.slice(i === -1 ? 0 : i), n].map(ten).join(" -> "));
      return;
    }
    if (xong.has(n)) return;
    dang.add(n);
    for (const k of canh.get(n) ?? []) di(k, [...duong, n]);
    dang.delete(n);
    xong.add(n);
  };
  for (const n of [...canh.keys()].sort()) di(n, []);
  return ra.sort();
}

test("không có vòng import nào ngoài những vòng đã ghim", () => {
  const thay = timVong(doThi());
  const moi = thay.filter((v) => !VONG_DA_BIET.includes(v));
  assert.deepEqual(
    moi,
    [],
    "vòng import MỚI — dải LogBox của nó sẽ đè lên nút ở đáy màn, và module " +
      `nạp giữa vòng thấy hàm nó import là undefined:\n  ${moi.join("\n  ")}`,
  );
});

test("danh sách ghim không có dòng thừa", () => {
  // Một dòng ghim cho một vòng đã được gỡ là chỗ trống cho vòng sau chui vào
  // mà không ai thấy. Ghim là món nợ, và món nợ phải trả hết được.
  const thay = timVong(doThi());
  const chet = VONG_DA_BIET.filter((v) => !thay.includes(v));
  assert.deepEqual(chet, [], `ghim vòng không còn tồn tại — xoá đi:\n  ${chet.join("\n  ")}`);
});

test("phép dò thật sự dựng được đồ thị", () => {
  // Không có ca này, một `giaiDuong` luôn trả null làm hai ca trên xanh vì đồ
  // thị RỖNG: không cạnh thì không vòng, và cổng tự tháo trong im lặng.
  const canh = doThi();
  assert.equal(canh.size > 100, true, `chỉ đọc được ${canh.size} file`);
  const tongCanh = [...canh.values()].reduce((a, b) => a + b.length, 0);
  assert.equal(tongCanh > 200, true, `chỉ giải được ${tongCanh} cạnh`);
  // Và một cạnh cụ thể phải có thật: chín màn lấy chỗ dựng header từ file lá.
  const tinNhan = join(SRC, "screens/chat/tin-nhan.ts");
  assert.equal(
    (canh.get(tinNhan) ?? []).includes(join(SRC, "danh-tinh.ts")),
    true,
    "không thấy cạnh tin-nhan.ts -> danh-tinh.ts",
  );
});
