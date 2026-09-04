/** Talks to services/api, for real.
 *
 * This file has carried two fakes. First its own even split --
 * `Math.floor(total / n)`, under a docstring saying nothing here computes
 * money. Then a fixture replayer that refused any amount not in a corpus:
 * honest, and useless in front of anyone, because typing a real number got a
 * refusal. Both are gone. It speaks the actual HTTP contract now.
 *
 * Nothing here computes money. The split comes from the server, which calls
 * the allocator that 41 hand-computed golden vectors are pinned against. A
 * second implementation in TypeScript would be a second thing to get wrong,
 * and `tests/offline.test.mjs` fails if one reappears.
 *
 * Three shapes the API insists on, each of which the app used to get wrong:
 *
 * - **Participants are UUIDs.** They were `p1`, `p2` -- readable, and rejected
 *   by every endpoint. Ids are minted per person in `participants.ts`.
 * - **Confirming re-sends the allocation that was on screen.** Not politeness:
 *   the server compares it against what it would compute now and refuses on a
 *   mismatch, so an expense that changed between looking and pressing cannot
 *   be confirmed by somebody who never saw the change.
 * - **Publishing names its batch.** The app called `/batches/current/publish`,
 *   a route that has never existed.
 *
 * There is no silent fallback to fixtures. If the API cannot be reached the
 * screen says so and names the address it tried. A demo that quietly runs on
 * made-up data is the failure this file keeps being rewritten to avoid.
 */
import { actorHeaders, datTokenPhien, tokenPhienHienTai } from "./danh-tinh";

// `datTokenPhien` / `tokenPhienHienTai` re-export vì chúng là TRẠNG THÁI, và
// chín mươi chỗ gọi đã quen đường này.
//
// `headerNguoiGoi` thì KHÔNG, và đó là chủ ý. Chuyền tiếp nó qua đây giữ
// nguyên vòng mà việc tách file sinh ra để gỡ: `tin-nhan.ts` vẫn import từ
// `./api`, nên `api.ts -> participants.ts -> chat/tin-nhan.ts -> api.ts` vẫn
// còn nguyên. Đo trên máy ảo: cảnh báo Require cycle vẫn hiện y như trước khi
// tách, và cái dải LogBox của nó nằm đè lên nút, nuốt luôn cú bấm của flow.
// Người gọi lấy thẳng từ `danh-tinh.ts`.
export { datTokenPhien, tokenPhienHienTai };
import type { BillReading, ReceiptScanWire } from "./receipt";
import type { Assignment } from "./assignment";
import {
  assignmentsBody,
  billCreateBody,
  soDuFromWire,
  type BillWire,
  type SoDu,
  type SoDuWire,
} from "./bill";
import {
  sapXepChang,
  type BodyTaoBuoiDi,
  type BuoiDi,
  type ChangGui,
  type CheckIn,
} from "./screens/len-plan/buoi-di";
import { type Participant, labelInGroup, makeIdFactory, type GroupMember } from "./participants";

/** Where the API lives. Overridable so a phone can reach a laptop. */
// Written as a plain `process.env.EXPO_PUBLIC_API_URL` on purpose, and it has
// to stay that way. Expo substitutes this at build time by pattern-matching
// the syntax tree, and its guard
// (babel-preset-expo/build/plugins/inline-env-vars.js) accepts the read only
// when the object being read from is a plain member expression. A defensive
// `process?.env?.EXPO_PUBLIC_API_URL` does not match: `process?.env` is an
// OptionalMemberExpression, the guard returns false, and the whole expression
// survives into the bundle unreplaced -- so every build fell through to the
// default below and the phone was pinned to the laptop's own localhost.
//
// The guard that used to wrap this was protecting against a target where
// `process` is undefined. There is no such target here. Metro replaces this
// read before the browser ever sees it (with the literal in a production
// build, with an import from `expo/virtual/env` in development), and the node
// test runner has `process` as a global. The guard bought nothing and cost the
// substitution. `tests/env-inlining.test.mjs` fails if the syntax drifts back.
declare const process: { env: Record<string, string | undefined> };

export const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

/* There is deliberately no `CONTEXT_ID` constant in this file any more.
 *
 * It used to hold `1aa00000-aaaa-…`, minted when nothing created a group, and
 * it never had a row in `contexts`. Two comments in this repository said so
 * outright while every expense in the app was still filed under it. That was
 * survivable only while the server took the caller's word for the group:
 * `propose` allocates and writes nothing, so it answered 200 and the split
 * screen looked right.
 *
 * `_require_participants_are_members` (service.py) closed that. A context with
 * no row has no members, so every participant is a stranger and `confirm`
 * answers `422 participant_not_in_context` -- for everyone, on the one path
 * this product exists to demonstrate. The same id also went out as
 * `X-Actor-Contexts`, which `confirm_expense` and `create_batch` check against
 * the expense's own context, so a body fixed without the header would only
 * have traded the 422 for a 403.
 *
 * So the group is now a parameter, the way `taoBuoiDi` and `docSoDu` already
 * took it: callers pass the id `khoiDongNhom` returned, and a group that does
 * not exist cannot be spelled by accident.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

/**
 * One press of one button: a key, and the clock reading its body is built from.
 *
 * The server enforces `Idempotency-Key` on every write route, and enforces it
 * by fingerprinting method + path + body. That makes the unit of protection an
 * *attempt*, not a call: retrying the same press must send the same key **and
 * the same bytes**, or the server sees a used key on a different request and
 * answers 422 `idempotency_key_reuse`.
 *
 * The clock is what made that non-obvious. Three bodies here stamp a time
 * (`occurred_at`, `due_at`, `guest_link_expires_at`). Read from `Date.now()` at
 * call time, pressing again a minute later changed the body under an unchanged
 * key -- so sending the header alone would have swapped a double write for a
 * refusal aimed at somebody who did nothing wrong. Reading it from the attempt
 * makes a retry byte-identical by construction rather than by care.
 */
export type Attempt = { readonly key: string; readonly at: number };

/** A draft expense as the organiser typed it, before the server has split it. */
export type Draft = {
  participants: Participant[];
  totalVnd: number;
  advancerId: string;
  occasion: string;
};

/** The server's split of a draft: allocations per person, who absorbed the rounding đồng. */
export type Proposal = {
  participants: Participant[];
  allocations: Record<string, number>;
  roundingGainers: string[];
  totalVnd: number;
  advancerId: string;
  occasion: string;
};

/** One obligation on a collection board as App B named it; status is the server's. */
export type Obligation = {
  id: string;
  senderId: string;
  senderName: string;
  recipient: string;
  amountVnd: number;
  status: "outstanding" | "partially_confirmed" | "confirmed" | "over_confirmed" | "waived" | "disputed";
};

/** One debt inside a guest envelope: a person can owe two people out of one round. */
export type EnvelopeObligation = {
  obligationId: string;
  amountVnd: number;
};

/**
 * What `publishBatch` hands back per sender: the private guest link and the
 * debts behind it. Owned here (not by a screen) because two shells share it.
 */
export type Envelope = {
  senderId: string;
  senderName: string;
  amountVnd: number;
  url: string;
  opened: boolean;
  obligations: EnvelopeObligation[];
};

const newKey = makeIdFactory();

/** Mint an attempt. Call this on the press, never inside a retry. */
export function newAttempt(): Attempt {
  return { key: newKey(), at: Date.now() };
}

/**
 * The attempt for one thing being written, minted once and then kept.
 *
 * `name` is what is being written -- an expense id, a batch id, an obligation
 * id -- so the map does the arithmetic the server's rule demands: the same
 * target keeps its key across retries, a different target gets its own. Callers
 * hold the book in a ref, because a re-render between the press and the reply
 * must not be able to lose the key and turn a retry into a second write.
 */
export function attemptFor(book: Record<string, Attempt>, name: string): Attempt {
  return (book[name] ??= newAttempt());
}

/**
 * What the idempotency middleware's own refusals mean.
 *
 * Applied in `call` rather than per route, matching how the protection is
 * installed: the middleware covers a write route the moment it is registered,
 * so the words for its refusals cannot depend on somebody remembering to add a
 * route to a list. Reaching any of these puts a sentence in front of a person
 * standing over their own money, and "Idempotency-Key was already used for a
 * different request" is not a sentence.
 */
const IDEMPOTENCY_REFUSALS: Record<string, string> = {
  // 409. The honest answer is that nobody knows yet whether it was written,
  // and the client is the one party that cannot find out. Telling somebody to
  // press again here is how one payment becomes two.
  idempotency_request_in_flight:
    "Lần bấm trước chưa chạy xong nên chưa biết máy chủ đã ghi hay chưa. " +
    "Chờ một chút rồi mở lại màn hình để xem, đừng bấm lại ngay.",
  // 422. Same key, different bytes. With attempts threaded properly this is
  // unreachable, which is why it says the app is at fault instead of asking a
  // person to fix something on their side.
  idempotency_key_reuse:
    "Nội dung gửi đi đã khác so với lần bấm trước, nên máy chủ không phát lại " +
    "kết quả cũ. Mở lại màn hình để xem máy chủ đang giữ gì trước khi gửi lại.",
  // 422. Only reachable if the app sends a malformed key, so it says so rather
  // than sending somebody to look for a mistake they did not make.
  invalid_idempotency_key:
    "App gửi một khoá không hợp lệ nên lệnh này chưa được ghi. Đây là lỗi của app.",
};

/**
 * Vietnamese carries diacritics; a sentence with none of them is not Vietnamese.
 *
 * Crude on purpose. The question this answers is not "which language is this"
 * but "did a person write this for a person", and every refusal sentence the
 * API is designed to emit is Vietnamese prose. A machine string that gets this
 * far -- `Internal Server Error`, `Field required`, a stringified list -- has
 * no diacritic in it, and a real Vietnamese sentence long enough to be a
 * refusal has several.
 */
const DAU_TIENG_VIET =
  /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụỳýỷỹỵ]/i;

/**
 * What a person reads when the server refuses, whatever the server sent.
 *
 * Two measured leaks live behind this function, and both put machine text in
 * front of somebody standing over their own money:
 *
 *  - **`detail` is not always a string.** The API has one handler, for
 *    `ApiProblem`, which does emit `{code, detail}` with a Vietnamese sentence.
 *    Nothing handles FastAPI's own `RequestValidationError`, so a malformed
 *    body comes back as `{"detail": [{type, loc, msg, input}, ...]}`. Measured
 *    against `create_app()`: `POST /expenses {"nope": 1}` answered 422 with
 *    three of those. Assigning that list to an `Error` message stringifies it,
 *    and the banner rendered `[object Object],[object Object],[object Object]`.
 *  - **The fallback was written for whoever was debugging.**
 *    `` `${method} ${path} trả về ${response.status}` `` is a log line. It named
 *    the route and the status and told a person nothing they could act on.
 *
 * The server's *good* sentences still win, and that is the half worth guarding:
 * `SCAN_REFUSALS` and the publish table exist because those sentences are
 * specific and correct. Replacing them with a generic apology would be the
 * same defect facing the other way, so a string that reads as Vietnamese prose
 * is passed through untouched and only the machine text is replaced.
 *
 * The status is used to choose the sentence and is never printed. A number is
 * not a next step, and a person who reads "500" has learned nothing except
 * that something is wrong, which the screen already told them.
 */
