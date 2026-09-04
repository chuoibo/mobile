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
import { ApiError, translatedAnonymous, translatedAsActor } from "../../api";
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
import { quenDiemDen } from "./diem-den";
import type { IconName } from "../ui";

const LOI_DIA_DIEM: Record<string, string> = {
  place_not_found: "Địa điểm này không còn trong danh mục.",
  permission_denied: "Bạn cần đăng nhập để lưu địa điểm.",
};

export type DanhMuc = {
  places: Place[];
  categories: Category[];
  /** Which destination these places are from. The server always picks one and
   *  says which, so the screen can name it instead of printing a city it hopes
   *  is right. */
  destination: { id: string; name: string };
};

/**
 * The catalogue for one destination, optionally narrowed further.
 *
 * `destination` omitted means «you choose» -- the server answers with its
 * default and names it in the body, which is what the header then draws.
 */
export async function docDanhMuc(
  opts: { category?: string | null; q?: string; destination?: string | null } = {},
): Promise<DanhMuc> {
  const params = new URLSearchParams();
  if (opts.category) params.set("category", opts.category);
  const q = opts.q?.trim();
  if (q) params.set("q", q);
  if (opts.destination) params.set("destination", opts.destination);
  const duoi = params.toString();
  const body = await translatedAnonymous<unknown>(LOI_DIA_DIEM, duoi ? `/places?${duoi}` : "/places", {
    method: "GET",
  });
  return parseCatalogue(body);
}

/**
 * The catalogue for a remembered destination, falling back to the server's own.
 *
 * A destination this phone stored can be gone from the catalogue -- an import
 * can drop one -- and that answers 404. The right response is the default
 * destination, not an error screen about a city somebody chose last week; the
 * stored choice is cleared so it stops being asked for.
 */
export async function docDanhMucCoLui(daChon: string | null): Promise<DanhMuc> {
  if (daChon === null) return docDanhMuc();
  try {
    return await docDanhMuc({ destination: daChon });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await quenDiemDen();
      return docDanhMuc();
    }
    throw error;
  }
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
    const van = gapChu([p.name, ...p.kinds, ...p.traits, p.address ?? ""].join(" "));
    return tu.every((t) => van.includes(t));
  });
}

/**
 * «Đang mở · 10:00 – 22:30», «Đã đóng · mở 10:00 – 22:30», or the truth.
 *
 * Three states since M9, because the catalogue has three: open, closed, and
 * «nobody told us». OpenStreetMap rarely carries opening hours, and a place
 * whose hours are unknown must not be drawn as closed -- that is a claim about
 * a business, made up by an app that does not know.
 */
export function cauMoCua(place: Pick<Place, "openNow" | "openHours">): string {
  if (place.openHours === null) {
    return place.openNow === null ? "Chưa có giờ mở cửa" : place.openNow ? "Đang mở" : "Đã đóng";
  }
  if (place.openNow === null) return `Giờ mở cửa: ${place.openHours}`;
  return place.openNow ? `Đang mở · ${place.openHours}` : `Đã đóng · mở ${place.openHours}`;
}

/** The second line of a card: kinds, then the travel estimate if there is one. */
export function dongPhu(place: Pick<Place, "kinds" | "travelMinutes">): string {
  const loai = formatKinds(place.kinds);
  if (place.travelMinutes === null) return loai;
  const di = `${place.travelMinutes} phút đi xe`;
  return loai ? `${loai} · ${di}` : di;
}

/** «200.000đ – 250.000đ mỗi người», or the words for not knowing. */
export function cauGia(place: Pick<Place, "priceMinVnd" | "priceMaxVnd">): string {
  if (place.priceMinVnd === null || place.priceMaxVnd === null) return "Chưa có giá";
  const tien = (v: number) => `${v.toLocaleString("vi-VN")}đ`;
  if (place.priceMinVnd === place.priceMaxVnd) return `${tien(place.priceMinVnd)} mỗi người`;
  return `${tien(place.priceMinVnd)} – ${tien(place.priceMaxVnd)} mỗi người`;
}

/**
 * Who the row came from, when somebody has to be credited.
 *
 * `null` for a row of our own seed data: there is nobody to credit and a line
 * saying so would be noise. For an OpenStreetMap row it is not decoration --
 * ODbL makes attribution a condition of using the data (ADR-0017).
 */
export function cauNguonDuLieu(place: Pick<Place, "source" | "license">): string | null {
  if (place.source !== "osm") return null;
  return "Dữ liệu địa điểm: OpenStreetMap (ODbL)";
}

/**
 * The short facts under a card name: only the ones this place actually has.
 *
 * A card used to draw four fixed slots -- stars, distance, price, open/closed
 * -- because every seed row had all four. An imported row may have none of
 * them, and four slots reading «-- · -- · --» is worse than three honest ones.
 * So the row is built from what exists, and when nothing does, the address
 * takes its place: a name and where it is, which is still a card.
 */
export function chiTietNgan(
  place: Pick<
    Place,
    "rating" | "ratingCount" | "distanceKm" | "priceMinVnd" | "priceMaxVnd" | "openNow" | "openHours" | "address"
  >,
): { icon: IconName; chu: string }[] {
  const ra: { icon: IconName; chu: string }[] = [];
  if (place.rating !== null) {
    const dem = place.ratingCount === null ? "" : ` (${place.ratingCount})`;
    ra.push({ icon: "star", chu: `${place.rating}${dem}` });
  }
  if (place.distanceKm !== null) {
    ra.push({ icon: "navigate-outline", chu: `${place.distanceKm} km` });
  }
  if (place.priceMinVnd !== null && place.priceMaxVnd !== null) {
    ra.push({ icon: "wallet-outline", chu: cauGia(place) });
  }
  if (place.openNow !== null || place.openHours !== null) {
    ra.push({ icon: "time-outline", chu: cauMoCua(place) });
  }
  if (ra.length === 0 && place.address !== null) {
    ra.push({ icon: "location-outline", chu: place.address });
  }
  return ra;
}

/**
 * The subtitle under the address: distance and ride time, when either is known.
 *
 * Both come from the catalogue rather than from the phone, so an imported
 * place has neither and the row falls back to naming the action itself. It is
 * still a row worth tapping: it opens the map app.
 */
export function cauDuongDi(place: Pick<Place, "distanceKm" | "travelMinutes">): string {
  const phan: string[] = [];
  if (place.distanceKm !== null) phan.push(`${place.distanceKm} km`);
  if (place.travelMinutes !== null) phan.push(`${place.travelMinutes} phút đi xe`);
  return phan.length === 0 ? "Mở bằng ứng dụng bản đồ" : phan.join(" · ");
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
