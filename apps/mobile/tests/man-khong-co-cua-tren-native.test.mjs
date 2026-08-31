/* Màn nào KHÔNG có cạnh nào dẫn tới trên native — đo bằng đồ thị, không bằng danh sách tay.
 *
 * ## Vì sao file này tồn tại
 *
 * `App.tsx` có hai cây, và chỉ một cây tồn tại trên điện thoại:
 *
 *   - cây THẬT: `<AppRoot>` -> `<VoTab>` -> các tab -> các màn con.
 *   - mười hai trang QUÉT (`XemBinhChon`, `XemNhanMat`, `XemMonCuaToi`, ...),
 *     mở bằng `?man=<tên>`. `manThamSo()` đọc `location.search`, và native
 *     không có `location`. Trên Android/iOS mười hai trang đó không tồn tại.
 *
 * Một màn mà cạnh DUY NHẤT dẫn tới nó đi qua một trang quét là một màn không ai
 * trên điện thoại tới được. Trong Chrome nó vẫn mở được, vẫn chụp ảnh được, vẫn
 * cho `imp detect` một con số đẹp. Đó đúng loại số mà đội này đã đo suốt một
 * ngày rồi mới biết mình đang đo thứ thay thế.
 *
 * `moi-man-co-duong-do.test.mjs` hỏi câu bên cạnh: "cái gì ĐO được màn này".
 * Câu trả lời của nó là một địa chỉ URL — tức là một câu về Chrome. File này
 * hỏi câu còn lại: "có cạnh nào dẫn tới màn này mà không cần `location` không".
 *
 * ## CHỨNG MINH
 *
 * Với mỗi màn dưới `src/screens`, có tồn tại một chuỗi mount từ cây THẬT của
 * `App.tsx` tới nó hay không. Vế trái (danh sách màn) và vế phải (các cạnh) đều
 * ĐỌC RA TỪ NGUỒN, không viết tay — một danh sách tay không tự biết mình thiếu
 * cái màn ai đó thêm ngày mai, mà đó lại đúng là ca file này sinh ra để bắt.
 *
 * Gốc là ĐÚNG MỘT nút: hàm `export default` của App.tsx. Các hàm cấp cao khác
 * trong App.tsx là nút riêng chứ không phải gốc, nên một component cục bộ mà
 * không ai mount sẽ kéo theo mọi màn nó chứa — xem `MAN_LUONG_HERO` và hai
 * canary đi kèm. Cạnh nằm trong một `prop={...}` là cạnh CÓ ĐIỀU KIỆN: nó chỉ
 * sống khi một file đã tới được thật sự viết `prop(`.
 *
 * ## KHÔNG CHỨNG MINH
 *
 * Đây là **CHẶN TRÊN của khả năng tới được**, không phải khả năng tới được.
 *
 *   - Một cạnh có trong đồ thị KHÔNG chứng minh ngón tay đi được qua nó. Màn
 *     con có thể nằm sau một điều kiện không ai thoả (`if (thu == null)`), hay
 *     sau một nút `opacity: 0`. Nên "tới được" ở đây đọc là "chưa bị loại trừ",
 *     không đọc là "đã đi thử".
 *   - Điều kiện của cạnh qua prop chỉ hỏi "còn ai GỌI prop này không", không
 *     hỏi lời gọi ấy có nằm trong nhánh người dùng tới được hay không. Một lời
 *     gọi trong nhánh chết vẫn giữ cạnh sống.
 *   - Ngược lại thì DỨT KHOÁT: KHÔNG có cạnh nào thì không có đường nào. Đó là
 *     giá trị của phép đo này và là lý do nó đáng chạy mỗi lần.
 *   - Không nói gì về cái đẹp, tương phản, cỡ chạm, hay việc màn có render nổi
 *     trên máy Android thật không. Cái đó cần emulator.
 *
 * Chạy từ `apps/mobile`:
 *
 *     node --test tests/man-khong-co-cua-tren-native.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const GOC = join(dirname(fileURLToPath(import.meta.url)), "..");

/* --------------------------------------------------------------- đọc nguồn */

