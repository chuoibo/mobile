/**
 * Hau kiem #431 (69938b7): do do RONG cua diem mu da duoc khai bao o
 * apps/mobile/tools/cap-mau-tinh.mjs.
 *
 * #431 sua mot loi that (chip "Level N" = aiInk tren aiSoft, 1.11:1 sang /
 * 1.10:1 toi) va them mot cong doc cap mau tu AST cho ca 66 man. Cong do CO
 * can: dua loi cu tro lai o dang truc tiep thi no do ngay.
 *
 * Cai probe nay do la: cung DUNG mot loi do, viet qua mot bien cuc bo, thi
 * bien mat khoi cong — va ba co che chong muc ruong cua chinh #431 (dem
 * boQua, san coverage, neo hoi quy) deu khong keu.
 *
 * Docstring cua cong CO ghi rang mau di qua bien khong duoc giai va roi vao
 * boQua. Probe nay khong to cong noi doi; no do xem loi khai bao do co lam
 * san coverage va neo hoi quy vo hieu hay khong.
 *
 * Chay:  node tests/qa/qa-tt-0054/do-mu-cua-cong-cap-mau.mjs
 * Thoat: 0 = diem mu dung nhu mo ta   2 = ket qua khac mo ta, doc lai
 */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const GOC_MOBILE = resolve(
  new URL(".", import.meta.url).pathname,
  "../../../apps/mobile",
);
const { quetFile, timTsx } = await import(
  join(GOC_MOBILE, "tools/cap-mau-tinh.mjs")
);

/** Ghi mot mau .tsx ra dia roi quet no — cung cach test cua #431 lam. */
function quetMau(nguon) {
  const d = mkdtempSync(join(tmpdir(), "qa-tt-0054-"));
  try {
    const f = join(d, "Mau.tsx");
    writeFileSync(f, nguon, "utf8");
    return quetFile(f);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
}

/* Dang A: dung cai loi #431 da sua, viet truc tiep. Day la DOI CHUNG DUONG —
 * neu dang nay khong do thi probe hong, khong phai cong hong. */
const DANG_TRUC_TIEP = `
  export function Mau() {
    const c = usePalette();
    return (
      <View style={{ backgroundColor: c.aiSoft }}>
        <Text style={{ ...type.label, color: c.aiInk }}>Level 3</Text>
      </View>
    );
  }
`;

/* Dang B: DUNG hai token do, dung mot cap mau do, chi khac cho dat ten. Day
 * la mot buoc refactor ma khong reviewer nao chan lai. */
const DANG_QUA_BIEN = `
  export function Mau() {
    const c = usePalette();
    const nenChip = c.aiSoft;
    const mucChip = c.aiInk;
    return (
      <View style={{ backgroundColor: nenChip }}>
        <Text style={{ ...type.label, color: mucChip }}>Level 3</Text>
      </View>
    );
  }
`;

const a = quetMau(DANG_TRUC_TIEP);
const b = quetMau(DANG_QUA_BIEN);

/* San coverage that cua #431: soCap > 300, tren toan bo src/. */
const ket = timTsx(join(GOC_MOBILE, "src")).map((f) => quetFile(f));
const soCap = ket.reduce((t, k) => t + k.soCap, 0);
const SAN = 300;

console.log("== hau kiem #431 tai 69938b7 ==");
console.log(`dang TRUC TIEP  : ${a.loi.length} loi   <- doi chung duong`);
console.log(`dang QUA BIEN   : ${b.loi.length} loi   <- cung mot cap mau`);
console.log(`san coverage    : soCap=${soCap}, san=${SAN}`);
console.log(
  `                  mat toi ${soCap - SAN - 1} cap (${(((soCap - SAN - 1) / soCap) * 100).toFixed(1)}%) van XANH`,
);

const nhuMoTa = a.loi.length > 0 && b.loi.length === 0 && soCap > SAN * 2;
if (!nhuMoTa) {
  console.log("\nKHAC MO TA: doc lai truoc khi trich dan probe nay.");
  process.exit(2);
}
console.log(
  "\nDiem mu dung nhu mo ta: cung mot cap mau, doi cho dat ten thi cong het thay.",
);
process.exit(0);
