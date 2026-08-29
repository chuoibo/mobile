/** F12 -- "quán nướng ngoài trời cho 6 người dưới 300k" asked out loud.
 *
 * `POST /places/search` is real: `services/api/app/api/routes/places.py`, work
 * item **rd-be-10**. React-free on purpose, like `places.ts` beside it, so the
 * parts that can be wrong -- the wire shape, the reading of `source`, the
 * refusal to invent a result -- are checked by `tests/tim-dia-diem.test.mjs`
 * rather than by looking at a phone.
 *
 * ## The sentence goes to the server untouched
 *
 * `askSearch` sends `{ query }` and nothing else. It does not prepend a
 * template, append the group profile, wrap the text in quotes, or glue on a
 * category the person happened to have selected. That is not tidiness: this
 * text reaches a model prompt, so it is the app's first real prompt-injection
 * surface, and every string this file concatenated around it would be a second
 * place where an instruction could be smuggled in and a second thing the
 * server's grounding could not see. The server owns the prompt. The client
 * owns one field.
 *
 * The only thing done to the text is `trim()` and a length cap, both of which
 * mirror constraints the server already enforces (`MAX_QUERY_CHARS = 300`,
 * blank rejected). Mirroring a limit is not composing a prompt; it spends one
 * fewer round trip to say the same no.
 *
 * ## Why `source: "ai"` with no places is not a failure
 *
 * The server distinguishes two outcomes the screen must never merge:
 *
 * * **`source: "ai"`, `places: []`** -- a model answered, the answer was
 *   grounded, and the honest answer was that nothing in the catalogue fits.
 *   `understood` is present, and this is precisely where it earns its place on
 *   screen: someone who typed "dưới 30k" and gets nothing needs to see that the
 *   AI read 30.000đ, not 300.000đ.
 * * **`source: "none"`** -- no model answer survived. The model was
 *   unreachable, or it named a place that does not exist and `ground_search`
 *   refused the whole reply rather than serving the part that happened to be
 *   real. `understood` is null because there is no reading to show.
 *
 * The route deliberately returns 200 for the second case, with an empty list,
 * and deliberately does not send the refusal code to the client. So this file
 * cannot -- and must not try to -- tell the person *which* of those causes
 * happened. `khong-tra-loi` says the true, narrow thing: nothing came back for
 * this sentence. Guessing a cause on screen would be inventing the one piece of
 * information the server withheld on purpose.
 */

import { parsePlace, PLACES_BASE_URL, type Category, type Place } from "./places";

/** The server's own cap (`app/places/search.py`, `MAX_QUERY_CHARS`). Mirrored,
 *  not re-decided: past it the route answers 422 and no model is ever called. */
export const MAX_QUERY_CHARS = 300;

/** Named in the UI so a 404 is attributable rather than mysterious. Seeing this
 *  means the app is pointed at an API build from before rd-be-10, which is
 *  usually a stale container on the port in `EXPO_PUBLIC_API_URL`. */
export const SEARCH_WORK_ITEM = "rd-be-10";

/**
 * What the model took the sentence to mean, in closed vocabularies only.
 *
 * Every field is either a number the server re-typed or a token the server
 * checked against the catalogue before sending it -- `ground_search` refuses
 * the entire answer over one unknown category or trait. So nothing here is
 * free model prose, and rendering it cannot become a second route for an
 * injected instruction to reach a screen.
 *
 * Every field is also allowed to be empty at once. A sentence the model drew no
 * conditions from is a real outcome, and `hieuDuocGi()` exists so the screen can
 * say that rather than draw an empty box.
 */
export type Understood = {
  /** Integer đồng. Money law 1 reaches the search box too: a budget that
   *  arrives fractional is a server defect, refused rather than rounded. */
  budgetPerPersonVnd: number | null;
  groupSize: number | null;
  maxDistanceKm: number | null;
  /** Category ids, guaranteed to exist in the catalogue. */
  categories: string[];
  /** Trait labels as the catalogue spells them ("Chill", "Ngoài trời"). */
  traits: string[];
};

/**
 * Everything the search can be showing.
 *
 * The failures are spelled out separately for the same reason `PlacesState`
 * spells its own out: "không mở được máy chủ" and "máy chủ có nhưng chưa có
 * route này" send a person to two different places.
 *
 * `khong-tra-loi` is the one that is *not* a defect. It is the server working
 * as designed and declining to serve a plausible answer it could not stand
 * behind, and the copy for it has to read like an answer, not like a crash.
 */
