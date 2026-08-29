/** Why a card is parsed before anything of it is drawn.
 *
 * The AI's itinerary arrives as `card`, and `card` is a free dict. There is
 * no schema on the wire and rd-be-04 (the work that would give the dict a
 * contract) is not on the server yet. A screen that renders `undefined` for a
 * missing time looks like a styling bug and gets chased in the wrong file for
 * an hour; a parser that drops the stage and keeps the rest is read once.
 *
 * The other trap is money. This product has one splitter, and it lives on the
 * server behind 41 hand-computed golden vectors. `tongDuTinhVnd` and
 * `duTinhMoiNguoiVnd` are shown when the server sent them and omitted when it
 * did not. Deriving one from the other (`tổng / số người`) would be a second
 * implementation of a division this client is forbidden to perform, and it
 * would be wrong the moment the server rounded. Integer đồng only; a
 * fractional đồng is refused as "not a number we can print" rather than
 * rounded into something that looks fine.
 *
 * `keHoachTuCard` returning `null` is the honest answer for garbage, a
 * missing title, an empty day list, or `null` itself. The screen then says
 * there is no plan yet -- the same rule as a missing `GET /places`, for the
 * same reason: a canned itinerary on screen is indistinguishable from one
 * the model wrote, and that is the thing the acceptance criteria forbid.
 */

export type Chang = {
  gio: string;
  ten: string;
  ghiChu?: string;
  loai?: string;
};

export type Ngay = {
  nhan: string;
  chang: Chang[];
};

export type KeHoach = {
  tieuDe: string;
  khoang?: string;
  soNguoi?: number;
  duTinhMoiNguoiVnd?: number;
  tongDuTinhVnd?: number;
  ngay: Ngay[];
  tomTat?: string[];
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function chuoi(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Integer đồng, or nothing. A float here is a server defect, not a rounding. */
function nguyenDong(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isInteger(value) || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

function soNguyen(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isInteger(value) || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

function docChang(raw: unknown): Chang | null {
  const o = asRecord(raw);
  if (!o) return null;
  const gio = chuoi(o.gio);
  const ten = chuoi(o.ten);
  // A stage with no time or no name would render the word "undefined" on the
  // timeline. Dropping the row is the whole point of parsing first.
  if (!gio || !ten) return null;
  const chang: Chang = { gio, ten };
  const ghiChu = chuoi(o.ghiChu);
  if (ghiChu) chang.ghiChu = ghiChu;
  const loai = chuoi(o.loai);
  if (loai) chang.loai = loai;
  return chang;
}

function docNgay(raw: unknown): Ngay | null {
  const o = asRecord(raw);
  if (!o) return null;
  const nhan = chuoi(o.nhan);
  if (!nhan || !Array.isArray(o.chang)) return null;
  const chang = o.chang.map(docChang).filter((c): c is Chang => c !== null);
  if (chang.length === 0) return null;
  return { nhan, chang };
}

/**
 * Turn one free-form `card` into a plan the screen can draw, or `null`.
 *
 * Never throws. A thrown card would blank the Plan tab, which is a worse
 * outcome than an empty state that says there is nothing to show.
 */
export function keHoachTuCard(card: unknown): KeHoach | null {
  const o = asRecord(card);
  if (!o) return null;
  const tieuDe = chuoi(o.tieuDe);
  if (!tieuDe || !Array.isArray(o.ngay)) return null;
  const ngay = o.ngay.map(docNgay).filter((n): n is Ngay => n !== null);
  // An empty day list after dropping broken stages is the same as a missing
  // plan: there is nothing to put on the timeline, so refuse rather than
  // draw a title over a blank column.
  if (ngay.length === 0) return null;
  const keHoach: KeHoach = { tieuDe, ngay };
  const khoang = chuoi(o.khoang);
  if (khoang) keHoach.khoang = khoang;
  const soNguoi = soNguyen(o.soNguoi);
  if (soNguoi !== null) keHoach.soNguoi = soNguoi;
  const duTinhMoiNguoiVnd = nguyenDong(o.duTinhMoiNguoiVnd);
  if (duTinhMoiNguoiVnd !== null) keHoach.duTinhMoiNguoiVnd = duTinhMoiNguoiVnd;
  const tongDuTinhVnd = nguyenDong(o.tongDuTinhVnd);
  if (tongDuTinhVnd !== null) keHoach.tongDuTinhVnd = tongDuTinhVnd;
  if (Array.isArray(o.tomTat)) {
    const tomTat = o.tomTat.map(chuoi).filter((s): s is string => s !== null);
    if (tomTat.length > 0) keHoach.tomTat = tomTat;
  }
  return keHoach;
}

/**
 * Money as Vietnamese writes it: `17.500.000đ`.
 *
 * `Intl` is not used. Hermes ships without full ICU unless the app opts into
 * a larger binary, and `toLocaleString` there silently falls back to the C
 * locale, which groups with commas. Formatting is not computing: grouping
 * digits does not invent a share.
 */
export function dinhDangTienVnd(amount: number): string {
  const negative = amount < 0;
  const digits = Math.abs(Math.trunc(amount)).toString();
  let grouped = "";
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) grouped += ".";
    grouped += digits[i];
  }
  return `${negative ? "-" : ""}${grouped}đ`;
}