export function thongDiepNguoiDoc(status: number, detail: unknown): string {
  if (typeof detail === "string" && detail.trim() !== "" && DAU_TIENG_VIET.test(detail)) {
    return detail.trim();
  }
  if (status === 0) return `Không nối được ${BASE_URL}. Máy chủ có đang chạy không?`;
  if (status === 401 || status === 403) {
    return "Tài khoản đang dùng chưa được phép làm việc này trong nhóm. Nhờ người tạo nhóm cấp quyền rồi thử lại.";
  }
  if (status === 404) {
    return "Máy chủ không có phần này. Nhiều khả năng app đang trỏ vào một bản API cũ hơn, kiểm tra lại địa chỉ máy chủ ghi ở cuối màn hình.";
  }
  if (status === 409) {
    return "Lần bấm trước chưa chạy xong nên chưa biết máy chủ đã ghi hay chưa. Chờ một chút rồi mở lại màn hình để xem, đừng bấm lại ngay.";
  }
  if (status === 429) {
    return "Máy chủ đang nhận quá nhiều yêu cầu cùng lúc. Chờ khoảng một phút rồi thử lại.";
  }
  if (status >= 400 && status < 500) {
    // Includes 422, which is where the list-shaped detail comes from. A
    // validation refusal means the app sent something the server does not
    // accept, so it is not something the person holding the phone can fix by
    // typing differently, and the copy must not send them looking.
    return "App gửi lên một yêu cầu máy chủ không nhận, nên việc này chưa được ghi. Đây là lỗi của app chứ không phải do bạn nhập sai. Thử lại sau, và báo cho nhóm kỹ thuật nếu vẫn vậy.";
  }
  if (status >= 500) {
    return "Máy chủ đang gặp sự cố nên chưa làm được việc này. Chưa có gì bị ghi sai, thử lại sau một chút.";
  }
  return "Chưa làm được việc này. Thử lại sau một chút.";
}

/** The parts of a request that do not depend on who is making it. */
type RequestShape = {
  method?: string;
  body?: unknown;
  /** Required for writes. A write without one is unprotected against retries. */
  attempt?: Attempt;
};

/**
 * A request made as somebody, which is nearly all of them.
 *
 * `actorId` is required, and that is the whole point of this type existing.
 * It used to be `actorId?: string` on a single shared options bag, so a call
 * that forgot to say who was making it compiled cleanly, sent no
 * `X-Actor-ID`, and came back 401 at runtime -- where the screen reported it
 * as a server fault. Three people walked into that in one day (#365, #379,
 * and one before them), which is the tell that the shape was wrong rather
 * than that three people were careless. `scripts/check_actor_headers.py`
 * caught each of them, but only in CI, and a compiler that already knows the
 * answer should not be leaving the job to a later gate.
 */
type ActorCallOptions = RequestShape & {
  actorId: string;
  /**
   * What this actor claims to be, when the default four roles are not enough.
   *
   * The expense flow acts as a plain member throughout, so the default covers
   * it. Group administration does not: `invite_context_member` in
   * `app/domain/permissions.py` asks for `group_admin`, which nothing in that
   * default list carries. Parameterised rather than widened, so one screen
   * needing an extra claim does not hand every other screen the same claim.
   *
   * It is worth being blunt about what this is. These headers are asserted by
   * the client because no gateway exists to overwrite them, so this parameter
   * does not *grant* anything -- the same request could always have been made
   * with curl. It records which claim a screen depends on, which is what will
   * have to be reproduced when real sessions arrive.
   */
  roles?: string;
  /** Which groups this actor claims to be in.
   *
   *  No default. It used to default to the synthetic `CONTEXT_ID`, so a call
   *  that forgot to name its group silently claimed membership of one that did
   *  not exist. Omitted means the header is not sent, which `deps.py` reads as
   *  "no contexts" -- the truthful answer for a route about a person.
   *
   *  Only carried when `actorId` is set: the headers are built together, and
   *  a group claim with nobody making it is not a claim. */
  contexts?: string;
};

/**
 * A request deliberately made as nobody.
 *
 * `actorId`, `roles` and `contexts` are typed `never` rather than left out,
 * so naming one is an error at the call site that names it instead of a field
 * quietly ignored on the way past. That matches what the code already did:
 * roles and a group claim were only ever read when an actor was set, so an
 * anonymous call carrying them was stating something that never travelled.
 *
 * Reaching for this type should feel like a decision, because it is one. Every
 * use of it in this file carries a comment saying which route is anonymous and
 * why.
 */
type AnonymousCallOptions = RequestShape & {
  actorId?: never;
  roles?: never;
  contexts?: never;
};

/**
 * One request as somebody. Sends `X-Actor-ID`, and cannot be asked not to.
 */
async function callAsActor<T>(path: string, options: ActorCallOptions): Promise<T> {
  const { actorId, roles, contexts } = options;
  return send<T>(path, actorHeaders(actorId, roles, contexts), options);
}

/**
 * One request as nobody, said out loud.
 *
 * Written out at each call site rather than reached by leaving a field off, so
 * that an anonymous request is something somebody chose and can be asked about
 * in review.
 */
async function callAnonymous<T>(path: string, options: AnonymousCallOptions): Promise<T> {
  return send<T>(path, { "Content-Type": "application/json" }, options);
}

