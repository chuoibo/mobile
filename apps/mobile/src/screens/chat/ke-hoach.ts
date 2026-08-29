/** Why a card is parsed before anything of it is drawn.
 *
 * The AI's answer arrives as `card`, a free dict on the wire. A screen that
 * renders `undefined` for a missing time looks like a styling bug and gets
 * chased in the wrong file for an hour; a parser that drops the stage and
 * keeps the rest is read once.
 *
 * THIS FILE WAS REWRITTEN AGAINST THE REAL CONTRACT. The first version was
 * written while rd-be-04 was still unmerged, against a shape guessed from the
 * mockup: `{tieuDe, ngay: [{nhan, chang: [...]}], tongDuTinhVnd, soNguoi}`.
 * rd-be-04 landed (main @ 7e1db9a) and the shape the server actually emits is
 * `{kind, payload}` with three kinds. Every field name in the guess was wrong.
 * Keeping the guess would have meant `keHoachTuCard` returning `null` for
 * every real card and the Plan tab reading "chưa có kế hoạch" forever, while
 * the tests stayed green because they fed it the guessed shape.
 *
 * Two things the real contract does NOT have, and which this file therefore
 * refuses to invent:
 *
 *  1. NO DAY GROUPING. `stops` is one flat list. The mockup draws "Ngày 1 /
 *     Ngày 2" tabs and the task sheet asked for them, but nothing on the wire
 *     says which stop belongs to which day. Splitting the list on a guess (by
 *     count, or by parsing `time_text` for a wrap-around) would put a day
 *     boundary on screen that the server never asserted. One timeline.
 *  2. NO MONEY TOTALS. `ground_card` rebuilds the payload from a key
 *     whitelist, and that whitelist has no `amount`, no `total`, no
 *     `per_person` -- deliberately, so a model cannot invent a number that
 *     looks like a settled share. The only money here is `price_min_vnd` /
 *     `price_max_vnd`, copied from the server's own place catalogue. This
 *     client adds nothing up. This product has one splitter and it lives on
 *     the server behind 41 hand-computed golden vectors.
 *
 * `theTuCard` returning `null` is the honest answer for garbage, an unknown
 * kind, or an empty list. The screen then says there is no plan yet -- the
 * same rule as a missing `GET /places`, for the same reason: a canned
 * itinerary on screen is indistinguishable from one the model wrote, and that
 * is the thing the acceptance criteria forbid.
 */

/** A place record. Copied from the server catalogue by `ground_card`; the
 *  model only ever chose its `id`, so every field here is server-owned. */
export type DiaDiem = {
  id: string;
  ten: string;
  diaChi?: string;
  giaMinVnd?: number;
  giaMaxVnd?: number;
  danhGia?: number;
  cachKm?: number;
  gioMo?: string;
  loai?: string;
};

export type Chang = {
  gio: string;
  ghiChu?: string;
  diaDiem: DiaDiem;
};

export type TheAi =
  | { kind: "text"; text: string }
  | { kind: "places"; intro?: string; diaDiem: DiaDiem[] }
  | { kind: "itinerary"; tieuDe: string; chang: Chang[] };

/** The itinerary variant, which is the one screen 2 draws. */
export type KeHoach = Extract<TheAi, { kind: "itinerary" }>;

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

