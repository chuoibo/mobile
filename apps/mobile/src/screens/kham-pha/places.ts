/** The place catalogue, as the app asks the server for it.
 *
 * Deliberately free of React so the parts that can be wrong -- the wire shape,
 * the money formatting, the refusal to show a percentage nobody computed --
 * are checked by `tests/kham-pha.test.mjs` rather than by looking at a phone.
 *
 * ## Where the data comes from, and what happens when it does not
 *
 * `GET /places` is real: `services/api/app/api/routes/places.py`, work item
 * **rd-be-05**. There is still no bundled catalogue, no fixture fallback and no
 * canned Vietnamese sentence standing in for a reason. If the server cannot be
 * reached, or is an older build without the route, the screen says which
 * address it tried rather than showing invented places -- the same rule
 * `api.ts` states for the expense flow, for the same reason. A demo quietly
 * running on made-up data is worse than a demo that is honest about being
 * unfinished.
 *
 * ## Why the percentage is gated on `source` and `verdict`
 *
 * rd-be-05's own brief: "Con số 95% không có giá trị tự thân... nếu là số giả
 * thì đừng hiện phần trăm."
 *
 * The server computes two things independently and does not let either one
 * write the other:
 *
 * * `score` is arithmetic over budget, taste, distance and group size. It
 *   arrives with `factors`, which is that arithmetic shown, so the number can
 *   be argued with instead of merely believed.
 * * `verdict` is Gemini's own answer, from a prompt that withholds the score
 *   and permits `khong-hop`. It is allowed to disagree with the score, and in
 *   practice it does -- a place that is cheap, close and roomy still gets
 *   `khong-hop` when it is shut this evening, which the arithmetic misses.
 *
 * `matchLabel()` is where those two meet, and the rule it enforces is: the
 * words **AI MATCH** and a percentage together require both a model answer and
 * a model verdict of `hop`. Everything else says less. The test file pins each
 * case, because this is the exact spot where a demo starts lying politely.
 */
import { chiTietLoi } from "../../ui/loi-tren-man";
import { nguonAnhAnToan } from "../../ui/nguon-anh";

/** Where the API lives. Same read as `api.ts`, and it has to stay this exact
 *  shape: Expo's inline-env-vars plugin pattern-matches the syntax tree and a
 *  defensive `process?.env?.X` is not substituted. See `api.ts` for the full
 *  account and `tests/env-inlining.test.mjs` for the gate. */
declare const process: { env: Record<string, string | undefined> };

export const PLACES_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

/** The group whose budget and taste the match is scored against. Same
 *  synthetic id the expense flow uses, so both halves of the app agree on
 *  which group is on screen. */
export const CONTEXT_ID = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";

/**
 * Who wrote the reason under a match score.
 *
 * `ai` means Gemini answered about this specific place and the server's
 * grounding check passed the sentence. `none` means it did not -- the model was
 * unreachable, skipped the row, or asserted a figure that was nowhere in the
 * data it was given. In that case `reason` is a plain factual line assembled
 * from the same numbers `factors` carries, and nothing on screen calls it AI.
 *
 * There is deliberately no third value. A dev stub server used to send one, and
 * the lesson was that a canned sentence is indistinguishable from a generated
 * one once it is on a screen -- so the union has no room left for it.
 */
export type ReasonSource = "ai" | "none";

/**
 * The model's own conclusion, absent when it did not give one.
 *
 * `khong-hop` is a first-class answer, not an error: the prompt is written to
 * make refusing possible, because a recommender that never says no is not
 * recommending anything.
 */
export type Verdict = "hop" | "tam" | "khong-hop";

export type MatchFactor = {
  /** "Budget", "Sở thích", "Nhóm", "Thời gian" -- the four rows the mockup
   *  draws feeding into the score. */
  label: string;
  detail: string;
};

export type Match = {
  /** 0-100. Server arithmetic over budget, taste, distance and group size --
   *  never a model output. `factors` is the working. */
  score: number;
  /** Natural Vietnamese, one or two sentences, naming the actual data. */
  reason: string;
  source: ReasonSource;
  /** Null whenever `source` is `none`; the model gave no answer to carry. */
  verdict: Verdict | null;
  factors: MatchFactor[];
};

export type GroupFit = {
  minPeople: number;
  maxPeople: number;
  /** "Bạn bè, đồng nghiệp" -- who the place suits, not who is in the group. */
  relation: string;
};

