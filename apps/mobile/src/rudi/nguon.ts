/**
 * Where a screen's numbers come from, decided in one place and said out loud.
 *
 * ## The problem this is the seam for
 *
 * The repo holds two apps. `src/screens/` is 54 screens wired to the 77 routes
 * that actually run; `src/rudi/` is 21 screens that look like the product and
 * read `fixtures.ts`. Every "the app is lying" symptom in the QA reports comes
 * out of that split: a beautiful screen with no data has to invent a number,
 * an invented number has to be hedged, and enough hedging becomes a lie.
 *
 * This module is where a RuDi screen asks "am I showing this group's real
 * money, or the Team Đà Lạt story?" -- and it must be a question with ONE
 * answer per launch, not per screen.
 *
 * ## Why live mode is opt-in rather than "whatever answers"
 *
 * The obvious design is to probe the server and go live if it replies. That
 * would make the numbers on screen depend on whether somebody happened to have
 * a server running, with no action by the person holding the phone. The demo
 * story and a real group's money would swap places silently. So live is
 * entered deliberately, and `viSao` records why it was not.
 *
 * ## A session is now enough, and what it took
 *
 * ADR-0014 shipped `POST /sessions` in #514, but the answer said only WHO you
 * are. There is no route that lists a person's contexts, so an app holding a
 * valid session still had no group to read and stayed on the fixture. That is
 * why `SessionResponse` now also carries `context_id`: sign-in happens by
 * redeeming an invitation to a TRIP, so the server knows the group at the
 * moment it issues the session.
 *
 * With that, a signed-in person is live and nobody has to pin anything into a
 * bundle. The `EXPO_PUBLIC_RUDI_*` pair stays as the DEV door -- it is how the
 * native gate drives live screens without minting an invitation every run --
 * and `tests/cau-hinh-ban-dung.test.mjs` refuses it in any shippable profile.
 *
 * ## Why `invited` is still not live
 *
 * Signing in is not joining. A first invitation lands `invited` and a member
 * still has to accept; the server refuses that person's group data, and this
 * screen must say the same thing rather than render an empty group as though
 * it were an empty trip.
 */

/** UUID as the server writes them. Same shape `navigation/lien-ket.ts` enforces. */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type Nguon =
  /** Fixture. `viSao` is shown to nobody by default, but it is the answer to
   *  "why is this still the demo", and a screen may print it. */
  | { kieu: "trai-nghiem"; viSao: string }
  /** Every number came from the server, as this person, in this group. */
  | { kieu: "live"; actorId: string; contextId: string };

/**
 * Dev-actor mode: an operator pins both halves of an identity at bundle time.
 *
 * Written as plain `process.env.X` member reads because Expo's inliner
 * pattern-matches the syntax tree -- `process?.env?.X` is an
 * OptionalMemberExpression, the guard returns false, and the read survives into
 * the bundle unreplaced. That exact mistake pinned every build to the
 * developer's own localhost once already; see `tests/env-inlining.test.mjs`.
 */
declare const process: { env: Record<string, string | undefined> };
const ACTOR_DEV = process.env.EXPO_PUBLIC_RUDI_ACTOR;
const CONTEXT_DEV = process.env.EXPO_PUBLIC_RUDI_CONTEXT;

/**
 * @param coPhien whether `src/api.ts` is holding a session bearer.
 *
 * Taken as an argument rather than imported so this stays a pure function of
 * its inputs and can be exercised without a device or a server.
 */
/** What the session module knows, reduced to what this decision needs. */
export type PhienToiThieu = {
  person_id: string;
  context_id: string | null;
  membership_state: "invited" | "active" | "left" | null;
};

export function nguonHienTai(
  phien: PhienToiThieu | null,
  moiTruong: { actor?: string; context?: string } = { actor: ACTOR_DEV, context: CONTEXT_DEV },
): Nguon {
  const { actor, context } = moiTruong;
  if (actor !== undefined || context !== undefined) {
    // Half a configuration is a mistake worth naming. Falling back quietly
    // would show fixture numbers to somebody who believes they pinned a group.
    if (actor === undefined || context === undefined) {
      return {
        kieu: "trai-nghiem",
        viSao: "Thiếu một nửa cấu hình dev: cần cả EXPO_PUBLIC_RUDI_ACTOR lẫn EXPO_PUBLIC_RUDI_CONTEXT.",
      };
    }
    if (!UUID_RE.test(actor) || !UUID_RE.test(context)) {
      // These go straight into a request path. A malformed one is a 404 storm
      // that reads on screen as "the server is broken".
      return {
        kieu: "trai-nghiem",
        viSao: "Cấu hình dev sai hình dạng: actor và context phải là UUID.",
      };
    }
    return { kieu: "live", actorId: actor, contextId: context };
  }
  if (phien !== null) {
    if (phien.context_id === null) {
      return {
        kieu: "trai-nghiem",
        viSao:
          "Đã đăng nhập nhưng chưa ở nhóm nào. Tạo nhóm hoặc nhận lời mời để xem dữ liệu thật.",
      };
    }
    if (phien.membership_state !== "active") {
      // The server will refuse this person's group data, and a screen that
      // rendered the group anyway would show an empty trip where the truth is
      // "nobody has accepted you yet".
      return {
        kieu: "trai-nghiem",
        viSao: "Đã đăng nhập, nhưng nhóm còn phải duyệt thì bạn mới xem được dữ liệu nhóm.",
      };
    }
    if (!UUID_RE.test(phien.context_id)) {
      return { kieu: "trai-nghiem", viSao: "Phiên mang một mã nhóm không đọc được." };
    }
    return { kieu: "live", actorId: phien.person_id, contextId: phien.context_id };
  }
  return { kieu: "trai-nghiem", viSao: "Chưa đăng nhập. Đây là bản trải nghiệm Team Đà Lạt." };
}
