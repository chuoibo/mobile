/** F14. Who a trip can still invite, and what the trip screen may say about
 *  the invites it has just made.
 *
 * No React and no fetch, so every rule below runs under bare node. The route
 * calls are deliberately NOT here: `screens/quan-tri/quan-tri.ts` already owns
 * `taoLoiMoiBuoiDi` and `thuHoiLoiMoi`, and a second copy of a route call is a
 * copy that drifts the day the route changes. This file is only the part that
 * decides which control may exist, which is the part a test can hold.
 *
 * ## Two server rules the screen has to obey, read from the server's own code
 *
 * **A `group` invite may only name an ACTIVE member.** `create_outing_invite`
 * calls `_require_participants_are_members` for `source: "group"`, and that
 * helper builds its roster from memberships whose `state == "active"`
 * (service.py:3620). So offering the button on an `invited` row earns a 422
 * `participant_not_in_context` -- a refusal whose wording is about the group
 * when the real answer is "that person has not accepted yet".
 *
 * **Revoking does not free the person to be invited again.** The row survives
 * with `revoked_at` set; `uq_outing_invites_person` is unique on
 * `(outing_id, invited_person_id)` with no clause about revocation
 * (models.py:1323), and the service's pre-check
 * `find_outing_invite_for_person` does not filter revoked rows either
 * (repository.py:2160). The second invite is therefore a 409
 * `invite_already_exists`. That is a one-way door, and the screen says so in
 * words instead of offering a button that answers 409.
 *
 * ## What this file cannot know
 *
 * There is no `GET /outings/{id}/invites`. Every list here is what THIS
 * session created; an empty one means "none made since the screen opened",
 * never "this trip has no invites". So `daMoi` is always a partial view, and
 * a row it does not mention may still be invited on the server -- the 409 is
 * the real guarantee, and these rules are only the courtesy in front of it.
 */
import type { LoiMoiBuoiDi } from "../quan-tri/quan-tri";
import { tenThanhVien } from "../quan-tri/quan-tri";
import type { ThanhVien } from "../vao-cua/cong-api";

/**
 * Read an invite token out of whatever somebody pasted.
 *
 * ## Why this exists at all
 *
 * `NhanLoiMoi` used to have exactly one entrance: the `#moi=<token>` fragment
 * that `navigation/lien-ket.ts` parses. That file says of itself, in its own
 * header, "Web only by nature -- `location` does not exist on a phone". This
 * product ships to Android and iOS. So the screen that accepts an invite was
 * reachable in Chrome and by nothing at all on the platform the product ships
 * on: the organiser could mint a link, and the person it was minted for had no
 * way to open it.
 *
 * Pasting is the honest native edge. There is no in-app inbox to read -- there
 * is no `GET /people/{id}/outing-invites` -- so the token genuinely does
 * arrive out of band, in whatever chat app the organiser used. What arrives is
 * one of three things, and refusing two of them would make the feature depend
 * on a link surviving a copy-paste:
 *
 *   - the whole `invite_path` the server sent (`/outing-invites/<token>`),
 *   - a full link somebody's chat app turned it into,
 *   - the bare token, read aloud across a table and typed.
 *
 * ## What it refuses, and why the refusal is narrow
 *
 * The token is pasted straight into a URL by `api.ts` (`/outing-invites/
 * ${token}/accept`). So the one thing this must never return is a string that
 * can steer that request somewhere else: a `..` segment, or anything still
 * holding a slash after the last segment is taken. That is the same guard
 * `lien-ket.ts` puts on `#moi=`, kept identical on purpose -- two doors into
 * one screen that disagree about what a token is would mean the safer door is
 * decoration.
 *
 * A query string or fragment is stripped rather than rejected: chat apps
 * append tracking parameters to links, and a person who pasted a working link
 * should not be told their invite is malformed because Zalo added `?fbclid=`.
 *
 * Returns null for anything it will not vouch for. The screen renders the null
 * as a sentence; it never sends a request built from a string it could not
 * read.
 */
