/**
 * How a person gets a session, and why they cannot yet.
 *
 * ## Status: the route does not exist
 *
 * ADR-0014 is 🟡 ĐỀ XUẤT. It says, in its own words: *«Không viết bảng session,
 * không đổi `get_actor`, không gắn OAuth trước khi ADR này đóng băng.»* The
 * server half is Codex's lane and the Lead's gate.
 *
 * `scripts/check_api_contract.py` refuses to merge a client that calls a path
 * the server does not declare, and that refusal is correct -- it is the reason
 * `docs/architecture/01` section 7 says server merges before client merges. So
 * this file contains **no path literal**. `doiLoiMoiLayPhien` is the shape of
 * the call, and it throws.
 *
 * ## Why a throwing function rather than a TODO comment
 *
 * A comment saying "chưa làm" is not checkable, and a function that silently
 * returns null reads, at every call site, exactly like a function that worked
 * and found nothing. `tests/rudi-phien.test.mjs` asserts the throw, so "not
 * built yet" is a fact with a gate on it. When the route lands, the test that
 * pins the throw goes red, and that is the intended way to notice.
 *
 * ## What the server must provide (ADR-0014 sections 3, 4, 5)
 *
 * - Bootstrap takes the raw secret of a NAMED invite (`source ∈ {group, friend}`,
 *   `invited_person_id IS NOT NULL`). A `source=link` invite must NOT mint a
 *   session; it goes through the existing `POST /outing-invites/{token}/accept`
 *   and is capped at `INVITED`.
 * - The session binds to `invited_person_id`. The caller does not name a person,
 *   and no `person_id` field on the body may be read.
 * - Only the SHA-256 digest is persisted, never the raw token.
 * - Losing a session (reinstall, new phone) rotates the secret on the existing
 *   invite row. The partial unique index on (outing_id, invited_person_id)
 *   makes a second named row a 409, so re-invite is not the re-login path.
 */

/** Thrown by every function here until Codex ships the route. */
export class ChuaCoRouteError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChuaCoRouteError";
  }
}

export type PhienMoi = {
  /** Raw bearer. Belongs in SecureStore and nowhere else. */
  token: string;
  /** Who the server says this session is. The client does not get to claim it. */
  personId: string;
  /** ISO 8601. The client does not extend it. */
  hetHan: string;
};

/**
 * Exchange a named invite's raw secret for a session.
 *
 * The argument is the secret handed over out of band, once. It is deliberately
 * NOT the invite id: `invite_id` already travels in
 * `OutingInviteAcceptResponse`, which makes it public data, and ADR-0014
 * section 3 names using it as a secret as a thing not to do.
 */
export async function doiLoiMoiLayPhien(_biMatLoiMoi: string): Promise<PhienMoi> {
  throw new ChuaCoRouteError(
    "Chưa có route cấp phiên. ADR-0014 mục 3 đang ở trạng thái ĐỀ XUẤT, và " +
      "máy chủ phải vào main trước client (docs/architecture/01 mục 7). " +
      "Bản trải nghiệm không cần phiên; đây là đường đăng nhập thật.",
  );
}

/**
 * End a session server-side.
 *
 * Separate from clearing the token on the device: a token deleted only here is
 * a token the server would still honour if it ever left the phone.
 */
export async function traLaiPhien(_token: string): Promise<void> {
  throw new ChuaCoRouteError(
    "Chưa có route thu hồi phiên. Xoá token trên máy là việc client làm được; " +
      "giết nó ở máy chủ thì chưa.",
  );
}
