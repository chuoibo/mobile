/** The three group-map routes, and every way each of them can fail.
 *
 * `GET /contexts/{id}/map` (F43), `GET /contexts/{id}/heatmap` (F44) and
 * `POST /contexts/{id}/meet` (F45) all landed in the same change as these
 * screens. That ordering is deliberate: `scripts/check_api_contract.py` reads
 * the tree it is in, so a client call and the route it calls have to arrive
 * together or the gate is right to refuse them.
 *
 * ## Why this file looks like `places.ts` and not like a fetch helper
 *
 * Same rule, same reason: **nothing here throws**. A rejected promise reaches
 * a screen as a blank panel, and a blank panel is indistinguishable from "this
 * group has never been anywhere" -- which is a claim about the group, made by
 * a bug. Every failure becomes a named state the screen says out loud.
 *
 * ## The one state that is not an error
 *
 * These three routes are gated on group membership, so they answer 403 to a
 * non-member. 403 here does not mean "something went wrong": it means the
 * person reading is not in this group any more. It gets its own state and its
 * own sentence, and neither of them contains the number 403.
 *
 * ## Disclosure fields are parsed as strictly as the data
 *
 * `scanned_checkins` / `truncated` / `unknown_area_count` bound how much
 * history the counts were built from. A screen that drops them presents a
 * summary of the first 500 check-ins of 900 as the group's habits, which is
 * wrong in a way no reader could detect. They are required fields here: a
 * server that stops sending them fails parsing rather than silently losing the
 * caveat.
 */
import { chiTietLoi } from "../../ui/loi-tren-man";
import { CONTEXT_ID, PLACES_BASE_URL } from "./places";

/* -------------------------------------------------------------------------
 * Wire shapes. Mirrors of the response models in `app/api/schemas.py`.
 * ---------------------------------------------------------------------- */

/** A pin the group has actually been to, and how often.
 *
 * `visitCount` and nothing else. There is no "visited by" and no "last
 * visited" because the server has no such field to send -- see
 * `VisitedPlace` in `schemas.py`. Privacy here is a property of the shape,
 * so this type is the same promise restated where the screens can see it. */
export type ChoDaDi = {
  placeId: string;
  placeName: string;
  lat: number;
  lng: number;
  visitCount: number;
};

/** A pin with no visit attached: trending and recommended both use it. */
export type ChoTrenBanDo = {
  placeId: string;
  placeName: string;
  lat: number;
  lng: number;
  rating: number;
  ratingCount: number;
};

/** A layer the map does not have, named rather than silently empty. */
export type LopChuaCo = { layer: string; reason: string };

export type BanDoNhomData = {
  daDi: ChoDaDi[];
  dangHot: ChoTrenBanDo[];
  nenThu: ChoTrenBanDo[];
  chuaCo: LopChuaCo[];
  daQuet: number;
  batHet: boolean;
};

export type KhuNhietDo = {
  id: string;
  label: string;
  lat: number;
  lng: number;
  visitCount: number;
  sharePercent: number;
};

export type NhietDoData = {
  khu: KhuNhietDo[];
  daNhanRa: number;
  khongRoKhu: number;
  daQuet: number;
  batHet: boolean;
};

export type KhuVuc = { id: string; label: string; lat: number; lng: number };

/** One journey, attributed to an area and to no one. */
export type ChangDuong = KhuVuc & { km: number };

export type CanBang = { worstKm: number; totalKm: number; spreadKm: number };

export type UngVienDiemHen = {
  placeId: string;
  placeName: string;
  category: string;
  address: string;
  lat: number;
  lng: number;
  canBang: CanBang;
  chang: ChangDuong[];
};

export type DiemHenData = {
  diemXuatPhat: KhuVuc[];
  ungVien: UngVienDiemHen[];
  /** True when exactly two areas were sent. With two origins the answer plus
   *  one origin yields the other, so a screen that gathered the areas from two
   *  different members must say so *before* showing the result to both. The
   *  server sets it; `DiemHen.tsx` is what acts on it. */
  suyNguocDuoc: boolean;
};

/* -------------------------------------------------------------------------
 * States. One per way the screen has to speak.
 * ---------------------------------------------------------------------- */

type LoiChung =
  | { kind: "chua-co-endpoint"; url: string; work: string }
  | { kind: "khong-con-trong-nhom" }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; status: number; detail: string }
  | { kind: "du-lieu-sai"; url: string; detail: string };

