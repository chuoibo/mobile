/** One place in full, from the server rather than from the list behind it.
 *
 * `GET /places/{place_id}` (work item rd-be-05) returns everything `GET /places`
 * returns plus the two fields the grid deliberately omits: `description`, the
 * prose about the venue, and `reviews`, what people wrote about it. Until this
 * file existed nothing in the app called it -- the detail screen was drawn
 * entirely out of the card the person had just tapped, so two fields the server
 * was already computing reached no screen at all.
 *
 * That is the whole reason for the route, and it is worth stating why it is a
 * route rather than more columns on the list: prose and reviews are the biggest
 * payload per place and are read for exactly one place at a time. Sending them
 * for all forty is a list response that grows with the corpus for the benefit of
 * a screen that shows one row of it.
 *
 * ## The list place stays the fallback, and that is deliberate
 *
 * `ChiTietDiaDiem` renders from the tapped `Place` immediately and folds this
 * response in when it lands. So a server without the route, an offline phone, or
 * a slow answer costs the description and the reviews and costs nothing else --
 * the screen never blanks, and it never waits before drawing a name, a price
 * band and the match reason it was opened for. The failure is visible (the
 * screen says so in one line) rather than silent, but it is not fatal.
 *
 * No React here on purpose, same rule as `places.ts`: the wire shape and the
 * refusals are checkable without a phone.
 */
import { chiTietLoi } from "../../ui/loi-tren-man";
import { parsePlace, PLACES_BASE_URL, PLACES_WORK_ITEM, type Place } from "./places";

/** One review as the server sends it. Three fields, no id and no date -- the
 *  server does not have either, and inventing "2 ngày trước" under a sentence
 *  is the kind of decoration that turns into a support question. */
export type Review = {
  author: string;
  /** 0-5, one place. Not forced to an integer: 4.5 is a real rating. */
  rating: number;
  body: string;
};

/** A `Place`, plus the two fields only the detail route carries. */
export type PlaceDetail = Place & {
  /** Prose about the venue, or null when the server has none for it. */
  description: string | null;
  reviews: Review[];
  /**
   * Whether photographs of this venue exist to be shown.
   *
   * True once a licensed photograph has been imported for the place (M12),
   * false for a place nobody has photographed yet. Still read rather than
   * inferred, because the gallery is a second request: the screen has to know
   * whether to make it at all, and an empty strip while that request is in
   * flight is worse than no strip.
   */
  photosAvailable: boolean;
  /**
   * What people do at this venue, in the server's words.
   *
   * Written when the place was imported, out of its own OpenStreetMap tags,
   * rather than asked of a model when the screen opens. So the sentences
   * describe what somebody recorded on the ground, and an empty list is the
   * honest answer for a venue whose tags say nothing about it -- the screen
   * leaves the section out instead of inventing a line for it.
   */
  activities: string[];
};

/**
 * Everything this screen's extra fetch can be.
 *
 * `khong-co` is separate from the failures: a 404 means the server is up,
 * answering, and does not have this id. On a detail screen opened from a card
 * the server itself sent, that means the catalogue moved under the reader --
 * different words, and a different thing to go and check, from "the route is
 * missing" or "nothing answered".
 */
export type ChiTietState =
  | { kind: "dang-tai" }
  | { kind: "co-du-lieu"; place: PlaceDetail }
  | { kind: "khong-co"; url: string }
  | { kind: "chua-co-endpoint"; url: string; work: string }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; status: number; detail: string }
  | { kind: "du-lieu-sai"; url: string; detail: string };

function parseReview(raw: unknown, field: string): Review {
  const r = raw as Record<string, unknown>;
  const rating = r.rating;
  if (typeof rating !== "number" || !Number.isFinite(rating)) {
    throw new Error(`${field}.rating phải là số, nhận được ${JSON.stringify(rating)}`);
  }
  if (rating < 0 || rating > 5) throw new Error(`${field}.rating ngoài 0-5: ${rating}`);
  const author = r.author;
  const body = r.body;
  if (typeof author !== "string" || author.trim() === "") {
    throw new Error(`${field}.author phải là chuỗi không rỗng`);
  }
  if (typeof body !== "string" || body.trim() === "") {
    throw new Error(`${field}.body phải là chuỗi không rỗng`);
  }
  return { author, rating, body };
}

/**
 * Turn the detail body into a `PlaceDetail`, or throw naming the field.
 *
 * `parsePlace` does the shared half, so the detail screen and the grid card can
 * never disagree about what a rating or a price band is. Only the three extra
 * fields are read here.
 */
