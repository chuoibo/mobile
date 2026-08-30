/** Group administration and outing invites: the five routes, and the rules
 *  a screen needs before it may offer a button.
 *
 * Split from the screen on purpose. Everything here runs under bare node, so
 * the parts that decide *whether a control may exist* -- who may change a
 * role, whose "leave" button this is -- are testable without rendering, and
 * the screen is left with layout.
 *
 * ## What the server actually allows, measured from its own tables
 *
 * `app/domain/permissions.py` is the source, not this comment, but three of
 * its entries shape every control on the screen and are worth stating where
 * the caller can see them:
 *
 *   - `set_member_role` asks for the `group_admin` ROLE **and** the predicate
 *     `is_group_admin`, and the service computes that predicate from
 *     `repository.membership_role(context_id, actor.id) == "admin"` -- the
 *     database row, not the header. So asserting `group_admin` in
 *     `X-Actor-Roles` is necessary and never sufficient: a plain member who
 *     sends the header still gets 403. The screen therefore reads its own
 *     membership row first and hides the control when that row says `member`.
 *   - `leave_context` requires `is_self`. `DELETE /contexts/{id}/members/{pid}`
 *     is **leaving**, not removing somebody else -- there is no route in this
 *     API that kicks another person out, and a "Xoá thành viên" button would
 *     be a 403 wearing a label that blames the network.
 *   - `invite_to_outing` and `revoke_outing_invite` only ask for ACTIVE
 *     membership of the outing's group, so any member may do both.
 *
 * ## The invite list is not readable
 *
 * There is no `GET /outings/{id}/invites`. The server mints an invite and
 * answers with it once; nothing can ask for the list again. So a screen can
 * only show the invites it created in this session, and it has to say so --
 * an empty list here means "none created since this screen opened", never
 * "this outing has no invites".
 */
import { type Attempt, translated } from "../../api";
import type { ThanhVien } from "../vao-cua/cong-api";

export type VaiTro = "member" | "admin";

/** One group, as `GET /contexts/{id}` answers it. */
export type NhomChiTiet = {
  id: string;
  display_name: string;
  created_by_id: string;
  created_at: string;
};

/** One membership row.
 *
 *  Re-exported from `vao-cua/cong-api` rather than declared again: the roster
 *  read this screen needs is `GET /contexts/{id}/members`, which that file
 *  already calls, and a second wire type for one route is a second place to
 *  get the state union wrong. */
export type ThanhVienChiTiet = ThanhVien;

/** One outing invite, as the two invite routes answer.
 *
 *  `invite_token` and `invite_path` arrive only on creation and only for a
 *  `link` invite -- the revoke reply carries neither, because handing the
 *  token back at the moment it stops working would be an invitation to paste
 *  it somewhere. Optional here for that reason, not for tolerance. */
export type LoiMoiBuoiDi = {
  id: string;
  outing_id: string;
  source: "group" | "friend" | "link";
  invited_person_id: string | null;
  invited_by_id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  invite_token: string | null;
  invite_path: string | null;
};

/**
 * The group-admin claim.
 *
 * Copied in spirit from `vao-cua/cong-api.ts`, which needs it for
 * `invite_context_member`. Sent only on the one call that asks for it. It
 * grants nothing `curl` could not assert -- there is no gateway to overwrite
 * these headers yet -- so its value is that the list of claims to reproduce
 * when real sessions arrive is written down rather than inferred.
 */
const QUYEN_ADMIN = "group_admin,member,advancer,recipient,batch_owner";

const NHOM_REFUSALS: Record<string, string> = {
  permission_denied:
    "Chỉ thành viên của nhóm mới xem được nhóm này. Nếu bạn vừa được mời, hãy nhận lời mời trước.",
  context_not_found: "Nhóm này không còn nữa.",
};

/**
 * Trade a group id for the group's name.
 *
 * The order of the server's two checks is a security property, not a detail:
 * membership is decided before the row is read, so an id that travels in a
 * share link cannot be used to enumerate which groups exist. Both the unknown
 * id and the group you are not in answer 403, and the copy above says the same
 * thing for both because the server deliberately does not distinguish them.
 */