export type TimKiemState =
  | { kind: "chua-tim" }
  | { kind: "dang-tim"; query: string }
  | { kind: "co-ket-qua"; query: string; understood: Understood; places: Place[] }
  | { kind: "khong-tra-loi"; query: string }
  | { kind: "cau-khong-hop-le"; max: number }
  | { kind: "chua-biet-la-ai" }
  | { kind: "bi-tu-choi"; url: string }
  | { kind: "qua-nhieu-lan"; query: string }
  | { kind: "chua-co-endpoint"; url: string; work: string }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; status: number; detail: string }
  | { kind: "du-lieu-sai"; url: string; detail: string };

function intOrNull(v: unknown, field: string): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v !== "number" || !Number.isFinite(v)) {
    throw new Error(`${field} phải là số hoặc null, nhận được ${JSON.stringify(v)}`);
  }
  // Money law 1 and headcounts alike: neither 249.5 đồng nor 6.5 người is a
  // value this screen is willing to render as though it were meant.
  if (!Number.isInteger(v)) {
    throw new Error(`${field} phải là số nguyên, nhận được ${v}`);
  }
  return v;
}

function numOrNull(v: unknown, field: string): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v !== "number" || !Number.isFinite(v)) {
    throw new Error(`${field} phải là số hoặc null, nhận được ${JSON.stringify(v)}`);
  }
  return v;
}

function strList(v: unknown, field: string): string[] {
  if (v === null || v === undefined) return [];
  if (!Array.isArray(v)) throw new Error(`${field} phải là mảng`);
  return v.map((x, i) => {
    if (typeof x !== "string" || x.trim() === "") {
      throw new Error(`${field}[${i}] phải là chuỗi không rỗng`);
    }
    return x;
  });
}

export function parseUnderstood(raw: unknown, field = "understood"): Understood {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error(`${field} phải là object`);
  }
  const u = raw as Record<string, unknown>;
  return {
    budgetPerPersonVnd: intOrNull(u.budget_per_person_vnd, `${field}.budget_per_person_vnd`),
    groupSize: intOrNull(u.group_size, `${field}.group_size`),
    maxDistanceKm: numOrNull(u.max_distance_km, `${field}.max_distance_km`),
    categories: strList(u.categories, `${field}.categories`),
    traits: strList(u.traits, `${field}.traits`),
  };
}

/**
 * Turn one search response into the state the screen renders.
 *
 * `source` is read before anything else, and it is the whole decision. A body
 * that says `none` is not parsed for places even if it carries some, because
 * `none` is the server's statement about the *whole* answer and a client that
 * salvaged rows from it would be re-opening exactly the hole `ground_search`
 * closes: serving the part of a refused answer that happened to look real.
 */
export function parseSearch(body: unknown, query: string): TimKiemState {
  const b = body as Record<string, unknown>;
  const source = b?.source;
  if (source !== "ai" && source !== "none") {
    throw new Error(`source phải là ai|none, nhận được ${JSON.stringify(source)}`);
  }
  if (source === "none") return { kind: "khong-tra-loi", query };

  if (!Array.isArray(b.places)) throw new Error("thiếu mảng `places`");
  return {
    kind: "co-ket-qua",
    query,
    // Not defaulted to an empty reading. `source: "ai"` and a missing
    // `understood` means the two halves of the server disagree about whether a
    // model answered, and a blank panel would report that disagreement as "AI
    // hiểu: không có gì" -- a sentence about the model that nothing supports.
    understood: parseUnderstood(b.understood),
    places: b.places.map((p, i) => parsePlace(p, `places[${i}]`)),
  };
}

export function searchUrl(base: string): string {
  return `${base.replace(/\/$/, "")}/places/search`;
}

/**
 * Ask the server what a sentence means, and turn every way that can go wrong
 * into a state the screen knows how to say out loud.
 *
 * Never throws, never falls back to `GET /places`. The route itself refuses to
 * fall back to keyword matching, and for the same reason: a plausible list
 * served while the feature is broken is a broken feature nobody can see is
 * broken. A screen that quietly degraded to substring matching would be the
 * client-side version of that lie.
 */
