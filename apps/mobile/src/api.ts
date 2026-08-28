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
  const result = await call<{
    expense_version_id: string;
    payer_acknowledgement: "pending" | "acknowledged";
  }>(`/expenses/${proposal.expenseId}/confirm`, {
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

/** Spec section 8.3: two gates before anything goes out in someone's name. */
export type PublishGates = {
  payerAcknowledged: boolean;
  recipientReady: boolean;
  recipientProblem: string | null;
};

export function canPublish(gates: PublishGates): boolean {
  return gates.payerAcknowledged && gates.recipientReady;
}

export class GateNotPassedError extends Error {
  constructor(gates: PublishGates) {
    const missing = [
      gates.payerAcknowledged ? null : "người ứng tiền chưa xác nhận",
      gates.recipientReady ? null : "chưa có tài khoản nhận",
    ].filter(Boolean);
    super(`Chưa phát được: ${missing.join(" và ")}. Spec mục 8.3.`);
    this.name = "GateNotPassedError";
  }
}

export type OpenedBatch = {
  batchId: string;
  obligations: Obligation[];
  gates: PublishGates;
};

/**
 * Open a collection round.
 *
 * `unreadyRecipientChoice` exists because the server refuses to freeze a batch
 * when somebody who is owed money has no bank account on file. It will not pick
 * for you, and it is right not to: "wait" and "split the blocked ones out" have
 * different consequences for the people involved, and neither is a default.
 *
 * The app passes nothing by default, so the refusal reaches the screen instead
 * of being silently resolved here.
 */
export async function openBatch(
  proposal: PendingProposal,
  expenseVersionId: string,
  acknowledged: boolean,
  unreadyRecipientChoice?: "wait" | "split_to_blocked_batch",
): Promise<OpenedBatch> {
  const nameOf = (id: string) =>
    proposal.participants.find((person: Participant) => person.id === id)?.name ?? id;

  const result = await call<{
    batch_id: string;
    obligations: {
      obligation_id: string;
      sender_id: string;
      recipient_id: string;
      amount_vnd: number;
    }[];
  }>("/batches", {
    body: {
      context_id: CONTEXT_ID,
      expense_version_ids: [expenseVersionId],
      due_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      unready_recipient_choice: unreadyRecipientChoice ?? null,
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
    gates: {
      // A real answer from the server, not a guess.
      payerAcknowledged: acknowledged,
      // The recipient gate is not readable from this endpoint yet, so it stays
      // shut. A gate that opens because nobody checked is not a gate.
      recipientReady: false,
      recipientProblem: `Chưa đọc được tài khoản nhận của ${nameOf(proposal.advancerId)}.`,
    },
  };
}

export async function publishBatch(
  batchId: string,
  gates: PublishGates,
  actorId: string,
): Promise<Envelope[]> {
  // Checked here as well as by the disabled button. A disabled button is a
  // courtesy; this is what holds when the function is called directly.
  if (!canPublish(gates)) {
    throw new GateNotPassedError(gates);
  }
  const result = await call<{
    guest_links: {
      sender_id: string;
      path: string;
      // One link can cover several obligations -- one person can owe two
      // different people out of the same round. The link is per sender, not
      // per debt, and each debt carries its own VietQR string.
      obligations: { obligation_id: string; amount_vnd: number }[];
    }[];
  }>(`/batches/${batchId}/publish`, {
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
    senderName: link.sender_id,
    amountVnd: link.obligations.reduce((sum, row) => sum + row.amount_vnd, 0),
    url: BASE_URL + link.path,
    opened: false,
  }));
}

/** The collection board, including anything a guest has objected to. */
export async function loadBoard(
  batchId: string,
  actorId: string,
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
      senderName: row.sender_id,
      recipient: row.recipient_id,
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