export type BanDoState =
  | { kind: "dang-tai" }
  | { kind: "co-du-lieu"; data: BanDoNhomData }
  | LoiChung;

export type NhietDoState =
  | { kind: "dang-tai" }
  | { kind: "co-du-lieu"; data: NhietDoData }
  | LoiChung;

export type DiemHenState =
  | { kind: "chua-hoi" }
  | { kind: "dang-tai" }
  | { kind: "co-du-lieu"; data: DiemHenData }
  | LoiChung;

export type KhuVucState =
  | { kind: "dang-tai" }
  | { kind: "co-du-lieu"; data: KhuVuc[] }
  | LoiChung;

/** Named in the UI so a 404 points at a stale API build rather than at a
 *  missing feature. These three routes ship with these screens. */
export const BAN_DO_WORK_ITEM = "rd-fe-33";

/* -------------------------------------------------------------------------
 * Parsing. Strict, and loud about which field was wrong.
 * ---------------------------------------------------------------------- */

function num(v: unknown, field: string): number {
  if (typeof v !== "number" || !Number.isFinite(v)) {
    throw new Error(`${field} phải là số, nhận được ${JSON.stringify(v)}`);
  }
  return v;
}

/** A count of rows. Fractional or negative means the server is wrong about
 *  something more serious than this field, so it is refused rather than
 *  rounded into a number that looks fine on screen. */
function dem(v: unknown, field: string): number {
  const n = num(v, field);
  if (!Number.isInteger(n) || n < 0) {
    throw new Error(`${field} phải là số đếm không âm, nhận được ${n}`);
  }
  return n;
}

function str(v: unknown, field: string): string {
  if (typeof v !== "string" || v.trim() === "") {
    throw new Error(`${field} phải là chuỗi không rỗng`);
  }
  return v;
}

function bool(v: unknown, field: string): boolean {
  if (typeof v !== "boolean") throw new Error(`${field} phải là true hoặc false`);
  return v;
}

function obj(v: unknown, field: string): Record<string, unknown> {
  if (typeof v !== "object" || v === null || Array.isArray(v)) {
    throw new Error(`${field} phải là một object`);
  }
  return v as Record<string, unknown>;
}

function arr(v: unknown, field: string): unknown[] {
  if (!Array.isArray(v)) throw new Error(`${field} phải là mảng`);
  return v;
}

function parseChoDaDi(raw: unknown, field: string): ChoDaDi {
  const o = obj(raw, field);
  return {
    placeId: str(o.place_id, `${field}.place_id`),
    placeName: str(o.place_name, `${field}.place_name`),
    lat: num(o.lat, `${field}.lat`),
    lng: num(o.lng, `${field}.lng`),
    visitCount: dem(o.visit_count, `${field}.visit_count`),
  };
}

function parseChoTrenBanDo(raw: unknown, field: string): ChoTrenBanDo {
  const o = obj(raw, field);
  return {
    placeId: str(o.place_id, `${field}.place_id`),
    placeName: str(o.place_name, `${field}.place_name`),
    lat: num(o.lat, `${field}.lat`),
    lng: num(o.lng, `${field}.lng`),
    rating: num(o.rating, `${field}.rating`),
    ratingCount: dem(o.rating_count, `${field}.rating_count`),
  };
}

export function parseBanDoNhom(body: unknown): BanDoNhomData {
  const b = obj(body, "body");
  return {
    daDi: arr(b.visited, "visited").map((x, i) => parseChoDaDi(x, `visited[${i}]`)),
    dangHot: arr(b.trending, "trending").map((x, i) => parseChoTrenBanDo(x, `trending[${i}]`)),
    nenThu: arr(b.recommended, "recommended").map((x, i) =>
      parseChoTrenBanDo(x, `recommended[${i}]`),
    ),
    chuaCo: arr(b.unavailable, "unavailable").map((x, i) => {
      const o = obj(x, `unavailable[${i}]`);
      return {
        layer: str(o.layer, `unavailable[${i}].layer`),
        reason: str(o.reason, `unavailable[${i}].reason`),
      };
    }),
    daQuet: dem(b.scanned_checkins, "scanned_checkins"),
    batHet: bool(b.truncated, "truncated"),
  };
}

