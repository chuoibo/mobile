/** The five requests the entry door makes, and what their refusals mean.
 *
 * Groups and memberships are a different corner of the API from the expense
 * path `api.ts` grew around, so they live here rather than swelling that file.
 * What is *not* duplicated is the plumbing: `translated` and the idempotency
 * key come from `api.ts`, because a second `fetch` wrapper would be a second
 * status-to-sentence table, and the one that already exists was tuned against
 * a real server.
 *
 * Naming a person is not here at all -- `registerPerson` in `api.ts` already
 * does it and is already pinned by tests. F01 and F03 call that one. Two
 * functions writing `PUT /people/{id}` would be two places to get the retry
 * key wrong, and the expense flow would keep the good one.
 */
import { type Attempt, translated } from "../../api";
import { chuanHoaSo } from "./danh-tinh";

export type ThanhVien = {
  id: string;
  context_id: string;
  person_id: string;
  state: "invited" | "active" | "left";
  role: "member" | "admin";
  invited_by_id: string | null;
  joined_at: string | null;
  left_at: string | null;
  created_at: string;
};

export type Nhom = {
  id: string;
  display_name: string;
  created_by_id: string;
  created_at: string;
};

/**
 * The group admin claim.
 *
 * `invite_context_member` in `app/domain/permissions.py` asks for
 * `group_admin`, and the default header in `api.ts` carries
 * `member,advancer,recipient,batch_owner` -- none of which is it. Without this
 * the invite is a 403 and the screen tells somebody to go and ask for a
 * permission that no screen can grant.
 *
 * Sent only on the calls that need it. The header is asserted by the client
 * because there is no gateway to overwrite it, so this grants nothing that
 * `curl` could not already assert; keeping it off the other calls is about
 * recording which screen depends on which claim, so that when real sessions
 * arrive the list of things to reproduce is written down rather than inferred.
 */
const QUYEN_ADMIN = "group_admin,member,advancer,recipient,batch_owner";

const DANH_TINH_REFUSALS: Record<string, string> = {
  identity_key_missing:
    "Máy chủ chưa cấu hình khoá danh tính nên chưa đăng nhập được. Báo người dựng máy chủ đặt MOBILE_PERSON_ID_KEY.",
  rate_limited:
    "Thử lại sau một phút. Máy chủ đang giới hạn số lần tra danh tính.",
  phone_not_mobile: "Chưa đúng dạng số di động Việt Nam.",
  phone_required: "Chưa gửi được số. Nhập lại rồi thử lần nữa.",
};

/**
 * The person id for a telephone number (F01, and bug-140342).
 *
 * The derivation used to be arithmetic in `danh-tinh.ts` and is now a request,
 * for one reason: it had to become keyed, and there is nowhere on this device
 * to keep a key. `person_identity.py` carries the measurement -- an id was
 * reversible back into its number at 257,316 candidates per second.
 *
 * So the digits now leave the device, which is a real cost and is why the
 * screen's own copy had to change with this call rather than after it. They go
 * in a POST body and not in a path, so uvicorn's access log does not see them,
 * and the server stores nothing.
 *
 * No idempotency key. The call writes nothing -- it is a pure function of the
 * number and the server's key -- so keying it would put a read into the
 * server's attempt store to protect a retry that was already safe.
 *
 * No actor header either, and that one is not an oversight: somebody signing
 * in does not have an id yet, which is the thing being asked for.
 *
 * Normalises before sending rather than shipping whatever is in the field. The
 * server normalises too and would reach the same answer, but sending the
 * canonical form means a stray space never travels, and it keeps the two
 * copies of the rule honest -- if they ever disagree, they disagree here at
 * one call site instead of silently across every sign-in.
 */
export async function layIdTuSo(raw: string): Promise<string> {
  const so = chuanHoaSo(raw);
  if (so === null) {
    // The number itself is not in this message on purpose: a thrown message
    // ends up in a console or in a bug report.
    throw new Error("Số điện thoại không hợp lệ, không thể tạo danh tính.");
  }
  const wire = await translated<{ person_id: string }>(
    DANH_TINH_REFUSALS,
    "/identity/person-id",
    { method: "POST", body: { phone: so } },
  );
  return wire.person_id;
}

