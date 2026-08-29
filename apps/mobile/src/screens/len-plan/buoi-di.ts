/** Pure outing rules. No React, no fetch: this file is what the tests run
 *  under bare node, so every check a person can fail has to live here.
 *
 *  The server stores timeline stops in the order it received them. Measured:
 *  sending 12:30 then 07:00 comes back as position 0 = 12:30. Sorting is
 *  therefore a client duty, and it is this file's, not a screen's.
 */
import { formatVnd, parseAmountVnd } from "../../../../../packages/shared/money.mjs";

const GIO_24H = /^([01][0-9]|2[0-3]):[0-5][0-9]$/;
const NGAY_ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const TITLE_MAX = 200;
const HEADCOUNT_MAX = 1000;

export type ChangDung = {
  position: number;
  at: string;
  label: string;
  place_name: string | null;
};

/** One stop on its way to PUT /outings/{id}/timeline. No position: the
 *  server assigns that from the array order after we sort. */
export type ChangGui = {
  at: string;
  label: string;
  place_name: string | null;
};

export type BuoiDi = {
  id: string;
  context_id: string;
  created_by_id: string;
  title: string;
  starts_on: string;
  ends_on: string;
  headcount: number;
  budget_per_person_vnd: number;
  created_at: string;
  stops: ChangDung[];
};

export type FormTaoBuoiDi = {
  title: string;
  starts_on: string;
  ends_on: string;
  headcount: string;
  nganSach: string;
};

export type BodyTaoBuoiDi = {
  title: string;
  starts_on: string;
  ends_on: string;
  headcount: number;
  budget_per_person_vnd: number;
};

export type KetQuaTao =
  | { ok: true; body: BodyTaoBuoiDi }
  | { ok: false; loi: string };

export type KetQuaChang = { ok: true } | { ok: false; loi: string };

function ngayHopLe(s: string): boolean {
  const m = NGAY_ISO.exec(s.trim());
  if (!m) return false;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function tachNgay(s: string): { y: number; m: number; d: number } | null {
  const m = NGAY_ISO.exec(s.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!ngayHopLe(s)) return null;
  return { y, m: mo, d };
}

function parseHeadcount(s: string): number | null {
  const t = s.trim();
  if (!/^[0-9]+$/.test(t)) return null;
  const n = Number(t);
  if (!Number.isInteger(n)) return null;
  return n;
}

/** Validate the create-outing form against the server's own bounds. */
export function kiemTraTaoBuoiDi(form: FormTaoBuoiDi): KetQuaTao {
  const title = form.title.trim();
  if (title === "") {
    return { ok: false, loi: "Đặt tên cho chuyến đi." };
  }
  if (title.length > TITLE_MAX) {
    return { ok: false, loi: "Tên chuyến tối đa 200 ký tự." };
  }
  if (!ngayHopLe(form.starts_on)) {
    return {
      ok: false,
      loi: "Ngày bắt đầu phải theo dạng năm-tháng-ngày, ví dụ 2026-09-07.",
    };
  }
  if (!ngayHopLe(form.ends_on)) {
    return {
      ok: false,
      loi: "Ngày kết thúc phải theo dạng năm-tháng-ngày, ví dụ 2026-09-08.",
    };
  }
  if (form.ends_on.trim() < form.starts_on.trim()) {
    return { ok: false, loi: "Ngày kết thúc không được trước ngày bắt đầu." };
  }
  const headcount = parseHeadcount(form.headcount);
  if (headcount === null || headcount <= 0 || headcount > HEADCOUNT_MAX) {
    return { ok: false, loi: "Số người từ 1 đến 1000." };
  }
  const nganSach = parseAmountVnd(form.nganSach);
  if (!nganSach.ok) {
    if (nganSach.reason === "too-large") {
      return { ok: false, loi: "Số tiền này lớn quá mức app nhận." };
    }
    return {
      ok: false,
      loi: "Ngân sách mỗi người là số tiền Việt Nam, viết bằng chữ số.",
    };
  }
  return {
    ok: true,
    body: {
      title,
      starts_on: form.starts_on.trim(),
      ends_on: form.ends_on.trim(),
      headcount,
      budget_per_person_vnd: nganSach.value,
    },
  };
}

/** Sort stops by clock time, stable when two stops share a time. */
export function sapXepChang<T extends { at: string }>(stops: readonly T[]): T[] {
  return stops
    .map((stop, index) => ({ stop, index }))
    .sort((a, b) => {
      const byTime = a.stop.at.localeCompare(b.stop.at);
      return byTime !== 0 ? byTime : a.index - b.index;
    })
    .map((row) => row.stop);
}

/** A clock time the server will accept, and a non-blank label. */
export function kiemTraChang(at: string, label: string): KetQuaChang {
  if (!GIO_24H.test(at.trim())) {
    return {
      ok: false,
      loi: "Giờ phải theo dạng 07:00, trong khoảng 00:00 đến 23:59.",
    };
  }
  if (label.trim() === "") {
    return { ok: false, loi: "Nhãn chặng không được để trống." };
  }
  if (label.trim().length > TITLE_MAX) {
    return { ok: false, loi: "Nhãn chặng tối đa 200 ký tự." };
  }
  return { ok: true };
}

/** "07 - 08/09/2026" when both days share a month. Hyphen, never an em-dash. */
export function nhanKhoangNgay(starts: string, ends: string): string {
  const a = tachNgay(starts);
  const b = tachNgay(ends);
  if (!a || !b) return `${starts} - ${ends}`;
  if (a.y === b.y && a.m === b.m && a.d === b.d) {
    return `${pad2(a.d)}/${pad2(a.m)}/${a.y}`;
  }
  if (a.y === b.y && a.m === b.m) {
    return `${pad2(a.d)} - ${pad2(b.d)}/${pad2(b.m)}/${b.y}`;
  }
  if (a.y === b.y) {
    return `${pad2(a.d)}/${pad2(a.m)} - ${pad2(b.d)}/${pad2(b.m)}/${b.y}`;
  }
  return `${pad2(a.d)}/${pad2(a.m)}/${a.y} - ${pad2(b.d)}/${pad2(b.m)}/${b.y}`;
}

/** Per-person budget as a reference figure, never a cap. */
export function nhanNganSach(vnd: number): string {
  return `~ ${formatVnd(vnd)}đ/người, số tham chiếu`;
}

/** Integer đồng. The product of two integers in this range stays exact. */
export function tongDuKien(budget: number, headcount: number): number {
  return budget * headcount;
}