export async function docNhom(contextId: string, actorId: string): Promise<NhomChiTiet> {
  return translated<NhomChiTiet>(NHOM_REFUSALS, `/contexts/${contextId}`, {
    method: "GET",
    actorId,
    contexts: contextId,
  });
}

const VAI_TRO_REFUSALS: Record<string, string> = {
  permission_denied:
    "Chỉ quản trị viên của chính nhóm này mới đổi được vai trò. Nhờ người mở nhóm làm giúp.",
  membership_not_found:
    "Người này không còn là thành viên đang hoạt động của nhóm, nên chưa đổi được vai trò.",
};

/**
 * Promote or demote one member.
 *
 * No identity field in the body: who is acting is `X-Actor-ID`, and who is
 * being changed is in the path. The body carries the role and nothing else,
 * which is the whole contract `MemberRoleRequest` declares.
 */
export async function datVaiTro(
  contextId: string,
  personId: string,
  role: VaiTro,
  actorId: string,
  attempt: Attempt,
): Promise<ThanhVienChiTiet> {
  return translated<ThanhVienChiTiet>(
    VAI_TRO_REFUSALS,
    `/contexts/${contextId}/members/${personId}/role`,
    {
      method: "PUT",
      body: { role },
      actorId,
      attempt,
      roles: QUYEN_ADMIN,
      contexts: contextId,
    },
  );
}

const ROI_NHOM_REFUSALS: Record<string, string> = {
  permission_denied:
    "Chỉ chính bạn mới rời nhóm thay bạn được. Máy chủ không có đường để một người xoá người khác khỏi nhóm.",
  membership_not_found: "Bạn không còn là thành viên đang hoạt động của nhóm này.",
};

/**
 * Leave the group, as yourself.
 *
 * `personId` is a parameter rather than being taken from `actorId` so the call
 * reads the same shape as the route it sends, but the server compares the two
 * (`is_self`) and refuses when they differ. The screen must therefore only
 * offer this on the signed-in person's own row -- see `coTheRoiNhom`.
 *
 * Answers 204 with no body, which `call` returns as `undefined`.
 */
export async function roiNhom(
  contextId: string,
  personId: string,
  actorId: string,
  attempt: Attempt,
): Promise<void> {
  await translated<void>(
    ROI_NHOM_REFUSALS,
    `/contexts/${contextId}/members/${personId}`,
    { method: "DELETE", actorId, attempt, contexts: contextId },
  );
}

const LOI_MOI_REFUSALS: Record<string, string> = {
  outing_not_found: "Chuyến này không còn nữa. Đọc lại danh sách chuyến rồi thử lại.",
  person_not_registered:
    "Người này chưa có tên trên máy chủ, nên chưa mời được. Thêm họ vào nhóm trước.",
  participant_not_in_context:
    "Người này không ở trong nhóm, nên chưa mời kiểu “thành viên nhóm” được.",
  invite_already_exists: "Người này đã được mời vào chuyến rồi.",
  permission_denied: "Chỉ thành viên của nhóm mới mời người vào chuyến được.",
};

/** What `POST /outings/{id}/invites` accepts. Two shapes, and the server's
 *  own validator refuses a mismatch: a `link` invite must not name a person,
 *  a `group` or `friend` invite must. Modelled as a union so the screen cannot
 *  build the refused shape by accident. */
export type ThanLoiMoi =
  | { source: "link" }
  | { source: "group" | "friend"; person_id: string };

export async function taoLoiMoiBuoiDi(
  outingId: string,
  than: ThanLoiMoi,
  actorId: string,
  attempt: Attempt,
  contextId: string,
): Promise<LoiMoiBuoiDi> {
  return translated<LoiMoiBuoiDi>(LOI_MOI_REFUSALS, `/outings/${outingId}/invites`, {
    method: "POST",
    body: than,
    actorId,
    attempt,
    contexts: contextId,
  });
}

const THU_HOI_REFUSALS: Record<string, string> = {
  invite_not_found: "Lời mời này không còn nữa.",
  invite_already_accepted:
    "Lời mời này đã có người dùng rồi, nên không thu hồi được nữa. Người đó đã ở trong chuyến.",
  permission_denied: "Chỉ thành viên của nhóm mới thu hồi được lời mời.",
};