export type Place = {
  id: string;
  name: string;
  category: string;
  /** The "BBQ · Lào · Local" line. Kept as parts so the separator is the
   *  screen's decision and a one-kind place does not render a dangling dot. */
  kinds: string[];
  /** Null since M9: no imported place has a rating, and inventing one would
   *  put a number on a card that no one ever gave. */
  rating: number | null;
  ratingCount: number | null;
  distanceKm: number | null;
  /** Integer đồng, both ends, or null when nobody has priced the place. Money
   *  law 1 still reaches here: a band that arrives as 249.5 is a defect
   *  upstream, not something to round on screen. */
  priceMinVnd: number | null;
  priceMaxVnd: number | null;
  address: string | null;
  /** `null` means «nobody told us», which is not «closed». The screen has to
   *  say those two differently. */
  openNow: boolean | null;
  openHours: string | null;
  travelMinutes: number | null;
  photoCount: number;
  /** The cover photograph, as a path on this app's own API, or null for a
   *  place nobody has photographed yet (M12). */
  photoUrl: string | null;
  /**
   * Whose photograph the cover is, and under what licence.
   *
   * They travel with the URL because ADR-0017 lets a photograph be *shown*
   * only where its credit is shown: a card that has the picture but not the
   * two words under it is not allowed to draw the picture. Null exactly when
   * `photoUrl` is null.
   */
  photoAuthor: string | null;
  photoLicense: string | null;
  traits: string[];
  groupFit: GroupFit | null;
  /** "new" | "hot" ribbon in the mockup's top-left. Null is the normal case. */
  flag: "new" | "hot" | null;
  lat: number;
  lng: number;
  /** Where the row came from. ODbL makes attribution a condition for `osm`,
   *  so the screen has to be able to name the source. */
  source: "seed" | "osm" | "curated";
  license: string | null;
  /** Null when the server could not score this place for this group. The
   *  card then shows no badge at all rather than a zero. */
  match: Match | null;
};

export type Category = { id: string; label: string };

/**
 * Everything the screen can be showing.
 *
 * Four of these five are failures, spelled out separately, because they need
 * different words. "Không mở được máy chủ" and "máy chủ có nhưng chưa có route
 * này" send a person to two different places, and collapsing them into one
 * "lỗi" is how an afternoon gets spent restarting a server that was fine.
 */
export type PlacesState =
  | { kind: "dang-tai" }
  | { kind: "co-du-lieu"; places: Place[]; categories: Category[] }
  | { kind: "chua-co-endpoint"; url: string; work: string }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; status: number; detail: string }
  | { kind: "du-lieu-sai"; url: string; detail: string };

/** Named in the UI so a 404 is attributable rather than mysterious. The route
 *  exists on `main` now, so seeing this on screen means the app is pointed at
 *  an API build from before rd-be-05 -- usually a stale container on the port
 *  in `EXPO_PUBLIC_API_URL`, not a missing feature. */
export const PLACES_WORK_ITEM = "rd-be-05";

function num(v: unknown, field: string): number {
  if (typeof v !== "number" || !Number.isFinite(v)) {
    throw new Error(`${field} phải là số, nhận được ${JSON.stringify(v)}`);
  }
  return v;
}

function int(v: unknown, field: string): number {
  const n = num(v, field);
  // Money law 1 -- integer đồng, no floats, not even at an intermediate step.
  // A price band that arrives fractional is a server defect and is refused
  // here rather than rounded into something that looks fine.
  if (!Number.isInteger(n)) {
    throw new Error(`${field} phải là số nguyên đồng, nhận được ${n}`);
  }
  return n;
}

/**
 * Optional versions of the three readers above (M9).
 *
 * Since the catalogue became a table fed by OpenStreetMap, most facts about a
 * place may be missing: OSM gives a name, a point and a kind, and nothing else
 * is guaranteed. `null` and `undefined` both mean «chưa có» and both come back
 * as `null`; anything present is still checked exactly as strictly as before,
 * so a rating of `"4.7"` is still a defect and still says so.
 */
function numOrNull(v: unknown, field: string): number | null {
  if (v === null || v === undefined) return null;
  return num(v, field);
}

function intOrNull(v: unknown, field: string): number | null {
  if (v === null || v === undefined) return null;
  return int(v, field);
}

function strOrNull(v: unknown, field: string): string | null {
  if (v === null || v === undefined) return null;
  const value = str(v, field);
  return value;
}

function str(v: unknown, field: string): string {
  if (typeof v !== "string" || v.trim() === "") {
    throw new Error(`${field} phải là chuỗi không rỗng`);
  }
  return v;
}

