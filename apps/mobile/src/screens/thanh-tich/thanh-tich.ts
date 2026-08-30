/** Turning one person's ledger into the achievements screen's numbers.
 *
 * ## Where the numbers come from, and why that mattered more than the layout
 *
 * The mockup (`product/RuDi_Mobile_Product_Mockups/07_profile_finance/03_
 * achievements/`) draws a fully populated screen: 12 chuyến đi, 34 check-in, 18
 * bill đã chia, 780/1000 điểm, six lit badges and three weekly challenges. Not
 * one of those figures has a table behind it in this product, so the whole
 * screen could have been typed in as constants and would have looked exactly
 * like the mockup. That is the failure `CaNhan.tsx` states in its own header:
 * "a shell is not a defect; a shell wearing real data's clothes is."
 *
 * So every figure this module returns is derived from `GET
 * /people/{id}/finance` -- the same self-only route the Cá nhân tab already
 * reads -- and anything that route cannot answer is returned as an explicit
 * "chưa đo được" carrying the reason, never as a plausible number.
 *
 * What the ledger genuinely knows, and what each thing here is built from:
 *
 *   expense_count      how many expenses this person is in
 *   group_count        how many groups they belong to
 *   outstanding_vnd    what they still owe
 *   movements[]        confirmed arrivals, each with occurred_at + context_id
 *
 * `movements` is the interesting one and the reason the weekly challenges are
 * real rather than decorative: it carries a timestamp per row, so "trong 7
 * ngày" is a filter over data the server sent, not a guess.
 *
 * What it cannot answer: trips, check-ins, photographs, places visited. There
 * are no such tables anywhere in this product. Badges resting on those come
 * back `chua-do-duoc` with the missing table named, which reads as an honest
 * locked badge and is one.
 *
 * ## No money arithmetic happens here
 *
 * `outstanding_vnd` is compared against zero and never added, subtracted or
 * split. Points are not money and the three money laws do not reach them; the
 * ledger's own numbers are passed through untouched, which is the rule
 * `tai-chinh.ts` states and the reason this file does not do sums on đồng.
 */
import type { Finance, Movement } from "../ca-nhan/tai-chinh";

/** How a point is earned. Exported because the screen prints the rule.
 *
 * A level nobody can explain is the thing the mockup's own spec argues against
 * ("Achievement criteria phải deterministic và explainable", §4). These three
 * numbers are the whole scoring system, they are shown to the person on the
 * screen, and the same input always produces the same level.
 *
 * They are a DEMO rule. No server scores anybody; there is no achievements
 * table, no points column, and nothing anywhere else in this product reads
 * them. The screen says that in as many words rather than leaving the reader
 * to assume a backend.
 */
export const DIEM_MOI_KHOAN_CHI = 10;
export const DIEM_MOI_NHOM = 25;
export const DIEM_MOI_CAP = 100;

/** Seven days, in milliseconds. The window the weekly challenges measure. */
export const TUAN_MS = 7 * 24 * 60 * 60 * 1000;

export type TienDoCap = {
  /** Total points, from the rule above. */
  diem: number;
  /** Current level. Starts at 1, never 0: a person with nothing has a level. */
  cap: number;
  /** Points earned inside the current level. */
  diemTrongCap: number;
  /** Points one level costs. Constant, but returned so the bar never has to
   *  re-derive it and the two cannot disagree. */
  diemMoiCap: number;
  /** The level being worked toward. */
  capSau: number;
};

/**
 * Level and progress, from the two counts the ledger can answer.
 *
 * Integer arithmetic throughout. A progress bar built on a float would be
 * invisible drift rather than a wrong number, but this repo has one rule about
 * intermediate values and keeping it here costs nothing.
 */
export function tienDoCapDo(so: Finance): TienDoCap {
  const diem = so.expense_count * DIEM_MOI_KHOAN_CHI + so.group_count * DIEM_MOI_NHOM;
  const capDaQua = Math.floor(diem / DIEM_MOI_CAP);
  return {
    diem,
    cap: capDaQua + 1,
    diemTrongCap: diem - capDaQua * DIEM_MOI_CAP,
    diemMoiCap: DIEM_MOI_CAP,
    capSau: capDaQua + 2,
  };
}

/** Three states, and the third is the one this screen exists to tell apart.
 *
 * `chua-dat` means measured and not yet earned: the ledger answered and the
 * answer was below the bar. `chua-do-duoc` means nothing measured it at all.
 * Drawing both as a grey padlock would merge "keep going" with "this product
 * cannot see that", which are opposite messages for the person reading.
 */
export type TrangThaiHuyHieu = "mo" | "chua-dat" | "chua-do-duoc";

export type HuyHieu = {
  id: string;
  ten: string;
  /** The rule, in words, always shown. A badge whose criterion is hidden is a
   *  badge nobody can aim at. */
  dieuKien: string;
  trangThai: TrangThaiHuyHieu;
  /** Progress toward the bar, for measured badges only. */
  daDat?: number;
  can?: number;
  /** Which table is missing, for `chua-do-duoc` badges only. */
  thieuGi?: string;
};

/**
 * The badge grid.
 *
 * The mockup draws eight. Four of them rest on things the ledger genuinely
 * knows and so can actually light up while somebody uses the demo -- split a
 * bill, come back, watch one open. The other four keep the mockup's names and
 * say plainly which table this product would need before they could mean
 * anything.
 *
 * The order is fixed and measured-first, so the grid reads as "here is what
 * you have earned" before "here is what is not built yet".
 */