/**
 * Pull an invite back.
 *
 * A POST rather than a DELETE because the row survives: revoking records
 * `revoked_at` on it. The reply carries no token -- see `LoiMoiBuoiDi`.
 */
export async function thuHoiLoiMoi(
  outingId: string,
  inviteId: string,
  actorId: string,
  attempt: Attempt,
  contextId: string,
): Promise<LoiMoiBuoiDi> {
  return translated<LoiMoiBuoiDi>(
    THU_HOI_REFUSALS,
    `/outings/${outingId}/invites/${inviteId}/revoke`,
    { method: "POST", actorId, attempt, contexts: contextId },
  );
}

/* ------------------------------------------------------- rules, no fetch */

/** This person's own membership row, or null if the roster does not hold one.
 *
 *  Null is a real answer and not an error: `GET /contexts/{id}/members` can
 *  succeed for somebody reading a group they were invited to but whose row is
 *  not ACTIVE, and a screen that assumed a row exists would render an admin
 *  control for a person the server will refuse. */
export function hangCuaToi(
  ds: readonly ThanhVienChiTiet[],
  personId: string | null,
): ThanhVienChiTiet | null {
  if (!personId) return null;
  return ds.find((t) => t.person_id === personId) ?? null;
}

/** Am I an admin of THIS group?
 *
 *  Read from the roster row, never from the header the app itself writes.
 *  That is the same question `set_member_role` asks the database, so a control
 *  gated on this matches what the server will do rather than what the client
 *  claims about itself. `invited` is not enough: the service's own predicate
 *  is satisfied only by an ACTIVE row. */
export function laQuanTri(
  ds: readonly ThanhVienChiTiet[],
  personId: string | null,
): boolean {
  const toi = hangCuaToi(ds, personId);
  return toi !== null && toi.state === "active" && toi.role === "admin";
}

/** May the role control be offered for this row?
 *
 *  Three conditions, and the last one is the one worth having in code rather
 *  than in a reviewer's head: the server's `set_membership_role` only touches
 *  an ACTIVE membership, so offering the button on an `invited` row would earn
 *  a 404 whose wording is about a membership rather than about the button. */
export function coTheDoiVaiTro(
  ds: readonly ThanhVienChiTiet[],
  toiId: string | null,
  hang: ThanhVienChiTiet,
): boolean {
  if (!laQuanTri(ds, toiId)) return false;
  if (hang.state !== "active") return false;
  // A group with no admin is a group nobody can ever administer again:
  // `set_member_role` requires `is_group_admin`, computed from an ACTIVE admin
  // membership row, so there is no route back once the last one is demoted.
  // Measured on a live server, not reasoned about -- a walk of this screen
  // demoted two admins in a row and left a real group in exactly that state,
  // with `PUT .../role` answering 403 to every member including the one who
  // created it. The server does not refuse this, so the screen does.
  if (hang.role === "admin" && soQuanTri(ds) <= 1) return false;
  return true;
}

/** How many ACTIVE admins this group has. */
export function soQuanTri(ds: readonly ThanhVienChiTiet[]): number {
  return ds.filter((t) => t.state === "active" && t.role === "admin").length;
}

/** Why the role control is missing from the last admin's row, in words.
 *
 *  Returned rather than rendered, so the screen prints one sentence in one
 *  place and the rule stays testable without a browser. Null when there is
 *  nothing to explain. */
export function loiNhacQuanTriCuoi(
  ds: readonly ThanhVienChiTiet[],
  toiId: string | null,
): string | null {
  if (!laQuanTri(ds, toiId)) return null;
  if (soQuanTri(ds) > 1) return null;
  return (
    "Nhóm chỉ còn một quản trị, nên app không cho bỏ quyền của người đó. " +
    // Hyphen, never an em-dash: `tests/dau-gach-dai.test.mjs` gates the source
    // against one reaching a person's screen, and this string is user-facing.
    "Máy chủ không có đường phong quản trị mới khi nhóm không còn quản trị nào. " +
    "Đặt thêm một người làm quản trị trước, rồi mới bỏ quyền."
  );
}

