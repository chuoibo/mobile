/** Talks to services/api.
 *
 * The routes do not exist yet (Codex owns them, in flight). Until they land,
 * `OFFLINE` REPLAYS fixtures so the screens can be walked end to end. The
 * fixture path is loud on purpose: a stub that looks like a real response is
 * how a demo quietly becomes a lie.
 *
 * Nothing here computes money, and that is now enforced rather than promised.
 * This file used to carry an even split written in TypeScript, sitting twenty
 * lines under this very sentence -- `Math.floor(total / n)`, a deficit, a
 * tie-break. That was a second allocator implementation and `/` produces float
 * intermediates, both forbidden. Worse, a client that derives its own split can
 * disagree with the server about money while looking perfectly convincing.
 *
 * So the fake replays instead. `src/fixtures/proposals.json` is generated from
 * the golden vectors by `services/api/tools/build_mobile_fixtures.py`, which
 * makes it a projection of the hand-computed oracle rather than a second source
 * of truth. When a draft matches no fixture the fake REFUSES -- loudly, by
 * throwing -- because inventing an answer is the exact failure this replaced.
 */
import type { Proposal } from "./screens/DeXuat";
import type { Obligation } from "./screens/DotThu";
import type { Envelope } from "./screens/ChiaSe";
import type { Draft, Participant } from "./screens/NhapKhoanChi";
import { PROPOSAL_FIXTURES } from "./fixtures/proposals";

/** One generated fixture. Shape mirrors build_mobile_fixtures.py. */
export type Fixture = {
  id: string;
  note: string;
  occasion: string;
  totalVnd: number;
  advancerId: string | null;
  participants: Participant[];
  allocations: Record<string, number>;
  roundingGainers: string[];
};

/** The situations the offline demo can actually answer. */
export const FIXTURES = PROPOSAL_FIXTURES;

export const OFFLINE = true;
export const BASE_URL = "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(BASE_URL + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${path} -> ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export class FixtureMissingError extends Error {
  constructor(draft: Draft) {
    super(
      `Chế độ dữ liệu giả không có sẵn đáp án cho ${draft.totalVnd}đ chia ` +
        `${draft.participants.length} người. Hãy chọn một tình huống mẫu. ` +
        `Ứng dụng cố ý không tự tính — phép chia thuộc về máy chủ.`,
    );
    this.name = "FixtureMissingError";
  }
}

/** The fixture whose input matches this draft exactly, or nothing. */
function lookupFixture(draft: Draft): Fixture | undefined {
  const wanted = [...draft.participants.map((p) => p.id)].sort().join(",");
  return FIXTURES.find(
    (fixture) =>
      fixture.totalVnd === draft.totalVnd &&
      (fixture.advancerId ?? null) === (draft.advancerId ?? null) &&
      [...fixture.participants.map((p) => p.id)].sort().join(",") === wanted,
  );
}

/** Replay a precomputed answer. No arithmetic: every number is read, not made. */
function replayProposal(draft: Draft): Proposal {
  const fixture = lookupFixture(draft);
  if (!fixture) {
    throw new FixtureMissingError(draft);
  }
  return {
    participants: draft.participants,
    allocations: fixture.allocations,
    roundingGainers: fixture.roundingGainers,
    totalVnd: fixture.totalVnd,
    advancerId: draft.advancerId,
    occasion: draft.occasion,
  };
}

export async function proposeSplit(draft: Draft): Promise<Proposal> {
  if (OFFLINE) return replayProposal(draft);
  return post<Proposal>("/expenses", {
    participants: draft.participants.map((p) => ({ id: p.id, display_name: p.name })),
    total_vnd: draft.totalVnd,
    advancer_id: draft.advancerId,
    items: [],
    surcharges: [],
    discounts: [],
  });
}

/** Spec section 8.3: two things must be true before anything goes out.
 *
 * Nothing may be sent in the advancer's name until they have acknowledged it,
 * and there must be a bank recipient to send people towards. The prototype used
 * to skip straight from "confirm the split" to "publish", which taught a flow
 * where a collection round can go out under someone's name before they agree
 * to it -- and left no place to set up or check the recipient at all.
 *
 * These are reported, never inferred. When the real API lands it decides; the
 * offline fake starts both closed so the demo has to walk through them.
 */
export type PublishGates = {
  payerAcknowledged: boolean;
  recipientReady: boolean;
  /** Why the recipient is not usable yet, in words a person can act on. */
  recipientProblem: string | null;
};

export type Batch = { obligations: Obligation[]; gates: PublishGates };

export function canPublish(gates: PublishGates): boolean {
  return gates.payerAcknowledged && gates.recipientReady;
}

export async function openBatch(proposal: Proposal): Promise<Batch> {
  if (OFFLINE) {
    const nameOf = (id: string) =>
      proposal.participants.find((p) => p.id === id)?.name ?? id;
    const obligations = Object.entries(proposal.allocations)
      .filter(([id, amount]) => id !== proposal.advancerId && amount > 0)
      .map(([id, amount], index) => ({
        id: `o${index + 1}`,
        senderId: id,
        senderName: nameOf(id),
        recipient: nameOf(proposal.advancerId),
        amountVnd: amount,
        status: "outstanding" as const,
      }));
    // Both gates start shut. A fake that opens them for convenience would
    // teach exactly the flow section 8.3 exists to prevent.
    return {
      obligations,
      gates: {
        payerAcknowledged: false,
        recipientReady: false,
        recipientProblem: `Chưa có tài khoản nhận cho ${nameOf(proposal.advancerId)}.`,
      },
    };
  }
  return post<Batch>("/batches", { proposal });
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

export async function publishBatch(
  obligations: Obligation[],
  gates: PublishGates,
): Promise<Envelope[]> {
  // Checked here as well as in the UI. A disabled button is a courtesy; this
  // is the part that holds when someone calls the function directly.
  if (!canPublish(gates)) {
    throw new GateNotPassedError(gates);
  }
  if (OFFLINE) {
    return obligations.map((o) => ({
      senderId: o.senderId,
      senderName: o.senderName,
      amountVnd: o.amountVnd,
      url: `${BASE_URL}/g/vi-du-${o.id}`,
      opened: false,
    }));
  }
  return post<Envelope[]>("/batches/current/publish", { obligations });
}
