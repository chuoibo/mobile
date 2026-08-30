/** F46. Two requests: the group was here, and who else has been.
 *
 * Kept out of the screen for the usual reason -- the wire shape and the
 * refusal wording are the parts that can be wrong, and neither needs a phone
 * to check. `tests/check-in.test.mjs` reads them.
 *
 * ## What the request does NOT carry
 *
 * A latitude. A longitude. A GPS reading of any kind.
 *
 * The body is `{place_id}` and the server looks the rest up in its own
 * catalogue. That is a deliberate refusal of the easier design: if this file
 * could send coordinates, it could write "the group was at 0,0" -- or at
 * somebody's home address -- into a group's permanent history, and no later
 * reader would have anything to check it against. Automatic place detection
 * from the phone's GPS is **F47** and is not built; a body with coordinates in
 * it would make this route look like it had been.
 *
 * ## What comes back is private
 *
 * A check-in list is where a group of people physically were and when. It
 * leaves the server only through `GET /contexts/{id}/memories`, which is gated
 * on membership, and it does not get logged here. `console.log` of a response
 * in this file would put a group's movements in a browser console during a
 * demo.
 */
import { ApiError, type Attempt, translatedAsActor } from "../../api";

/** One row of the group's wall. `kind` says which shape the row is in; the
 *  two sets of fields are mutually exclusive and the database enforces it. */
export type KyNiem = {
  id: string;
  context_id: string;
  author_id: string;
  kind: "photo" | "checkin";
  image_url: string | null;
  caption: string | null;
  place_id: string | null;
  place_name: string | null;
  lat: number | null;
  lng: number | null;
  created_at: string;
  cursor: string;
};

const CHECK_IN_REFUSALS: Record<string, string> = {
  place_not_found:
    "Máy chủ không có chỗ này trong danh mục, nên chưa check-in được. Mở lại màn Khám phá để lấy danh sách mới.",
  permission_denied:
    "Chỉ thành viên của nhóm mới check-in được. Nhận lời mời vào nhóm trước đã.",
  context_not_found: "Nhóm này không còn nữa.",
};

/**
 * Check in, as a member of this group.
 *
 * Sends an idempotency key like every other write in this app: a check-in
 * pressed twice on a flaky connection should be one mark on the timeline, not
 * two identical ones a minute apart that make a group look like it left and
 * came back.
 */
export async function checkIn(
  contextId: string,
  placeId: string,
  actorId: string,
  attempt: Attempt,
  caption?: string | null,
): Promise<KyNiem> {
  return translatedAsActor<KyNiem>(
    CHECK_IN_REFUSALS,
    `/contexts/${contextId}/checkins`,
    {
      method: "POST",
      body: caption ? { place_id: placeId, caption } : { place_id: placeId },
      actorId,
      attempt,
      contexts: contextId,
    },
  );
}

const DOC_REFUSALS: Record<string, string> = {
  permission_denied:
    "Chỉ thành viên của nhóm mới xem được check-in của nhóm.",
  context_not_found: "Nhóm này không còn nữa.",
};

/**
 * The group's check-ins at one place, newest first.
 *
 * A GET, so no idempotency key -- the header only protects writes.
 *
 * `place_id` narrows *inside* a group; it never stands in for the group. The
 * context is in the path and the server checks membership before it reads a
 * row, so this cannot be pointed at somebody else's history by changing a
 * query parameter.
 */
export async function checkInTaiDay(
  contextId: string,
  placeId: string,
  actorId: string,
): Promise<KyNiem[]> {
  const wire = await translatedAsActor<{ memories: KyNiem[] }>(
    DOC_REFUSALS,
    `/contexts/${contextId}/memories?kind=checkin&place_id=${encodeURIComponent(placeId)}&limit=20`,
    { method: "GET", actorId, contexts: contextId },
  );
  return wire.memories;
}

/** What went wrong, in a sentence that is safe to put on a screen.
 *
 * Only `ApiError` text is known to be safe. Any other throw could carry a URL
 * with a context id in it, or a fetch failure naming an internal host, and
 * this screen's errors are read by whoever is standing at the restaurant. */
export function loiCheckIn(loi: unknown): string {
  return loi instanceof ApiError
    ? loi.message
    : "Chưa check-in được. Thử lại sau một chút.";
}

/** "19:30 · 29/8" -- short enough for a list row.
 *
 * Formatted from the server's timestamp in the device's own zone, which is
 * what somebody reading "we were here at" expects. Deliberately not a relative
 * string ("2 giờ trước"): a relative time computed at render is wrong the
 * moment the screen sits open, and a check-in is a fact about a clock. */
export function gioNgan(iso: string): string {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return "";
  const hai = (n: number) => String(n).padStart(2, "0");
  return `${hai(t.getHours())}:${hai(t.getMinutes())} · ${t.getDate()}/${t.getMonth() + 1}`;
}