function strList(v: unknown, field: string): string[] {
  if (!Array.isArray(v)) throw new Error(`${field} phải là mảng`);
  return v.map((x, i) => str(x, `${field}[${i}]`));
}

/**
 * Read a server-sent image URL. Tolerant on purpose: missing, null, a
 * non-string, or an empty string become `null` rather than a throw, because
 * most places have no photograph and every card must still render.
 *
 * Only addresses on this app's own API are accepted, and the rule lives in
 * `nguonAnhAnToan` rather than here. This value goes straight into an
 * `<Image>`, which *dials* it -- so an arbitrary host would learn the reader's
 * IP and the moment they opened the screen. See `src/ui/nguon-anh.ts` for the
 * full account of why the origin, and not just the scheme, is the thing being
 * checked.
 *
 * This used to accept any `http(s)://` address and reject relative paths --
 * backwards on both sides, since `/contexts/{id}/photos/{id}` is the shape the
 * photo route actually returns.
 */
function parsePhotoUrl(v: unknown): string | null {
  return nguonAnhAnToan(v, PLACES_BASE_URL);
}

function parseMatch(raw: unknown, field: string): Match | null {
  if (raw === null || raw === undefined) return null;
  const m = raw as Record<string, unknown>;
  const source = m.source;
  if (source !== "ai" && source !== "none") {
    throw new Error(`${field}.source phải là ai|none, nhận được ${JSON.stringify(source)}`);
  }
  const verdict = m.verdict ?? null;
  if (verdict !== null && verdict !== "hop" && verdict !== "tam" && verdict !== "khong-hop") {
    throw new Error(`${field}.verdict phải là hop|tam|khong-hop|null, nhận được ${JSON.stringify(verdict)}`);
  }
  // A model answer with no verdict, or a verdict with no model answer, means
  // the two halves of the server disagree about whether Gemini spoke. Refusing
  // is better than picking one and rendering a badge on a coin toss.
  if ((source === "ai") !== (verdict !== null)) {
    throw new Error(`${field}: source=${source} nhưng verdict=${JSON.stringify(verdict)}`);
  }
  const score = num(m.score, `${field}.score`);
  if (score < 0 || score > 100) throw new Error(`${field}.score ngoài 0-100: ${score}`);
  const factors = Array.isArray(m.factors) ? m.factors : [];
  return {
    score,
    reason: str(m.reason, `${field}.reason`),
    source,
    verdict,
    factors: factors.map((f, i) => {
      const o = f as Record<string, unknown>;
      return {
        label: str(o.label, `${field}.factors[${i}].label`),
        detail: str(o.detail, `${field}.factors[${i}].detail`),
      };
    }),
  };
}

/**
 * Turn one wire object into a `Place`, or throw naming the field.
 *
 * Strict on purpose. A screen that renders `undefined` for a rating looks like
 * a styling bug and gets chased in the wrong file for an hour; a refusal that
 * names `places[3].rating` is read once and fixed.
 */
