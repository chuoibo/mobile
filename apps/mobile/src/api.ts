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
import type { Proposal } from "./screens/DeXuat";
import type { Obligation } from "./screens/DotThu";
import type { Envelope } from "./screens/ChiaSe";
import type { Draft, Participant } from "./screens/NhapKhoanChi";
import type { ReceiptScanWire } from "./receipt";
import { makeIdFactory } from "./participants";

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

/**
 * The group this app acts inside.
 *
 * `contexts` exists as a table now, but nothing in this flow creates one yet,
 * so a fixed synthetic id stands in. Fixed rather than generated per launch:
 * an expense and the batch that collects it have to agree on the group, and a
 * value that changes on reload splits one group into two without saying so.
 */
export const CONTEXT_ID = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";

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

function actorHeaders(actorId: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    // A trusted gateway is supposed to write these; there is no gateway yet,
    // so the app writes them. That is exactly why this must not be reachable
    // from the internet as it stands -- anybody who can set a header can be
    // anybody. Said here rather than left to be discovered.
    "X-Actor-ID": actorId,
    "X-Actor-Roles": "member,advancer,recipient,batch_owner",
    "X-Actor-Contexts": CONTEXT_ID,
  };
}

type CallOptions = {
  method?: string;
  body?: unknown;
  actorId?: string;
  /** Required for writes. A write without one is unprotected against retries. */
  attempt?: Attempt;
};