/** The shared body of both: identical wire behaviour, different headers. */
async function send<T>(
  path: string,
  actorHeadersOrNone: Record<string, string>,
  { method = "POST", body, attempt }: RequestShape,
): Promise<T> {
  const headers: Record<string, string> = { ...actorHeadersOrNone };
  // The header the server's middleware keys off. Without it the middleware
  // passes the request straight through -- which is what this app did on every
  // route, so the protection was installed and switched off. Measured against a
  // real server: two identical `POST /expenses` with no header left two rows in
  // `expenses`, and the same two with a header left one.
  //
  // Keys are scoped by `X-Actor-ID` server-side, falling back to a shared
  // anonymous scope when the app does not send one (`/expenses` today). UUIDs
  // do not collide across that shared scope, so this is safe, but it is the
  // reason a key must stay a UUID rather than becoming anything readable.
  if (attempt) headers["Idempotency-Key"] = attempt.key;

  let response: Response;
  try {
    response = await fetch(BASE_URL + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // Never reached is not the same as returned an error, and saying "500"
    // when nothing answered sends a person to debug the wrong machine.
    throw new ApiError(
      0,
      "unreachable",
      `Không nối được ${BASE_URL}. Máy chủ có đang chạy không?`,
    );
  }

  if (!response.ok) {
    // The API returns {code, detail}. A proxy or a crash might not, so fall
    // back to the status rather than inventing a code.
    //
    // `detail` stays `unknown` all the way to `thongDiepNguoiDoc`. It used to
    // be typed by assignment into a `string`, which is how a 422's list of
    // validation objects reached an `Error` message and rendered as
    // "[object Object]" -- see that function's header for the measurement.
    let code = `http_${response.status}`;
    let detail: unknown = null;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; there is nothing to read, so the status chooses the words */
    }
    throw new ApiError(
      response.status,
      code,
      IDEMPOTENCY_REFUSALS[code.toLowerCase()] ?? thongDiepNguoiDoc(response.status, detail),
    );
  }
  // 204 means the server did the thing and has nothing to say about it, so
  // there is no body to parse. `response.json()` on an empty body throws a raw
  // SyntaxError, which is not an `ApiError` and so escapes every refusal table
  // in this file -- a caller would show the browser's own English parser text
  // for a call that actually SUCCEEDED. `DELETE .../reactions` is the first
  // route here to answer 204; before it, this line was unreachable-but-wrong.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * The intent key for naming one person.
 *
 * The name is part of the key, not just the id. `attemptFor` hands back the
 * same key for the same intent, and the server fingerprints method + path +
 * body; keying on the id alone would send a changed `display_name` under an
 * already-used key and earn a 422 aimed at somebody who only corrected a typo.
 * Renaming is a different intent, so it mints a different key. Same shape as
 * `expenseIntent` in App.tsx, for the same reason.
 */
function nameIntent(person: Participant): string {
  return `dat-ten:${person.id}:${person.name}`;
}

/**
 * What the server's refusals to name somebody mean.
 *
 * Built per person rather than declared as a constant so the sentence can say
 * which of them it is about. A group of six produces six of these calls, and
 * "không đổi được tên" without a name tells the organiser to go and check all
 * six.
 *
 * `permission_denied` here is always the rename rule: the server lets any
 * member name an id that has no row, and only the person themselves change a
 * name that already exists. Reaching it means this id was named something else
 * before, which on one phone means the organiser edited a name after a first
 * send.
 */
function nameRefusals(person: Participant): Record<string, string> {
  return {
    permission_denied:
      `Người này đã được đặt tên khác trước đó, và chỉ chính họ mới đổi được. ` +
      `Giữ nguyên tên cũ, hoặc xoá "${person.name}" khỏi danh sách rồi thêm lại như một người mới.`,
    person_not_registered: `Máy chủ chưa nhận ra ${person.name}. Thử gửi lại một lần nữa.`,
  };
}

/**
 * Tell the server who an id belongs to.
 *
 * Participant ids are minted on this phone and then used in expenses,
 * obligations and envelopes. Until this call exists for each of them, the
 * server holds ids and no names, so `get_guest_envelope` has nothing to join
 * and the guest page says "Phần của a5b2c277-9b99-4699-a875-ed324e886237" to a
 * stranger being asked for money.
 *
 * That is not hypothetical: `PUT /people/{id}` shipped as the only way a name
 * enters this product, and nothing called it. The route was green, the client
 * was green, and the one screen an outsider ever sees still printed a UUID,
 * because the half that was missing was this one.
 */
export async function registerPerson(
  person: Participant,
  actorId: string,
  attempt: Attempt,
): Promise<void> {
  await translatedAsActor<{ id: string; display_name: string }>(
    nameRefusals(person),
    `/people/${person.id}`,
    { method: "PUT", body: { display_name: person.name }, actorId, attempt },
  );
}

/**
 * Name everybody in the roster, before anything refers to them.
 *
 * Sequential rather than `Promise.all`. The calls are independent, so parallel
 * would be faster, but a failure part-way through has to be able to say which
 * person it was about, and a rejected `Promise.all` reports one failure while
 * the rest keep running against a server that has already refused once.
 *
 * Failure is not swallowed. A name that silently does not arrive puts a machine
 * id back on the guest page, which is exactly the bug this exists to close, and
 * it would do it while every screen in the app still showed the typed name.
 */
export async function registerPeople(
  people: Participant[],
  actorId: string,
  book: Record<string, Attempt>,
): Promise<void> {
  for (const person of people) {
    await registerPerson(person, actorId, attemptFor(book, nameIntent(person)));
  }
}

export type ExpenseItemWire = {
  item_id: string;
  label: string;
  amount_vnd: number;
  shared_by: string[];
};

type ExpenseInput = {
  context_id: string;
  description: string;
  recorded_by_id: string;
  paid_by_id: string;
  verification_scope: "totals_only" | "items_reviewed";
  occurred_at: string;
  participants: string[];
  total_amount_vnd: number;
  items: ExpenseItemWire[];
  surcharges: never[];
  discounts: never[];
};

type AllocationWire = {
  allocations: Record<string, number>;
  rounding_gainers: string[];
  warnings: string[];
};

/**
 * What the allocator's refusals mean to the person holding the phone.
 *
 * `blockingProblem` in `assignment.ts` is the first line of defence and
 * should stop these from being reachable. This table is the net underneath:
 * a race, a stale roster, a line that became 0đ after the preview, should
 * still read as a next move rather than as `EMPTY_SHARED_BY`.
 */
const ALLOCATOR_REFUSALS: Record<string, string> = {
  reconciliation_mismatch:
    "Tổng các món không khớp tổng bill. Quay lại màn trước kiểm tra lại từng dòng tiền.",
  empty_shared_by:
    "Có món chưa ai nhận. Tích ít nhất một người đã ăn từng món trước khi gửi.",
  zero_amount:
    "Có món đang 0đ. Quay lại màn trước để sửa giá hoặc xoá món đó.",
  unknown_participant:
    "Một người trong danh sách chia không còn trong nhóm. Xoá họ khỏi món, hoặc thêm lại vào nhóm.",
  duplicate_shared_by:
    "Một món đang gán trùng một người. Đây là lỗi của app, mở lại màn hình rồi thử lại.",
  amount_too_large:
    "Một món vượt quá số tiền app nhận. Quay lại màn trước giảm giá hoặc xoá món.",
  negative_amount:
    "Một món đang mang số âm. Quay lại màn trước sửa lại giá.",
};

function expenseBody(input: {
  contextId: string;
  occasion: string;
  actorId: string;
  payerId: string;
  participantIds: string[];
  totalVnd: number;
  items: ExpenseItemWire[];
  occurredAt: number;
}): ExpenseInput {
  return {
    context_id: input.contextId,
    description: input.occasion,
    recorded_by_id: input.actorId,
    paid_by_id: input.payerId,
    verification_scope: input.items.length > 0 ? "items_reviewed" : "totals_only",
    // From the attempt, not the clock: a retry has to send the same bytes.
    occurred_at: new Date(input.occurredAt).toISOString(),
    participants: input.participantIds,
    total_amount_vnd: input.totalVnd,
    items: input.items,
    surcharges: [],
    discounts: [],
  };
}

type ExpenseResponse = {
  expense_id: string;
  proposal: ExpenseInput;
  allocation: AllocationWire;
};

/** A proposal plus what `confirmExpense` needs to prove it saw it. */
export type PendingProposal = Proposal & {
  expenseId: string;
  serverProposal: ExpenseInput;
  /** The group this bill was proposed under.
   *
   *  Carried on the proposal rather than asked for again at `confirm` and
   *  `openBatch`. Those two are the calls the server checks the group on, and
   *  a second parameter is a second chance to name a different one -- which is
   *  how an expense allocated inside one group gets written into another. */
  contextId: string;
};

export type SplitPreview = {
  allocations: Record<string, number>;
  roundingGainers: string[];
  warnings: string[];
};

/**
 * Ask the server what this matrix costs each person, without confirming.
 *
 * Same `POST /expenses` as `proposeSplit`. The caller keys the attempt on
 * the matrix signature, so ticking the same boxes again replays rather than
 * inserting another expense.
 */
export async function previewSplit(
  input: {
    contextId: string;
    participantIds: string[];
    totalVnd: number;
    items: ExpenseItemWire[];
    payerId: string;
    occasion: string;
  },
  attempt: Attempt,
): Promise<SplitPreview> {
  const body = expenseBody({
    contextId: input.contextId,
    occasion: input.occasion,
    actorId: input.payerId,
    payerId: input.payerId,
    participantIds: input.participantIds,
    totalVnd: input.totalVnd,
    items: input.items,
    occurredAt: attempt.at,
  });
  // No `contexts`, and no `actorId` to hang one on: `POST /expenses` is the
  // one write this client sends anonymously, on purpose (see `callAnonymous`,
  // on the shared idempotency scope). The group travels in the body, which is
  // where the allocator reads it. `confirm` is where the server starts
  // checking it.
  const result = await translatedAnonymous<ExpenseResponse>(ALLOCATOR_REFUSALS, "/expenses", {
    body,
    attempt,
  });
  return {
    allocations: result.allocation.allocations,
    roundingGainers: result.allocation.rounding_gainers,
    warnings: result.allocation.warnings ?? [],
  };
}

export async function proposeSplit(
  contextId: string,
  draft: Draft,
  attempt: Attempt,
  items: ExpenseItemWire[] = [],
): Promise<PendingProposal> {
  const body = expenseBody({
    contextId,
    occasion: draft.occasion,
    actorId: draft.advancerId,
    payerId: draft.advancerId,
    participantIds: draft.participants.map((person: Participant) => person.id),
    totalVnd: draft.totalVnd,
    items,
    occurredAt: attempt.at,
  });
  // Anonymous like `previewSplit`, and for the reason spelled out there.
  const result = await translatedAnonymous<ExpenseResponse>(ALLOCATOR_REFUSALS, "/expenses", {
    body,
    attempt,
  });

  return {
    participants: draft.participants,
    allocations: result.allocation.allocations,
    roundingGainers: result.allocation.rounding_gainers,
    totalVnd: draft.totalVnd,
    advancerId: draft.advancerId,
    occasion: draft.occasion,
    expenseId: result.expense_id,
    serverProposal: result.proposal,
    contextId,
  };
}

/**
 * Write the split into the ledger.
 *
 * `expected_allocations` is the set of numbers the person actually looked at.
 * The server refuses if they no longer match what it would compute, which is
 * the point: a split that changed between the screen and the button must not
 * be confirmed by somebody who never saw the change.
 */
export async function confirmExpense(
  proposal: PendingProposal,
  attempt: Attempt,
): Promise<{ expenseVersionId: string; acknowledged: boolean }> {
  const result = await translatedAsActor<{
    expense_version_id: string;
    payer_acknowledgement: "pending" | "acknowledged";
  }>(CONFIRM_REFUSALS, `/expenses/${proposal.expenseId}/confirm`, {
    body: {
      proposal: proposal.serverProposal,
      expected_allocations: proposal.allocations,
      acknowledge_as_advancer: true,
    },
    actorId: proposal.advancerId,
    attempt,
    contexts: proposal.contextId,
  });
  return {
    expenseVersionId: result.expense_version_id,
    acknowledged: result.payer_acknowledgement === "acknowledged",
  };
}

/**
 * Spec section 8.3 has two gates. The app models exactly one of them.
 *
 * Gate 1 -- the advancer agreed -- is knowable here: `confirmExpense` returns
 * the server's answer.
 *
 * Gate 2 -- there is a confirmed account for the money to land in -- is not.
 * No endpoint reports it. So the client hardcoded it shut, which made
 * publishing impossible, and then a button was added that opened it by being
 * tapped. A gate whose only control is a button that opens it is not a gate,
 * and worse, it put a claim on screen that nobody had checked.
 *
 * Both are gone. Gate 2 lives on the server, which decides it from its own
 * stored facts and refuses with a reason. The app asks and reports the answer
 * instead of holding an opinion it has no way to form.
 */
export type PublishGates = {
  payerAcknowledged: boolean;
};

export function canPublish(gates: PublishGates): boolean {
  return gates.payerAcknowledged;
}

export class GateNotPassedError extends Error {
  constructor(_gates: PublishGates) {
    super("Chưa phát được: người ứng tiền chưa xác nhận. Spec mục 8.3.");
    this.name = "GateNotPassedError";
  }
}

/**
 * What the server's refusals to open a round mean.
 *
 * Separate from `PUBLISH_REFUSALS` because they are different moments with
 * different things to do about them, and one table covering both would invite
 * a message that fits neither. Found by walking the app: pressing "Đúng rồi,
 * ghi vào sổ" put the words "Batch cannot be frozen" on screen -- the server's
 * own English, under a Vietnamese heading, with no hint of what to do.
 */
const CONFIRM_REFUSALS: Record<string, string> = {
  proposal_changed:
    "Khoản chi đã đổi kể từ lúc bạn nhìn. Quay lại xem con số mới trước khi ghi vào sổ.",
  expense_not_found: "Không tìm thấy khoản chi này trên máy chủ.",
};

export const OPEN_BATCH_REFUSALS: Record<string, string> = {
  unready_recipient_choice_required:
    "Người ứng tiền chưa có tài khoản nhận. Chưa biết chuyển tiền về đâu thì " +
    "chưa mở đợt thu được.",
  recipient_setup_incomplete:
    "Người ứng tiền chưa có tài khoản nhận đã được xác nhận.",
  no_obligations: "Khoản này không ai nợ ai. Không có gì để thu.",
};

/**
 * What the server's refusals to publish mean.
 *
 * The keys are the gate codes returned by `unmet_publish_gates()` in
 * `services/api/app/domain/collection.py`, plus the one code `publish_batch()`
 * raises before it reaches the gates. They are not a guess: `tests/
 * publish-refusals.test.mjs` parses those two Python functions and fails if a
 * key here is not a code publish can send, or a code publish can send has no
 * words here.
 *
 * That test exists because this table shipped wrong. It named codes that
 * appeared nowhere in `services/api/app`, so every gate fell through and put
 * "A publish gate is not satisfied" on screen next to somebody's name and
 * somebody's money. The old test was green throughout: it built its
 * expectations from this object's own keys.
 *
 * Still deliberately incomplete. A code nobody listed falls through to the
 * server's own detail rather than to a friendly sentence that might be wrong
 * about what just happened, and that fallthrough is the more important half.
 */
export const PUBLISH_REFUSALS: Record<string, string> = {
  advancer_acknowledgement_required:
    "Người ứng tiền chưa xác nhận. App không gửi gì dưới tên một người trước khi họ đồng ý.",
  // Unreachable from this app today, which is exactly why it is written down.
  // `sendPublish` hard-codes `delivery_method: "personal_link"`, so reaching
  // this line means the app stopped sending it, and a person should not have
  // to read the server's English to find that out.
  delivery_method_required:
    "Chưa chọn cách gửi phong bì cho đợt thu này, nên chưa phát được.",
  batch_not_found: "Không tìm thấy đợt thu này trên máy chủ.",
};

export type OpenedBatch = {
  batchId: string;
  obligations: Obligation[];
  gates: PublishGates;
};

/**
 * Open a collection round.
 *
 * The server used to refuse to freeze a batch when somebody who is owed money
 * had no bank account on file, and this function carried a parameter for the
 * organiser's answer to that. Both are gone with the payment rail: there are
 * no accounts, so there is no such refusal and nothing to choose.
 */
export async function openBatch(
  proposal: PendingProposal,
  expenseVersionId: string,
  acknowledged: boolean,
  attempt: Attempt,
  members: GroupMember[],
): Promise<OpenedBatch> {
  const nameOf = (id: string) => nameFrom(proposal.participants, members, id);

  const result = await translatedAsActor<{
    batch_id: string;
    obligations: {
      obligation_id: string;
      sender_id: string;
      recipient_id: string;
      amount_vnd: number;
    }[];
  }>(OPEN_BATCH_REFUSALS, "/batches", {
    body: {
      context_id: proposal.contextId,
      expense_version_ids: [expenseVersionId],
      // Counted from the attempt, so a retry asks for the same due date rather
      // than one seven days from whenever the connection came back.
      due_at: new Date(attempt.at + 7 * 24 * 60 * 60 * 1000).toISOString(),
    },
    actorId: proposal.advancerId,
    attempt,
    contexts: proposal.contextId,
  });

  return {
    batchId: result.batch_id,
    obligations: result.obligations.map((row) => ({
      id: row.obligation_id,
      senderId: row.sender_id,
      senderName: nameOf(row.sender_id),
      recipient: nameOf(row.recipient_id),
      amountVnd: row.amount_vnd,
      status: "outstanding" as const,
    })),
    // A real answer from the server, not a guess. Gate 2 is deliberately
    // absent from this type -- see PublishGates.
    gates: { payerAcknowledged: acknowledged },
  };
}

/**
 * Publish, and put people's names on what comes out.
 *
 * The roster is a parameter because the server answers in ids: `guest_links`
 * carries `sender_id` and nothing else about who that is. Without it the share
 * screen read "Gửi cho 6b4bda36-93e6-4a94-b7ca-48757974f36d", and the message
 * copied to the clipboard said "Phần của 6b4bda36-…" -- an organiser cannot
 * tell which link belongs to whom, which is the one job that screen has.
 *
 * The group membership is a second parameter for the same reason one screen up:
 * publish answers against the roster the SERVER holds, which regularly names
 * somebody who is in the group but not on the bill that was typed. Neither list
 * has a default, deliberately -- an empty one is not a degraded lookup, it is
 * every name on the screen turning into an id, and that is not a thing to let a
 * caller do by forgetting.
 */
export async function publishBatch(
  batchId: string,
  gates: PublishGates,
  actorId: string,
  attempt: Attempt,
  roster: Participant[],
  members: GroupMember[],
): Promise<Envelope[]> {
  // Checked here as well as by the disabled button. A disabled button is a
  // courtesy; this is what holds when the function is called directly.
  if (!canPublish(gates)) {
    throw new GateNotPassedError(gates);
  }
  // Gate 2 is the server's to enforce, so its refusal is the only true answer
  // about it.
  return sendPublish(batchId, actorId, attempt, roster, members);
}

/**
 * Run a call and put its known refusals into Vietnamese.
 *
 * The lookup is case-insensitive, and that is not tidiness. The server mixes
 * two conventions: codes raised by a domain transition arrive upper-cased
 * (`UNREADY_RECIPIENT_CHOICE_REQUIRED`), codes raised directly by the API
 * arrive lower-cased (`recipient_setup_incomplete`). A table written in one
 * casing silently misses half the refusals, and a miss looks exactly like a
 * code nobody thought about -- it falls through to the server's English.
 *
 * The code is preserved on the error. Only the sentence changes, so a bug
 * report still names what actually happened.
 *
 * Exported for the entry-door screens (`screens/vao-cua/`), which speak to
 * `/people`, `/contexts` and `/memberships` rather than to the expense path
 * this file grew around. They call this instead of writing a second `fetch`
 * wrapper, because the parts worth not duplicating are the ones that took
 * measurement to get right: the idempotency header, the status-to-sentence
 * table above, and `thongDiepNguoiDoc` -- a second copy of those would be a
 * second place for machine text to reach somebody's screen.
 */
export async function translatedAsActor<T>(
  table: Record<string, string>,
  path: string,
  options: ActorCallOptions,
): Promise<T> {
  return viDich(table, () => callAsActor<T>(path, options));
}

/**
 * `translatedAsActor` for the handful of routes that are anonymous on purpose.
 *
 * Split for the same reason `callAnonymous` is split from `callAsActor`: this
 * wrapper is the door most screens go through, so leaving it able to accept a
 * missing actor would have left the hole open in the place it is most used.
 */
export async function translatedAnonymous<T>(
  table: Record<string, string>,
  path: string,
  options: AnonymousCallOptions,
): Promise<T> {
  return viDich(table, () => callAnonymous<T>(path, options));
}

async function viDich<T>(
  table: Record<string, string>,
  run: () => Promise<T>,
): Promise<T> {
  try {
    return await run();
  } catch (problem) {
    if (problem instanceof ApiError) {
      const said = table[problem.code.toLowerCase()];
      if (said) throw new ApiError(problem.status, problem.code, said);
    }
    throw problem;
  }
}

/**
 * The one place a server-supplied id becomes a name a person reads.
 *
 * Both callers here answer routes the server resolves against ITS roster --
 * `POST /batches` and `POST /batches/{id}/publish` -- so the ids coming back
 * routinely name people who are legitimately absent from the bill somebody
 * typed. Looking only at the bill and ending `?? id` therefore printed a UUID
 * where a name goes, on the collection board, beside the QR code, on the share
 * row, and inside the message copied to the clipboard and sent to a real
 * person. That was bug-050923 again, one layer down from the three screens
 * already fixed for it.
 *
 * This used to be two private helpers with two different policies -- and the
 * older one carried an argument FOR printing the id: that a fallback word
 * would make two different people look like the same one. `labelInGroup`
 * answers that, because it widens to the group and numbers duplicates across
 * both lists before it gives up. Only somebody neither list can name reaches
 * the fallback, and a raw UUID does not tell two of those apart for a human
 * reader either -- it only looks as though it does.
 *
 * Both lists are typed as required, so app code cannot forget one. They are
 * still read defensively, because the callers are not all typed: the hero walk
 * and the QA scripts under `tests/qa/` are plain `.mjs` and call these routes
 * with the arguments they had when they were written. A missing list there
 * should narrow the lookup, not throw -- `labelInGroup` reads `.filter` off it,
 * and a TypeError raised from inside the money path is a worse failure than a
 * name that falls back to a word. Neither branch can return an id.
 */
function nameFrom(
  roster: Participant[],
  members: GroupMember[],
  id: string,
): string {
  return labelInGroup(
    { participants: roster ?? [], advancerId: null },
    members ?? [],
    id,
  );
}

async function sendPublish(
  batchId: string,
  actorId: string,
  attempt: Attempt,
  roster: Participant[],
  members: GroupMember[],
): Promise<Envelope[]> {
  const result = await translatedAsActor<{
    guest_links: {
      sender_id: string;
      path: string;
      // One link can cover several obligations -- one person can owe two
      // different people out of the same round. The link is per sender, not
      // per debt.
      obligations: {
        obligation_id: string;
        amount_vnd: number;
      }[];
    }[];
  }>(PUBLISH_REFUSALS, `/batches/${batchId}/publish`, {
    body: {
      delivery_method: "personal_link",
      // Also counted from the attempt. A retry that moved this would hand the
      // same guests links with a different lifetime depending on how long the
      // network was down.
      guest_link_expires_at: new Date(
        attempt.at + 14 * 24 * 60 * 60 * 1000,
      ).toISOString(),
    },
    actorId,
    attempt,
  });

  // `link.amount_vnd` was read here for a while. No such field is sent, so the
  // share screen printed "undefined đ" next to a real person's name -- and every
  // test passed, because none of them had ever published against a real server.
  return result.guest_links.map((link) => ({
    senderId: link.sender_id,
    senderName: nameFrom(roster, members, link.sender_id),
    amountVnd: link.obligations.reduce((sum, row) => sum + row.amount_vnd, 0),
    url: BASE_URL + link.path,
    opened: false,
    obligations: link.obligations.map((row) => ({
      obligationId: row.obligation_id,
      amountVnd: row.amount_vnd,
    })),
  }));
}

/** The collection board, including anything a guest has objected to. */
/**
 * Read the collection board.
 *
 * `contextId` leads, the way `docSoDu` and `taoBill` take it, because the
 * server's check on this route is fail-closed against `X-Actor-Contexts`:
 * `view_collection_board` compares the batch's own group against the header
 * and refuses when it is not there. It used to be satisfied by the synthetic
 * default in `actorHeaders`, which matched only because the batch had been
 * opened under the same synthetic id. With the group real on both sides, the
 * header has to name it.
 */
export async function loadBoard(
  contextId: string,
  batchId: string,
  actorId: string,
  roster: Participant[],
  members: GroupMember[],
): Promise<{ obligations: Obligation[]; disputedCount: number }> {
  const result = await callAsActor<{
    disputed_count: number;
    obligations: {
      obligation_id: string;
      sender_id: string;
      recipient_id: string;
      amount_vnd: number;
      obligation_status: Obligation["status"];
      disputed: boolean;
    }[];
  }>(`/batches/${batchId}/obligations`, { method: "GET", actorId, contexts: contextId });

  return {
    disputedCount: result.disputed_count,
    obligations: result.obligations.map((row) => ({
      id: row.obligation_id,
      senderId: row.sender_id,
      senderName: nameFrom(roster, members, row.sender_id),
      recipient: nameFrom(roster, members, row.recipient_id),
      amountVnd: row.amount_vnd,
      // Payment status and dispute are separate facts on the wire, and the
      // board has one slot. Showing "disputed" over "outstanding" is safe;
      // showing it over "confirmed" would hide money that arrived.
      status:
        row.disputed && row.obligation_status === "outstanding"
          ? "disputed"
          : row.obligation_status,
    })),
  };
}

/**
 * Record that the money arrived.
 *
 * Only the person owed it may say this, and saying it is not the same as a
 * bank telling anyone anything -- the product holds no money and sees no
 * statement. `receiver_confirmed` means one person pressed a button. The whole
 * design rests on that being visible rather than dressed up as settlement.
 *
 * The attempt's key goes out twice, and the two are not redundant. In the body
 * it is the route's own field, which stops a second confirmation from pushing
 * an obligation to `over_confirmed` -- a state that reads as somebody having
 * paid more than they owed. In the header it is what the middleware keys off,
 * so the retry gets the first reply replayed rather than re-running the
 * handler. Same value, because they are protecting the same press.
 */
export async function confirmReceipt(
  obligationId: string,
  amountVnd: number,
  actorId: string,
  attempt: Attempt,
): Promise<{ status: Obligation["status"] }> {
  const result = await callAsActor<{
    obligation_status: Obligation["status"];
  }>(`/obligations/${obligationId}/confirm-receipt`, {
    body: { amount_vnd: amountVnd, idempotency_key: attempt.key },
    actorId,
    attempt,
  });
  return { status: result.obligation_status };
}

/* ------------------------------------------------------- reading a bill */

/**
 * Send one bill photo to be read, and get back what the reader saw.
 *
 * `POST /receipts/scan` is multipart, not JSON, so it cannot go through
 * `call`. Three differences, each of which broke this once:
 *
 *  - **No `Content-Type` header.** `actorHeaders` sets `application/json`, and
 *    a multipart body sent under that header arrives as an unparseable blob.
 *    The boundary has to be chosen by whatever assembles the `FormData`, and
 *    setting the header by hand is what stops it being written.
 *  - **No `Idempotency-Key`.** Reading is not a write. Nothing is stored, no
 *    ledger row appears, and pressing the shutter twice is a person asking to
 *    be read twice -- replaying the first answer would hide a retry that was
 *    meant to fix a blurry frame.
 *  - **Two ways to put a file in a `FormData`.** On a phone, React Native
 *    accepts `{uri, name, type}` and streams the file itself. On the web the
 *    manipulator hands back a `blob:` url, and that object appends as the
 *    string "[object Object]" -- a 422 with no clue why. The web path has to
 *    fetch its own blob first.
 *
 * The photo is not logged, not cached and not kept. `withBillPhoto` in
 * `src/camera/` deletes the file once this resolves, including when it throws.
 */
export async function scanReceipt(
  photo: { uri: string; bytes: number },
  actorId: string,
): Promise<ReceiptScanWire> {
  const form = new FormData();
  await appendImageField(form, photo, "bill.jpg");

  const { "Content-Type": _dropped, ...headers } = actorHeaders(actorId);

  let response: Response;
  try {
    response = await fetch(BASE_URL + "/receipts/scan", { method: "POST", headers, body: form });
  } catch {
    throw new ApiError(
      0,
      "unreachable",
      `Không nối được ${BASE_URL}. Máy chủ có đang chạy không?`,
    );
  }

  if (!response.ok) {
    let code = `http_${response.status}`;
    let detail: unknown = null;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; there is nothing to read, so the status chooses the words */
    }
    throw new ApiError(
      response.status,
      code,
      SCAN_REFUSALS[code.toLowerCase()] ?? thongDiepNguoiDoc(response.status, detail),
    );
  }
  // A cast, not a parse, like every other route in this file -- and the one
  // place where that has already cost something. `ReceiptScanWire` once
  // declared a `confidence` the server had removed; the cast asserted it was
  // there, `undefined` came out, and a screen rendered a percent sign with
  // nothing in front of it. Nothing here can catch that, so the checking lives
  // one step down in `readingFromWire`, which treats anything other than an
  // explicit `false` for `needs_review` as "needs review".
  return (await response.json()) as ReceiptScanWire;
}