function moiFileTsx(thuMuc) {
  const ra = [];
  for (const ten of readdirSync(thuMuc)) {
    const duong = join(thuMuc, ten);
    if (statSync(duong).isDirectory()) ra.push(...moiFileTsx(duong));
    else if (ten.endsWith(".tsx")) ra.push(relative(GOC, duong));
  }
  return ra;
}

/** Every `.tsx` under `src/`, plus `App.tsx`, as repo-relative paths. */
function moiNguon() {
  return [...moiFileTsx(join(GOC, "src")), "App.tsx"].sort();
}

function docNguon(danhSach) {
  const ra = new Map();
  for (const f of danhSach) ra.set(f, readFileSync(join(GOC, f), "utf8"));
  return ra;
}

/* ------------------------------------------------------------------ đồ thị */

/** Resolve a relative import specifier to a file in `nguon`, or null. */
function giaiDuong(tuFile, spec, nguon) {
  if (!spec.startsWith(".")) return null;
  const goc = resolve("/", dirname(tuFile), spec).slice(1);
  for (const ung of [goc + ".tsx", goc + "/index.tsx"]) {
    if (nguon.has(ung)) return ung;
  }
  return null;
}

const RE_IMPORT = /import\s*(?:\{([^}]*)\}|([A-Z]\w*))\s*from\s*"([^"]+)"/g;

/**
 * file -> tập file nó MOUNT.
 *
 * Một cạnh cần cả hai: import được giải về một file `.tsx` có thật, VÀ tên
 * import đó xuất hiện dạng `<Ten` trong chính file. Chỉ import không đủ — một
 * `import type` hay một helper không phải một cạnh người bấm đi qua được.
 */
function dungCanh(nguon) {
  const canh = new Map();
  for (const [f, s] of nguon) {
    const tap = new Set();
    for (const m of s.matchAll(RE_IMPORT)) {
      const dich = giaiDuong(f, m[3], nguon);
      if (!dich) continue;
      for (const ten of (m[1] ?? m[2] ?? "").match(/[A-Z]\w*/g) ?? []) {
        if (new RegExp("<" + ten + "\\b").test(s)) tap.add(dich);
      }
    }
    canh.set(f, tap);
  }
  return canh;
}

/** Which top-level function in `App.tsx` owns each line. */
function chuCuaDong(nguonApp) {
  const dong = nguonApp.split("\n");
  const ham = [];
  for (let i = 0; i < dong.length; i++) {
    const m = /^(?:export default )?function (\w+)/.exec(dong[i]);
    if (m) ham.push([i, m[1]]);
  }
  return { dong, ham };
}

function chu(ham, i) {
  let cur = "<dau-file>";
  for (const [j, ten] of ham) {
    if (j <= i) cur = ten;
    else break;
  }
  return cur;
}

/* ------------------------------------------- App.tsx là một CÂY, không một nút
 *
 * Bản đầu của file này coi cả `App.tsx` là một nút: mọi dòng `<X` nằm ngoài một
 * hàm `Xem*` đều được tính là GỐC. Đo được rằng đó là một lỗ, và lỗ nằm đúng
 * trên luồng hero:
 *
 *   `LuongKhoanChi` — thân của cả luồng chụp bill -> chia tiền -> VietQR — là
 *   một component CỤC BỘ trong App.tsx. Nó tới được điện thoại qua đúng một sợi
 *   chỉ: `App()` dựng JSX trong prop `renderKhoanChi`, `AppRoot` chuyền tiếp,
 *   `VoTab` GỌI nó. Cắt sợi chỉ đó ở bất kỳ đầu nào là luồng hero chết trên
 *   Android, mà bảng cũ vẫn in `51/54, 3 mồ côi` — vì các dòng `<ChupBill`,
 *   `<GoiYChia`, `<DotThu` vẫn nằm nguyên trong App.tsx, chỉ là không ai mount
 *   cái component chứa chúng nữa.
 *
 * Nên bây giờ mỗi hàm cấp cao của App.tsx là một nút riêng (`App.tsx#App`,
 * `App.tsx#LuongKhoanChi`, ...), và gốc là ĐÚNG MỘT nút: hàm `export default`.
 */

