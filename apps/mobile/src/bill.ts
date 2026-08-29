/** The `/bills` wire: a bill that outlives the screen showing it.
 *
 * Until now the assignment matrix existed only in React state. A person ticked
 * who ate what, `POST /expenses` split it, and the matrix itself was never
 * written anywhere -- so `suggested_item_keys`, `assignment_state` and the
 * whole `/bills` family sat unused on a server that had implemented them. Two
 * consequences, and the second is the one that matters: closing the app lost
 * the work, and nobody could reopen a bill to see who had claimed what.
 *
 * This module is the mapping, and only the mapping. No `fetch` lives here so
 * the money shapes can be tested without a server, which is the same reason
 * `assignment.ts` and `receipt.ts` are separate from `api.ts`.
 *
 * ## Money is integer dong, and this module refuses to pass on anything else
 *
 * Rule 1 of the three money rules bans `float` at every intermediate value,
 * not just at the edges. A `line_total_vnd` of `12000.5` reaching the server is
 * a 422 that says nothing useful; the same value reaching a total is a number
 * on screen nobody can reproduce. `nguyenDong` throws at the boundary instead,
 * where the field name is still known.
 */
import {
  whoOn,
  type Assignment,
} from "./assignment";
import type { BillLine, BillReading } from "./receipt";

/* ------------------------------------------------------------------ wire */

export type BillItemWire = {
  item_key: string;
  name: string;
  quantity: number;
  unit_price_vnd: number | null;
  line_total_vnd: number;
  suggested_participant_ids: string[];
};

export type BillCreateWire = {
  context_id: string;
  printed_total_vnd: number | null;
  items_total_vnd: number;
  confidence: number;
  needs_review: boolean;
  items: BillItemWire[];
  surcharges: never[];
  discounts: never[];
};

/** One item's shares as the server reports them back.
 *
 * `source` is the field that separates a guess from a decision: `ai_suggested`
 * is what the reader proposed and nobody has confirmed, `confirmed` is what a
 * person ticked. The screen must not draw those the same way, which is why
 * this is carried through rather than flattened to a list of ids.
 */
export type BillShareWire = {
  participant_id: string;
  source: "ai_suggested" | "confirmed";
  decided_by_id: string | null;
  decided_at: string | null;
};

export type BillItemResponseWire = {
  item_key: string;
  name: string;
  quantity: number;
  unit_price_vnd: number | null;
  line_total_vnd: number;
  position: number;
  shares: BillShareWire[];
};

export type BillWire = {
  id: string;
  context_id: string;
  printed_total_vnd: number | null;
  items_total_vnd: number;
  needs_review: boolean;
  created_by_id: string;
  created_at: string;
  assignment_state: "confirmed" | "ai_suggested";
  suggested_item_keys: string[];
  items: BillItemResponseWire[];
  surcharges: unknown[];
  discounts: unknown[];
};

export type BillAssignmentsWire = {
  assignments: { item_key: string; participant_ids: string[] }[];
};

/* --------------------------------------------------------------- guards */

/**
 * Let an integer number of dong through, refuse anything else.
 *
 * Thrown rather than coerced. `Math.round` here would be the product quietly
 * inventing a number that no receipt printed and no person agreed to, which is
 * the exact failure rule 1 exists to prevent -- and it would do it silently,
 * at the one place where the mistake is still attributable to a field.
 */
export function nguyenDong(value: number, field: string): number {
  if (!Number.isInteger(value)) {
    throw new RangeError(`${field} phải là số nguyên đồng, nhận được ${value}`);
  }
  return value;
}

/* ---------------------------------------------------------------- create */

/**
 * The body that stores this reading as a bill.
 *
 * `suggested_participant_ids` carries the matrix the app is holding at the
 * moment of the write, which for a fresh scan is the "everyone shares every
 * line" default. That is deliberately recorded as a *suggestion*: the server
 * stamps those shares `ai_suggested`, so a bill nobody has touched comes back
 * with `assignment_state: "ai_suggested"` and the screen can say so out loud
 * rather than presenting a default as a decision.
 *
 * `confidence` is 0 here and that is not a placeholder. `ReceiptScanResponse`
 * deliberately does not return one -- ADR-0009 decision 4 refuses to hand the
 * client a percentage, because rd-qa-03 measured that the number tracked how
 * legible the print was rather than whether the money was right. The server
 * keeps its own score where it gates. The client has `needs_review`, which is
 * the signal it is meant to branch on, and reporting a confidence it does not
 * have would be inventing evidence.
 */
export function billCreateBody(
  reading: BillReading,
  contextId: string,
  assignment: Assignment,
): BillCreateWire {
  const items = reading.lines.map((line) => billItem(line, assignment));
  return {
    context_id: contextId,
    printed_total_vnd:
      reading.printedTotalVnd === null
        ? null
        : nguyenDong(reading.printedTotalVnd, "printed_total_vnd"),
    items_total_vnd: items.reduce((sum, item) => sum + item.line_total_vnd, 0),
    confidence: 0,
    needs_review: reading.needsReview,
    items,
    surcharges: [],
    discounts: [],
  };
}

function billItem(line: BillLine, assignment: Assignment): BillItemWire {
  return {
    // `BillLine.id` is already `mon-0`, `mon-1`, ... -- short, stable for the
    // life of the reading, and well inside the server's 64-character limit on
    // `item_key`. Sending the name instead would break on two dishes with the
    // same name, which one menu in four has.
    item_key: line.id,
    name: line.name,
    quantity: nguyenDong(line.quantity, `quantity của "${line.name}"`),
    // The reader reports a line total, not always a unit price, and dividing
    // one by the other here would put a non-integer on the wire the moment a
    // price does not divide evenly. The server takes null.
    unit_price_vnd: null,
    line_total_vnd: nguyenDong(line.lineTotalVnd, `giá của "${line.name}"`),
    suggested_participant_ids: whoOn(assignment, line.id),
  };
}