/**
 * What a refusal to read a bill means to the person holding the phone.
 *
 * The server's own sentences are already Vietnamese and already correct, so
 * these only replace the ones that describe the machine rather than the next
 * move. "Không đọc được bill" tells somebody nothing they cannot see; what
 * they need is which of the three fixable things to try.
 *
 * `receipt_reader_unavailable` is 502 and deliberately says nothing about the
 * upstream. The route is built so a credential or a quota error cannot reach
 * a screen, and repeating an upstream message here would undo that.
 */
const SCAN_REFUSALS: Record<string, string> = {
  receipt_unreadable:
    "Chưa đọc được bill này. Thường là do ảnh mờ, thiếu sáng, hoặc bill bị gập che mất cột tiền. " +
    "Chụp lại gần hơn một chút, để cả tờ bill nằm trong khung.",
  unsupported_image_type: "Tệp này không phải ảnh mà app đọc được. Chọn một ảnh JPG hoặc PNG.",
  image_too_large: "Ảnh nặng quá 8 MB nên máy chủ từ chối. Chụp lại bằng camera trong app để ảnh được nén sẵn.",
  receipt_reader_unavailable:
    "Bộ đọc bill đang không trả lời. Thử lại sau một chút, hoặc nhập tay các món ở bước sau.",
  permission_denied: "Tài khoản này chưa được phép đọc bill trong nhóm.",
};

/**
 * Put one image into a multipart field named `image`.
 *
 * Shared by `scanReceipt` and `quetAnhChupMan` so the blob:/data: branch
 * exists in one place. A third copy of `fetch(photo.uri)` would be a third
 * call site the API-contract reader cannot follow, and that pin is counted.
 */