/** Innermost enclosing `prop={...}` for each line, or null. */
function propTheoDong(src) {
  const ra = [];
  const ngan = [];
  let sau = 0;
  let trongDong = null;
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (ch === "\n") {
      ra.push(trongDong);
      trongDong = ngan.length > 0 ? ngan[ngan.length - 1].ten : null;
      continue;
    }
    if (ch === "{") {
      sau++;
      const m = /(\w+)=$/.exec(src.slice(Math.max(0, i - 48), i));
      if (m) ngan.push({ ten: m[1], sau });
    } else if (ch === "}") {
      if (ngan.length > 0 && ngan[ngan.length - 1].sau === sau) ngan.pop();
      sau--;
    }
    if (ngan.length > 0) trongDong = ngan[ngan.length - 1].ten;
  }
  ra.push(trongDong);
  return ra;
}

/** Named imports of `App.tsx` that resolve to a real `.tsx`. */
function nhapCuaApp(nguon) {
  const nhap = new Map();
  for (const m of nguon.get("App.tsx").matchAll(/import\s*\{([^}]*)\}\s*from\s*"(\.[^"]+)"/g)) {
    const dich = giaiDuong("App.tsx", m[2], nguon);
    if (!dich) continue;
    for (const ten of m[1].match(/[A-Z]\w*/g) ?? []) nhap.set(ten, dich);
  }
  return nhap;
}

/** The `export default function` of App.tsx — the single root of the real tree. */
function tenGoc(nguonApp) {
  const m = /export default function (\w+)/.exec(nguonApp);
  return m ? m[1] : null;
}

/**
 * Cạnh trong App.tsx: `App.tsx#<hàm>` -> file, hoặc -> `App.tsx#<hàm cục bộ>`.
 *
 * Cạnh nằm trong một `prop={...}` mang theo tên prop ở `can`: nó là cạnh CÓ
 * ĐIỀU KIỆN, chỉ sống khi có ai đó thật sự GỌI prop ấy (xem `toiDuoc`).
 *
 * Trang quét (`Xem*`) không sinh cạnh: đó là toàn bộ lý do file này tồn tại.
 */
function dungCanhApp(nguon, quet) {
  const app = nguon.get("App.tsx");
  const { dong, ham } = chuCuaDong(app);
  const cucBo = new Set(ham.map(([, t]) => t));
  const nhap = nhapCuaApp(nguon);
  const prop = propTheoDong(app);
  const canh = new Map();
  const them = (tu, dich, can) => {
    if (!canh.has(tu)) canh.set(tu, []);
    canh.get(tu).push({ dich, can });
  };
  for (let i = 0; i < dong.length; i++) {
    const tu = "App.tsx#" + chu(ham, i);
    const can = prop[i] ?? null;
    for (const [ten, dich] of nhap) {
      if (new RegExp("<" + ten + "\\b").test(dong[i])) them(tu, dich, can);
    }
    for (const ten of cucBo) {
      if (quet.has(ten)) continue;
      if (new RegExp("<" + ten + "\\b").test(dong[i])) them(tu, "App.tsx#" + ten, can);
    }
  }
  return canh;
}

/**
 * Điểm bất động: tập tới được lớn dần, cạnh có điều kiện được xét lại mỗi vòng.
 *
 * Điều kiện của một cạnh qua prop `p` là: có một file ĐÃ tới được viết `p(`.
 * Khai báo (`p={...}`, `p:` trong kiểu, `p,` khi destructure) không khớp — chỉ
 * lời GỌI mới khớp. Đây là chặn trên, không phải bằng chứng ngón tay đi qua:
 * nó nói "còn có người gọi", không nói "gọi trong nhánh người dùng tới được".
 */
