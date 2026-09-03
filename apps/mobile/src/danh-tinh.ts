/* Ai đang gọi, và bằng bằng chứng gì.
 *
 * ## Vì sao nó là một file riêng chứ không nằm trong `api.ts`
 *
 * Chín module tự dựng header vì chúng có trước `callAsActor` hoặc cần hình dạng
 * mà nó không có (multipart, query, cursor). Khi cả chín được đưa về gọi
 * `headerNguoiGoi` của `api.ts`, Metro báo ngay, và nó hiện lên ngay trên màn
 * chào của máy ảo:
 *
 *     Require cycle: src/api.ts -> src/participants.ts
 *                    -> src/screens/chat/tin-nhan.ts -> src/api.ts
 *
 * `api.ts` vốn đã import `participants.ts`, và `participants.ts` import
 * `tin-nhan.ts`. Vòng đó không dừng ở một cảnh báo vàng: module nào được nạp
 * giữa vòng sẽ thấy `headerNguoiGoi` là `undefined`, nên chỗ hỏng sẽ là một cú
 * crash trên đúng đường mà bản vá này dựng ra để chữa.
 *
 * Nên chỗ dựng danh tính nằm ở một file LÁ: nó không import gì trong `src/`.
 * `api.ts` lấy từ đây và re-export, chín module kia gọi qua `api.ts` như cũ, và
 * không ai phải nhớ thứ tự nạp.
 */
/** The session this app is signed in with, or `null`.
 *
 * Module state rather than a parameter threaded through ninety call sites,
 * and that is deliberate: a session is a property of the app, not of a
 * request. Threading it would mean every new call site is a chance to forget,
 * and forgetting means a 401 that reads like a server fault -- the exact
 * failure `ActorCallOptions` was reshaped to prevent for `actorId`.
 *
 * Written from `phien.ts`, which owns reading and storing it. Nothing here
 * touches SecureStore: this module is imported by the node test suite, which
 * has no native modules, and pulling one in would make the whole API layer
 * unloadable there.
 */
let tokenPhien: string | null = null;

/** Sign in (a token) or sign out (`null`). */
export function datTokenPhien(token: string | null): void {
  tokenPhien = token;
}

/** What `phien.ts` stored, for the sign-out call that has to send it itself. */
export function tokenPhienHienTai(): string | null {
  return tokenPhien;
}

export function actorHeaders(
  actorId: string,
  roles = "member,advancer,recipient,batch_owner",
  contexts?: string,
): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    // Still sent, and no longer what a production server believes. Since
    // ADR-0014 `get_actor` reads these only when the host is explicitly in
    // `dev`; in `prod` they are ignored and the `Authorization` header below
    // is the whole of the answer. Both are sent so that one build works
    // against the demo box and against a real host without a flag.
    "X-Actor-ID": actorId,
    "X-Actor-Roles": roles,
  };
  // Every identified request goes through here -- including the four
  // multipart calls that build their headers from this function and then use
  // `fetch` directly, which is why the bearer is attached here rather than in
  // `send`. A route added later cannot forget it.
  if (tokenPhien !== null) headers["Authorization"] = `Bearer ${tokenPhien}`;
  // Omitted rather than defaulted. The default used to be the synthetic
  // `CONTEXT_ID`, which meant every person-scoped call claimed membership of a
  // group that did not exist, and -- worse -- a group-scoped call that forgot
  // to name its group inherited that claim instead of failing. `deps.py` reads
  // a missing header as "no contexts", which is the truthful answer for a
  // route about a person.
  if (contexts !== undefined) headers["X-Actor-Contexts"] = contexts;
  return headers;
}

/**
 * Identity headers for a module that runs its own `fetch`.
 *
 * ## Why this is exported
 *
 * Nine modules build `X-Actor-ID` by hand -- `screens/chat/tin-nhan.ts`,
 * `screens/ca-nhan/tai-chinh.ts`, `screens/album/album-api.ts` and six more --
 * because they predate `callAsActor` or need a shape it does not have
 * (multipart, query strings, cursors). Each grew its own private `headers()`.
 *
 * That was harmless while identity WAS the header. Since ADR-0014 it is not:
 * a production server ignores `X-Actor-*` and reads `Authorization`, so every
 * one of those nine modules got 401 on a real host while `src/api.ts` worked.
 * Measured against a `prod` server on 2026-09-03: `GET /people/{id}/finance`,
 * `GET /contexts/{id}/recap` and `GET /contexts/{id}/messages` all answered 401
 * to a request carrying only the header trio.
 *
 * The failure was invisible in the worst way. `doc-live.ts` swallowed the recap
 * 401 into "no total available", so the settlement screen printed *«máy chủ
 * chưa có tổng cho nhóm này»* -- a sentence that was false, on a screen this
 * whole branch exists to stop lying.
 *
 * So there is one builder again, and `tests/mot-cho-dung-danh-tinh.test.mjs`
 * refuses a second one.
 */
export function headerNguoiGoi(
  actorId: string,
  opts: { roles?: string | null; contexts?: string; key?: string } = {},
): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...actorHeaders(actorId, opts.roles ?? undefined, opts.contexts),
  };
  // `roles: null` means "claim nothing", and it is not the same as leaving
  // `roles` out: leaving it out takes `actorHeaders`'s four-role default.
  // `POST /places/search` reads `actor.id` and nothing else, so four roles
  // there is a claim the screen does not need -- and the same header trio
  // reaches every other route, where the claim would still be asserted.
  // `tests/tim-dia-diem.test.mjs` pins that, and caught this exact regression
  // the first time these headers were routed through here.
  if (opts.roles === null) delete headers["X-Actor-Roles"];
  if (opts.key) headers["Idempotency-Key"] = opts.key;
  return headers;
}