export function docMaLoiMoi(text: string): string | null {
  const cat = text.trim().split(/[?#]/, 1)[0] ?? "";
  if (cat === "") return null;
  // Last non-empty segment: handles the bare token, `/outing-invites/<t>`, and
  // `https://host/outing-invites/<t>/` alike, without caring which it was.
  const doan = cat.split("/").filter((s) => s !== "");
  const ma = doan[doan.length - 1] ?? "";
  if (ma === "" || ma === "." || ma === "..") return null;
  // A token is what the server mints: url-safe base64 or hex. Anything holding
  // a character that changes the meaning of a path is not one.
  if (!/^[A-Za-z0-9_-]{8,128}$/.test(ma)) return null;
  // `/outing-invites` alone is a path, not a token. Refuse the route's own
  // name so a half-copied link cannot read as a valid code.
  if (ma === "outing-invites" || ma === "accept") return null;
  return ma;
}

/** One roster row as the invite card offers it. */
export type HangMoi = {
  personId: string;
  ten: string;
  /** May the invite button be offered on this row? */
  moiDuoc: boolean;
  /** Why not, in a sentence the card prints. Null when it may. */
  vi: string | null;
};

/**
 * The invite this session already made for one person, revoked or not.
 *
 * Revoked rows count. The unique index does not care that an invite was
 * pulled back, so neither may this lookup.
 */
export function loiMoiCuaNguoi(
  daMoi: readonly LoiMoiBuoiDi[],
  personId: string,
): LoiMoiBuoiDi | null {
  return daMoi.find((m) => m.invited_person_id === personId) ?? null;
}

/**
 * The roster, each row carrying whether it may be invited and why not.
 *
 * Rows are kept rather than filtered out. A name that vanishes from a list is
 * a name somebody goes looking for; a name that stays with "Đã mời" beside it
 * answers the question they were about to ask.
 */
export function danhSachMoiDuoc(
  roster: readonly ThanhVien[],
  toiId: string | null,
  daMoi: readonly LoiMoiBuoiDi[],
): HangMoi[] {
  return roster.map((hang) => {
    const chung = { personId: hang.person_id, ten: tenThanhVien(hang) };
    if (hang.state === "left") {
      return { ...chung, moiDuoc: false, vi: "Đã rời nhóm." };
    }
    if (hang.state === "invited") {
      return {
        ...chung,
        moiDuoc: false,
        vi: "Chưa nhận lời vào nhóm, nên chưa mời vào chuyến được.",
      };
    }
    if (toiId !== null && hang.person_id === toiId) {
      return { ...chung, moiDuoc: false, vi: "Đây là bạn." };
    }
    const da = loiMoiCuaNguoi(daMoi, hang.person_id);
    if (da !== null) {
      return {
        ...chung,
        moiDuoc: false,
        vi: da.revoked_at
          ? "Đã thu hồi lời mời. Máy chủ giữ lại dòng cũ nên không mời lại người này vào chuyến này được."
          : "Đã mời vào chuyến này.",
      };
    }
    return { ...chung, moiDuoc: true, vi: null };
  });
}

/**
 * Fold a created or revoked invite into the session list.
 *
 * A revoke reply carries `invite_token: null` on purpose -- handing the token
 * back at the moment it stops working would be an invitation to paste it
 * somewhere. Merging rather than replacing is what keeps the link on screen,
 * struck through, instead of making it disappear the moment it is pulled
 * back. Written here rather than inline in the screen because dropping the
 * token on revoke is a one-character mistake and a silent one.
 */
export function gopLoiMoi(
  truoc: readonly LoiMoiBuoiDi[],
  sau: LoiMoiBuoiDi,
): LoiMoiBuoiDi[] {
  if (!truoc.some((m) => m.id === sau.id)) return [sau, ...truoc];
  return truoc.map((m) =>
    m.id === sau.id
      ? {
          ...sau,
          invite_token: sau.invite_token ?? m.invite_token,
          invite_path: sau.invite_path ?? m.invite_path,
        }
      : m,
  );
}

/**
 * What to call one invite, without ever printing a raw id.
 *
 * A UUID is not a name. The roster is the only place a `group` invite's
 * person has one, and when it holds no row this says so in words -- the same
 * rule `tenThanhVien` follows, for the same reason.
 */
export function tenLoiMoi(
  moi: LoiMoiBuoiDi,
  roster: readonly ThanhVien[],
): string {
  if (moi.source === "link") return "Lời mời bằng link";
  const hang = roster.find((t) => t.person_id === moi.invited_person_id);
  if (!hang) return "Lời mời cho một người";
  return `Lời mời cho ${tenThanhVien(hang)}`;
}

/**
 * One line under the list: how many invites this session made, and how many
 * of them still work.
 *
 * `bayGio` is a parameter rather than `Date.now()` so this is testable and so
 * a screen that renders twice in one second cannot disagree with itself --
 * the same reason `trangThaiLoiMoi` takes one.
 */
export function tomTatLoiMoi(
  daMoi: readonly LoiMoiBuoiDi[],
  bayGio: number,
): string {
  if (daMoi.length === 0) {
    return "Chưa tạo lời mời nào trong lượt này.";
  }
  const con = daMoi.filter(
    (m) => m.revoked_at === null && !hetHan(m, bayGio),
  ).length;
  return `${daMoi.length} lời mời tạo trong lượt này, ${con} còn hiệu lực.`;
}

function hetHan(moi: LoiMoiBuoiDi, bayGio: number): boolean {
  const het = Date.parse(moi.expires_at);
  return Number.isFinite(het) && het <= bayGio;
}