export function parsePlace(raw: unknown, field: string): Place {
  const p = raw as Record<string, unknown>;
  const flag = p.flag ?? null;
  if (flag !== null && flag !== "new" && flag !== "hot") {
    throw new Error(`${field}.flag phải là new|hot|null, nhận được ${JSON.stringify(flag)}`);
  }
  const fit = p.group_fit as Record<string, unknown> | null | undefined;
  const priceMin = intOrNull(p.price_min_vnd, `${field}.price_min_vnd`);
  const priceMax = intOrNull(p.price_max_vnd, `${field}.price_max_vnd`);
  if (priceMin !== null && priceMax !== null && priceMax < priceMin) {
    throw new Error(`${field}: khoảng giá ngược, ${priceMin} > ${priceMax}`);
  }
  // Half a band is not a band: one end without the other cannot be drawn and
  // cannot be compared, so it is a server defect rather than a display case.
  if ((priceMin === null) !== (priceMax === null)) {
    throw new Error(`${field}: khoảng giá thiếu một đầu`);
  }
  const source = p.source ?? "seed";
  if (source !== "seed" && source !== "osm" && source !== "curated") {
    throw new Error(
      `${field}.source phải là seed|osm|curated, nhận được ${JSON.stringify(source)}`,
    );
  }
  return {
    id: str(p.id, `${field}.id`),
    name: str(p.name, `${field}.name`),
    category: str(p.category, `${field}.category`),
    kinds: strList(p.kinds ?? [], `${field}.kinds`),
    rating: numOrNull(p.rating, `${field}.rating`),
    ratingCount: intOrNull(p.rating_count, `${field}.rating_count`),
    distanceKm: numOrNull(p.distance_km, `${field}.distance_km`),
    priceMinVnd: priceMin,
    priceMaxVnd: priceMax,
    address: strOrNull(p.address, `${field}.address`),
    // Three states, not two: true, false, and «nobody told us».
    openNow: p.open_now === null || p.open_now === undefined ? null : p.open_now === true,
    openHours: strOrNull(p.open_hours, `${field}.open_hours`),
    travelMinutes: intOrNull(p.travel_minutes, `${field}.travel_minutes`),
    photoCount: int(p.photo_count ?? 0, `${field}.photo_count`),
    photoUrl: parsePhotoUrl(p.photo_url),
    photoAuthor: strOrNull(p.photo_author, `${field}.photo_author`),
    photoLicense: strOrNull(p.photo_license, `${field}.photo_license`),
    traits: strList(p.traits ?? [], `${field}.traits`),
    groupFit: fit
      ? {
          minPeople: int(fit.min_people, `${field}.group_fit.min_people`),
          maxPeople: int(fit.max_people, `${field}.group_fit.max_people`),
          relation: str(fit.relation, `${field}.group_fit.relation`),
        }
      : null,
    flag,
    lat: num(p.lat, `${field}.lat`),
    lng: num(p.lng, `${field}.lng`),
    source,
    license: strOrNull(p.license, `${field}.license`),
    match: parseMatch(p.match, `${field}.match`),
  };
}

export function parseCatalogue(body: unknown): {
  places: Place[];
  categories: Category[];
  destination: { id: string; name: string };
} {
  const b = body as Record<string, unknown>;
  if (!Array.isArray(b?.places)) throw new Error("thiếu mảng `places`");
  const cats = Array.isArray(b.categories) ? b.categories : [];
  // Required since M10: a list of places with no city attached cannot be
  // labelled, and the screen would have to invent the name it prints.
  const d = b.destination as Record<string, unknown> | undefined;
  if (d === undefined || d === null) throw new Error("thiếu `destination`");
  return {
    places: b.places.map((p, i) => parsePlace(p, `places[${i}]`)),
    categories: cats.map((cat, i) => {
      const o = cat as Record<string, unknown>;
      return { id: str(o.id, `categories[${i}].id`), label: str(o.label, `categories[${i}].label`) };
    }),
    destination: { id: str(d.id, "destination.id"), name: str(d.name, "destination.name") },
  };
}

export function placesUrl(base: string, opts: { category?: string | null; q?: string } = {}): string {
  const params = new URLSearchParams({ context_id: CONTEXT_ID });
  if (opts.category) params.set("category", opts.category);
  if (opts.q && opts.q.trim()) params.set("q", opts.q.trim());
  return `${base.replace(/\/$/, "")}/places?${params.toString()}`;
}

/**
 * Ask the server for places, and turn every way that can go wrong into a
 * state the screen knows how to say out loud.
 *
 * Never throws. A rejected promise here would surface as a blank tab, which
 * is the one outcome this whole file exists to prevent.
 */
export async function fetchPlaces(
  opts: { category?: string | null; q?: string; base?: string; fetchImpl?: typeof fetch } = {},
): Promise<PlacesState> {
  const base = opts.base ?? PLACES_BASE_URL;
  const url = placesUrl(base, opts);
  const doFetch = opts.fetchImpl ?? fetch;

  let res: Response;
  try {
    res = await doFetch(url, { headers: { Accept: "application/json" } });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: chiTietLoi(e) };
  }

  // 404 still gets its own state now that the route exists: the server is up
  // and answering, but this one path is missing, which points at a stale API
  // build rather than at the network. Two different afternoons.
  if (res.status === 404) return { kind: "chua-co-endpoint", url, work: PLACES_WORK_ITEM };
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
    const parsed = parseCatalogue(await res.json());
    return { kind: "co-du-lieu", places: parsed.places, categories: parsed.categories };
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: chiTietLoi(e) };
  }
}

/* -------------------------------------------------------------------------
 * Formatting. Every one of these is a place a number can be made to lie.
 * ---------------------------------------------------------------------- */

/**
 * "200–250k" for a band, "250k" when both ends agree.
 *
 * Integer arithmetic throughout. `Math.round(vnd / 1000)` on a value the
 * parser has already forced to an integer đồng cannot introduce a fraction,
 * and the parser refuses the input that would.
 */