export function parseNhietDo(body: unknown): NhietDoData {
  const b = obj(body, "body");
  return {
    khu: arr(b.areas, "areas").map((x, i) => {
      const o = obj(x, `areas[${i}]`);
      const share = dem(o.share_percent, `areas[${i}].share_percent`);
      if (share > 100) {
        throw new Error(`areas[${i}].share_percent không thể lớn hơn 100, nhận được ${share}`);
      }
      return {
        id: str(o.id, `areas[${i}].id`),
        label: str(o.label, `areas[${i}].label`),
        lat: num(o.lat, `areas[${i}].lat`),
        lng: num(o.lng, `areas[${i}].lng`),
        visitCount: dem(o.visit_count, `areas[${i}].visit_count`),
        sharePercent: share,
      };
    }),
    daNhanRa: dem(b.resolved_checkins, "resolved_checkins"),
    khongRoKhu: dem(b.unknown_area_count, "unknown_area_count"),
    daQuet: dem(b.scanned_checkins, "scanned_checkins"),
    batHet: bool(b.truncated, "truncated"),
  };
}

function parseKhuVuc(raw: unknown, field: string): KhuVuc {
  const o = obj(raw, field);
  return {
    id: str(o.id, `${field}.id`),
    label: str(o.label, `${field}.label`),
    lat: num(o.lat, `${field}.lat`),
    lng: num(o.lng, `${field}.lng`),
  };
}

export function parseDiemHen(body: unknown): DiemHenData {
  const b = obj(body, "body");
  return {
    diemXuatPhat: arr(b.origins, "origins").map((x, i) => parseKhuVuc(x, `origins[${i}]`)),
    ungVien: arr(b.candidates, "candidates").map((x, i) => {
      const o = obj(x, `candidates[${i}]`);
      const f = obj(o.fairness, `candidates[${i}].fairness`);
      return {
        placeId: str(o.place_id, `candidates[${i}].place_id`),
        placeName: str(o.place_name, `candidates[${i}].place_name`),
        category: str(o.category, `candidates[${i}].category`),
        address: str(o.address, `candidates[${i}].address`),
        lat: num(o.lat, `candidates[${i}].lat`),
        lng: num(o.lng, `candidates[${i}].lng`),
        canBang: {
          worstKm: num(f.worst_km, `candidates[${i}].fairness.worst_km`),
          totalKm: num(f.total_km, `candidates[${i}].fairness.total_km`),
          spreadKm: num(f.spread_km, `candidates[${i}].fairness.spread_km`),
        },
        chang: arr(o.travel, `candidates[${i}].travel`).map((t, j) => {
          const leg = obj(t, `candidates[${i}].travel[${j}]`);
          return {
            ...parseKhuVuc(leg, `candidates[${i}].travel[${j}]`),
            km: num(leg.km, `candidates[${i}].travel[${j}].km`),
          };
        }),
      };
    }),
    suyNguocDuoc: bool(b.two_origin_inversion, "two_origin_inversion"),
  };
}

/* -------------------------------------------------------------------------
 * Calls.
 * ---------------------------------------------------------------------- */

export function khuVucUrl(base: string): string {
  return `${base.replace(/\/$/, "")}/areas`;
}

export function banDoUrl(base: string, contextId: string = CONTEXT_ID): string {
  return `${base.replace(/\/$/, "")}/contexts/${contextId}/map`;
}

export function nhietDoUrl(base: string, contextId: string = CONTEXT_ID): string {
  return `${base.replace(/\/$/, "")}/contexts/${contextId}/heatmap`;
}

export function diemHenUrl(base: string, contextId: string = CONTEXT_ID): string {
  return `${base.replace(/\/$/, "")}/contexts/${contextId}/meet`;
}

type GoiOpts = {
  personId: string;
  contextId?: string;
  base?: string;
  fetchImpl?: typeof fetch;
};

/**
 * The shared half of all three calls: send the actor, read the response, and
 * turn every status into a state.
 *
 * `X-Actor-ID` is not optional here. All three routes are member-gated, and
 * without the header the gateway shim has no actor to check, so the answer is
 * an authorisation failure rather than data. `scripts/check_actor_headers.py`
 * is the gate that keeps this true.
 */
