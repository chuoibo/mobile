import { PROPOSAL_FIXTURES } from "./fixtures/proposals.js";
/** The situations the offline demo can actually answer. */
export const FIXTURES = PROPOSAL_FIXTURES;
export const OFFLINE = true;
export const BASE_URL = "http://localhost:8000";
async function post(path, body) {
    const response = await fetch(BASE_URL + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(`${path} -> ${response.status}`);
    }
    return response.json();
}
export class FixtureMissingError extends Error {
    constructor(draft) {
        super(`Chế độ dữ liệu giả không có sẵn đáp án cho ${draft.totalVnd}đ chia ` +
            `${draft.participants.length} người. Hãy chọn một tình huống mẫu. ` +
            `Ứng dụng cố ý không tự tính — phép chia thuộc về máy chủ.`);
        this.name = "FixtureMissingError";
    }
}
/** The fixture whose input matches this draft exactly, or nothing. */
function lookupFixture(draft) {
    const wanted = [...draft.participants.map((p) => p.id)].sort().join(",");
    return FIXTURES.find((fixture) => fixture.totalVnd === draft.totalVnd &&
        (fixture.advancerId ?? null) === (draft.advancerId ?? null) &&
        [...fixture.participants.map((p) => p.id)].sort().join(",") === wanted);
}
/** Replay a precomputed answer. No arithmetic: every number is read, not made. */
function replayProposal(draft) {
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
export async function proposeSplit(draft) {
    if (OFFLINE)
        return replayProposal(draft);
    return post("/expenses", {
        participants: draft.participants.map((p) => ({ id: p.id, display_name: p.name })),
        total_vnd: draft.totalVnd,
        advancer_id: draft.advancerId,
        items: [],
        surcharges: [],
        discounts: [],
    });
}
export function canPublish(gates) {
    return gates.payerAcknowledged && gates.recipientReady;
}
export async function openBatch(proposal) {
    if (OFFLINE) {
        const nameOf = (id) => proposal.participants.find((p) => p.id === id)?.name ?? id;
        const obligations = Object.entries(proposal.allocations)
            .filter(([id, amount]) => id !== proposal.advancerId && amount > 0)
            .map(([id, amount], index) => ({
            id: `o${index + 1}`,
            senderId: id,
            senderName: nameOf(id),
            recipient: nameOf(proposal.advancerId),
            amountVnd: amount,
            status: "outstanding",
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
    return post("/batches", { proposal });
}
export class GateNotPassedError extends Error {
    constructor(gates) {
        const missing = [
            gates.payerAcknowledged ? null : "người ứng tiền chưa xác nhận",
            gates.recipientReady ? null : "chưa có tài khoản nhận",
        ].filter(Boolean);
        super(`Chưa phát được: ${missing.join(" và ")}. Spec mục 8.3.`);
        this.name = "GateNotPassedError";
    }
}
export async function publishBatch(obligations, gates) {
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
    return post("/batches/current/publish", { obligations });
}