async function appendImageField(
  form: FormData,
  photo: { uri: string },
  filename: string,
): Promise<void> {
  if (photo.uri.startsWith("blob:") || photo.uri.startsWith("data:")) {
    const blob = await fetch(photo.uri).then((r) => r.blob());
    form.append("image", blob, filename);
  } else {
    // React Native's own FormData understands this shape and nothing else.
    form.append("image", { uri: photo.uri, name: filename, type: "image/jpeg" } as never);
  }
}

/**
 * One model-read transaction from a screenshot. No line items, no people.
 *
 * `POST /screenshots/scan` is a read, same shape as `POST /receipts/scan`:
 * multipart field `image`, no `Content-Type` (the boundary must be chosen by
 * FormData), no `Idempotency-Key` (nothing is stored). The two ways to put a
 * file in FormData are the same two `scanReceipt` already has, and they live
 * in `appendImageField` so they cannot drift.
 */
export type ScreenshotScanWire = {
  source: "grab" | "shopeefood" | "banking" | "receipt";
  merchant: string;
  total_vnd: number;
  occurred_on: string | null;
  needs_review: boolean;
};

export async function quetAnhChupMan(
  photo: { uri: string; bytes: number },
  actorId: string,
): Promise<ScreenshotScanWire> {
  const form = new FormData();
  await appendImageField(form, photo, "anh.jpg");

  const { "Content-Type": _dropped, ...headers } = actorHeaders(actorId);

  let response: Response;
  try {
    response = await fetch(BASE_URL + "/screenshots/scan", { method: "POST", headers, body: form });
  } catch {
    throw new ApiError(
      0,
      "unreachable",
      `Không nối được ${BASE_URL}. Máy chủ có đang chạy không?`,
    );
  }

  if (!response.ok) {
    let code = `http_${response.status}`;
    let detail: unknown = null;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; there is nothing to read, so the status chooses the words */
    }
    throw new ApiError(
      response.status,
      code,
      SCREENSHOT_REFUSALS[code.toLowerCase()] ?? thongDiepNguoiDoc(response.status, detail),
    );
  }
  return (await response.json()) as ScreenshotScanWire;
}

/**
 * What a refusal to read a screenshot means to the person holding the phone.
 *
 * Same job as `SCAN_REFUSALS`: replace a machine code with the next move.
 * The server's own Vietnamese sentences win when they arrive; these cover
 * the codes that name the reader rather than the photo.
 */
const SCREENSHOT_REFUSALS: Record<string, string> = {
  screenshot_unreadable:
    "Không đọc được giao dịch từ ảnh chụp màn hình. Kiểm tra ảnh rồi thử lại.",
  not_a_transaction:
    "Ảnh này không thể hiện một giao dịch đã xong, nên chưa tạo được khoản chi từ đó.",
  screenshot_model_named_a_person:
    "Máy đọc đã nêu tên một người. Kết quả bị từ chối vì tên người chỉ đến từ phiên đăng nhập, không phải từ ảnh.",
  unsupported_image_type: "Tệp này không phải ảnh mà app đọc được. Chọn một ảnh JPG hoặc PNG.",
  image_too_large: "Ảnh chụp màn hình nặng quá 8 MB nên máy chủ từ chối. Chọn một ảnh nhẹ hơn.",
  screenshot_reader_unavailable:
    "Bộ đọc ảnh chụp màn hình đang không trả lời. Thử lại sau một chút.",
  screenshot_reader_not_configured:
    "Máy chủ chưa cấu hình khoá đọc ảnh chụp màn hình. Đây là lỗi phía máy chủ, không phải ảnh bạn chọn.",
};

/* --------------------------------------------- chat expense draft (F24) */

/**
 * A model-read draft from one chat message. Identities are roster ids only.
 *
 * `POST /contexts/{id}/messages/{id}/expense-draft` never creates or
 * allocates an expense. The screen that calls this must say so: a draft is
 * a reading, not a ledger row. `detected === (draft !== null)` is enforced
 * server-side; this type just carries what arrived.
 */
export type ChatExpenseDraftWire = {
  context_id: string;
  message_id: string;
  detected: boolean;
  draft: {
    title: string;
    amount_vnd: number;
    paid_by_id: string;
    shared_by: string[];
    needs_review: boolean;
  } | null;
  reason: string | null;
};

/**
 * Ask the reader what one message looks like as an expense.
 *
 * A POST that writes nothing, so no `Idempotency-Key`. Goes through `call`
 * like every other JSON route: actor headers, Vietnamese refusals, no
 * invented codes.
 */
export async function napNhapKhoanChiTuChat(
  contextId: string,
  messageId: string,
  actorId: string,
): Promise<ChatExpenseDraftWire> {
  return translatedAsActor<ChatExpenseDraftWire>(
    CHAT_EXPENSE_REFUSALS,
    `/contexts/${contextId}/messages/${messageId}/expense-draft`,
    { method: "POST", actorId, contexts: contextId },
  );
}

const CHAT_EXPENSE_REFUSALS: Record<string, string> = {
  chat_expense_model_named_a_person:
    "Máy đọc đã nêu tên người trả hoặc người chia. Bản nháp bị từ chối vì tên người chỉ được lấy từ danh sách nhóm, không phải từ tin nhắn.",
  chat_expense_unreadable:
    "Không đọc được khoản chi từ tin nhắn. Kiểm tra lại nội dung rồi thử lại.",
  chat_reader_unavailable:
    "Bộ đọc tin nhắn đang không trả lời. Thử lại sau một chút.",
  chat_reader_not_configured:
    "Máy chủ chưa cấu hình khoá đọc khoản chi từ tin nhắn. Đây là lỗi phía máy chủ, sửa tin nhắn không giúp được.",
};

/* --------------------------------------------- photographs people keep */

/**
 * One image on its way back from the server, after it has been sanitised.
 *
 * `byteSize`, `width` and `height` describe **the stored image, not the file
 * that was chosen**. The server decodes every upload, drops the metadata and
 * re-encodes, so these three routinely disagree with what the picker reported --
 * measured on the demo stack, an 861-byte primer came back 305 bytes. Comparing
 * them against a client-side size and complaining about the difference would be
 * reporting the feature working as a fault.
 *
 * `url` is a path on this API, never an absolute address, and that is what makes
 * it safe to hand to `image_url` on a memory or a message. See `nguon-anh.ts`.
 */
export type AnhDaTai = {
  id: string;
  url: string;
  contentType: string;
  byteSize: number;
  width: number;
  height: number;
};

/**
 * What a refusal to accept a photograph means to the person who chose it.
 *
 * Every sentence names the next move and none of them prints a status code. A
 * person who reads "413" has learned that something is wrong, which the screen
 * already told them, and nothing about what to do instead.
 *
 * `image_dimensions_too_large` is a separate refusal from `image_too_large` on
 * the server and gets separate words here, because the two have different
 * answers: a heavy file can be re-saved smaller, a 20000-px panorama cannot be
 * fixed by compressing it. Collapsing them into "ảnh quá lớn" would send half
 * the people who hit it to do something that cannot work.
 */
export const ANH_REFUSALS: Record<string, string> = {
  image_too_large:
    "Tấm ảnh này nặng quá 10 MB nên máy chủ không nhận. Chọn một tấm nhẹ hơn giúp mình.",
  image_dimensions_too_large:
    "Tấm ảnh này có kích thước quá lớn nên máy chủ không nhận. Chọn một tấm khác giúp mình.",
  not_an_image:
    "File bạn chọn không phải là ảnh nên máy chủ không đọc được. Chọn một tấm ảnh JPG hoặc PNG.",
  permission_denied:
    "Bạn cần là thành viên của nhóm này mới đăng ảnh lên tường được. Nhờ người tạo nhóm mời bạn vào rồi thử lại.",
  photo_not_found: "Không tìm thấy tấm ảnh này trên máy chủ.",
  avatar_not_found: "Người này chưa có ảnh đại diện nào.",
};

/**
 * Send one image, as multipart, and hand back where it now lives.
 *
 * Shared by the group wall and the avatar because the two differ only in their
 * path and in which header the server checks; everything that is easy to get
 * wrong is identical, and all four of those things have been got wrong here
 * before:
 *
 *  - **No `Content-Type` header.** `actorHeaders` sets `application/json`, and
 *    a multipart body under that header arrives as an unparseable blob. The
 *    boundary has to be chosen by whatever assembles the `FormData`, so the
 *    header must be *absent*, not merely different.
 *  - **The field is called `file`.** Not `image`, which is what
 *    `POST /receipts/scan` calls its own. A mismatch is a 422 that says nothing
 *    about field names.
 *  - **`X-Actor-Roles` is required.** Without `member` in it the server answers
 *    403 `role_not_permitted`, which reads exactly like "you are not in this
 *    group" and sends somebody to fix their membership instead of the header.
 *  - **Two ways to put a file in a `FormData`.** React Native accepts
 *    `{uri, name, type}` and streams the file. On the web the manipulator hands
 *    back a `blob:` url, and that object appends as the literal string
 *    "[object Object]".
 *
 * Deliberately does not go through `call`: that function sets a JSON
 * `Content-Type` and `JSON.stringify`s its body, both of which are wrong here.
 * It does not reuse `scanReceipt`'s copy of the same logic either. That one
 * sits on the bill path, which has been repaired twice in two days, and folding
 * a second caller into it now would put this feature's bugs and the hero flow's
 * bugs in one place. The duplication is named rather than hidden, and the day
 * the bill path is next opened is the day to merge them.
 *
 * No `Idempotency-Key`. The middleware fingerprints method + path + body, and a
 * body here is several megabytes of JPEG; the protection that matters for this
 * feature is the one on the write that *references* the photo, which is where
 * the key is sent. Uploading the same picture twice costs a stored blob nobody
 * points at, not a duplicated row on anybody's wall.
 */
async function guiAnhLen(
  path: string,
  photo: { uri: string },
  headers: Record<string, string>,
): Promise<AnhDaTai> {
  const form = new FormData();
  if (photo.uri.startsWith("blob:") || photo.uri.startsWith("data:")) {
    const blob = await fetch(photo.uri).then((r) => r.blob());
    form.append("file", blob, "anh.jpg");
  } else {
    // React Native's own FormData understands this shape and nothing else.
    form.append("file", { uri: photo.uri, name: "anh.jpg", type: "image/jpeg" } as never);
  }

  let response: Response;
  try {
    response = await fetch(BASE_URL + path, { method: "POST", headers, body: form });
  } catch {
    throw new ApiError(
      0,
      "unreachable",
      `Không nối được ${BASE_URL}. Máy chủ có đang chạy không?`,
    );
  }

  if (!response.ok) {
    let code = `http_${response.status}`;
    let detail: unknown = null;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; there is nothing to read, so the status chooses the words */
    }
    throw new ApiError(
      response.status,
      code,
      ANH_REFUSALS[code.toLowerCase()] ?? thongDiepNguoiDoc(response.status, detail),
    );
  }

  const wire = (await response.json()) as {
    id: string;
    url: string;
    content_type: string;
    byte_size: number;
    width: number;
    height: number;
  };
  return {
    id: wire.id,
    url: wire.url,
    contentType: wire.content_type,
    byteSize: wire.byte_size,
    width: wire.width,
    height: wire.height,
  };
}

/** Put a photograph into one group's private storage. Members only, server-side. */
export async function taiAnhNhom(
  contextId: string,
  photo: { uri: string },
  actorId: string,
): Promise<AnhDaTai> {
  const { "Content-Type": _dropped, ...headers } = actorHeaders(actorId, "member", contextId);
  return guiAnhLen(`/contexts/${contextId}/photos`, photo, headers);
}

/**
 * Set this person's avatar. Only ever your own -- the server checks `is_self`.
 *
 * The address it answers with is `/people/{id}/avatar`, which is stable: it does
 * not change when a new picture is uploaded, and it is the same address every
 * other screen already builds from a person id. So nothing has to be stored,
 * threaded through a roster, or added to a profile response for a new avatar to
 * appear -- the frames pointing at it simply start resolving.
 *
 * `contexts` is deliberately left at the default. This route is about a person,
 * not a group, and the server's permission check for it never reads the header.
 */
