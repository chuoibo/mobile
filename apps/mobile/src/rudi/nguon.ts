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
 * ## Why a bearer is still not enough
 *
 * ADR-0014 shipped in PR #514: `POST /sessions` exists, `src/phien.ts` redeems
 * a named invitation for one, and `src/api.ts` puts the bearer on every
 * identified request. So a session is real now. It is still not a group.
 *
 * `SessionResponse` carries `token`, `person_id`, `expires_at` and
 * `membership_state` -- and no `context_id`. `contexts.py` declares `POST
 * /contexts`, `GET /contexts/{id}`, members, balances and membership accept,
 * and nothing that lists the contexts a person belongs to. Re-checked against
 * `origin/main` at 03eb05a, after #514 merged.
 *
 * The legacy tree works around it by replaying `POST /contexts` under a derived
 * idempotency key. That reaches the demo group and would be wrong for a real
 * one: it would name a second group beside the one somebody is looking at.
 *
 * So a session alone still lands in `trai-nghiem`, with that stated as the
 * reason rather than left for a reader to discover from an empty screen.
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
export function nguonHienTai(
  coPhien: boolean,
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
  if (coPhien) {
    return {
      kieu: "trai-nghiem",
      viSao:
        "Đã đăng nhập, nhưng chưa biết nhóm nào: SessionResponse không mang context_id và " +
        "máy chủ chưa có route liệt kê nhóm của một người. Xem " +
        "docs/claude/2026-09-03/adr-0014-nua-client-da-san-sang.md.",
    };
  }
  return { kieu: "trai-nghiem", viSao: "Chưa đăng nhập. Đây là bản trải nghiệm Team Đà Lạt." };
}
