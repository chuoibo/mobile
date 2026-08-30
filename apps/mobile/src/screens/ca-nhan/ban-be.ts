/** F03/F04 over the wire: find somebody by number, ask, answer, list.
 *
 * `services/api/app/api/routes/friends.py` is written around one rule -- the
 * telephone number goes in and never comes back out -- and this file is the
 * client half of that rule. Three things it does on purpose:
 *
 * **The number travels in a POST body and nowhere else.** `timBanTheoSo` takes
 * the number as an argument and puts it in `body`. It is never interpolated
 * into a path, never appended as `?phone=`, and never logged. uvicorn writes
 * method and path into its access log; a number in a query string is a number
 * written to disk on the server, forever, by a route whose whole design is
 * about not storing it. That is the 24th shape QA measured and the only one
 * the server cannot defend against on its own, because it is the client that
 * decides the URL.
 *
 * **Nothing that comes back carries a number.** `NguoiTimDuoc` has two fields
 * because `PersonMatchResponse` has two fields. There is no telephone number
 * on the wire to render by accident -- the server never stored one -- and this
 * type is written to keep it that way if the response ever grows.
 *
 * **The refusal tables are read off the server, not invented.** Every key
 * below is a code raised in `routes/friends.py`, `api/service.py` or
 * `domain/friendship.py`; `tests/ban-be.test.mjs` parses those three files and
 * fails on a key that no longer exists. A table nobody checks is how
 * `PUBLISH_REFUSALS` shipped naming two codes the server had never sent.
 *
 * Split out of the screen so the parts worth asserting -- the shape check, the
 * sentences, the request the app builds -- can be exercised without rendering.
 */
import { BASE_URL, translated, type Attempt } from "../../api";

/** Who holds a number. An id and a name; there is no third field. */
export type NguoiTimDuoc = {
  person_id: string;
  display_name: string;
};

/** One friend edge, as whichever party is reading it sees it. */
export type LoiMoi = {
  id: string;
  requester_id: string;
  addressee_id: string;
  /** Whoever the reader is not. Resolved by the server, not by this app. */
  other_person_id: string;
  other_display_name: string;
  state: "pending" | "accepted" | "declined" | "blocked";
  created_at: string;
  decided_at: string | null;
};

export type Ban = {
  person_id: string;
  display_name: string;
  friends_since: string;
};

export type TraLoi = "accept" | "decline" | "block";

/* --------------------------------------------------- the shape of a number */

const DAU_PHAN_CACH = /[\s.\-()]/g;

/**
 * Nine digits after the trunk prefix, first of them one of 3 5 7 8 9.
 *
 * A copy of `_MOBILE` in `services/api/app/api/person_identity.py`, and a copy
 * is a liability, so it is a *checked* copy: `tests/ban-be.test.mjs` reads the
 * regex out of that Python file and fails if the two stop agreeing. Same trick
 * `tests/publish-refusals.test.mjs` uses on the publish gate codes, for the
 * same reason -- a client rule that drifts from the server rule produces a
 * refusal the person holding the phone cannot act on.
 */
const SO_DI_DONG = /^[35789]\d{8}$/;

/**
 * Does this look like a Vietnamese mobile number at all?
 *
 * Deliberately NOT an authority on validity -- the server decides that, and
 * its 422 says so in Vietnamese. This exists for one narrower job: the lookup
 * route allows thirty calls a minute per caller, and spending one of them on a
 * half-typed number means the person who then types it correctly is the one
 * who gets throttled. So the button stays inert until the field holds
 * something that could be a number.
 *
 * Accepts what `canonical_mobile` accepts: `+84`, a bare `84`, a trunk `0`, or
 * none of the three, with spaces, dots, dashes and brackets anywhere.
 */
export function soCoTheGoi(raw: string): boolean {
  const packed = raw.replace(DAU_PHAN_CACH, "");
  if (packed === "") return false;
  const rest = packed.startsWith("+84")
    ? packed.slice(3)
    : packed.startsWith("84")
      ? packed.slice(2)
      : packed.startsWith("0")
        ? packed.slice(1)
        : packed;
  return SO_DI_DONG.test(rest);
}

/* ------------------------------------------------------ what refusals mean */

/**
 * Refusals of `POST /friends/lookup`.
 *
 * The server's own sentences are already Vietnamese and already correct; these
 * replace the two where the app can say more about what to do next, and leave
 * the rest alone. Not one of them interpolates anything: the input to this
 * route is a telephone number, and a refusal that echoed its input is how a
 * refusal becomes a disclosure. The same reasoning is written out at length in
 * the route's own module docstring.
 */
export const LOI_TIM: Record<string, string> = {
  person_not_found:
    "Chưa có ai dùng số này trong Rủ Đi. Kiểm tra lại số, hoặc rủ họ tải app rồi tìm lại sau.",
  phone_not_mobile:
    "Số này chưa đúng dạng số di động Việt Nam. Nhập 10 số bắt đầu bằng 0, hoặc dạng +84.",
  // 429. The wording matters more than most: throttled and broken look
  // identical from the outside, and somebody who reads a bare refusal here
  // concludes the app is broken and stops. It says the wait, and says the app
  // is fine.
  rate_limited:
    "Bạn vừa tìm hơi nhiều lần nên máy chủ tạm nghỉ một chút. Thử lại sau một phút. App không hỏng, chỉ đang chờ.",
  // 503. Configured wrongly, not broken, and above all not the fault of the
  // number that was typed -- so the sentence says so before somebody spends
  // ten minutes retyping their friend's number.
  identity_key_missing:
    "Máy chủ chưa bật được phần tìm bạn. Đây là lỗi cấu hình phía máy chủ chứ không phải do số bạn nhập. Báo nhóm kỹ thuật giúp mình.",
  permission_denied: "Tài khoản đang dùng chưa được phép tìm bạn bằng số điện thoại.",
};

