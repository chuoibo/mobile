/** Reading a group's trip albums (F36) and the AI reel over one of them (F37).
 *
 * Three GETs, no writes. The shapes below are transcribed from the server's own
 * `AlbumListResponse` / `AlbumResponse` / `ReelResponse` in
 * `services/api/app/api/schemas.py` and checked against a live
 * `GET /openapi.json`, rather than invented on this side. A hand-written client
 * contract that drifts from the server is how a screen ends up rendering
 * `undefined` under a green test run.
 *
 * Nothing here computes money. `split_total_vnd` arrives already summed from
 * the ledger on the request that asked; this file passes the integer through
 * and the screen prints it. A second summation in TypeScript would be the one
 * arithmetic this product cannot afford to have two implementations of.
 *
 * No identity travels in a body, because there are no bodies -- who is asking
 * is the `X-Actor-ID` header and nothing else. `context_id` is in the path on
 * all three routes by the server's own design: it proves ACTIVE membership
 * before it looks an outing up, so a stranger gets the same 403 whether the
 * outing id is real or invented.
 */
import { BASE_URL } from "../../api";

/** One photograph inside an album, pointing at the memory wall's own URL.
 *
 * `image_url` is a relative `/contexts/{id}/photos/{id}` path served by the one
 * route that guards it. The album copies no bytes and mints no second media
 * door, so the screen still fetches every frame through `Anh`, with headers.
 */
export type AnhAlbum = {
  memory_id: string;
  image_url: string;
  caption: string | null;
  /** ISO-8601 with a timezone. The server refuses to emit a naive one. */
  created_at: string;
  reaction_count: number;
  comment_count: number;
};

export type DiaDiemAlbum = {
  place_id: string;
  place_name: string | null;
};

/** One row of the album shelf. */
export type TomTatAlbum = {
  outing_id: string;
  title: string;
  /** The trip's year, computed server-side. Never an AI-composed album name. */
  period_label: string;
  /** `YYYY-MM-DD`, calendar days with no timezone. */
  starts_on: string;
  ends_on: string;
  in_progress: boolean;
  photo_count: number;
  checkin_count: number;
  place_count: number;
  /** Đồng, integer, recomputed from the ledger on this request. */
  split_total_vnd: number;
  expense_count: number;
  headcount: number;
  /** The album's newest photograph, or null for a trip with none. */
  cover: AnhAlbum | null;
};

export type DanhSachAlbum = {
  context_id: string;
  albums: TomTatAlbum[];
};

/** One trip read as an album. `highlights` is a subset of `photos`, ordered by
 *  the hearts the group itself left -- their judgement counted, not a model's
 *  guess at it. */
export type Album = {
  context_id: string;
  outing_id: string;
  title: string;
  period_label: string;
  starts_on: string;
  ends_on: string;
  in_progress: boolean;
  photos: AnhAlbum[];
  photo_count: number;
  places: DiaDiemAlbum[];
  place_count: number;
  checkin_count: number;
  highlights: AnhAlbum[];
  split_total_vnd: number;
  expense_count: number;
  headcount: number;
};

/** One memory the model picked, with every displayed fact owned by the server.
 *
 * `note` is the model's sentence about this pick. It is the ONLY string on the
 * reel a machine wrote, and the screen labels it as such -- everything beside
 * it (caption, place, counts, time) is a row out of the database.
 */
export type CanhPhim = {
  memory_id: string;
  image_url: string | null;
  caption: string | null;
  place_name: string | null;
  created_at: string;
  reaction_count: number;
  comment_count: number;
  note: string;
};

/** Why a reel is or is not there. The server keeps AI provenance in its own
 *  fields rather than folding "no model" into "no memories". */
export type LyDoPhim = "ok" | "no_memories" | "unavailable" | "ungrounded";

export type ThuocPhim = {
  context_id: string;
  outing_id: string;
  reeled: boolean;
  reason: LyDoPhim;
  /** `"ai"` when a model composed this, `"none"` when nothing did. */
  source: "ai" | "none";
  title: string | null;
  picks: CanhPhim[];
};

export class AlbumError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "AlbumError";
  }
}