function toiDuoc(goc, canhApp, canhFile, nguon) {
  const thay = new Set([goc]);
  const goiDuoc = (p) => {
    const re = new RegExp("\\b" + p + "\\s*\\(");
    for (const n of thay) {
      const f = n.startsWith("App.tsx#") ? "App.tsx" : n;
      if (re.test(nguon.get(f) ?? "")) return true;
    }
    return false;
  };
  for (;;) {
    const truoc = thay.size;
    for (const n of [...thay]) {
      if (n.startsWith("App.tsx#")) {
        for (const { dich, can } of canhApp.get(n) ?? []) {
          if (can !== null && !goiDuoc(can)) continue;
          thay.add(dich);
        }
      } else {
        for (const dich of canhFile.get(n) ?? []) thay.add(dich);
      }
    }
    if (thay.size === truoc) return thay;
  }
}

/** Toàn bộ phép đo, trên một bản nguồn có thể bị thay đổi để làm đối chứng. */
function doMotLuot(nguon) {
  const app = nguon.get("App.tsx");
  const { ham } = chuCuaDong(app);
  const quet = new Set(ham.map(([, t]) => t).filter((t) => t.startsWith("Xem")));
  const canhFile = dungCanh(nguon);
  const canhApp = dungCanhApp(nguon, quet);
  const goc = "App.tsx#" + tenGoc(app);
  const thay = toiDuoc(goc, canhApp, canhFile, nguon);
  const man = [...nguon.keys()].filter((f) => f.startsWith("src/screens/")).sort();
  return {
    man,
    quet,
    goc,
    toiDuoc: man.filter((f) => thay.has(f)),
    mocoi: man.filter((f) => !thay.has(f)),
  };
}

const NGUON = docNguon(moiNguon());
const DO = doMotLuot(NGUON);

/* ------------------------------------------------------- nền đo phải đứng
 *
 * Ba ca dưới đây không nói gì về sản phẩm. Chúng nói rằng cái thước còn là
 * thước. Một bảng toàn xanh với thước gãy trông y hệt một bảng toàn xanh.
 */

test("nền: có ít nhất 40 màn được liệt kê, và danh sách đọc từ đĩa", () => {
  assert.ok(
    DO.man.length >= 40,
    `chỉ tìm thấy ${DO.man.length} màn dưới src/screens — phép quét thư mục hỏng, ` +
      "và một danh sách rỗng thì mọi khẳng định dưới đây đều xanh vì không có gì để xét.",
  );
});

test("nền: App.tsx tự khai rằng trang quét đọc location", () => {
  const app = NGUON.get("App.tsx");
  const than = /function manThamSo\(\)[\s\S]{0,400}?\n\}/.exec(app);
  assert.ok(than, "không tìm thấy `manThamSo` trong App.tsx");
  assert.match(
    than[0],
    /location/,
    "`manThamSo` không còn đọc `location`. Nếu nó đọc thứ khác thì cả tiền đề " +
      '"trang quét là web-only" đã đổi, và cổng này đang đo một thứ không còn đúng.',
  );
});

test("nền: mỗi hàm Xem* thật sự nằm sau một nhánh manThamSo()", () => {
  const app = NGUON.get("App.tsx");
  // Một dòng vừa nhắc cổng đọc `location` (`manThamSo` trực tiếp, hoặc `manDo`
  // là hàm chỉ gọi lại nó) vừa mount hàm `Xem*` thì hàm đó nằm sau cổng ấy.
  assert.match(
    app,
    /function manDo\(\)[\s\S]{0,200}?manThamSo\(\)/,
    "`manDo` không còn rẽ theo `manThamSo` — nhánh nó gác đã đổi nghĩa.",
  );
  const dongCong = app.split("\n").filter((d) => /manThamSo\(\)|manDo\(\)/.test(d));
  for (const ten of DO.quet) {
    assert.ok(
      dongCong.some((d) => new RegExp("<" + ten + "\\b").test(d)),
      `\`${ten}\` mang tiền tố Xem nhưng không nằm sau nhánh \`manThamSo()\` nào. ` +
        "Hoặc nó không phải trang quét, hoặc nhánh đã bị đổi — cả hai đều làm " +
        "phép chia cây THẬT / cây QUÉT sai, và mọi con số dưới đây theo đó sai.",
    );
  }
});