async function call<T>(path: string, { method = "POST", body, actorId, attempt }: CallOptions): Promise<T> {
  const headers: Record<string, string> = actorId
    ? actorHeaders(actorId)
    : { "Content-Type": "application/json" };
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
    let code = `http_${response.status}`;
    let detail = `${method} ${path} trả về ${response.status}`;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; the status-based message is the honest one */
    }
    throw new ApiError(response.status, code, IDEMPOTENCY_REFUSALS[code.toLowerCase()] ?? detail);
  }
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
  await translated<{ id: string; display_name: string }>(
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

type ExpenseInput = {
  context_id: string;
  description: string;
  recorded_by_id: string;
  paid_by_id: string;
  verification_scope: "totals_only";
  occurred_at: string;
  participants: string[];
  total_amount_vnd: number;
  items: never[];
  surcharges: never[];
  discounts: never[];
};

/** A proposal plus what `confirmExpense` needs to prove it saw it. */
export type PendingProposal = Proposal & {
  expenseId: string;
  serverProposal: ExpenseInput;
};

export async function proposeSplit(draft: Draft, attempt: Attempt): Promise<PendingProposal> {
  const body: ExpenseInput = {
    context_id: CONTEXT_ID,
    description: draft.occasion,
    recorded_by_id: draft.advancerId,
    paid_by_id: draft.advancerId,
    verification_scope: "totals_only",
    // From the attempt, not the clock: a retry has to send the same bytes.
    occurred_at: new Date(attempt.at).toISOString(),
    participants: draft.participants.map((person: Participant) => person.id),
    total_amount_vnd: draft.totalVnd,
    items: [],
    surcharges: [],
    discounts: [],
  };
  const result = await call<{
    expense_id: string;
    proposal: ExpenseInput;
    allocation: { allocations: Record<string, number>; rounding_gainers: string[] };
  }>("/expenses", { body, attempt });

  return {
    participants: draft.participants,
    allocations: result.allocation.allocations,
    roundingGainers: result.allocation.rounding_gainers,
    totalVnd: draft.totalVnd,
    advancerId: draft.advancerId,
    occasion: draft.occasion,
    expenseId: result.expense_id,
    serverProposal: result.proposal,
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
  const result = await translated<{
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

const OPEN_BATCH_REFUSALS: Record<string, string> = {
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
 * The keys are the three gate codes returned by `unmet_publish_gates()` in
 * `services/api/app/domain/collection.py`, plus the one code `publish_batch()`
 * raises before it reaches the gates. They are not a guess: `tests/
 * publish-refusals.test.mjs` parses those two Python functions and fails if a
 * key here is not a code publish can send, or a code publish can send has no
 * words here.
 *
 * That test exists because this table shipped wrong. It named
 * `advancer_not_acknowledged` and `bank_recipient_snapshot_invalid`, neither
 * of which appears anywhere in `services/api/app`, so all three gates fell
 * through and put "A publish gate is not satisfied" on screen next to
 * somebody's name and somebody's money. The old test was green throughout: it
 * built its expectations from this object's own keys.
 *
 * Still deliberately incomplete. A code nobody listed falls through to the
 * server's own detail rather than to a friendly sentence that might be wrong
 * about what just happened, and that fallthrough is the more important half.
 */
export const PUBLISH_REFUSALS: Record<string, string> = {
  advancer_acknowledgement_required:
    "Người ứng tiền chưa xác nhận. App không gửi gì dưới tên một người trước khi họ đồng ý.",
  // One code, two situations: the snapshot was never confirmed, or it was
  // confirmed and then changed after the round froze. The server does not say
  // which, so neither does this. Naming the wrong one would send somebody to
  // fix a thing that is not broken.
  valid_bank_recipient_snapshot_required:
    "Tài khoản nhận đã đóng băng cùng đợt thu này không còn dùng được. Kiểm tra lại tài khoản nhận của người ứng tiền trước khi phát.",
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
 * The server refuses to freeze a batch when somebody who is owed money has no
 * bank account on file, and it is right not to pick for you: "wait" and "split
 * the blocked ones out" have different consequences for the people involved.
 *
 * A parameter for that choice used to sit here. Nothing called it and no test
 * exercised it, so it was a promise the app could not keep -- and an untaken
 * branch on the money path is worse than an absent one, because it reads as
 * handled. The refusal reaches the screen instead, with the reason attached.
 */
export async function openBatch(
  proposal: PendingProposal,
  expenseVersionId: string,
  acknowledged: boolean,
  attempt: Attempt,
): Promise<OpenedBatch> {
  const nameOf = (id: string) =>
    proposal.participants.find((person: Participant) => person.id === id)?.name ?? id;

  const result = await translated<{
    batch_id: string;
    obligations: {
      obligation_id: string;
      sender_id: string;
      recipient_id: string;
      amount_vnd: number;
    }[];
  }>(OPEN_BATCH_REFUSALS, "/batches", {
    body: {
      context_id: CONTEXT_ID,
      expense_version_ids: [expenseVersionId],
      // Counted from the attempt, so a retry asks for the same due date rather
      // than one seven days from whenever the connection came back.
      due_at: new Date(attempt.at + 7 * 24 * 60 * 60 * 1000).toISOString(),
    },
    actorId: proposal.advancerId,
    attempt,
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
 */
export async function publishBatch(
  batchId: string,
  gates: PublishGates,
  actorId: string,
  attempt: Attempt,
  roster: Participant[] = [],
): Promise<Envelope[]> {
  // Checked here as well as by the disabled button. A disabled button is a
  // courtesy; this is what holds when the function is called directly.
  if (!canPublish(gates)) {
    throw new GateNotPassedError(gates);
  }
  // Gate 2 is the server's to enforce, so its refusal is the only true answer
  // about it.
  return sendPublish(batchId, actorId, attempt, roster);
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
 */
async function translated<T>(
  table: Record<string, string>,
  path: string,
  options: CallOptions,
): Promise<T> {
  try {
    return await call<T>(path, options);
  } catch (problem) {
    if (problem instanceof ApiError) {
      const said = table[problem.code.toLowerCase()];
      if (said) throw new ApiError(problem.status, problem.code, said);
    }
    throw problem;
  }
}

function nameFrom(roster: Participant[], id: string): string {
  // Falling back to the id is deliberate: a missing name is a display problem,
  // and hiding it behind "Người nhận" would make two different people look
  // like the same one on a screen whose whole purpose is telling them apart.
  return roster.find((person) => person.id === id)?.name ?? id;
}

async function sendPublish(
  batchId: string,
  actorId: string,
  attempt: Attempt,
  roster: Participant[],
): Promise<Envelope[]> {
  const result = await translated<{
    guest_links: {
      sender_id: string;
      path: string;
      // One link can cover several obligations -- one person can owe two
      // different people out of the same round. The link is per sender, not
      // per debt, and each debt carries its own VietQR string.
      obligations: { obligation_id: string; amount_vnd: number }[];
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
    senderName: nameFrom(roster, link.sender_id),
    amountVnd: link.obligations.reduce((sum, row) => sum + row.amount_vnd, 0),
    url: BASE_URL + link.path,
    opened: false,
  }));
}

/** The collection board, including anything a guest has objected to. */
export async function loadBoard(
  batchId: string,
  actorId: string,
  roster: Participant[] = [],
): Promise<{ obligations: Obligation[]; disputedCount: number }> {
  const result = await call<{
    disputed_count: number;
    obligations: {
      obligation_id: string;
      sender_id: string;
      recipient_id: string;
      amount_vnd: number;
      obligation_status: Obligation["status"];
      disputed: boolean;
    }[];
  }>(`/batches/${batchId}/obligations`, { method: "GET", actorId });

  return {
    disputedCount: result.disputed_count,
    obligations: result.obligations.map((row) => ({
      id: row.obligation_id,
      senderId: row.sender_id,
      senderName: nameFrom(roster, row.sender_id),
      recipient: nameFrom(roster, row.recipient_id),
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
  const result = await call<{
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
  if (photo.uri.startsWith("blob:") || photo.uri.startsWith("data:")) {
    const blob = await fetch(photo.uri).then((r) => r.blob());
    form.append("image", blob, "bill.jpg");
  } else {
    // React Native's own FormData understands this shape and nothing else.
    form.append("image", { uri: photo.uri, name: "bill.jpg", type: "image/jpeg" } as never);
  }

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
    let detail = `Máy chủ trả về ${response.status} khi đang đọc bill.`;
    try {
      const problem = await response.json();
      if (problem?.code) code = problem.code;
      if (problem?.detail) detail = problem.detail;
    } catch {
      /* not JSON; the status-based sentence is the honest one */
    }
    throw new ApiError(response.status, code, SCAN_REFUSALS[code.toLowerCase()] ?? detail);
  }
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