function tieuDe(contextId: string, personId: string): Record<string, string> {
  return {
    "X-Actor-ID": personId,
    "X-Actor-Roles": "member",
    "X-Actor-Contexts": contextId,
    Accept: "application/json",
  };
}

/** One GET, with the refusal turned into a sentence a person can act on.
 *
 * No cache and no fallback data anywhere below. A stale album served while the
 * network is down would say the trip has nothing in it, which is a different
 * statement from "we could not ask" -- and on this screen the first reads as a
 * group that never took a photograph.
 */
async function doc<T>(
  duong: string,
  contextId: string,
  personId: string,
  fetchImpl: typeof fetch,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchImpl(`${BASE_URL}${duong}`, { headers: tieuDe(contextId, personId) });
  } catch {
    // Names the address it tried. "Không kết nối được" on its own sends
    // somebody to check their wifi when the real answer is that the phone is
    // pointed at the laptop's own localhost.
    throw new AlbumError(0, `Không gọi được ${BASE_URL}`);
  }
  if (!response.ok) {
    let code = "";
    try {
      code = ((await response.json()) as { code?: string }).code ?? "";
    } catch {
      code = "";
    }
    throw new AlbumError(response.status, loiAlbum(response.status, code));
  }
  return (await response.json()) as T;
}

/** F36. Every trip this group has, as a shelf of albums. */
export function layDanhSachAlbum(
  contextId: string,
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<DanhSachAlbum> {
  return doc<DanhSachAlbum>(
    `/contexts/${contextId}/albums`,
    contextId,
    personId,
    fetchImpl,
  );
}

/** F36. One trip, with its photographs, places and money. */
export function layAlbum(
  contextId: string,
  outingId: string,
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Album> {
  return doc<Album>(
    `/contexts/${contextId}/albums/${outingId}`,
    contextId,
    personId,
    fetchImpl,
  );
}

/** F37. The AI reel over one album.
 *
 * A 200 here does not mean a reel exists: the server answers 200 with
 * `reeled: false` and a `reason` when the model was unavailable or its picks
 * did not ground. That is deliberate on its side and must stay deliberate on
 * this one -- the screen renders the reason instead of an empty carousel.
 */
export function layThuocPhim(
  contextId: string,
  outingId: string,
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ThuocPhim> {
  return doc<ThuocPhim>(
    `/contexts/${contextId}/albums/${outingId}/reel`,
    contextId,
    personId,
    fetchImpl,
  );
}

/** Refusals in words the person reading them can act on. */
export function loiAlbum(status: number, code: string): string {
  if (code === "permission_denied" || status === 403) {
    return "Album là của riêng nhóm. Bạn cần là thành viên đang hoạt động mới xem được.";
  }
  if (status === 401) return "Chưa đăng nhập nên chưa hỏi được máy chủ.";
  if (status === 404) return "Không tìm thấy chuyến này trong nhóm.";
  // F37 charges the caller before it reaches the model, so this one is a real
  // answer rather than a server fault: the reel has a window and it is full.
  if (status === 429) return "Bạn vừa dựng thước phim liên tục. Chờ một chút rồi thử lại.";
  if (status >= 500) return "Máy chủ đang lỗi, chưa đọc được album.";
  return `Máy chủ trả lỗi ${status}.`;
}

/** Why this reel is empty, in the group's own language.
 *
 * Four reasons and four sentences, because "chưa có thước phim" for all of them
 * would hide the one difference that matters to somebody standing there: a trip
 * with no photographs is waiting on them, and a model that was unreachable is
 * waiting on us.
 */
export function lyDoPhim(reason: LyDoPhim): string {
  if (reason === "no_memories") {
    return "Chuyến này chưa có tấm ảnh nào trong nhóm, nên chưa có gì để dựng thành thước phim. Thêm ảnh vào tường kỷ niệm rồi quay lại.";
  }
  if (reason === "unavailable") {
    return "AI chưa trả lời được lúc này. Không có bản dựng sẵn nào để thay thế, nên màn này không hiện gì thay vì hiện một thước phim cũ.";
  }
  if (reason === "ungrounded") {
    return "AI có trả lời, nhưng những gì nó chọn không khớp với ảnh thật của chuyến này nên máy chủ đã bỏ. Thà không có thước phim còn hơn có một cái nói về tấm ảnh không tồn tại.";
  }
  return "";
}