async function goi<T>(
  url: string,
  init: RequestInit,
  parse: (body: unknown) => T,
  opts: GoiOpts,
): Promise<{ kind: "co-du-lieu"; data: T } | LoiChung> {
  const doFetch = opts.fetchImpl ?? fetch;

  let res: Response;
  try {
    res = await doFetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        "X-Actor-ID": opts.personId,
        ...(init.headers ?? {}),
      },
    });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: chiTietLoi(e) };
  }

  // 403 before 404: being outside the group is not a failure of anything, and
  // it is the only non-error non-answer these routes have.
  if (res.status === 403) return { kind: "khong-con-trong-nhom" };
  if (res.status === 404) return { kind: "chua-co-endpoint", url, work: BAN_DO_WORK_ITEM };
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.text()).slice(0, 200) || detail;
    } catch {
      /* body already read or not text; the status alone still says enough */
    }
    return { kind: "may-chu-loi", url, status: res.status, detail };
  }

  try {
    return { kind: "co-du-lieu", data: parse(await res.json()) };
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: chiTietLoi(e) };
  }
}

/**
 * The districts the meeting-point route will accept.
 *
 * Fetched rather than written into the app. The eight ids live in
 * `app/places/areas.py`, and a hand-kept copy here would be a third copy to
 * drift -- the failure that produces is a picker offering an id the server
 * answers 422 for, which looks to a user like a form refusing a reasonable
 * answer for no reason.
 */
export async function fetchKhuVuc(opts: GoiOpts): Promise<KhuVucState> {
  const url = khuVucUrl(opts.base ?? PLACES_BASE_URL);
  return goi(
    url,
    { method: "GET" },
    (body) => arr(body, "body").map((x, i) => parseKhuVuc(x, `[${i}]`)),
    opts,
  );
}

export async function fetchBanDoNhom(opts: GoiOpts): Promise<BanDoState> {
  const url = banDoUrl(opts.base ?? PLACES_BASE_URL, opts.contextId);
  return goi(url, { method: "GET" }, parseBanDoNhom, opts);
}

export async function fetchNhietDo(opts: GoiOpts): Promise<NhietDoState> {
  const url = nhietDoUrl(opts.base ?? PLACES_BASE_URL, opts.contextId);
  return goi(url, { method: "GET" }, parseNhietDo, opts);
}

/**
 * Ask for a meeting point.
 *
 * The body carries areas and nothing else. There is no member field to fill in
 * and no place to put one: the mapping from a person to an area stays on the
 * phone that knows it. See `MeetingPointRequest` -- the server sets
 * `extra="forbid"`, so an extra field is a 422 rather than something quietly
 * ignored, and that is the behaviour this function is written to keep.
 */
export async function fetchDiemHen(
  khuVucIds: string[],
  opts: GoiOpts,
): Promise<DiemHenState> {
  const url = diemHenUrl(opts.base ?? PLACES_BASE_URL, opts.contextId);
  return goi(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_areas: khuVucIds }),
    },
    parseDiemHen,
    opts,
  );
}

/* -------------------------------------------------------------------------
 * Formatting.
 * ---------------------------------------------------------------------- */

/** "3 lần" -- the unit is always written, because a bare numeral beside a
 *  place name reads as a rank or a rating just as easily as a count. */
export function soLan(n: number): string {
  return `${n} lần`;
}

/** Kilometres to one decimal. The server sends a float and this is a distance,
 *  not money -- money law 1 governs đồng, and rounding a journey to the whole
 *  kilometre would make two candidates 400 m apart look identical. */
export function soKm(km: number): string {
  return `${km.toFixed(1)} km`;
}

/**
 * The disclosure sentence that goes above every list on these screens.
 *
 * Above, not below: a caveat under a list is read after the reader has already
 * believed the list. When the scan hit its ceiling the sentence says so in
 * words, because `truncated` is the difference between "the group's habits"
 * and "the first 500 check-ins of them".
 */
export function cauDaQuet(daQuet: number, batHet: boolean): string {
  if (batHet) {
    return `Đếm từ ${daQuet} lần check-in gần nhất. Nhóm còn nhiều hơn thế, phần cũ hơn chưa tính vào đây.`;
  }
  if (daQuet === 0) return "Nhóm chưa có lần check-in nào, nên chưa có gì để đếm.";
  return `Đếm từ toàn bộ ${daQuet} lần check-in của nhóm.`;
}

/** The heatmap's second disclosure: check-ins that fell outside every district
 *  the product knows. Silence here would present a fraction as the whole. */
export function cauKhongRoKhu(khongRoKhu: number): string | null {
  if (khongRoKhu <= 0) return null;
  return `${khongRoKhu} lần check-in ở nơi chưa nằm trong danh sách khu vực, nên không vào bảng này.`;
}