/* --------------------------------------------------- ĐỐI CHỨNG DƯƠNG và ÂM
 *
 * Thước phải xếp đúng một màn ai cũng biết là tới được, VÀ phải biết nói KHÔNG
 * với một màn ai cũng biết là không tới được. Thiếu vế nào thì con số còn lại
 * không dùng được.
 */

test("đối chứng dương: Khám phá — tab người ta bấm mỗi ngày — được xếp là TỚI ĐƯỢC", () => {
  assert.ok(
    DO.toiDuoc.includes("src/screens/kham-pha/KhamPha.tsx"),
    "Khám phá bị xếp mồ côi. Đồ thị gãy, và một đồ thị gãy in ra danh sách mồ côi dài đẹp mắt.",
  );
});

test("đối chứng âm: một màn CHỈ trang quét mount được xếp là MỒ CÔI", () => {
  assert.ok(
    DO.mocoi.includes("src/screens/binh-chon/BinhChon.tsx"),
    "BinhChon chỉ được `XemBinhChon` mount (xem `duong-dong-binh-chon.test.mjs`, #402). " +
      "Thước không thấy điều đó thì nó không biết nói KHÔNG.",
  );
});

test("canary: gỡ đúng MỘT dòng mount thì Khám phá phải rơi khỏi tập tới được", () => {
  const gia = new Map(NGUON);
  const votab = "src/navigation/VoTab.tsx";
  const truoc = gia.get(votab);
  assert.match(truoc, /<KhamPha\b/, "VoTab không còn mount KhamPha — neo của canary đã trượt");
  gia.set(votab, truoc.replace(/<KhamPha\b/, "<KhongPhaiKhamPha"));

  const sau = doMotLuot(gia);
  assert.ok(
    sau.mocoi.includes("src/screens/kham-pha/KhamPha.tsx"),
    "Bỏ dòng mount duy nhất của Khám phá mà thước vẫn nói tới được. " +
      "Nghĩa là nó không đọc cạnh — nó đang xanh vì lý do khác.",
  );
});

/* ------------------------------------------- luồng hero treo trên MỘT sợi chỉ
 *
 * `LuongKhoanChi` là component cục bộ trong App.tsx mang cả luồng chụp bill ->
 * chia tiền -> VietQR. Nó tới được điện thoại qua đúng một sợi: `App()` dựng nó
 * trong prop `renderKhoanChi`, `AppRoot` chuyền, `VoTab` gọi. Cắt ở đầu nào
 * cũng làm luồng chết trên Android.
 *
 * Đo được trên bản f8fbf49..221d0a6 (trước thay đổi này): cắt sợi chỉ đó rồi
 * chạy cổng này thì nó vẫn in `51/54, 3 mồ côi, 10/10 xanh` — bảng không đổi
 * một chữ. Chỉ các ca đi bộ trong CHROME bắt được (14 ca đỏ trong `npm test`).
 * Nghĩa là câu hỏi "còn sống trên native không" lúc đó chỉ có Chrome trả lời,
 * mà Chrome đúng là thứ thay thế đội này đang rời bỏ.
 */

const MAN_LUONG_HERO = [
  "src/screens/ChupBill.tsx",
  "src/screens/KetQuaNhanDien.tsx",
  "src/screens/GoiYChia.tsx",
  "src/screens/NhapKhoanChi.tsx",
  "src/screens/DotThu.tsx",
  "src/screens/KetQuaThanhToan.tsx",
  "src/screens/tai-khoan/TaiKhoanNhan.tsx",
];

test("đối chứng dương: cả bảy màn của luồng hero đang được xếp là TỚI ĐƯỢC", () => {
  // Không có ca này thì hai canary dưới xanh một cách rỗng: một thước xếp mọi
  // thứ là mồ côi cũng "bắt" được cả hai mutation.
  for (const f of MAN_LUONG_HERO) {
    assert.ok(DO.toiDuoc.includes(f), `${f} đang bị xếp mồ côi trước khi đột biến gì cả.`);
  }
});