const TAO_NHOM_REFUSALS: Record<string, string> = {
  person_not_registered:
    "Chưa có tên cho tài khoản này nên chưa mở được nhóm. Quay lại màn đăng ký và nhập tên hiển thị.",
  permission_denied: "Tài khoản này chưa được phép mở nhóm mới.",
};

/**
 * Open a group. The creator comes out of it as an active admin.
 *
 * That bootstrap is the server's, not this app's: `create_context` in
 * `service.py` adds the creator and accepts the membership inside the same
 * transaction, so there is no window where a group exists with nobody able to
 * administer it. Worth knowing here because it is why the screen does not
 * follow this with an invite-yourself call -- doing so would earn a 409 on the
 * partial unique index and look like a bug in the group that was just made.
 */
export async function taoNhom(
  tenNhom: string,
  actorId: string,
  attempt: Attempt,
): Promise<Nhom> {
  return translated<Nhom>(TAO_NHOM_REFUSALS, "/contexts", {
    method: "POST",
    body: { display_name: tenNhom },
    actorId,
    attempt,
  });
}

const MOI_REFUSALS: Record<string, string> = {
  person_not_registered:
    "Người này chưa có tên trên máy chủ, nên chưa mời được. Thêm lại bạn đó bằng ô phía trên.",
  membership_conflict: "Người này đã ở trong nhóm hoặc đã được mời rồi.",
  duplicate_membership: "Người này đã ở trong nhóm hoặc đã được mời rồi.",
  permission_denied:
    "Chỉ người tạo nhóm mới mời được thành viên. Nhờ người đó mời giúp.",
};

/**
 * Invite somebody who already has a name on the server.
 *
 * The server checks `_require_registered_person(person_id)` before it writes,
 * so the order the screen does this in is not cosmetic: a friend is named with
 * `registerPerson` first, and only then invited. Inviting first earns a
 * refusal that reads as if the friend were the problem.
 */
export async function moiVaoNhom(
  contextId: string,
  personId: string,
  actorId: string,
  attempt: Attempt,
): Promise<ThanhVien> {
  return translated<ThanhVien>(MOI_REFUSALS, `/contexts/${contextId}/members`, {
    method: "POST",
    body: { person_id: personId },
    actorId,
    attempt,
    roles: QUYEN_ADMIN,
    contexts: contextId,
  });
}

const NHAN_REFUSALS: Record<string, string> = {
  membership_not_found: "Lời mời này không còn nữa. Nhờ nhóm mời lại.",
  permission_denied:
    "Lời mời này gửi cho người khác, nên tài khoản đang dùng không nhận thay được.",
};

/**
 * Accept an invitation, as the person it was sent to.
 *
 * `accept_context_membership` requires `is_invitee`, compared against
 * `X-Actor-ID`. So `actorId` here must be the invited person and not whoever
 * is looking at the screen -- which is why the button that calls this is only
 * enabled for the signed-in person's own invitation, rather than sitting on
 * every pending row and quietly asserting somebody else's identity to make
 * itself work.
 */
export async function nhanLoiMoi(
  membershipId: string,
  actorId: string,
  attempt: Attempt,
): Promise<ThanhVien> {
  return translated<ThanhVien>(
    NHAN_REFUSALS,
    `/memberships/${membershipId}/accept`,
    { method: "POST", actorId, attempt },
  );
}

const DANH_SACH_REFUSALS: Record<string, string> = {
  permission_denied:
    "Chỉ thành viên của nhóm mới xem được danh sách này. Nếu bạn vừa được mời, hãy nhận lời mời trước.",
  context_not_found: "Nhóm này không còn nữa.",
};

/**
 * Who is in the group, invited and active alike.
 *
 * A GET, so no idempotency key: the header only protects writes, and sending
 * one here would key a read into the server's attempt store for nothing.
 */
export async function danhSachThanhVien(
  contextId: string,
  actorId: string,
): Promise<ThanhVien[]> {
  const wire = await translated<{ context_id: string; members: ThanhVien[] }>(
    DANH_SACH_REFUSALS,
    `/contexts/${contextId}/members`,
    { method: "GET", actorId, contexts: contextId },
  );
  return wire.members;
}
