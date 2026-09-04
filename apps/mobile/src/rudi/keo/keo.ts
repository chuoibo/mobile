/**
 * Kèo (outings) on the real API (M4): the wire for a group's outings, their
 * timelines with catalogue places, and check-ins at a stop, plus the pure
 * helpers the screens share.
 *
 * Money and dates stay the server's: the form validation (`kiemTraTaoBuoiDi`)
 * and the stop sort (`sapXepChang`) come from App B's `buoi-di.ts`, and the
 * server refuses a stop whose `place_id` is not in its catalogue
 * (`stop_place_unknown`) before writing anything.
 */
import {
  checkInChang,
  docCheckIn,
  docDanhSachBuoiDi,
  luuDongThoiGian,
  taoBuoiDi,
  ApiError,
  type Attempt,
} from "../../api";
import {
  sapXepChang,
  type BodyTaoBuoiDi,
  type BuoiDi,
  type ChangDung,
  type ChangGui,
  type CheckIn,
} from "../../screens/len-plan/buoi-di";

/** Server refusals, in the words the screen says. */
export const LOI_KEO: Record<string, string> = {
  stop_place_unknown: "Chặng nêu một địa điểm không có trong danh mục.",
  already_checked_in: "Bạn đã đánh dấu tới chặng này rồi.",
  outing_not_found: "Kèo này không còn.",
  stop_not_found: "Chặng này không còn trong kèo.",
  permission_denied: "Bạn không còn ở trong nhóm này.",
};

/** Translate a server refusal code through `LOI_KEO`; other errors pass through. */
export async function dich<T>(chay: () => Promise<T>): Promise<T> {
  try {
    return await chay();
  } catch (error) {
    if (error instanceof ApiError) {
      const cau = LOI_KEO[error.code];
      if (cau !== undefined) throw new ApiError(error.status, error.code, cau);
    }
    throw error;
  }
}

export async function docKeoCuaNhom(contextId: string, personId: string): Promise<BuoiDi[]> {
  const ra = await dich(() => docDanhSachBuoiDi(contextId, personId));
  return ra.outings;
}

export async function taoKeo(contextId: string, personId: string, body: BodyTaoBuoiDi, attempt: Attempt): Promise<BuoiDi> {
  return dich(() => taoBuoiDi(contextId, body, personId, attempt));
}

export async function luuLichTrinh(
  outing: Pick<BuoiDi, "id" | "context_id">,
  stops: ChangGui[],
  personId: string,
  attempt: Attempt,
): Promise<BuoiDi> {
  return dich(() => luuDongThoiGian(outing.id, stops, personId, attempt, outing.context_id));
}

export async function danhDauToi(stopId: string, contextId: string, personId: string, attempt: Attempt): Promise<CheckIn> {
  return dich(() => checkInChang(stopId, personId, attempt, contextId));
}

export async function docDaToi(outing: Pick<BuoiDi, "id" | "context_id">, personId: string): Promise<CheckIn[]> {
  const ra = await dich(() => docCheckIn(outing.id, personId, outing.context_id));
  return ra.checkins;
}

/** A stop as the timeline PUT wants it, from a stop the server already holds. */
export function changGuiTu(stop: ChangDung): ChangGui {
  return { at: stop.at, label: stop.label, place_name: stop.place_name, place_id: stop.place_id };
}

/** The whole timeline with one stop added, sorted by clock time. */
export function themChang(hienTai: readonly ChangDung[], moi: ChangGui): ChangGui[] {
  return sapXepChang([...hienTai.map(changGuiTu), moi]);
}

/** The whole timeline with one stop's place changed, nothing else touched. */
export function ganDiaDiem(
  hienTai: readonly ChangDung[],
  stopId: string,
  place: { id: string; name: string },
): ChangGui[] {
  return sapXepChang(
    hienTai.map((s) => (s.id === stopId ? { ...changGuiTu(s), place_id: place.id, place_name: place.name } : changGuiTu(s))),
  );
}

/** Today as the form's ISO date, in the phone's own calendar day. */
export function homNayIso(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** The next full hour as "HH:MM", the default for a stop added now. */
export function gioTiepTheo(now: Date = new Date()): string {
  const h = (now.getHours() + 1) % 24;
  return `${String(h).padStart(2, "0")}:00`;
}

/** «2 chặng» / «Chưa có chặng nào». */
export function cauSoChang(n: number): string {
  return n === 0 ? "Chưa có chặng nào" : `${n} chặng`;
}

/** «Chưa ai tới» / «1 đã tới» / «3 đã tới · bạn». */
export function cauDaToi(checkins: readonly CheckIn[], personId: string): string {
  if (checkins.length === 0) return "Chưa ai tới";
  const toi = checkins.some((c) => c.person_id === personId);
  return `${checkins.length} đã tới${toi ? " · bạn" : ""}`;
}

/** What the person typed for a stop is a stop the server will take, or a sentence. */
export function kiemTraChangMoi(at: string, label: string): { ok: true } | { ok: false; loi: string } {
  if (!/^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(at.trim())) return { ok: false, loi: "Giờ theo dạng 24 giờ, ví dụ 18:30." };
  const ten = label.trim();
  if (ten === "") return { ok: false, loi: "Đặt tên cho chặng, ví dụ Ăn tối." };
  if (ten.length > 200) return { ok: false, loi: "Tên chặng tối đa 200 ký tự." };
  return { ok: true };
}
