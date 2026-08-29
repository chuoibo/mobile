/** Who ate which line of a bill, as data the screen holds.
 *
 * Attribution, not a split. Every amount that leaves this file is a copy of
 * `line.lineTotalVnd`; the allocator on the server is the only thing in the
 * product that divides those amounts between people. A second implementation
 * here is how two screens end up showing two numbers for one dinner.
 *
 * `shared_by` is emitted in a canonical order (sorted ids) so the same set of
 * ticks serialises to the same bytes. The preview reuses one idempotency key
 * per signature; a body that drifted with tick-order would earn 422 instead
 * of a replay.
 */
import {
  blockingProblem as receiptBlocking,
  type BillLine,
  type BillReading,
} from "./receipt";

export type Assignment = Record<string, string[]>;

function whoOn(a: Assignment, lineId: string): string[] {
  return a[lineId] ?? [];
}

function ordered(ids: string[]): string[] {
  return [...ids].sort((left, right) => (left < right ? -1 : left > right ? 1 : 0));
}

export function everyoneShares(lines: BillLine[], participantIds: string[]): Assignment {
  const next: Assignment = {};
  for (const line of lines) {
    next[line.id] = [...participantIds];
  }
  return next;
}

export function toggle(a: Assignment, lineId: string, personId: string): Assignment {
  const current = whoOn(a, lineId);
  const nextWho = current.includes(personId)
    ? current.filter((id) => id !== personId)
    : [...current, personId];
  return { ...a, [lineId]: nextWho };
}

export function isOn(a: Assignment, lineId: string, personId: string): boolean {
  return whoOn(a, lineId).includes(personId);
}

export function countOn(a: Assignment, lineId: string): number {
  return whoOn(a, lineId).length;
}

export function dropPerson(a: Assignment, personId: string): Assignment {
  const next: Assignment = {};
  for (const lineId of Object.keys(a)) {
    next[lineId] = a[lineId].filter((id) => id !== personId);
  }
  return next;
}

export function addPersonToAll(
  a: Assignment,
  lineIds: string[],
  personId: string,
): Assignment {
  const next: Assignment = { ...a };
  for (const lineId of lineIds) {
    const current = whoOn(next, lineId);
    next[lineId] = current.includes(personId) ? current : [...current, personId];
  }
  return next;
}

export function syncLines(
  a: Assignment,
  lines: BillLine[],
  participantIds: string[],
): Assignment {
  const next: Assignment = {};
  for (const line of lines) {
    next[line.id] = a[line.id] !== undefined ? a[line.id] : [...participantIds];
  }
  return next;
}

/**
 * Reconcile an assignment with the roster that is about to be sent.
 *
 * The roster can still change after the matrix is built: `NhapKhoanChi` can
 * add or drop a name. Two things have to be true of what reaches the
 * allocator, and neither is true by accident:
 *
 *   - nobody in `shared_by` is outside `participants`, which is
 *     `UNKNOWN_PARTICIPANT`;
 *   - somebody added later is not left owing nothing without having said so.
 *
 * What it must NOT do is re-tick a box a person deliberately cleared. The
 * newcomer default therefore applies only to somebody who appears on no line
 * at all. The corner it does not cover: clearing one person from every single
 * line reads identically to never having placed them, so they are put back.
 * Removing them from the group is the way to say that, and it is the control
 * the screen offers.
 */
export function alignToRoster(
  a: Assignment,
  lines: BillLine[],
  participantIds: string[],
): Assignment {
  const keep = new Set(participantIds);
  const synced = syncLines(a, lines, participantIds);
  const next: Assignment = {};
  for (const lineId of Object.keys(synced)) {
    next[lineId] = synced[lineId].filter((id) => keep.has(id));
  }
  const placed = new Set<string>();
  for (const who of Object.values(next)) {
    for (const id of who) placed.add(id);
  }
  const lineIds = lines.map((line) => line.id);
  let result = next;
  for (const id of participantIds) {
    if (!placed.has(id)) result = addPersonToAll(result, lineIds, id);
  }
  return result;
}

export function itemsForWire(reading: BillReading, a: Assignment): {
  item_id: string;
  label: string;
  amount_vnd: number;
  shared_by: string[];
}[] {
  return reading.lines.map((line) => ({
    item_id: line.id,
    label: line.name,
    amount_vnd: line.lineTotalVnd,
    shared_by: ordered(whoOn(a, line.id)),
  }));
}

export function signature(
  reading: BillReading,
  participantIds: string[],
  a: Assignment,
): string {
  const people = ordered(participantIds);
  const lines = [...reading.lines]
    .map((line) => `${line.id}:${line.lineTotalVnd}:${line.name}:${ordered(whoOn(a, line.id)).join(",")}`)
    .sort();
  return `${people.join(",")}|${lines.join(";")}`;
}

export function blockingProblem(
  reading: BillReading,
  participantIds: string[],
  a: Assignment,
): string | null {
  if (participantIds.length === 0) {
    return "Chưa có ai trong nhóm. Thêm người bằng nút + ở trên.";
  }
  const fromReceipt = receiptBlocking(reading);
  if (fromReceipt !== null) return fromReceipt;

  const orphans = reading.lines.filter((line) => whoOn(a, line.id).length === 0);
  if (orphans.length === 1) {
    return `Món "${orphans[0].name}" chưa ai nhận. Tích ít nhất một người đã ăn món này.`;
  }
  if (orphans.length > 1) {
    return `${orphans.length} món chưa ai nhận. Tích ít nhất một người cho từng món.`;
  }

  const zeros = reading.lines.filter((line) => line.lineTotalVnd === 0);
  if (zeros.length === 1) {
    return `Món "${zeros[0].name}" đang 0đ. Quay lại màn trước để sửa giá hoặc xoá món.`;
  }
  if (zeros.length > 1) {
    return `${zeros.length} món đang 0đ. Quay lại màn trước để sửa giá hoặc xoá chúng.`;
  }
  return null;
}
