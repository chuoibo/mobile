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
import { ApiError, BASE_URL, translatedAnonymous, translatedAsActor } from "../../api";
import { nguonAnhAnToan } from "../../ui/nguon-anh";
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
  /** Whose taste the match percentages are relative to (M11). */
  gu: Gu;
};

/**
 * The basis every badge on the screen is scored against.
 *
 * `chua-biet` is not an error and not an empty group: it is «we have not been
 * told anything about you», and it is why the cards come back with no
 * percentage at all. Saying which of the three it is, in the screen's own
 * words, is the difference between «không có chỗ nào hợp gu bạn» (a claim
 * about the places) and «Rủ Đi chưa biết gu bạn» (a claim about us).
 */
export type Gu = {
  co_so: "nhom" | "ca-nhan" | "chua-biet";
  so_thich: string[];
  /** Chosen tastes this catalogue has nothing to match against. */
  chua_co_trong_danh_muc: string[];
  nguoi: number;
  nguoi_da_chon: number;
};

const GU_CHUA_BIET: Gu = {
  co_so: "chua-biet",
  so_thich: [],
  chua_co_trong_danh_muc: [],
  nguoi: 0,
  nguoi_da_chon: 0,
};

/**
 * The one line the screen prints about whose taste the badges follow.
 *
 * Three states, three different sentences, and the «chưa biết» one names the
 * next move rather than describing an absence: the person can fix it, and the
 * screen is the only place they would find that out.
 */
export function cauGu(gu: Gu | null): string {
  if (gu === null || gu.co_so === "chua-biet") {
    return "Chưa biết gu bạn nên chưa xếp hạng. Chọn sở thích ở Cá nhân để Rủ Đi xếp giúp.";
  }
  if (gu.co_so === "ca-nhan") {
    return gu.so_thich.length === 0
      ? "Xếp theo mức chi bạn đã chọn."
      : `Xếp theo ${gu.so_thich.length} sở thích bạn đã chọn.`;
  }
  return `Xếp theo gu nhóm: ${gu.nguoi_da_chon}/${gu.nguoi} người đã chọn sở thích.`;
}

/** «Rủ Đi chưa có nhóm địa điểm này», or empty. A claim about the catalogue. */
export function cauChuaCo(gu: Gu | null, ten: (id: string) => string): string {
  if (gu === null) return "";
  // A word this build cannot name is dropped rather than printed as its id:
  // the sentence is about the catalogue, and a storage key on screen is not.
  const ds = gu.chua_co_trong_danh_muc.map(ten).filter((chu) => chu !== "");
  if (ds.length === 0) return "";
  return `Rủ Đi chưa nhập nhóm địa điểm cho: ${ds.join(", ")}.`;
}

function docGu(body: unknown): Gu {
  const raw = (body as { group?: Record<string, unknown> } | null)?.group;
  if (raw === undefined || raw === null) return GU_CHUA_BIET;
  const co_so = raw.basis;
  if (co_so !== "nhom" && co_so !== "ca-nhan" && co_so !== "chua-biet") return GU_CHUA_BIET;
  const chuoi = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
  const so = (value: unknown): number => (typeof value === "number" && Number.isInteger(value) ? value : 0);
  return {
    co_so,
    so_thich: chuoi(raw.interests),
    chua_co_trong_danh_muc: chuoi(raw.uncovered_interests),
    nguoi: so(raw.people),
    nguoi_da_chon: so(raw.people_answered),
  };
}

/**
 * The catalogue for one destination, optionally narrowed further.
 *
 * `destination` omitted means «you choose» -- the server answers with its
 * default and names it in the body, which is what the header then draws.
 */
export async function docDanhMuc(
  opts: {
    category?: string | null;
    q?: string;
    destination?: string | null;
    /** Read as this person when there is a session (M11): the badge is scored
     *  against their stated taste. Absent means an anonymous read, which the
     *  route serves as a catalogue with no percentages. */
    personId?: string | null;
  } = {},
): Promise<DanhMuc> {
  const params = new URLSearchParams();
  if (opts.category) params.set("category", opts.category);
  const q = opts.q?.trim();
  if (q) params.set("q", q);
  if (opts.destination) params.set("destination", opts.destination);
  const duoi = params.toString();
  const duong = duoi ? `/places?${duoi}` : "/places";
  const body =
    opts.personId != null
      ? await translatedAsActor<unknown>(LOI_DIA_DIEM, duong, { method: "GET", actorId: opts.personId })
      : await translatedAnonymous<unknown>(LOI_DIA_DIEM, duong, { method: "GET" });
  return { ...parseCatalogue(body), gu: docGu(body) };
}

/**
 * The catalogue for a remembered destination, falling back to the server's own.
 *
 * A destination this phone stored can be gone from the catalogue -- an import
 * can drop one -- and that answers 404. The right response is the default
 * destination, not an error screen about a city somebody chose last week; the
 * stored choice is cleared so it stops being asked for.
 */
