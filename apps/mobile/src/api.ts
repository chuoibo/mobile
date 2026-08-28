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

/** Where the API lives. Overridable so a phone can reach a laptop. */
// Read through a guard rather than `process.env` directly: this module is
// compiled for the node test runner as well as for Metro, and `process` does
// not exist in every target. Expo inlines `EXPO_PUBLIC_*` at build time.
declare const process: { env?: Record<string, string | undefined> } | undefined;

export const BASE_URL =
  (typeof process !== "undefined" ? process?.env?.EXPO_PUBLIC_API_URL : undefined) ??
  "http://localhost:8099";

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

async function call<T>(
  path: string,
  { method = "POST", body, actorId }: { method?: string; body?: unknown; actorId?: string },
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE_URL + path, {
      method,
      headers: actorId ? actorHeaders(actorId) : { "Content-Type": "application/json" },
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
    throw new ApiError(response.status, code, detail);
  }
  return (await response.json()) as T;
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

export async function proposeSplit(draft: Draft): Promise<PendingProposal> {
  const body: ExpenseInput = {
    context_id: CONTEXT_ID,
    description: draft.occasion,
    recorded_by_id: draft.advancerId,
    paid_by_id: draft.advancerId,
    verification_scope: "totals_only",
    occurred_at: new Date().toISOString(),
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
  }>("/expenses", { body });

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
      due_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    },
    actorId: proposal.advancerId,
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
  roster: Participant[] = [],
): Promise<Envelope[]> {
  // Checked here as well as by the disabled button. A disabled button is a
  // courtesy; this is what holds when the function is called directly.
  if (!canPublish(gates)) {
    throw new GateNotPassedError(gates);
  }
  // Gate 2 is the server's to enforce, so its refusal is the only true answer
  // about it.
  return sendPublish(batchId, actorId, roster);
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
  options: { method?: string; body?: unknown; actorId?: string },
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
      guest_link_expires_at: new Date(
        Date.now() + 14 * 24 * 60 * 60 * 1000,
      ).toISOString(),
    },
    actorId,
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
 * `idempotency_key` is generated per attempt and reused on retry, because a
 * flaky connection must not turn one arrival into two. Confirming twice would
 * push an obligation to `over_confirmed`, which reads as somebody having paid
 * more than they owed.
 */
export async function confirmReceipt(
  obligationId: string,
  amountVnd: number,
  actorId: string,
  idempotencyKey: string,
): Promise<{ status: Obligation["status"] }> {
  const result = await call<{
    obligation_status: Obligation["status"];
  }>(`/obligations/${obligationId}/confirm-receipt`, {
    body: { amount_vnd: amountVnd, idempotency_key: idempotencyKey },
    actorId,
  });
  return { status: result.obligation_status };
}