export async function taiAnhDaiDien(
  personId: string,
  photo: { uri: string },
  actorId: string,
): Promise<AnhDaTai> {
  const { "Content-Type": _dropped, ...headers } = actorHeaders(actorId, "member");
  return guiAnhLen(`/people/${personId}/avatar`, photo, headers);
}

/** Where a person's avatar lives, whether or not one has been uploaded.
 *
 * Always the same string for the same person. A 404 is the ordinary answer for
 * "no picture yet", and `Anh` already draws the caller's stand-in for a frame
 * whose load failed, so no screen needs to ask first.
 */
export function duongDanAnhDaiDien(personId: string): string {
  return `/people/${personId}/avatar`;
}

/**
 * Fetch a photograph the server permission-checks, and hand back an address a
 * frame can actually display.
 *
 * ## Why a frame cannot simply be pointed at the address
 *
 * Every image route this product has is permission-checked, and the check reads
 * a header:
 *
 *     GET /people/{id}/avatar          without X-Actor-ID -> 401
 *     GET /contexts/{cid}/photos/{pid} without X-Actor-ID -> 401
 *
 * An `<img>` cannot send a header, and react-native-web's `<Image>` becomes an
 * `<img>`. So `<Image source={{uri: "/people/x/avatar"}}>` is not "the read path
 * wired up" -- it is a request that is *guaranteed* to be refused. Worse, the
 * refusal is silent: `Anh` reacts to a failed load by drawing its stand-in, and
 * the stand-in for an avatar is the person's initials, which is exactly what a
 * person with no photograph yet also sees. Upload returns 201, the picture
 * never appears, and every surface agrees that nothing is wrong. That is what
 * shipped in rd-fe-25 and what #222 was sent back for.
 *
 * React Native's own `Image` does accept `source={{uri, headers}}`, so a native
 * build could pass the header through. react-native-web ignores it. Fetching
 * the bytes here instead is one path that works on both, and it keeps the rule
 * in one place rather than leaving web quietly broken.
 *
 * ## What comes back
 *
 * A `blob:` URL where the platform has one, a `data:` URL where it does not.
 * Both are local, so the frame that displays it makes no second request and
 * carries no header of its own. Hand the result to `boNguonCucBo` when the
 * frame is done with it; a `blob:` URL pins its bytes in memory until revoked.
 *
 * `contexts` matters for the group wall and not for an avatar: the photo route
 * checks membership of the context in the address, and the avatar route checks
 * whether the two people share one. Passing it wrong is a 403, not a leak --
 * the server decides either way.
 */
export async function taiAnhCoQuyen(
  url: string,
  actorId: string,
  contexts?: string,
): Promise<string> {
  // Same reason as `guiAnhLen`: `actorHeaders` sets `application/json`, which is
  // a lie about a request that wants image bytes back.
  const { "Content-Type": _dropped, ...headers } = actorHeaders(actorId, "member", contexts);

  let response: Response;
  try {
    response = await fetch(url, { headers });
  } catch {
    throw new ApiError(
      0,
      "unreachable",
      `Không nối được ${BASE_URL}. Máy chủ có đang chạy không?`,
    );
  }

  if (!response.ok) {
    let code = `http_${response.status}`;
    let detail: unknown = null;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; the status chooses the words */
    }
    throw new ApiError(
      response.status,
      code,
      ANH_REFUSALS[code.toLowerCase()] ?? thongDiepNguoiDoc(response.status, detail),
    );
  }

  return nguonCucBo(await response.blob());
}

/** Turn fetched bytes into something `<Image>` accepts, on either platform.
 *
 *  `URL.createObjectURL` is the cheap answer and exists on web. React Native
 *  has `Blob` but not reliably that method, so the fallback reads the bytes
 *  into a `data:` URL, which every `Image` implementation understands. Base64
 *  costs a third more memory, which is the right trade for a picture the server
 *  has already re-encoded and capped. */
function nguonCucBo(blob: Blob): Promise<string> {
  const url = (globalThis as { URL?: { createObjectURL?: (b: Blob) => string } }).URL;
  if (typeof url?.createObjectURL === "function") {
    return Promise.resolve(url.createObjectURL(blob));
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(new ApiError(0, "image_unreadable", "Không đọc được tấm ảnh vừa tải về."));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(blob);
  });
}

/** Release what `taiAnhCoQuyen` handed out. A no-op for `data:`, which owns no
 *  resource; a `blob:` URL holds its bytes alive until this is called. */
export function boNguonCucBo(uri: string): void {
  if (!uri.startsWith("blob:")) return;
  const url = (globalThis as { URL?: { revokeObjectURL?: (u: string) => void } }).URL;
  url?.revokeObjectURL?.(uri);
}

/* --------------------------------------------------- the memory wall (rd-be-07) */

/** One keepsake on the wall, as the server describes it.
 *
 * The last three fields are optional, and their optionality is load-bearing
 * rather than defensive typing. They arrive from a server that has the hearts
 * and comments tables; a server that does not have them omits all three. So
 * their presence IS the capability check, and the wall reads it that way: no
 * fields, no heart button drawn at all.
 *
 * The alternative -- draw the button always and let it 404 -- is the shape this
 * screen's own docblock argues against. A heart that fails on press says "your
 * tap did not register", which is a lie about a feature that was never built.
 *
 * `viewer_has_reacted` is computed for the actor making the request. There is
 * no `viewer_id` query parameter to pass and none should be invented: one would
 * let a caller ask whether somebody ELSE had reacted.
 */
export type KyNiemWire = {
  id: string;
  author_id: string;
  kind: "photo" | "checkin";
  image_url: string | null;
  caption: string | null;
  place_name: string | null;
  created_at: string;
  reaction_count?: number;
  comment_count?: number;
  viewer_has_reacted?: boolean;
};

/** True when the server that answered this feed can hold hearts and comments.
 *
 * Keyed on `reaction_count` rather than on truthiness of the whole row: a photo
 * with zero hearts sends `0`, which is falsy, and a check written as
 * `if (m.reaction_count)` would hide the buttons on exactly the photographs
 * that have not been reacted to yet -- that is, on all of them, on day one. */
export function coTuongTac(kyNiem: KyNiemWire): boolean {
  return typeof kyNiem.reaction_count === "number";
}

/**
 * Hang a photograph on the group's wall.
 *
 * `imageUrl` must be the `url` a previous `taiAnhNhom` handed back, and the
 * group in it must be the group being written to. The server enforces both --
 * the schema pins the shape and the service re-parses it rather than trusting
 * the schema -- so an address pointing anywhere else is a 422 rather than a row.
 * That is the first of the two layers; `nguonAnhAnToan` in `ui/nguon-anh.ts` is
 * the second, and it runs on the way back out because a row written before the
 * server's check existed is still in the database.
 *
 * The attempt is keyed on the photo by the caller, so a second press while the
 * first is still in flight replays the first answer instead of hanging the same
 * picture on the wall twice.
 */
export async function themKyNiemAnh(
  contextId: string,
  imageUrl: string,
  caption: string | null,
  actorId: string,
  attempt: Attempt,
): Promise<KyNiemWire> {
  return translatedAsActor<KyNiemWire>(ANH_REFUSALS, `/contexts/${contextId}/memories`, {
    method: "POST",
    body: { image_url: imageUrl, caption: caption?.trim() ? caption.trim() : null },
    actorId,
    attempt,
    roles: "member",
    contexts: contextId,
  });
}

/** Read the wall. Group-private: a non-member gets 403 whatever the header says. */
export async function docKyNiem(
  contextId: string,
  actorId: string,
  limit = 24,
): Promise<KyNiemWire[]> {
  const result = await translatedAsActor<{ memories: KyNiemWire[] }>(
    ANH_REFUSALS,
    `/contexts/${contextId}/memories?limit=${limit}&kind=photo`,
    { method: "GET", actorId, roles: "member", contexts: contextId },
  );
  return result.memories ?? [];
}

/* ------------------------------------------- F38, the home widget (rd-fe-38) */

/** The one photograph a widget draws, as `WidgetPhotoResponse` sends it.
 *
 * Deliberately not a `KyNiemWire`. The server made the same choice on its side
 * and said why: a widget renders outside the app, next to a lock screen, and
 * the wall's row carries a cursor, two social counters, `viewer_has_reacted`
 * and four location columns -- four more group-private fields on a surface
 * somebody else can read over your shoulder. Mirroring the narrower shape here
 * means a screen that accidentally reaches for `place_name` does not compile
 * rather than rendering a blank.
 *
 * `author_name` arrives already resolved, for the same reason the comment feed
 * resolves `display_name`: a second lookup keyed on `author_id` is a second
 * answer to "who posted this", and the two disagree the moment somebody renames
 * themselves between the two calls.
 */
export type AnhWidgetWire = {
  memory_id: string;
  /** The relative `/contexts/{id}/photos/{id}` address the wall stores. It is
   *  permission-checked, so it goes through `Anh` with a `nguoiXem`, never
   *  straight into an `<Image>`. */
  image_url: string;
  caption: string | null;
  author_id: string;
  author_name: string;
  created_at: string;
};

/** What one group's widget shows right now, or that it shows nothing.
 *
 * `photo: null` is a 200 and a real state, not a failure: a group that has not
 * hung a photograph yet has answered the question honestly. The server refuses
 * to spell that as a 404 on purpose -- a second status code separating "empty"
 * from "forbidden" is exactly the difference a stranger is fishing for -- and
 * this client must not reintroduce the distinction by treating an empty body
 * as an error. */
export type WidgetWire = {
  context_id: string;
  photo: AnhWidgetWire | null;
};

/**
 * F38. Read the newest photograph of one group.
 *
 * No body and no query string, because the route has neither. There is
 * therefore no field in which this client could name a person, a row, or a
 * group other than the one in the path -- the actor is the header, the group is
 * the address. Adding one would be inventing a request shape the server never
 * agreed to.
 *
 * Group-private: a non-member gets 403 whatever the roles header claims, since
 * the service asks the roster rather than believing `X-Actor-Contexts`.
 */
export async function docWidget(
  contextId: string,
  actorId: string,
): Promise<WidgetWire> {
  return translatedAsActor<WidgetWire>(ANH_REFUSALS, `/contexts/${contextId}/widget`, {
    method: "GET",
    actorId,
    roles: "member",
    contexts: contextId,
  });
}

/* ------------------------------- hearts and comments on the wall (rd-fe-33) */

/**
 * One comment under one photograph, as the server describes it.
 *
 * `display_name` arrives already resolved. The wall does not hold a roster and
 * must not go and build one: a second lookup keyed on `author_id` is a second
 * answer to "who wrote this", and the two disagree the moment somebody renames
 * themselves between the two calls.
 */
export type BinhLuanWire = {
  id: string;
  memory_id: string;
  author_id: string;
  display_name: string;
  body: string;
  created_at: string;
};

/** Longest body the server will take. Mirrored here so the composer can refuse
 *  before the round trip; the server is still the one that decides. */
export const BINH_LUAN_TOI_DA = 2000;

/**
 * What the wall says when a heart or a comment is refused.
 *
 * `is_group_member` is the one worth reading twice. A 403 here does NOT mean
 * "something went wrong" -- it means the person has been removed from the group
 * since the wall was drawn, and the sentence has to say that rather than offer
 * a retry that cannot work.
 *
 * `already_reacted` and `reaction_not_found` are both states the button should
 * never reach, because it knows `viewer_has_reacted` before it presses. They
 * are here because "should never" means "will, when two devices press at once",
 * and the honest answer then is that the wall is out of date, not that the
 * person did something wrong.
 */
export const XA_HOI_REFUSALS: Record<string, string> = {
  is_group_member:
    "Bạn không còn trong nhóm này nên không thả tim hay bình luận được nữa.",
  memory_not_found: "Ảnh này vừa được gỡ khỏi tường nhóm nên không còn để thả tim.",
  already_reacted: "Bạn đã thả tim cho ảnh này rồi. Kéo xuống để xem lại tường nhóm.",
  reaction_not_found: "Tim của bạn ở ảnh này đã được gỡ trước đó rồi.",
};