export async function docDanhMucCoLui(
  daChon: string | null,
  personId?: string | null,
): Promise<DanhMuc> {
  if (daChon === null) return docDanhMuc({ personId });
  try {
    return await docDanhMuc({ destination: daChon, personId });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      await quenDiemDen();
      return docDanhMuc({ personId });
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

/**
 * One licensed photograph of a place, with the provenance the screen prints
 * beside it.
 *
 * ADR-0017 lets a photograph of a real venue into this product on exactly one
 * condition: it can say whose work it is, under what licence, and where the
 * original lives. So those three are non-optional here, and a row that arrives
 * without them is refused rather than drawn without a credit -- the server
 * already refuses to store one (`place_photo_cites_its_source`), and a client
 * that would render it anyway is the second half of that promise missing.
 */
export type AnhDiaDiem = {
  id: string;
  /** A path on this app's own API, origin-checked like every other image. */
  url: string;
  author: string;
  license: string;
  /** Where the original lives, so a reader can check the credit. */
  sourceUrl: string;
  title: string | null;
  width: number | null;
  height: number | null;
};

function soDuong(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.trunc(v) : null;
}

function chuKhongRong(raw: Record<string, unknown>, khoa: string, field: string): string {
  const v = raw[khoa];
  if (typeof v !== "string" || v.trim() === "") {
    throw new Error(`${field}.${khoa} phải là chuỗi không rỗng`);
  }
  return v;
}

/**
 * Read one photograph, or throw naming the field.
 *
 * The URL goes through the same origin check as the cards' cover photograph:
 * an `<Image>` dials whatever it is handed, so an address on somebody else's
 * host would tell that host who opened this screen and when.
 */
export function parseAnhDiaDiem(raw: unknown, field: string): AnhDiaDiem {
  const a = (raw ?? {}) as Record<string, unknown>;
  const url = nguonAnhAnToan(a.url, BASE_URL);
  if (url === null) throw new Error(`${field}.url không phải địa chỉ ảnh của máy chủ này`);
  const title = a.title;
  return {
    id: chuKhongRong(a, "id", field),
    url,
    author: chuKhongRong(a, "author", field),
    license: chuKhongRong(a, "license", field),
    sourceUrl: chuKhongRong(a, "source_url", field),
    title: typeof title === "string" && title.trim() !== "" ? title : null,
    width: soDuong(a.width),
    height: soDuong(a.height),
  };
}

/**
 * The gallery of one place.
 *
 * Public, like the catalogue: these are licensed photographs of a venue
 * anybody can walk into. The other kind of photograph of the same place --
 * one a group took there -- is that group's and never arrives on this route.
 */
export async function docAnhDiaDiem(placeId: string): Promise<AnhDiaDiem[]> {
  const body = await translatedAnonymous<{ photos?: unknown[] }>(
    LOI_DIA_DIEM,
    `/places/${encodeURIComponent(placeId)}/photos`,
    { method: "GET" },
  );
  return (body.photos ?? []).map((raw, i) => parseAnhDiaDiem(raw, `photos[${i}]`));
}

/** What an `<Image>` needs. No headers: these bytes are public. */
export function nguonAnhDiaDiem(anh: Pick<AnhDiaDiem, "url">): { uri: string } {
  return { uri: BASE_URL + anh.url };
}

/**
 * The credit line under a photograph.
 *
 * Author first because that is whose work it is; the licence second because
 * that is the permission this app is relying on. Both are printed, always --
 * a photograph whose credit did not fit on the screen is a photograph this
 * product is not allowed to show.
 *
 * «Quanh đây» is not padding. The importer finds these by geosearch within 250
 * metres of the venue, so what it proves is that the picture was taken around
 * here -- not that it is a picture *of* this business. A cover photograph with
 * no such word on it is a claim the data does not support, which is the same
 * failure as a stock photo wearing a real name.
 */
export function cauGiayPhep(anh: Pick<AnhDiaDiem, "author" | "license">): string {
  return `Ảnh quanh đây: ${anh.author} · ${anh.license}`;
}

/**
 * The one sentence under a gallery, where there is room to say the whole
 * thing rather than the two words a card can fit.
 */
export const CAU_NGUON_ANH =
  "Ảnh có giấy phép chụp quanh đây, từ Wikimedia Commons. Không phải ảnh do nơi này cung cấp.";

/**
 * The cover photograph of a card, or null when it may not be drawn.
 *
 * «May not», not «is not there»: a URL whose author or licence did not come
 * with it is refused here, because ADR-0017 allows the picture only where the
 * credit goes with it. The card then falls back to the typographic tile --
 * which is exactly what the design rule prescribes for a photograph that
 * cannot say where it came from.
 */
export function anhBiaThe(
  place: Pick<Place, "photoUrl" | "photoAuthor" | "photoLicense">,
): { nguon: { uri: string }; giayPhep: string } | null {
  if (place.photoUrl === null || place.photoAuthor === null || place.photoLicense === null) {
    return null;
  }
  return {
    nguon: { uri: BASE_URL + place.photoUrl },
    giayPhep: cauGiayPhep({ author: place.photoAuthor, license: place.photoLicense }),
  };
}

/**
 * The heading over «nên làm gì ở đây», or null when the server knows nothing.
 *
 * Returning null rather than an empty section keeps the screen from printing a
 * promise it cannot keep: for most imported places the tags say nothing about
 * what people do there, and a heading over blank space reads as a bug.
 */
export function cauHoatDong(activities: string[]): string | null {
  return activities.length === 0 ? null : "Nên làm gì ở đây";
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