export async function askSearch(
  query: string,
  opts: { base?: string; fetchImpl?: typeof fetch; actorId?: string } = {},
): Promise<TimKiemState> {
  const base = opts.base ?? PLACES_BASE_URL;
  const url = searchUrl(base);
  const doFetch = opts.fetchImpl ?? fetch;

  const trimmed = query.trim();
  if (!trimmed || trimmed.length > MAX_QUERY_CHARS) {
    return { kind: "cau-khong-hop-le", max: MAX_QUERY_CHARS };
  }

  // Answered here rather than by the server, for the same reason the length cap
  // is: the app already knows this one. Sending the request anyway would spend a
  // round trip to be told 401, and 401 is the status this screen has the least
  // ability to explain -- "máy chủ từ chối" is true and sends the person to look
  // at the server, when what actually happened is that nobody is signed in yet.
  if (!opts.actorId) return { kind: "chua-biet-la-ai" };

  let res: Response;
  try {
    res = await doFetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        // Who is spending the quota. rd-be-13 meters this route at 12 calls per
        // minute *per actor*, so the header is what keeps one person's burst
        // from being everybody's outage. Deliberately the only actor header
        // sent: `search_places` reads `actor.id` and authorises nothing, and a
        // role claimed here would be a claim this screen does not need.
        "X-Actor-ID": opts.actorId,
      },
      // The sentence, alone, as its own field. See the module header.
      body: JSON.stringify({ query: trimmed }),
    });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: (e as Error).message };
  }

  if (res.status === 404) return { kind: "chua-co-endpoint", url, work: SEARCH_WORK_ITEM };
  // The actor header went out and was still refused, so the two sides disagree
  // about who this is. Carries no body: the server says `authentication_required`
  // in English, and neither that nor the address it names is something the
  // person holding the phone can act on beyond signing in again.
  if (res.status === 401 || res.status === 403) return { kind: "bi-tu-choi", url };
  // Metered, not broken. Distinguished from every other refusal because it is
  // the only one that fixes itself by waiting, and because `may-chu-loi` would
  // put the limiter's English sentence and its window size on screen.
  if (res.status === 429) return { kind: "qua-nhieu-lan", query: trimmed };
  // 422 gets its own state so FastAPI's validation body never reaches a person.
  // The client mirrors both of the server's limits, so arriving here means the
  // two copies have drifted -- worth a plain sentence, not a JSON dump.
  if (res.status === 422) return { kind: "cau-khong-hop-le", max: MAX_QUERY_CHARS };
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
    return parseSearch(await res.json(), trimmed);
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: (e as Error).message };
  }
}

/* -------------------------------------------------------------------------
 * Saying the reading back. This is the half of F12 a person can argue with.
 * ---------------------------------------------------------------------- */

export type DongHieu = { label: string; value: string };

/** "300k/người" from integer đồng. Same rounding as `formatPriceBand`, and the
 *  parser has already refused anything fractional that would round visibly. */
export function formatNganSach(vnd: number): string {
  return `${Math.round(vnd / 1000)}k/người`;
}

/** "5km", and "1.5km" when the halves matter. Matches `formatDistance`'s rule
 *  of dropping a decimal that has stopped being information. */
export function formatBanKinh(km: number): string {
  return Number.isInteger(km) ? `${km}km` : `${km.toFixed(1)}km`;
}

/**
 * The model's reading, as rows a person can check against what they typed.
 *
 * Category ids are resolved to their catalogue labels when the catalogue is on
 * hand, and shown raw when it is not. Raw is not a bug worth hiding: an id on
 * screen is ugly and readable, whereas dropping the row would quietly shrink
 * the reading being shown back, which is the one thing this panel exists to
 * prevent.
 *
 * Returns `[]` when the model drew no conditions at all. That is a real answer
 * and the caller has to say it in words -- see `CauAiHieu.tsx`, which prints a
 * sentence rather than an empty box.
 */
export function hieuDuocGi(u: Understood, categories: Category[] = []): DongHieu[] {
  const nhan = new Map(categories.map((k) => [k.id, k.label]));
  const rows: DongHieu[] = [];
  if (u.budgetPerPersonVnd !== null) {
    rows.push({ label: "Ngân sách", value: formatNganSach(u.budgetPerPersonVnd) });
  }
  if (u.groupSize !== null) rows.push({ label: "Số người", value: `${u.groupSize} người` });
  if (u.maxDistanceKm !== null) {
    rows.push({ label: "Khoảng cách", value: `trong ${formatBanKinh(u.maxDistanceKm)}` });
  }
  if (u.categories.length > 0) {
    rows.push({ label: "Loại chỗ", value: u.categories.map((id) => nhan.get(id) ?? id).join(", ") });
  }
  if (u.traits.length > 0) rows.push({ label: "Đặc điểm", value: u.traits.join(", ") });
  return rows;
}