export function formatPriceBand(minVnd: number, maxVnd: number): string {
  const k = (v: number) => `${Math.round(v / 1000)}`;
  return minVnd === maxVnd ? `${k(minVnd)}k` : `${k(minVnd)}–${k(maxVnd)}k`;
}

/** "~200–250k/người", the mockup's own phrasing. */
export function formatPricePerPerson(minVnd: number, maxVnd: number): string {
  return `~${formatPriceBand(minVnd, maxVnd)}/người`;
}

/** "1.2km" under 10km, "12km" above -- one decimal stops being information. */
export function formatDistance(km: number): string {
  return km < 10 ? `${km.toFixed(1)}km` : `${Math.round(km)}km`;
}

export function formatRating(rating: number, count: number): string {
  return `${rating.toFixed(1)} (${count})`;
}

/** "BBQ · Lào · Local", and just "BBQ" when that is all there is. */
export function formatKinds(kinds: string[]): string {
  return kinds.join(" · ");
}

/**
 * What the badge on a card is allowed to say.
 *
 * The whole point of rd-be-05 is that the number is worthless without a reason,
 * and a number nobody computed is worse than no number. Four cases, and each
 * one says exactly as much as it can support:
 *
 * | source | verdict     | badge              | why |
 * |--------|-------------|--------------------|-----|
 * | `ai`   | `hop`       | AI MATCH 96%       | model read the row and agreed with the arithmetic |
 * | `ai`   | `tam`       | TẠM HỢP 81%        | model saw a gap; the percentage still holds, the enthusiasm does not |
 * | `ai`   | `khong-hop` | AI: CHƯA HỢP       | no percentage -- see below |
 * | `none` | `null`      | ĐIỂM 40%           | arithmetic only; nothing here is a model output |
 *
 * The third row is the one worth defending. A place can score 81 on budget,
 * distance and capacity and still be shut this evening, and that is a real
 * observed case, not a hypothetical. Printing "81%" beside "chưa hợp" invites
 * the reader to weigh a number against a conclusion that already outranks it.
 * The score does not vanish -- it is in the detail sheet with its factors --
 * but it does not get to argue with the verdict from the front of the card.
 */
export function matchLabel(match: Match | null): { text: string; real: boolean } | null {
  if (!match) return null;
  const pct = Math.round(match.score);
  if (match.source !== "ai") return { text: `ĐIỂM ${pct}%`, real: false };
  if (match.verdict === "khong-hop") return { text: "AI: CHƯA HỢP", real: true };
  if (match.verdict === "tam") return { text: `TẠM HỢP ${pct}%`, real: true };
  return { text: `AI MATCH ${pct}%`, real: true };
}

/* `locNoiBo` lived here: a local substring filter over the loaded list, which
 * the note above it called what it was, a stand-in for the language problem
 * "quán chill view đẹp ở Đà Lạt budget ~250k" actually poses. rd-fe-15 wired
 * the box to `POST /places/search`, so the stand-in was removed rather than
 * left exported beside the real thing. An unreachable helper with passing
 * tests is worse than no helper: the tests keep reporting coverage for
 * behaviour no one on a phone can get to. See `tim-kiem.ts`. */

/** Open before closed, then best-scoring first, unscored last, ties broken by
 *  rating so the order does not shuffle between two identical renders.
 *
 *  `openNow` is a TIER, not a term in the score. A closed place does not merely
 *  lose points -- it sorts below every open place, however well it scores.
 *  Weighting it instead would let a closed place out-argue an open one on
 *  budget and distance and be recommended for tonight.
 *
 *  This mirrors the server's ordering on purpose. The server sorts, but the
 *  screen re-sorts after a local search; without the same rule here, filtering
 *  would quietly restore the order the server had just rejected. */
export function byMatchThenRating(a: Place, b: Place): number {
  // Three states since M9, and the tier is «known open» versus everything
  // else: an unknown door is not an open one, and it is not a shut one either.
  // Same rule the server sorts by, for the same reason as the note above.
  const moA = a.openNow === true;
  const moB = b.openNow === true;
  if (moA !== moB) return moA ? -1 : 1;
  const sa = a.match?.score ?? -1;
  const sb = b.match?.score ?? -1;
  if (sa !== sb) return sb - sa;
  // An unrated place sorts after a rated one at equal score, rather than being
  // ranked as if somebody had given it zero stars.
  return (b.rating ?? -1) - (a.rating ?? -1);
}