/**
 * Drop a heart on one photograph. The person doing it is the actor header, so
 * there is no body: there is no field in which to claim to be somebody else.
 *
 * Pressing twice is a 409, not a silent toggle. The button decides between this
 * and `boTim` from `viewer_has_reacted`, which the feed sends for the caller --
 * so reaching 409 means the wall on screen is older than the database, and the
 * sentence above says exactly that.
 */
export async function thaTim(
  contextId: string,
  memoryId: string,
  actorId: string,
): Promise<void> {
  await translatedAsActor<void>(
    XA_HOI_REFUSALS,
    `/contexts/${contextId}/memories/${memoryId}/reactions`,
    { method: "POST", actorId, roles: "member", contexts: contextId },
  );
}

/** Take back your own heart. There is no route for taking back anybody else's,
 *  which is why this too carries no body. Answers 204. */
export async function boTim(
  contextId: string,
  memoryId: string,
  actorId: string,
): Promise<void> {
  await translatedAsActor<void>(
    XA_HOI_REFUSALS,
    `/contexts/${contextId}/memories/${memoryId}/reactions`,
    { method: "DELETE", actorId, roles: "member", contexts: contextId },
  );
}

/** Read one photograph's comments. Group-private, like everything on this wall. */
export async function docBinhLuan(
  contextId: string,
  memoryId: string,
  actorId: string,
): Promise<BinhLuanWire[]> {
  const result = await translatedAsActor<{ comments: BinhLuanWire[] }>(
    XA_HOI_REFUSALS,
    `/contexts/${contextId}/memories/${memoryId}/comments`,
    { method: "GET", actorId, roles: "member", contexts: contextId },
  );
  return result.comments ?? [];
}

/**
 * Say something under a photograph.
 *
 * The body is the only field: authorship comes from the header, so this cannot
 * post in somebody else's name even by accident. Keyed on the memory and the
 * text so that a second press while the first is still in flight replays the
 * first answer instead of leaving the same sentence on the wall twice -- the
 * same trick `themKyNiemAnh` uses, for the same reason.
 */
export async function guiBinhLuan(
  contextId: string,
  memoryId: string,
  body: string,
  actorId: string,
  attempt: Attempt,
): Promise<BinhLuanWire> {
  return translatedAsActor<BinhLuanWire>(
    XA_HOI_REFUSALS,
    `/contexts/${contextId}/memories/${memoryId}/comments`,
    {
      method: "POST",
      body: { body },
      actorId,
      attempt,
      roles: "member",
      contexts: contextId,
    },
  );
}

/* ------------------------------------------------------- outings (F13/F15) */

export type { BodyTaoBuoiDi, BuoiDi, ChangGui, CheckIn };

/**
 * Create an outing in a real group.
 *
 * The group is a parameter, not a constant: callers pass the id
 * `khoiDongNhom` actually returned. This file used to hold a synthetic
 * `CONTEXT_ID` with no row in `contexts`, and posting under it was a 403.
 */
export async function taoBuoiDi(
  contextId: string,
  body: BodyTaoBuoiDi,
  actorId: string,
  attempt: Attempt,
): Promise<BuoiDi> {
  return callAsActor<BuoiDi>(`/contexts/${contextId}/outings`, {
    method: "POST",
    body,
    actorId,
    attempt,
    contexts: contextId,
  });
}

/**
 * Accept an outing invite by token.
 *
 * A write: the server mints a membership, so this carries `Idempotency-Key`
 * like every other write. The reply names ids and `membership_state` only.
 * It does not carry the group name or the trip name -- a link redeemer is
 * not a member yet, and the screen must not invent either name.
 */
export type OutingInviteAcceptWire = {
  invite_id: string;
  outing_id: string;
  context_id: string;
  membership_id: string;
  membership_state: "invited" | "active";
};

export async function nhanLoiMoiBuoiDi(
  token: string,
  actorId: string,
  attempt: Attempt,
): Promise<OutingInviteAcceptWire> {
  return callAsActor<OutingInviteAcceptWire>(`/outing-invites/${token}/accept`, {
    method: "POST",
    actorId,
    attempt,
  });
}

/** List the group's outings. Membership is a query, not the actor header. */
export async function docDanhSachBuoiDi(
  contextId: string,
  actorId: string,
): Promise<{ context_id: string; outings: BuoiDi[] }> {
  return callAsActor<{ context_id: string; outings: BuoiDi[] }>(
    `/contexts/${contextId}/outings`,
    { method: "GET", actorId, contexts: contextId },
  );
}

/**
 * Replace the timeline. Sorted here, not by the server: the server stores
 * the array it was given, in that order, so position only matches clock
 * time if we sort first.
 */
export async function luuDongThoiGian(
  outingId: string,
  stops: ChangGui[],
  actorId: string,
  attempt: Attempt,
  contextId: string,
): Promise<BuoiDi> {
  return callAsActor<BuoiDi>(`/outings/${outingId}/timeline`, {
    method: "PUT",
    body: {
      stops: sapXepChang(stops).map((stop) => ({
        at: stop.at,
        label: stop.label,
        place_name: stop.place_name,
        place_id: stop.place_id ?? null,
      })),
    },
    actorId,
    attempt,
    contexts: contextId,
  });
}

/**
 * F46. Say the actor reached this stop.
 *
 * Deliberately sends NO body. The server already knows who is asking and what
 * time it is, and those are the only two facts a check-in records. A body
 * would be somewhere for a coordinate to arrive, and a coordinate attached to
 * a person is a movement record the whole group can read -- reading the
 * phone's GPS is F47 and is not built.
 *
 * A second press comes back 409 `already_checked_in`; the unique index in the
 * database is what refuses it, not a check on this side.
 */
export async function checkInChang(
  stopId: string,
  actorId: string,
  attempt: Attempt,
  contextId: string,
): Promise<CheckIn> {
  return callAsActor<CheckIn>(`/outing-stops/${stopId}/checkins`, {
    method: "POST",
    actorId,
    attempt,
    contexts: contextId,
  });
}

/** Who has arrived where, for one outing. Members only, enforced server-side. */
export async function docCheckIn(
  outingId: string,
  actorId: string,
  contextId: string,
): Promise<{ outing_id: string; checkins: CheckIn[] }> {
  return callAsActor<{ outing_id: string; checkins: CheckIn[] }>(
    `/outings/${outingId}/checkins`,
    { method: "GET", actorId, contexts: contextId },
  );
}

/* --------------------------------------------------- a bill that persists */

/**
 * Store the reading as a bill, and get back the server's view of it.
 *
 * The write that was missing. Everything downstream of the matrix -- reopening
 * a bill, seeing which lines are still the machine's guess, asking the group
 * for balances -- needs the bill to have an id, and until this call existed it
 * never got one: the matrix lived in React state and died with the screen.
 *
 * `attempt` matters more here than on a read. Two presses of "Tiếp tục" on a
 * slow connection are one person asking once, and without the header each
 * press leaves its own bill row -- two bills for one dinner, each holding half
 * the group's ticks.
 */
export async function taoBill(
  reading: BillReading,
  contextId: string,
  assignment: Assignment,
  actorId: string,
  attempt: Attempt,
): Promise<BillWire> {
  return callAsActor<BillWire>("/bills", {
    body: billCreateBody(reading, contextId, assignment),
    actorId,
    attempt,
    contexts: contextId,
  });
}

/** Reopen a stored bill. Members of its group only, enforced server-side. */
export async function docBill(
  billId: string,
  actorId: string,
  contextId: string,
): Promise<BillWire> {
  return callAsActor<BillWire>(`/bills/${billId}`, {
    method: "GET",
    actorId,
    contexts: contextId,
  });
}

/**
 * Turn this group's ticks into decisions.
 *
 * The response is the bill re-read, not an acknowledgement, and the caller is
 * meant to replace its state with it. That is what moves `assignment_state`
 * off `ai_suggested` and empties `suggested_item_keys`: the screen stops
 * describing the matrix as a guess because the server has stopped calling it
 * one, rather than because the app decided locally that it had saved.
 */
export async function luuGanMon(
  billId: string,
  reading: BillReading,
  assignment: Assignment,
  actorId: string,
  contextId: string,
  attempt: Attempt,
): Promise<BillWire> {
  return callAsActor<BillWire>(`/bills/${billId}/assignments`, {
    method: "PUT",
    body: assignmentsBody(reading, assignment),
    actorId,
    attempt,
    contexts: contextId,
  });
}

/** What the server makes of a STORED bill's ticks. */
export type ChiaBill = {
  /** Person id -> đồng. Integer đồng throughout; the server sends integers and
   *  nothing on this side divides. */
  allocations: Record<string, number>;
  /** Person id -> the exact rational share, as the server printed it. Carried
   *  because it is the working behind a dong that looks one off. */
  exactShares: Record<string, string>;
  roundingGainers: string[];
  warnings: string[];
  /** Whether the ticks this split was computed from are a decision or still the
   *  reader's guess. The screen says which; it does not decide. */
  assignmentState: "confirmed" | "ai_suggested";
  suggestedItemKeys: string[];
  totalAmountVnd: number;
};

/** The wire shape of `POST /bills/{id}/split`, snake_case as the server sends it.
 *
 * Named rather than written inline at the call site, and it has to stay named.
 * `scripts/check_actor_headers.py` finds a `call<T>(...)` by matching the type
 * argument with `<[^<>()]*>`, which cannot span the nested `<>` of a
 * `Record<string, number>`. Inline, the whole call went unseen, the gate read
 * "no arguments" as "no actor passed", and it failed this function for an
 * omission that is not there -- the headers below have always been sent.
 */
type ChiaBillWire = {
  allocation: {
    allocations: Record<string, number>;
    exact_shares: Record<string, string>;
    rounding_gainers: string[];
    warnings: string[];
  };
  assignment_state: "confirmed" | "ai_suggested";
  suggested_item_keys: string[];
  total_amount_vnd: number;
};

/**
 * Ask the server to split a bill it already stored.
 *
 * Not `previewSplit`. That one posts a fresh `POST /expenses` built from the
 * matrix this phone is holding, which is the right call while somebody is still
 * ticking boxes. This one names a bill id and nothing else: the server reads the
 * shares IT has, against the roster IT has, and answers. So it is the only way
 * to ask "what does the server think this bill costs each of us" -- and the only
 * way for the two to be caught disagreeing.
 *
 * The body carries no identity. `BillSplitRequest` has a `paid_by_id`, which is
 * for writing the split into the ledger; a preview does not need one and does
 * not send one, so there is no field here in which a caller could name somebody
 * else. `for_ledger` stays at its `false` default for the same reason: this call
 * must not write.
 *
 * Nothing is computed on this side. Every dong shown from this response is a
 * dong the allocator produced -- two divisions in one product is how one dinner
 * shows two numbers.
 */
export async function docChiaBill(
  billId: string,
  actorId: string,
  contextId: string,
  attempt: Attempt,
): Promise<ChiaBill> {
  const result = await callAsActor<ChiaBillWire>(`/bills/${billId}/split`, {
    method: "POST",
    // Empty on purpose -- see above. `for_ledger` defaults false server-side.
    body: {},
    actorId,
    attempt,
    contexts: contextId,
  });
  return {
    allocations: result.allocation.allocations,
    exactShares: result.allocation.exact_shares,
    roundingGainers: result.allocation.rounding_gainers,
    warnings: result.allocation.warnings ?? [],
    assignmentState: result.assignment_state,
    suggestedItemKeys: result.suggested_item_keys,
    totalAmountVnd: result.total_amount_vnd,
  };
}

/**
 * Who owes whom across this group, net of everything in the ledger.
 *
 * Not this bill's split. This is the group's whole position, which is the
 * question a person actually has after a dinner -- one bill's numbers are
 * already on the screen they just left. `transfers` are proposals needing
 * consent, never obligations; `proven_minimal` says whether the server proved
 * the list is the shortest, and is passed through rather than assumed.
 */