/* ----------------------------------------------------------- assignments */

/** The body that turns suggestions into decisions, for every line. */
export function assignmentsBody(
  reading: BillReading,
  assignment: Assignment,
): BillAssignmentsWire {
  return {
    assignments: reading.lines.map((line) => ({
      item_key: line.id,
      participant_ids: whoOn(assignment, line.id),
    })),
  };
}

/**
 * Rebuild the app's matrix from a bill the server is holding.
 *
 * This is what makes reopening a bill show what people actually ticked, and
 * it is keyed on `item_key` rather than on position: the server returns items
 * carrying an explicit `position`, but relying on array order to line rows up
 * with their owners is how somebody's food gets billed to somebody else.
 */
export function assignmentFromBill(bill: BillWire): Assignment {
  const out: Assignment = {};
  for (const item of bill.items) {
    out[item.item_key] = item.shares.map((share) => share.participant_id);
  }
  return out;
}

/**
 * Whether this bill's shares are decisions or still the machine's guess.
 *
 * `suggested_item_keys` is the per-line version of the same fact, and the two
 * disagree in the case that matters: a bill where somebody has confirmed four
 * lines out of six reports `assignment_state: "ai_suggested"` and lists the
 * two that are still guesses. A screen that only read the top-level state
 * would mark all six as unconfirmed and ask a person to redo work they did.
 */
export function laGoiY(bill: BillWire, itemKey: string): boolean {
  return bill.suggested_item_keys.includes(itemKey);
}

/**
 * What the screen may claim about where these ticks live.
 *
 * Pure, and separate from the component, because this is the sentence most
 * likely to drift into a comfortable lie. Three states, and the first is the
 * one worth protecting: a bill that failed to store must say so. An app that
 * silently keeps working after a failed write teaches people their ticks are
 * safe, and the lesson only gets corrected when they close it and lose an
 * evening's arithmetic.
 *
 * `suggested_item_keys` is preferred over `assignment_state` for the middle
 * case because the two disagree exactly where it matters: a bill with four
 * lines confirmed and two still guesses reports `ai_suggested` at the top
 * level, and reading only that would tell a person none of their work landed.
 */
export function moTaTrangThaiGan(bill: BillWire | null | undefined): string {
  // `== null`, so a prop that never arrived lands here rather than three lines
  // down on `.suggested_item_keys`. `undefined` is not a third state meaning
  // anything: it is the absence of a bill, same as `null`, and the version of
  // this that tested `=== null` threw on every caller that omitted the prop.
  // The same shape `readingFromWire` guards against -- a missing field read as
  // an answer instead of as an absence -- except this one failed loudly, which
  // is the lucky half of that family.
  if (bill == null) {
    return "Chưa lưu được lên máy chủ. Các ô đã tích chỉ nằm trên máy này.";
  }
  const con = bill.suggested_item_keys.length;
  if (con === 0) {
    return "Đã lưu. Ai ăn món gì là do nhóm chốt, không phải máy đoán.";
  }
  if (con === bill.items.length) {
    return "Máy đọc gợi ý sẵn ai ăn món gì. Sửa lại cho đúng rồi bấm Xem kết quả.";
  }
  return `Đã lưu. Còn ${con} món vẫn là máy đoán, chưa ai xác nhận.`;
}

/* --------------------------------------------------------------- balances */

export type SoDuWire = {
  balances: { person_id: string; net_vnd: number }[];
  /* `sender_id` / `recipient_id`, not `from_id` / `to_id`. Read off
   * `SettlementTransferProposal` rather than guessed: the guessed pair parses
   * without complaint and puts `undefined` where a name goes, which renders as
   * a blank row instead of an error anybody would notice. */
  transfers: { sender_id: string; recipient_id: string; amount_vnd: number }[];
  proven_minimal: boolean;
  transfer_count: number;
};

/** One "A trả B bao nhiêu" row.
 *
 * A proposal, never an obligation. The server's own schema says these
 * "must not be treated as a frozen obligation" -- an obligation exists only
 * after a batch is published, and showing one of these as settled money would
 * claim a state the ledger is not in.
 */
export type ChuyenTien = {
  fromId: string;
  toId: string;
  amountVnd: number;
};

export type SoDu = {
  netByPerson: Record<string, number>;
  transfers: ChuyenTien[];
  /**
   * Whether the server proved this transfer list is the shortest possible.
   *
   * Shown, not hidden, and never upgraded to a claim when false. "Ít nhất có
   * thể" on a list that was not proven minimal is the kind of small lie that
   * costs trust in a money screen for nothing.
   */
  provenMinimal: boolean;
};

export function soDuFromWire(wire: SoDuWire): SoDu {
  const netByPerson: Record<string, number> = {};
  for (const row of wire.balances) {
    netByPerson[row.person_id] = nguyenDong(row.net_vnd, "net_vnd");
  }
  return {
    netByPerson,
    transfers: wire.transfers.map((row) => ({
      fromId: row.sender_id,
      toId: row.recipient_id,
      amountVnd: nguyenDong(row.amount_vnd, "amount_vnd"),
    })),
    provenMinimal: wire.proven_minimal === true,
  };
}