test("nền: dòng mount LuongKhoanChi thật sự nằm trong prop renderKhoanChi", () => {
  // Ghim máy đọc prop vào thực tế. Nếu nó trả null ở đây thì cạnh thành vô
  // điều kiện và canary "VoTab thôi gọi" bên dưới mất hiệu lực trong im lặng.
  const app = NGUON.get("App.tsx");
  const prop = propTheoDong(app);
  const i = app.split("\n").findIndex((d) => /<LuongKhoanChi\b/.test(d));
  assert.ok(i >= 0, "không còn dòng nào mount LuongKhoanChi — neo đã trượt");
  assert.equal(
    prop[i],
    "renderKhoanChi",
    "máy đọc prop không thấy dòng này nằm trong `renderKhoanChi={...}`.",
  );
});

test("canary: App() thôi dựng LuongKhoanChi thì bảy màn luồng hero phải rơi", () => {
  const gia = new Map(NGUON);
  const truoc = gia.get("App.tsx");
  assert.match(truoc, /<LuongKhoanChi\b/, "neo của canary đã trượt");
  gia.set("App.tsx", truoc.replace(/<LuongKhoanChi\b/, "<KhongPhaiLuongKhoanChi"));

  const sau = doMotLuot(gia);
  for (const f of MAN_LUONG_HERO) {
    assert.ok(
      sau.mocoi.includes(f),
      `Cắt mount của LuongKhoanChi mà ${f} vẫn được xếp là tới được. ` +
        "Thước đang tính mọi dòng `<X` trong App.tsx là gốc, kể cả dòng nằm " +
        "trong một component không ai mount — đúng lỗ đã đo được.",
    );
  }
});