export async function docSoDu(
  contextId: string,
  actorId: string,
): Promise<SoDu> {
  const wire = await callAsActor<SoDuWire>(`/contexts/${contextId}/balances`, {
    method: "GET",
    actorId,
    contexts: contextId,
  });
  return soDuFromWire(wire);
}

/* --------------------------------------------------- posts (F39) and audiences (F42) */

/**
 * One of the four words a post can be addressed to.
 *
 * A vocabulary, not a ladder: `friends` and `group` reach two disjoint sets of
 * people, and neither contains the other. Nothing in this file compares two
 * of these by position.
 */
export type PostAudience = "only_me" | "friends" | "group" | "public";

/** One post, as a reader who is allowed to have it receives it. */
export type PostWire = {
  id: string;
  author_id: string;
  audience: PostAudience;
  context_id: string | null;
  body: string;
  image_url: string | null;
  created_at: string;
};

/**
 * What a refusal to write or read a post means to the person holding the phone.
 *
 * The server's own detail for these codes is English (`Post visibility must
 * be one of the four known levels`). That sentence names the enum, not the
 * next move, so it is replaced here rather than passed through.
 */
const BAI_REFUSALS: Record<string, string> = {
  unknown_audience:
    "Mức người đọc này app không gửi được. Chọn lại một trong bốn lựa chọn trên màn.",
  group_audience_needs_context:
    "Chọn nhóm đã, rồi mới đăng được bài cho nhóm đó.",
  context_not_addressable:
    "Chỉ bài cho một nhóm mới được gắn nhóm. Chọn lại mức người đọc.",
  post_not_found:
    "Bài này không còn hoặc không phải dành cho bạn.",
  permission_denied:
    "Tài khoản đang dùng chưa được phép đăng bài này.",
};

export type BodyDangBai = {
  body: string;
  audience: PostAudience;
  contextId?: string | null;
  imageUrl?: string | null;
};

/**
 * Build the POST /posts body. `author_id` is absent on purpose: the writer is
 * the actor header. `context_id` is present only for `group`.
 */
export function thanDangBaiApi(input: BodyDangBai): {
  body: string;
  audience: PostAudience;
  context_id?: string;
  image_url?: string;
} {
  const than: {
    body: string;
    audience: PostAudience;
    context_id?: string;
    image_url?: string;
  } = { body: input.body, audience: input.audience };
  if (input.audience === "group" && input.contextId) {
    than.context_id = input.contextId;
  }
  if (input.imageUrl) than.image_url = input.imageUrl;
  return than;
}

/**
 * F39. Say something, as yourself, to one of F42's four audiences.
 *
 * A write, so it carries `Idempotency-Key`. There is no `author_id` in the
 * body and no recipient list -- both absences are the feature, not omissions.
 */
export async function dangBai(
  input: BodyDangBai,
  actorId: string,
  attempt: Attempt,
): Promise<PostWire> {
  return translatedAsActor<PostWire>(BAI_REFUSALS, "/posts", {
    method: "POST",
    body: thanDangBaiApi(input),
    actorId,
    attempt,
  });
}

/** Everything this actor may read, newest first. The reader is the actor. */
export async function docBangTin(actorId: string, limit = 50): Promise<PostWire[]> {
  const result = await translatedAsActor<{ posts: PostWire[] }>(
    BAI_REFUSALS,
    `/posts?limit=${limit}`,
    { method: "GET", actorId },
  );
  return result.posts ?? [];
}

/** One post, or 404 -- including when it exists and is not for you. */
export async function docBai(postId: string, actorId: string): Promise<PostWire> {
  return translatedAsActor<PostWire>(BAI_REFUSALS, `/posts/${postId}`, {
    method: "GET",
    actorId,
  });
}

/** One person's wall, already narrowed to what this caller may see. */
export async function docTuongNguoi(
  personId: string,
  actorId: string,
  limit = 50,
): Promise<PostWire[]> {
  const result = await translatedAsActor<{ person_id: string; posts: PostWire[] }>(
    BAI_REFUSALS,
    `/people/${personId}/posts?limit=${limit}`,
    { method: "GET", actorId },
  );
  return result.posts ?? [];
}

/* ------------------------------------------- group voting, F17 (rd-fe-17) */

/**
 * One choice on the ballot, as the server counts it.
 *
 * `ballot_count` arrives already tallied. The app must not recount it from
 * anything else it holds: `src/screens/chat/binh-chon.ts` folds ballots out of
 * chat messages for the older message-backed card, and two live vote counters
 * in one product is the same class of failure as two splitters. These types
 * are the server's answer, and nothing here derives a second one.
 */
export type LuaChonWire = {
  id: string;
  position: number;
  label: string;
  place_name: string | null;
  ballot_count: number;
};

/**
 * One vote, with the result already decided by the domain.
 *
 * Four fields carry the outcome and none of them is computed here:
 *
 *  - `leading_option_ids` is every option level at the top. It has more than
 *    one entry exactly when the vote is tied.
 *  - `is_tie` says so directly, so no screen has to infer a tie from a list
 *    length and get it wrong on the empty-vote case.
 *  - `decided_option_id` is null while it is tied and while it is open. A
 *    screen that wants "the winner" must read this and accept null, never
 *    fall back to `leading_option_ids[0]` -- picking the first of a tie is
 *    choosing a side the group did not choose.
 *  - `my_option_id` is the caller's own ballot, resolved from the actor
 *    header. There is no request field that could name anybody else.
 */
export type CuocBinhChonWire = {
  id: string;
  context_id: string;
  outing_id: string | null;
  created_by_id: string;
  question: string;
  created_at: string;
  closed_at: string | null;
  is_closed: boolean;
  options: LuaChonWire[];
  total_ballots: number;
  leading_option_ids: string[];
  is_tie: boolean;
  decided_option_id: string | null;
  my_option_id: string | null;
};

/** The receipt for one ballot. `replaced_previous_ballot` is how the screen
 *  knows to say "đã đổi phiếu" rather than "đã bỏ phiếu". */
export type PhieuDaBoWire = {
  vote_id: string;
  option_id: string;
  voter_id: string;
  created_at: string;
  updated_at: string;
  replaced_previous_ballot: boolean;
};

/**
 * What a refused ballot means to the person holding the phone.
 *
 * `vote_closed` is the one worth having words for: it is not an error the
 * person can fix, it is news. Somebody closed the vote between the screen
 * loading and the tap landing, and the answer is to re-read the result, not
 * to try again.
 */
const BINH_CHON_REFUSALS: Record<string, string> = {
  vote_closed:
    "Cuộc bình chọn này đã đóng nên không đổi phiếu được nữa. Kéo xuống để xem kết quả.",
  vote_already_closed:
    "Cuộc bình chọn này đã đóng nên không đổi phiếu được nữa. Kéo xuống để xem kết quả.",
  option_not_found:
    "Lựa chọn này không còn trong cuộc bình chọn. Tải lại rồi chọn lại giúp mình.",
  permission_denied:
    "Bạn không ở trong nhóm này nên không xem được cuộc bình chọn.",
  not_vote_creator:
    "Chỉ người mở cuộc bình chọn mới đóng được nó.",
};

/** Every vote in one group, newest handling left to the server's order. */
export async function docDanhSachBinhChon(
  contextId: string,
  actorId: string,
): Promise<CuocBinhChonWire[]> {
  const result = await translatedAsActor<{ context_id: string; votes: CuocBinhChonWire[] }>(
    BINH_CHON_REFUSALS,
    `/contexts/${contextId}/votes`,
    { method: "GET", actorId, roles: "member", contexts: contextId },
  );
  return result.votes ?? [];
}

/** One vote and its current tally. Members only, enforced server-side. */
export async function docBinhChon(
  voteId: string,
  actorId: string,
  contextId: string,
): Promise<CuocBinhChonWire> {
  return translatedAsActor<CuocBinhChonWire>(BINH_CHON_REFUSALS, `/votes/${voteId}`, {
    method: "GET",
    actorId,
    roles: "member",
    contexts: contextId,
  });
}

/**
 * Cast, or change, this caller's ballot.
 *
 * The body carries `option_id` and nothing else -- there is no `voter_id` to
 * send, because the server reads the voter off the actor header. Changing your
 * mind is the same call with a different option, which is why no
 * `Idempotency-Key` is sent: the route is idempotent by design, and a key
 * fingerprinted on method + path + body would refuse the honest case of
 * somebody tapping back onto the option they had already chosen.
 */
export async function boPhieu(
  voteId: string,
  optionId: string,
  actorId: string,
  contextId: string,
): Promise<PhieuDaBoWire> {
  return translatedAsActor<PhieuDaBoWire>(BINH_CHON_REFUSALS, `/votes/${voteId}/ballots`, {
    method: "POST",
    body: { option_id: optionId },
    actorId,
    roles: "member",
    contexts: contextId,
  });
}

/**
 * Close the vote. The answer is the vote re-read, not an acknowledgement.
 *
 * The caller replaces its state with the response for the same reason
 * `luuGanMon` does: `is_closed`, `decided_option_id` and `is_tie` become true
 * because the server said so, not because the app decided locally that the
 * tap had worked.
 */
export async function dongBinhChon(
  voteId: string,
  actorId: string,
  contextId: string,
): Promise<CuocBinhChonWire> {
  return translatedAsActor<CuocBinhChonWire>(BINH_CHON_REFUSALS, `/votes/${voteId}/close`, {
    method: "POST",
    actorId,
    roles: "member",
    contexts: contextId,
  });
}

/* -------------------------------------- self-tagging, F22 (rd-fe-22) */

/**
 * Claim the dishes you ate. Only ever your own.
 *
 * `item_keys` is the caller's COMPLETE set of claims on this bill, not an
 * addition to it -- the server releases every key absent from the list. That
 * is how a mis-tap is undone without a second endpoint, and it is why the
 * screen sends the whole tick state rather than a delta.
 *
 * There is no `participant_id` in the body and there cannot be one: the
 * server's model forbids extra fields, so a body naming anybody is a 422
 * before a line of its code runs. The person charged is the caller.
 */
export async function nhanMonCuaToi(
  billId: string,
  itemKeys: readonly string[],
  actorId: string,
  contextId: string,
): Promise<BillWire> {
  return callAsActor<BillWire>(`/bills/${billId}/my-items`, {
    method: "POST",
    body: { item_keys: [...itemKeys] },
    actorId,
    roles: "member",
    contexts: contextId,
  });
}

/**
 * One rectangle on a group photograph, as a fraction of the image.
 *
 * Fractions rather than pixels, so the overlay is drawn against whatever size
 * the frame happens to be laid out at. There is nothing identifying in here:
 * `box_key` is an ordinal within one response, is not derived from the pixels,
 * and is NOT stable between requests -- so two responses cannot be joined on
 * it, and a claim stored against one is meaningless after a re-scan.
 */
export type OKhuonMatWire = {
  box_key: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type KhuonMatWire = {
  photo_id: string;
  boxes: OKhuonMatWire[];
};

const KHUON_MAT_REFUSALS: Record<string, string> = {
  rate_limited:
    "Máy đang tìm khuôn mặt cho nhiều tấm quá. Chờ một chút rồi thử lại giúp mình.",
  face_detection_unavailable:
    "Máy chưa tìm được khuôn mặt trên tấm này. Bạn vẫn chọn người bằng tay được.",
  permission_denied:
    "Bạn không ở trong nhóm này nên không mở được tấm ảnh.",
};

/**
 * Find the faces in one group photograph the caller may already see.
 *
 * POST on a route that reads and stores nothing, which looks wrong until you
 * read the server's note: a GET invites a client to poll it and a remounting
 * screen to re-issue it, and each run is a multi-megapixel cascade on the box
 * the money routes share. There is no request body, so there is no field
 * through which this app could name a person or pick a detector.
 */
export async function timKhuonMat(
  contextId: string,
  photoId: string,
  actorId: string,
): Promise<KhuonMatWire> {
  return translatedAsActor<KhuonMatWire>(
    KHUON_MAT_REFUSALS,
    `/contexts/${contextId}/photos/${photoId}/face-boxes`,
    { method: "POST", actorId, roles: "member", contexts: contextId },
  );
}