/** Ratings and distances are genuinely fractional, unlike money. */
function soThuc(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function docDiaDiem(raw: unknown): DiaDiem | null {
  const o = asRecord(raw);
  if (!o) return null;
  const id = chuoi(o.id);
  const ten = chuoi(o.name);
  // Without an id and a name there is nothing to show and nothing to link to.
  if (!id || !ten) return null;
  const diaDiem: DiaDiem = { id, ten };
  const diaChi = chuoi(o.address);
  if (diaChi) diaDiem.diaChi = diaChi;
  const giaMin = nguyenDong(o.price_min_vnd);
  if (giaMin !== null) diaDiem.giaMinVnd = giaMin;
  const giaMax = nguyenDong(o.price_max_vnd);
  if (giaMax !== null) diaDiem.giaMaxVnd = giaMax;
  const danhGia = soThuc(o.rating);
  if (danhGia !== null) diaDiem.danhGia = danhGia;
  const cachKm = soThuc(o.distance_km);
  if (cachKm !== null) diaDiem.cachKm = cachKm;
  const gioMo = chuoi(o.open_hours);
  if (gioMo) diaDiem.gioMo = gioMo;
  const loai = chuoi(o.category);
  if (loai) diaDiem.loai = loai;
  return diaDiem;
}

function docChang(raw: unknown): Chang | null {
  const o = asRecord(raw);
  if (!o) return null;
  const gio = chuoi(o.time_text);
  const diaDiem = docDiaDiem(o.place);
  // A stage with no time or no place would render the word "undefined" on the
  // timeline. Dropping the row is the whole point of parsing first.
  if (!gio || !diaDiem) return null;
  const chang: Chang = { gio, diaDiem };
  const ghiChu = chuoi(o.note);
  if (ghiChu) chang.ghiChu = ghiChu;
  return chang;
}

/**
 * Turn one free-form `card` into something the screen can draw, or `null`.
 *
 * Never throws. A thrown card would blank the whole thread, which is a worse
 * outcome than one bubble that says it could not read the answer.
 */
export function theTuCard(card: unknown): TheAi | null {
  const o = asRecord(card);
  if (!o) return null;
  const payload = asRecord(o.payload);
  if (!payload) return null;

  if (o.kind === "text") {
    const text = chuoi(payload.text);
    return text ? { kind: "text", text } : null;
  }

  if (o.kind === "places") {
    if (!Array.isArray(payload.places)) return null;
    const diaDiem = payload.places
      .map(docDiaDiem)
      .filter((d): d is DiaDiem => d !== null);
    if (diaDiem.length === 0) return null;
    const the: Extract<TheAi, { kind: "places" }> = { kind: "places", diaDiem };
    const intro = chuoi(payload.intro);
    if (intro) the.intro = intro;
    return the;
  }

  if (o.kind === "itinerary") {
    const tieuDe = chuoi(payload.title);
    if (!tieuDe || !Array.isArray(payload.stops)) return null;
    const chang = payload.stops.map(docChang).filter((c): c is Chang => c !== null);
    // An empty stop list after dropping broken rows is the same as a missing
    // plan: there is nothing to put on the timeline, so refuse rather than
    // draw a title over a blank column.
    if (chang.length === 0) return null;
    return { kind: "itinerary", tieuDe, chang };
  }

  // Unknown kind. The server rejects these before they are stored, so one
  // arriving here means the client is older than the server, not that the
  // model misbehaved. Either way there is no safe way to draw it.
  return null;
}

/** Narrow to the itinerary kind, for the Plan tab and screen 2. */
export function keHoachTuCard(card: unknown): KeHoach | null {
  const the = theTuCard(card);
  return the !== null && the.kind === "itinerary" ? the : null;
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

/**
 * The price line for one place, or nothing.
 *
 * Both bounds present and different reads as a range; one bound, or two equal
 * bounds, reads as a single figure. Nothing is averaged: the midpoint of a
 * range the server gave as a range is a number the server never said.
 */
export function khoangGia(diaDiem: DiaDiem): string | null {
  const { giaMinVnd: min, giaMaxVnd: max } = diaDiem;
  if (min !== undefined && max !== undefined) {
    return min === max ? dinhDangTienVnd(min) : `${dinhDangTienVnd(min)} - ${dinhDangTienVnd(max)}`;
  }
  if (min !== undefined) return `từ ${dinhDangTienVnd(min)}`;
  if (max !== undefined) return `tới ${dinhDangTienVnd(max)}`;
  return null;
}
