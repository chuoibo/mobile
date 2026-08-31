/* Bảng đột biến cho `tests/duong-vao-xa-hoi.test.mjs`.
 *
 * Một dấu xanh không nói được ca nào TREO vào dòng nào. #488 đã đỏ đúng vì
 * chuyện đó: cổng bắt 7/7 cast, mà bỏ một dòng lái thì 550 ca vẫn xanh với hồi
 * quy còn sống. Nên mỗi cạnh ở đây bị cắt riêng, và bảng in ra ca nào đỏ theo.
 *
 * Cách chạy (từ `apps/mobile/`):
 *
 *     node tools/dot-bien-duong-bam.mjs
 *
 * Mỗi lượt: sửa một dòng trong `src/`, dựng lại web export (~7s), chạy file
 * test, rồi `git checkout` trả lại. Cây phải SẠCH trước khi chạy — script từ
 * chối chạy nếu không, vì `git checkout` cuối mỗi lượt sẽ nuốt mất bản sửa
 * đang dở của người chạy.
 *
 * Hàng CANARY chạy trước và không đột biến gì: nếu nền không xanh thì mọi ô đỏ
 * phía dưới đều vô nghĩa, và một bảng toàn đỏ không phân biệt được cái gì đang
 * được gác với cái gì chỉ đang hỏng.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const MUC = [
  {
    ma: "CANARY",
    y: "nền sạch, không đột biến — mọi ca phải xanh",
    file: null,
  },
  {
    ma: "M1",
    y: "F37: hàng [+] 'Album chuyến đi' không mở luồng album nữa",
    file: "src/navigation/VoTab.tsx",
    tu: "album: () => setLuongAlbum(true),",
    thanh: "album: () => {},",
  },
  {
    ma: "M2",
    y: "F37: nút 'Dựng thước phim' ở đáy đường không gọi reel nữa",
    file: "src/screens/album/AlbumChuyenDi.tsx",
    tu: '<NutVien nhan="Dựng thước phim" onPress={onXemPhim} chinh />',
    thanh: '<NutVien nhan="Dựng thước phim" onPress={() => {}} chinh />',
  },
  {
    ma: "M3",
    y: "F40+F41: hàng [+] 'Kỷ niệm nhóm' không mở tường nữa",
    file: "src/navigation/VoTab.tsx",
    tu: '"ky-niem": () => setLuongKyNiem(true),',
    thanh: '"ky-niem": () => {},',
  },
  {
    ma: "M4",
    y: "F40: trái tim trên thẻ ảnh không gọi /reactions nữa",
    file: "src/screens/ky-niem/TimVaBinhLuan.tsx",
    tu: "          onPress={doiTim}",
    thanh: "          onPress={() => {}}",
  },
  {
    ma: "M5",
    y: "F41: nút bình luận không mở ô soạn nữa",
    file: "src/screens/ky-niem/TimVaBinhLuan.tsx",
    tu: "          onPress={onDoiMoRong}",
    thanh: "          onPress={() => {}}",
  },
  {
    ma: "M6",
    y: "F42: nút 'Viết lên tường' không mở ô soạn nữa",
    file: "src/screens/ca-nhan/Tuong.tsx",
    tu: 'onPress={() => setMoSoan(true)}',
    thanh: 'onPress={() => {}}',
  },
  {
    ma: "M7",
    y: "F42: bấm một mức người đọc không đổi lựa chọn nữa",
    file: "src/screens/ca-nhan/Tuong.tsx",
    tu: "onPress={() => chonMuc(muc)}",
    thanh: "onPress={() => {}}",
  },
  {
    ma: "M8",
    y: "ĐỐI CHỨNG: hàng [+] 'Tạo khoản chi' không mở luồng khoản chi nữa",
    file: "src/navigation/VoTab.tsx",
    tu: '"khoan-chi": () => setLuongKhoanChi(true),',
    thanh: '"khoan-chi": () => {},',
  },
];

function chay(lenh, args) {
  try {
    return { ma: 0, ra: execFileSync(lenh, args, { encoding: "utf8", stdio: "pipe" }) };
  } catch (err) {
    return { ma: err.status ?? 1, ra: `${err.stdout ?? ""}${err.stderr ?? ""}` };
  }
}

/** Tên những ca ĐỎ, đọc từ dòng TAP `not ok N - <tên>`. */
function caDo(ra) {
  return [...ra.matchAll(/^\s*not ok \d+ - (.+)$/gm)]
    .map((m) => m[1].trim())
    .filter((t) => !t.startsWith("từ shell bấm được"));
}

const ban = chay("git", ["status", "--porcelain", "--", "src", "App.tsx"]);
if (ban.ra.trim()) {
  console.error("cây src/ không sạch; script này sẽ git checkout đè lên. Dừng.\n" + ban.ra);
  process.exit(2);
}

const bang = [];
for (const m of MUC) {
  if (m.file) {
    const truoc = readFileSync(m.file, "utf8");
    const dem = truoc.split(m.tu).length - 1;
    if (dem !== 1) {
      // Neo trượt là kiểu hỏng nguy hiểm nhất ở đây: nó in ra XANH, và cái
      // xanh đó đọc y hệt "đột biến không bị bắt". Dừng, đừng đoán.
      console.error(`${m.ma}: neo khớp ${dem} lần trong ${m.file} (cần đúng 1). Dừng.`);
      process.exit(2);
    }
    writeFileSync(m.file, truoc.replace(m.tu, m.thanh));
  }

  const dung = chay("npm", ["run", "build:check"]);
  if (dung.ma !== 0) {
    console.error(`${m.ma}: dựng export hỏng\n${dung.ra.slice(-2000)}`);
    if (m.file) chay("git", ["checkout", "--", m.file]);
    process.exit(2);
  }

  const kq = chay("node", ["--test", "tests/duong-vao-xa-hoi.test.mjs"]);
  const do_ = caDo(kq.ra);
  const so = kq.ra.match(/# pass (\d+)[\s\S]*?# fail (\d+)/);
  bang.push({ ma: m.ma, y: m.y, pass: so?.[1] ?? "?", fail: so?.[2] ?? "?", do: do_ });

  if (m.file) chay("git", ["checkout", "--", m.file]);
  console.log(`${m.ma}  pass ${so?.[1] ?? "?"} / fail ${so?.[2] ?? "?"}  ${m.y}`);
  for (const t of do_) console.log(`        ĐỎ: ${t}`);
}

console.log("\n=== bảng ===");
for (const h of bang) {
  console.log(`${h.ma.padEnd(7)} pass=${String(h.pass).padEnd(2)} fail=${String(h.fail).padEnd(2)} ${h.y}`);
  for (const t of h.do) console.log(`        ${t}`);
}

// Dựng lại lần cuối để cây không ở lại với export của đột biến cuối cùng.
chay("npm", ["run", "build:check"]);
