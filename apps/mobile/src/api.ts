/** Talks to services/api.
 *
 * The routes do not exist yet (Codex owns them, in flight). Until they land,
 * `OFFLINE` returns fixtures so the screens can be walked end to end. The
 * fixture path is loud on purpose: a stub that looks like a real response is
 * how a demo quietly becomes a lie.
 *
 * Nothing here computes money. The split comes from the server, which calls
 * the allocator that 41 hand-computed golden vectors are pinned against.
 * A second implementation in TypeScript would be a second thing to get wrong.
 */
import type { Proposal } from "./screens/DeXuat";
import type { Obligation } from "./screens/DotThu";
import type { Envelope } from "./screens/ChiaSe";
import type { Draft } from "./screens/NhapKhoanChi";

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

/** Even split, computed the way the server will, for fixture mode only. */
function fixtureProposal(draft: Draft): Proposal {
  const n = draft.participants.length;
  const floor = Math.floor(draft.totalVnd / n);
  const deficit = draft.totalVnd - floor * n;
  // Largest remainder with every remainder equal: the advancer absorbs the
  // rounding first, then plain byte order. Mirrors ADR-0004 decisions 16 and 17.
  const ordered = [...draft.participants].sort((a, b) =>
    a === draft.advancer ? -1 : b === draft.advancer ? 1 : (a < b ? -1 : a > b ? 1 : 0)
  );
  const gainers = ordered.slice(0, deficit);
  const allocations: Record<string, number> = {};
  for (const name of draft.participants) {
    allocations[name] = floor + (gainers.includes(name) ? 1 : 0);
  }
  return {
    allocations,
    roundingGainers: gainers,
    totalVnd: draft.totalVnd,
    advancer: draft.advancer,
    occasion: draft.occasion,
  };
}

export async function proposeSplit(draft: Draft): Promise<Proposal> {
  if (OFFLINE) return fixtureProposal(draft);
  return post<Proposal>("/expenses", {
    participants: draft.participants,
    total_vnd: draft.totalVnd,
    advancer_id: draft.advancer,
    items: [],
    surcharges: [],
    discounts: [],
  });
}

export async function openBatch(proposal: Proposal): Promise<Obligation[]> {
  if (OFFLINE) {
    return Object.entries(proposal.allocations)
      .filter(([name, amount]) => name !== proposal.advancer && amount > 0)
      .map(([name, amount], index) => ({
        id: `o${index + 1}`,
        sender: name,
        recipient: proposal.advancer,
        amountVnd: amount,
        status: "outstanding" as const,
      }));
  }
  return post<Obligation[]>("/batches", { proposal });
}

export async function publishBatch(obligations: Obligation[]): Promise<Envelope[]> {
  if (OFFLINE) {
    return obligations.map((o) => ({
      sender: o.sender,
      amountVnd: o.amountVnd,
      url: `${BASE_URL}/g/vi-du-${o.id}`,
      opened: false,
    }));
  }
  return post<Envelope[]>("/batches/current/publish", { obligations });
}
