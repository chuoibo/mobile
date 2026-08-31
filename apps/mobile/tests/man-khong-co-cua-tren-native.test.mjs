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
 * ## KHÔNG CHỨNG MINH
 *
 * Đây là **CHẶN TRÊN của khả năng tới được**, không phải khả năng tới được.
 *
 *   - Một cạnh có trong đồ thị KHÔNG chứng minh ngón tay đi được qua nó. Màn
 *     con có thể nằm sau một điều kiện không ai thoả (`if (thu == null)`), sau
 *     một prop chỉ fragment mới truyền, hay sau một nút `opacity: 0`. Nên
 *     "tới được" ở đây đọc là "chưa bị loại trừ", không đọc là "đã đi thử".
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

/**
 * Gốc của cây THẬT: mọi màn `App.tsx` mount ở NGOÀI các trang quét.
 *
 * "Trang quét" nhận diện bằng tiền tố `Xem`, và cái tên đó KHÔNG được tin
 * suông — `cuaQuetDocLocation` dưới đây bắt `App.tsx` tự khai rằng `manThamSo`
 * đọc `location`, và ca "trang quét phải rẽ qua manThamSo" bắt mỗi hàm `Xem*`
 * thật sự nằm sau một nhánh `manThamSo()`. Không có hai ca đó thì đổi tên hàm
 * là gỡ được cổng trong im lặng.
 */
function goCayThat(nguon) {
  const { dong, ham } = chuCuaDong(nguon.get("App.tsx"));
  const quet = new Set(ham.map(([, t]) => t).filter((t) => t.startsWith("Xem")));
  const nhap = new Map();
  for (const m of nguon.get("App.tsx").matchAll(/import\s*\{([^}]*)\}\s*from\s*"(\.[^"]+)"/g)) {
    const dich = giaiDuong("App.tsx", m[2], nguon);
    if (!dich) continue;
    for (const ten of m[1].match(/[A-Z]\w*/g) ?? []) nhap.set(ten, dich);
  }
  const goc = new Set();
  for (let i = 0; i < dong.length; i++) {
    if (quet.has(chu(ham, i))) continue;
    for (const [ten, dich] of nhap) {
      if (new RegExp("<" + ten + "\\b").test(dong[i])) goc.add(dich);
    }
  }
  return { goc, quet };
}

function toiDuoc(goc, canh) {
  const thay = new Set(goc);
  const chong = [...goc];
  while (chong.length > 0) {
    for (const dich of canh.get(chong.pop()) ?? []) {
      if (!thay.has(dich)) {
        thay.add(dich);
        chong.push(dich);
      }
    }
  }
  return thay;
}

/** Toàn bộ phép đo, trên một bản nguồn có thể bị thay đổi để làm đối chứng. */
function doMotLuot(nguon) {
  const canh = dungCanh(nguon);
  const { goc, quet } = goCayThat(nguon);
  const thay = toiDuoc(goc, canh);
  const man = [...nguon.keys()].filter((f) => f.startsWith("src/screens/")).sort();
  return {
    man,
    quet,
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
