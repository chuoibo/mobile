/**
 * Chia hóa đơn in the RuDi shell on a real session (M5): the bridge from a
 * photo (or a hand-typed list) to a bill the server holds, an assignment the
 * server holds, a split the server computes, and an expense the server
 * writes to the ledger.
 *
 * Every number that says who owes what comes back from the server. This
 * module adds lines, formats sentences and picks names; it never divides.
 * The wire functions and the pure editors are App B's (`api.ts`,
 * `receipt.ts`, `assignment.ts`, `bill.ts`), which is where the tests that
 * pin the three money laws already live.
 */
import {
  attemptFor,
  confirmExpense,
  docChiaBill,
  luuGanMon,
  proposeSplit,
  scanReceipt,
  taoBill,
  type Attempt,
  type ChiaBill,
} from "../../api";
import { itemsForWire, whoOn, type Assignment } from "../../assignment";
import { type BillWire } from "../../bill";
import { dinhDangTienVnd } from "../../screens/chat/ke-hoach";
import { addLine, itemsTotalVnd, readingFromWire, type BillReading } from "../../receipt";

/** One group member as the assignment matrix names them. */
export type ThanhVien = { id: string; name: string };

/** A bill with no lines yet: the hand-typed path starts here. */
export function hoaDonTrong(): BillReading {
  return { lines: [], printedTotalVnd: null, needsReview: false, warnings: [] };
}

/** A new empty line with an id no existing line has. */
export function themMon(reading: BillReading): BillReading {
  let n = reading.lines.length;
  const co = new Set(reading.lines.map((l) => l.id));
  while (co.has(`mon-${n}`)) n += 1;
  return addLine(reading, `mon-${n}`);
}

/** The photo, read by the server: a reading, or a thrown ApiError with its sentence. */
export async function docBillTuAnh(photo: { uri: string; bytes: number }, personId: string): Promise<BillReading> {
  return readingFromWire(await scanReceipt(photo, personId));
}

export async function taoBillTrenMayChu(
  reading: BillReading,
  contextId: string,
  assignment: Assignment,
  personId: string,
  attempt: Attempt,
): Promise<BillWire> {
  return taoBill(reading, contextId, assignment, personId, attempt);
}

export async function luuGanMonTrenMayChu(
  billId: string,
  reading: BillReading,
  assignment: Assignment,
  personId: string,
  contextId: string,
  attempt: Attempt,
): Promise<BillWire> {
  return luuGanMon(billId, reading, assignment, personId, contextId, attempt);
}

export async function chiaTrenMayChu(billId: string, personId: string, contextId: string, attempt: Attempt): Promise<ChiaBill> {
  return docChiaBill(billId, personId, contextId, attempt);
}

/** Members that appear in at least one share, in roster order. */
export function nguoiThamGia(reading: BillReading, assignment: Assignment, roster: readonly ThanhVien[]): ThanhVien[] {
  const trong = new Set<string>();
  for (const line of reading.lines) for (const id of whoOn(assignment, line.id)) trong.add(id);
  return roster.filter((tv) => trong.has(tv.id));
}

/**
 * Propose the expense from the bill and write it to the ledger: two server
 * calls, each under its own Attempt so a retry replays instead of doubling.
 */
export async function ghiVaoSo(input: {
  reading: BillReading;
  assignment: Assignment;
  roster: readonly ThanhVien[];
  contextId: string;
  payerId: string;
  occasion: string;
  attempts: Record<string, Attempt>;
}): Promise<{ expenseVersionId: string; acknowledged: boolean }> {
  const participants = nguoiThamGia(input.reading, input.assignment, input.roster);
  const items = itemsForWire(input.reading, input.assignment);
  const draft = {
    participants,
    totalVnd: itemsTotalVnd(input.reading),
    advancerId: input.payerId,
    occasion: input.occasion,
  };
  const khoa = `khoan-chi:${input.payerId}:${draft.totalVnd}:${input.occasion}:${participants.map((p) => p.id).join(",")}`;
  const proposal = await proposeSplit(input.contextId, draft, attemptFor(input.attempts, khoa), items);
  return confirmExpense(proposal, attemptFor(input.attempts, `xac-nhan:${proposal.expenseId}`));
}

/** A member's name for the screen; never the id. */
export function tenCua(roster: readonly ThanhVien[], id: string): string {
  const tv = roster.find((t) => t.id === id);
  if (tv === undefined) return "Thành viên";
  return tv.name;
}

/** «3 món · 1.280.000đ» */
export function cauTongMon(reading: BillReading): string {
  const n = reading.lines.length;
  return `${n} món · ${dinhDangTienVnd(itemsTotalVnd(reading))}`;
}

/** The server's split as rows the screen draws: name, đồng, whether rounding landed on them. */
export function hangKetQua(chia: ChiaBill, roster: readonly ThanhVien[]): { id: string; ten: string; tien: string; lamTron: boolean }[] {
  return Object.entries(chia.allocations)
    .map(([id, dong]) => ({ id, ten: tenCua(roster, id), tien: dinhDangTienVnd(dong), lamTron: chia.roundingGainers.includes(id) }))
    .sort((a, b) => a.ten.localeCompare(b.ten, "vi"));
}

/** What a scan refusal means for the next move, or the honest generic line. */
export function cauSauKhiScanHong(message: string): string {
  return `${message} Bạn có thể nhập món bằng tay.`;
}