test("canary: VoTab thôi GỌI renderKhoanChi thì bảy màn luồng hero phải rơi", () => {
  // Dạng chết thứ hai, tàng hình hơn: dòng `<LuongKhoanChi` vẫn nằm nguyên
  // trong App.tsx, prop vẫn được chuyền qua AppRoot, chỉ là không ai gọi nó.
  const gia = new Map(NGUON);
  const votab = "src/navigation/VoTab.tsx";
  const truoc = gia.get(votab);
  assert.match(truoc, /\brenderKhoanChi\s*\(/, "VoTab không còn gọi renderKhoanChi — neo đã trượt");
  gia.set(votab, truoc.replace(/\brenderKhoanChi\s*\(/g, "khongAiGoiNua("));

  const sau = doMotLuot(gia);
  for (const f of MAN_LUONG_HERO) {
    assert.ok(
      sau.mocoi.includes(f),
      `Prop được chuyền nhưng KHÔNG ai gọi, mà ${f} vẫn được xếp là tới được. ` +
        "Một prop không ai gọi không phải một cạnh.",
    );
  }
});

test("canary: một màn không ai mount phải bị bắt", () => {
  const gia = new Map(NGUON);
  gia.set("src/screens/khong-ai-goi/ManMoCoi.tsx", "export function ManMoCoi() { return null; }\n");
  const sau = doMotLuot(gia);
  assert.ok(
    sau.mocoi.includes("src/screens/khong-ai-goi/ManMoCoi.tsx"),
    "Thêm một màn không ai import mà thước không thấy — cổng này không bắt được " +
      "đúng ca nó sinh ra để bắt.",
  );
});

/* ------------------------------------------------------------ phán quyết
 *
 * Bảng dưới là các màn ĐÃ BIẾT là không có cạnh nào trên native, mỗi cái kèm
 * lý do viết ra thành câu. Giảm bảng này nghĩa là NỐI MỘT CẠNH THẬT hoặc xoá
 * mã chết, không phải xoá một dòng ở đây.
 *
 * Một lý do trong bảng là một LỜI KHAI, không bao giờ là một giấy thông hành.
 */
const MO_COI_DA_KHAI = {
  // #402 đã đo: `votes` 0 dòng, `vote_ballots` 0 dòng. Bình chọn của sản phẩm
  // sống hoàn toàn trong luồng tin nhắn (`cardMoBinhChon` / `cardBoPhieu`), là
  // một hệ khác với `/votes/{id}` mà màn này vẽ. Nối một nút từ thẻ bình chọn
  // trong chat sang đây sẽ ghép hai nguồn số khác nhau vào một màn — đó là
  // cách hai màn hình hiện hai con số cho cùng một cuộc bình chọn, chứ không
  // phải một cạnh còn thiếu.
  "src/screens/binh-chon/BinhChon.tsx":
    "Vỏ cho tuyến /votes mà sản phẩm không ghi vào. Cần một quyết định về việc " +
    "bình chọn sống ở đâu, không phải một nút.",

  // Cần `anhUri` mà `Image.getSize` đọc được. Ảnh thật của nhóm nằm sau
  // `GET /contexts/{cid}/photos/{pid}`, kiểm quyền, nên chỉ tới được qua
  // `taiAnhCoQuyen` -> `blob:` — đường của web. Nối nút từ tường kỷ niệm bây
  // giờ sẽ mở một màn có khung trống trên điện thoại.
  "src/screens/nhan-mat/NhanMatTrenAnh.tsx":
    "Chặn ở đường ẢNH, không ở đường bấm: ảnh nhóm kiểm quyền, mà màn này nhận " +
    "một URI trần.",

  // Không file nào import. Lõi thuần của nó (`extraction.ts`, `review()`) có
  // test riêng và vẫn sống; màn thì không. `TheNhapChiTuChat` là thứ đang ship
  // cho cùng việc đó.
  "src/screens/TheDeXuat.tsx":
    "Không ai import. Trùng việc với TheNhapChiTuChat đang ship — cần một quyết " +
    "định giữ hay xoá, của người sở hữu luồng nhập từ chat.",
};

test("không màn nào mất cửa trên native mà không được khai ra", () => {
  const chuaKhai = DO.mocoi.filter((f) => !(f in MO_COI_DA_KHAI));
  assert.deepEqual(
    chuaKhai,
    [],
    "Màn dưới đây không có CẠNH NÀO dẫn tới trên native, và không có dòng nào " +
      "khai điều đó:\n  " +
      chuaKhai.join("\n  ") +
      "\n\nTrên Android/iOS chúng không mở được bằng bất cứ cú bấm nào. Nối một " +
      "cạnh thật, hoặc thêm một dòng vào `MO_COI_DA_KHAI` nói rõ vì sao chưa nối được.",
  );
});

test("bảng khai không được phình: mỗi dòng phải là một màn thật và thật sự mồ côi", () => {
  for (const f of Object.keys(MO_COI_DA_KHAI)) {
    assert.ok(NGUON.has(f), `\`${f}\` được khai là mồ côi nhưng file không tồn tại.`);
    assert.ok(
      DO.mocoi.includes(f),
      `\`${f}\` đã có cạnh dẫn tới trên native rồi. Xoá nó khỏi \`MO_COI_DA_KHAI\` — ` +
        "một lời khai đã hết đúng là một lời khai che mất màn kế tiếp.",
    );
  }
});

test("số đo in ra để người đọc thấy, không chỉ thấy dấu xanh", () => {
  const tong = DO.man.length;
  const mc = DO.mocoi.length;
  console.log(
    `\n  màn dưới src/screens: ${tong}` +
      `\n  chưa bị loại trừ (có ít nhất một cạnh từ cây THẬT): ${tong - mc}` +
      `\n  KHÔNG có cạnh nào trên native: ${mc}` +
      `\n  trang quét ?man= (web-only, không tính là cạnh): ${DO.quet.size}` +
      "\n  lưu ý: 'có cạnh' là CHẶN TRÊN, không phải 'ngón tay đi được'.\n",
  );
  assert.ok(mc <= Object.keys(MO_COI_DA_KHAI).length);
});