/**
 * Refusals of `POST /friends/requests`.
 *
 * `request_not_open` is the interesting one, and the sentence is short on
 * purpose. The server answers with that one code for three different
 * situations -- already friends, a request already pending, and blocked -- and
 * it does that deliberately: `service.py` gives the race arm the same status
 * and the same code as the read arm so that "a blocked person cannot tell a
 * block from a duplicate by timing". Writing "hai bạn đã là bạn rồi, hoặc lời
 * mời trước còn đang chờ" here would undo that on the client, because it names
 * two of the three states and so tells whoever is blocked that they are not.
 *
 * So the sentence says what is true of all three -- it did not go -- and sends
 * the reader to the two lists further down the screen, which are their own and
 * which they are entitled to read.
 */
export const LOI_GUI: Record<string, string> = {
  person_not_found:
    "Người này không còn trong Rủ Đi nữa. Tìm lại bằng số điện thoại một lần nữa.",
  request_not_open:
    "Lời mời này chưa gửi được. Kéo xuống xem \"Lời mời đã gửi\" và \"Bạn bè\" bên dưới để biết hai bạn đang ở đâu.",
  self_edge: "Đây là số của chính bạn. Không tự kết bạn với mình được.",
  permission_denied: "Tài khoản đang dùng chưa được phép gửi lời mời kết bạn.",
};

/** Refusals of `POST /friends/requests/{id}/respond`. */
export const LOI_TRA_LOI: Record<string, string> = {
  friend_request_not_found:
    "Lời mời này không còn nữa. Có thể bạn đã trả lời rồi ở lần mở trước. Tải lại danh sách để xem trạng thái mới nhất.",
  // 403. The server sends its domain code as the detail here rather than a
  // sentence (`only_addressee_may_answer`), so without this line a machine
  // string would reach the screen.
  permission_denied: "Chỉ người được mời mới trả lời được lời mời này.",
  not_pending:
    "Lời mời này đã được trả lời rồi. Tải lại danh sách để xem trạng thái mới nhất.",
  already_blocked: "Lời mời này đã bị chặn từ trước.",
  not_a_party: "Lời mời này không phải của bạn.",
};

/** Refusals of the two read routes. Both are self-only at the server. */
export const LOI_DOC: Record<string, string> = {
  permission_denied: "Chỉ chính chủ mới xem được danh sách bạn bè của mình.",
};

/* ------------------------------------------------------------- the calls */

/**
 * Who holds this number.
 *
 * POST, with the number in the body. Read the top of this file before changing
 * the method or the path: `GET /friends/lookup?phone=...` would put a real
 * telephone number into the server's access log on every search, and no amount
 * of care further down would take it back out.
 */
export async function timBanTheoSo(
  soDienThoai: string,
  actorId: string,
): Promise<NguoiTimDuoc> {
  return translated<NguoiTimDuoc>(LOI_TIM, "/friends/lookup", {
    method: "POST",
    body: { phone: soDienThoai },
    actorId,
  });
}

/**
 * Ask somebody to be friends.
 *
 * 201 means asked. It does not mean friends, and the screen that calls this
 * has to say so -- see `KetBan.tsx`, where the returned `state` is rendered as
 * a wait rather than as a result.
 */
export async function guiLoiMoi(
  addresseeId: string,
  actorId: string,
  attempt: Attempt,
): Promise<LoiMoi> {
  return translated<LoiMoi>(LOI_GUI, "/friends/requests", {
    method: "POST",
    body: { addressee_id: addresseeId },
    actorId,
    attempt,
  });
}

/** Answer one. Only the person it was addressed to may accept or decline. */
export async function traLoiLoiMoi(
  requestId: string,
  quyetDinh: TraLoi,
  actorId: string,
  attempt: Attempt,
): Promise<LoiMoi> {
  return translated<LoiMoi>(
    LOI_TRA_LOI,
    `/friends/requests/${requestId}/respond`,
    { method: "POST", body: { decision: quyetDinh }, actorId, attempt },
  );
}

/**
 * Pending requests in one direction.
 *
 * The server reads anything other than the literal `outgoing` as `incoming`,
 * so an unknown value narrows the result rather than widening it. This sends
 * one of the two words and nothing else.
 */
export async function docLoiMoi(
  personId: string,
  actorId: string,
  huong: "incoming" | "outgoing",
): Promise<LoiMoi[]> {
  const wire = await translated<{ requests: LoiMoi[] }>(
    LOI_DOC,
    `/people/${personId}/friend-requests?direction=${huong}`,
    { method: "GET", actorId },
  );
  return wire.requests;
}

/** This person's friends. Self-only, enforced at the server. */
export async function docDanhSachBan(
  personId: string,
  actorId: string,
): Promise<Ban[]> {
  const wire = await translated<{ friends: Ban[] }>(
    LOI_DOC,
    `/people/${personId}/friends`,
    { method: "GET", actorId },
  );
  return wire.friends;
}

/* -------------------------------------------------------------- for the eye */

/** The monogram an avatar frame falls back to. No photos of real people. */
export function chuDau(ten: string): string {
  const word = ten.trim().split(/\s+/).pop() ?? "";
  return word === "" ? "?" : word.slice(0, 1).toUpperCase();
}

/** The address this screen talks to, printed on every dead end. */
export const DIA_CHI_API = BASE_URL;