export function parsePlaceDetail(body: unknown): PlaceDetail {
  const base = parsePlace(body, "place");
  const p = body as Record<string, unknown>;
  const description = p.description;
  if (description !== null && description !== undefined && typeof description !== "string") {
    throw new Error(`place.description phải là chuỗi hoặc null`);
  }
  const rawReviews = p.reviews;
  if (rawReviews !== undefined && !Array.isArray(rawReviews)) {
    throw new Error("place.reviews phải là mảng");
  }
  const rawActivities = p.activities;
  if (rawActivities !== undefined && rawActivities !== null && !Array.isArray(rawActivities)) {
    throw new Error("place.activities phải là mảng");
  }
  return {
    ...base,
    description: typeof description === "string" && description.trim() !== "" ? description : null,
    reviews: (rawReviews ?? []).map((r: unknown, i: number) => parseReview(r, `place.reviews[${i}]`)),
    photosAvailable: p.photos_available === true,
    activities: (rawActivities ?? []).map((a: unknown, i: number) => {
      if (typeof a !== "string" || a.trim() === "") {
        throw new Error(`place.activities[${i}] phải là chuỗi không rỗng`);
      }
      return a;
    }),
  };
}

export function placeDetailUrl(base: string, placeId: string): string {
  // `encodeURIComponent` and not a template hole: this id comes off a wire
  // object and ends up in a path, and a screen that asks the server about
  // `../../etc` is a screen writing somebody else's URL.
  return `${base.replace(/\/$/, "")}/places/${encodeURIComponent(placeId)}`;
}

/**
 * Ask the server for one place in full.
 *
 * Never throws, for the same reason `fetchPlaces` never does: a rejected promise
 * on a detail screen is a blank card, and every one of these states has words a
 * person can act on.
 */
export async function fetchPlaceDetail(
  placeId: string,
  opts: { base?: string; fetchImpl?: typeof fetch } = {},
): Promise<ChiTietState> {
  const base = opts.base ?? PLACES_BASE_URL;
  const url = placeDetailUrl(base, placeId);
  const doFetch = opts.fetchImpl ?? fetch;

  let res: Response;
  try {
    res = await doFetch(url, { headers: { Accept: "application/json" } });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: chiTietLoi(e) };
  }

  // A 404 here is ambiguous in a way the list's is not -- it is either "no such
  // place" or "no such route" -- and the body is what separates them. The route
  // answers `{"detail": ...}`; a server without the route answers FastAPI's own
  // `{"detail":"Not Found"}`. Rather than pattern-match English, the split is
  // made on the header the API sets on every one of its own refusals.
  if (res.status === 404) {
    let known = false;
    try {
      const body = (await res.json()) as Record<string, unknown>;
      known = typeof body?.code === "string" || body?.detail !== "Not Found";
    } catch {
      /* not JSON at all: treat as a server that does not have the route */
    }
    return known
      ? { kind: "khong-co", url }
      : { kind: "chua-co-endpoint", url, work: PLACES_WORK_ITEM };
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.text()).slice(0, 200) || detail;
    } catch {
      /* body already consumed or not text; the status alone still says enough */
    }
    return { kind: "may-chu-loi", url, status: res.status, detail };
  }

  try {
    return { kind: "co-du-lieu", place: parsePlaceDetail(await res.json()) };
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: chiTietLoi(e) };
  }
}

/** One line saying why the extra fields are not on screen, or null when they
 *  are. The detail screen is still fully usable in every one of these states,
 *  so this reads as a note rather than as an error banner. */
export function loiChiTiet(state: ChiTietState): string | null {
  switch (state.kind) {
    case "dang-tai":
    case "co-du-lieu":
      return null;
    case "khong-co":
      return "Máy chủ không còn địa điểm này. Phần giới thiệu và đánh giá lấy từ đó nên cũng không có.";
    case "chua-co-endpoint":
      return `Máy chủ đang chạy nhưng chưa có route GET /places/{id} (${state.work}). Phần trên vẫn là dữ liệu thật từ danh sách.`;
    case "khong-noi-duoc":
      return `Không nối được ${state.url} để lấy giới thiệu và đánh giá.`;
    case "may-chu-loi":
      return `Máy chủ trả HTTP ${state.status} khi hỏi chi tiết địa điểm này.`;
    case "du-lieu-sai":
      return `Chi tiết địa điểm sai định dạng: ${state.detail}`;
  }
}