export function huyHieuCuaNguoi(so: Finance): HuyHieu[] {
  const doDuoc = (id: string, ten: string, dieuKien: string, daDat: number, can: number): HuyHieu => ({
    id,
    ten,
    dieuKien,
    trangThai: daDat >= can ? "mo" : "chua-dat",
    daDat,
    can,
  });
  const chuaDoDuoc = (id: string, ten: string, dieuKien: string, thieuGi: string): HuyHieu => ({
    id,
    ten,
    dieuKien,
    trangThai: "chua-do-duoc",
    thieuGi,
  });

  // `sòng phẳng` is binary, so it is expressed as 1-of-1 rather than given a
  // separate shape: one code path draws every measured badge, and a state with
  // its own rendering is a state nobody keeps working.
  const soPhang = so.expense_count > 0 && so.outstanding_vnd === 0 ? 1 : 0;

  return [
    doDuoc("mo-hang", "Mở hàng", "Chia khoản chi đầu tiên", so.expense_count, 1),
    doDuoc("bill-hero", "Bill Hero", "Có mặt trong 5 khoản chi", so.expense_count, 5),
    doDuoc("trip-planner", "Trip Planner", "Đi cùng 2 nhóm khác nhau", so.group_count, 2),
    doDuoc("song-phang", "Sòng phẳng", "Trả hết phần mình đang nợ", soPhang, 1),
    chuaDoDuoc(
      "food-hunter",
      "Food Hunter",
      "Check-in 10 quán ăn",
      "sản phẩm chưa có bảng đếm check-in theo người",
    ),
    chuaDoDuoc(
      "photographer",
      "Photographer",
      "Đăng 20 tấm ảnh vào kỷ niệm nhóm",
      "ảnh kỷ niệm chưa được đếm theo người đăng",
    ),
    chuaDoDuoc(
      "explorer",
      "Explorer",
      "Tới 15 địa điểm khác nhau",
      "chưa có bảng địa điểm đã tới của một người",
    ),
    chuaDoDuoc(
      "master-traveler",
      "Master Traveler",
      "Đi 20 chuyến",
      "chưa có bảng chuyến đi tính theo người",
    ),
  ];
}

/** How many confirmed arrivals landed inside the window ending at `bayGio`.
 *
 * Rows the server sent with an unparseable date are dropped rather than
 * counted: a `NaN` comparison is false in both directions, so a bad row would
 * otherwise sit permanently outside every window while still inflating nothing
 * -- but being explicit costs one line and makes the behaviour testable.
 */
export function soGiaoDichTrongTuan(movements: Movement[], bayGio: number): number {
  const tu = bayGio - TUAN_MS;
  let n = 0;
  for (const m of movements) {
    const at = new Date(m.occurred_at).getTime();
    if (Number.isNaN(at)) continue;
    if (at >= tu && at <= bayGio) n += 1;
  }
  return n;
}

/** How many distinct groups this person has actually moved money in. */
export function soNhomDaChuyenTien(movements: Movement[]): number {
  return new Set(movements.map((m) => m.context_id)).size;
}

export type ThuThach = {
  id: string;
  ten: string;
  daDat: number;
  can: number;
  xong: boolean;
};

/**
 * The three weekly challenges, all measured.
 *
 * This card was the one at real risk of becoming decoration. "Thử thách tuần
 * này" needs a time window, and a screen with no clock would have had to either
 * invent progress or draw three empty bars. `movements[].occurred_at` is what
 * makes it honest: the server timestamps every confirmed arrival, so a seven
 * day window is a filter over real rows.
 *
 * `bayGio` is a parameter rather than a call to `Date.now()` inside the loop.
 * A frozen clock is how a time-windowed test passes while measuring nothing,
 * so the tests hand in the instant and the screen hands in the real one.
 */
export function thuThachTuan(so: Finance, bayGio: number): ThuThach[] {
  const trongTuan = soGiaoDichTrongTuan(so.movements, bayGio);
  const nhomDaChuyen = soNhomDaChuyenTien(so.movements);
  const raw: { id: string; ten: string; daDat: number; can: number }[] = [
    { id: "giao-dich-tuan", ten: "Xác nhận 2 giao dịch trong 7 ngày", daDat: trongTuan, can: 2 },
    { id: "hai-nhom", ten: "Chuyển tiền ở 2 nhóm khác nhau", daDat: nhomDaChuyen, can: 2 },
    {
      id: "het-no",
      ten: "Về 0 đồng còn nợ",
      daDat: so.outstanding_vnd === 0 ? 1 : 0,
      can: 1,
    },
  ];
  return raw.map((t) => ({ ...t, xong: t.daDat >= t.can }));
}

/** `2/3`, and never `2/0`. The denominator is a constant in every caller, but
 *  printing a fraction is the kind of thing that outlives the constant. */
export function phanSo(daDat: number, can: number): string {
  return `${Math.min(daDat, can)}/${can}`;
}

/** How full a bar is, 0 to 1, clamped. Returns 0 rather than dividing by zero. */
export function tiLe(daDat: number, can: number): number {
  if (can <= 0) return 0;
  return Math.max(0, Math.min(1, daDat / can));
}