/** May "Rời nhóm" be offered on this row?
 *
 *  Only on your own ACTIVE row. The server compares `actor.id` with the
 *  `person_id` in the path (`is_self`), so any other row would be the app
 *  asserting somebody else's identity -- the one thing header auth makes easy
 *  and the reason nothing here may be built on it. */
export function coTheRoiNhom(toiId: string | null, hang: ThanhVienChiTiet): boolean {
  if (!toiId) return false;
  return hang.person_id === toiId && hang.state === "active";
}

/** The role this row would be set to if the button were pressed. */
export function vaiTroDoiThanh(hang: ThanhVienChiTiet): VaiTro {
  return hang.role === "admin" ? "member" : "admin";
}

/** "Đặt làm quản trị" / "Bỏ quyền quản trị", matching `vaiTroDoiThanh`. */
export function nhanNutVaiTro(hang: ThanhVienChiTiet): string {
  return hang.role === "admin" ? "Bỏ quyền quản trị" : "Đặt làm quản trị";
}

/** What to call this person, without ever printing a raw id.
 *
 *  A UUID is not a name. Where the server sent one and it is blank, this says
 *  so in words -- the same rule `Nhom.tsx` follows, for the same reason. */
export function tenThanhVien(hang: ThanhVienChiTiet): string {
  const ten = hang.display_name?.trim();
  return ten && ten.length > 0 ? ten : "Thành viên chưa rõ tên";
}

/** "Đang trong nhóm · quản trị" -- state and role in one line.
 *
 *  The `left` branch is written and, measured against a live server, never
 *  reached: `GET /contexts/{id}/members` drops a membership once it is left,
 *  so the row disappears rather than arriving with `state: "left"`. Kept
 *  because `left` is in the wire union the server declares, and a `switch`
 *  over a union that quietly omits one arm is how the day it starts arriving
 *  becomes a blank line on a roster. */
export function moTaHang(hang: ThanhVienChiTiet): string {
  const trangThai =
    hang.state === "active"
      ? "Đang trong nhóm"
      : hang.state === "invited"
        ? "Đã mời, chờ nhận lời"
        : "Đã rời nhóm";
  return `${trangThai} · ${hang.role === "admin" ? "quản trị" : "thành viên"}`;
}

/** Where a link invite points, as something a person can copy.
 *
 *  The server sends `invite_path` (`/outing-invites/<token>`); this app opens
 *  such a link at `#moi=<token>`, which is what `lien-ket.ts` parses. Built
 *  from `invite_token` rather than by slicing the path, because a path shape
 *  is the server's to change and a token is the value both sides agreed on.
 *  Null for an invite that carries no token -- every `group` invite, and every
 *  revoke reply. */
export function duongDanMoi(moi: LoiMoiBuoiDi, goc: string): string | null {
  if (!moi.invite_token) return null;
  return `${goc.replace(/\/$/, "")}/#moi=${moi.invite_token}`;
}

/** Live, revoked, or expired -- in the words the card prints.
 *
 *  `bayGio` is a parameter rather than `Date.now()` so this is testable and so
 *  a screen that renders twice in one second cannot disagree with itself. */
export function trangThaiLoiMoi(moi: LoiMoiBuoiDi, bayGio: number): string {
  if (moi.revoked_at) return "Đã thu hồi";
  const het = Date.parse(moi.expires_at);
  if (Number.isFinite(het) && het <= bayGio) return "Đã hết hạn";
  return "Đang hiệu lực";
}

/** Whether to offer the revoke button.
 *
 *  Not a guard against an error. Measured on a live server, revoking an
 *  already-revoked invite answers 200 and leaves `revoked_at` where it was --
 *  the route is idempotent, and only an ACCEPTED invite is refused (409
 *  `invite_already_accepted`). So this is courtesy, not protection: a button
 *  that says "Thu hồi" beside a line that already says "Đã thu hồi" asks
 *  somebody to wonder which of the two is true. */
export function coTheThuHoi(moi: LoiMoiBuoiDi): boolean {
  return moi.revoked_at === null;
}
