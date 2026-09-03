/**
 * Khám phá on the real catalogue (M4): the wire for `/places`, `/places/{id}`
 * and the person's saved places, plus the pure helpers the two screens share.
 *
 * The parsers are App B's (`screens/kham-pha/places.ts`,
 * `chi-tiet-dia-diem.ts`): they already refuse the shapes that would put a
 * wrong number on a card (fractional đồng, a match nobody computed). What
 * changes here is the transport: the catalogue is public and is read as
 * nobody; saving a place is the person's own row and goes with the bearer.
 * No synthetic `context_id` travels on the query string.
 */
import { translatedAnonymous, translatedAsActor } from "../../api";
import {
  parsePlaceDetail,
  type PlaceDetail,
} from "../../screens/kham-pha/chi-tiet-dia-diem";
import {
  formatKinds,
  parseCatalogue,
  type Category,
  type Place,
} from "../../screens/kham-pha/places";
import type { TimKiemState } from "../../screens/kham-pha/tim-kiem";
import type { IconName } from "../ui";

const LOI_DIA_DIEM: Record<string, string> = {
  place_not_found: "Địa điểm này không còn trong danh mục.",
  permission_denied: "Bạn cần đăng nhập để lưu địa điểm.",
};

export type DanhMuc = { places: Place[]; categories: Category[] };

/** The catalogue, optionally narrowed by a category id or a name query. */
export async function docDanhMuc(opts: { category?: string | null; q?: string } = {}): Promise<DanhMuc> {
  const params = new URLSearchParams();
  if (opts.category) params.set("category", opts.category);
  const q = opts.q?.trim();
  if (q) params.set("q", q);
  const duoi = params.toString();
  const body = await translatedAnonymous<unknown>(LOI_DIA_DIEM, duoi ? `/places?${duoi}` : "/places", {
    method: "GET",
  });
  return parseCatalogue(body);
}

export async function docChiTiet(placeId: string): Promise<PlaceDetail> {
  const body = await translatedAnonymous<unknown>(LOI_DIA_DIEM, `/places/${encodeURIComponent(placeId)}`, {
    method: "GET",
  });
  return parsePlaceDetail(body);
}

type DaLuuTraVe = { saved?: { place_id?: unknown }[] };

/** Ids of the places this person saved, as the server holds them. */
export async function docDaLuu(personId: string): Promise<string[]> {
  const body = await translatedAsActor<DaLuuTraVe>(LOI_DIA_DIEM, "/people/me/saved-places", {
    method: "GET",
    actorId: personId,
  });
  const ids: string[] = [];
  for (const hang of body.saved ?? []) {
    if (typeof hang.place_id === "string") ids.push(hang.place_id);
  }
  return ids;
}

export async function luuDiaDiem(personId: string, placeId: string): Promise<void> {
  await translatedAsActor<unknown>(LOI_DIA_DIEM, `/people/me/saved-places/${encodeURIComponent(placeId)}`, {
    method: "PUT",
    actorId: personId,
  });
}

export async function boLuuDiaDiem(personId: string, placeId: string): Promise<void> {
  await translatedAsActor<unknown>(LOI_DIA_DIEM, `/people/me/saved-places/${encodeURIComponent(placeId)}`, {
    method: "DELETE",
    actorId: personId,
  });
}

/** Toggle in a list of ids without touching the server's answer. */
export function daoLuu(daLuu: string[], placeId: string): string[] {
  return daLuu.includes(placeId) ? daLuu.filter((id) => id !== placeId) : [...daLuu, placeId];
}

const BIEU_TUONG: Record<string, IconName> = {
  "quan-an-local": "restaurant-outline",
  cafe: "cafe-outline",
  "vui-choi": "game-controller-outline",
  "di-choi-dem": "moon-outline",
};

/** The glyph for a catalogue category id; anything new gets a pin. */
export function bieuTuongLoai(categoryId: string): IconName {
  const co = BIEU_TUONG[categoryId];
  if (co === undefined) return "location-outline";
  return co;
}

/** Lower-case without diacritics, so «oc» finds «Ốc» and «dl» finds nothing false. */
function gapChu(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

/** Name, kinds, traits and address contain the words typed, in any order, accents optional. */
export function locTheoTen(places: Place[], q: string): Place[] {
  const tu = gapChu(q).split(/\s+/).filter(Boolean);
  if (tu.length === 0) return places;
  return places.filter((p) => {
    const van = gapChu([p.name, ...p.kinds, ...p.traits, p.address].join(" "));
    return tu.every((t) => van.includes(t));
  });
}

/** «Đang mở · 10:00 – 22:30» or «Đã đóng · mở 10:00 – 22:30». */
export function cauMoCua(place: Pick<Place, "openNow" | "openHours">): string {
  return place.openNow ? `Đang mở · ${place.openHours}` : `Đã đóng · mở ${place.openHours}`;
}

/** The second line of a card: kinds, then the travel estimate. */
export function dongPhu(place: Pick<Place, "kinds" | "travelMinutes">): string {
  const loai = formatKinds(place.kinds);
  const di = `${place.travelMinutes} phút đi xe`;
  return loai ? `${loai} · ${di}` : di;
}

/** A `geo:` URL the phone's map app understands; no map SDK in this build. */
export function duongChiDuong(place: Pick<Place, "lat" | "lng" | "name">): string {
  return `geo:${place.lat},${place.lng}?q=${encodeURIComponent(place.name)}`;
}

/**
 * What the search screen says when the server did not hand back places.
 * `null` means there are results (or nothing was asked yet).
 */
export function cauTimKiem(trang: TimKiemState): string | null {
  switch (trang.kind) {
    case "chua-tim":
    case "dang-tim":
    case "co-ket-qua":
      return null;
    case "khong-tra-loi":
      return "Rủ Đi AI chưa đủ chắc để xếp hạng cho câu này. Thử nói rõ số người, ngân sách hoặc khu vực.";
    case "cau-khong-hop-le":
      return `Câu tìm cần từ 1 tới ${trang.max} ký tự.`;
    case "chua-biet-la-ai":
      return "Cần đăng nhập để hỏi Rủ Đi AI.";
    case "bi-tu-choi":
      return "Máy chủ từ chối yêu cầu này.";
    case "qua-nhieu-lan":
      return "Hết lượt hỏi trong phút này. Thử lại sau một chút.";
    case "chua-co-endpoint":
      return "Máy chủ này chưa có tìm kiếm bằng câu.";
    case "khong-noi-duoc":
      return "Không nối được máy chủ. Kiểm tra mạng rồi thử lại.";
    case "may-chu-loi":
      return "Máy chủ đang lỗi. Thử lại sau.";
    case "du-lieu-sai":
      return "Máy chủ trả dữ liệu không đọc được.";
    default:
      return null;
  }
}
