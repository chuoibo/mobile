/**
 * Draft display of who-owes-whom on the RuDi fixture screens.
 *
 * This is not the product allocator. The server's `app/domain/allocator.py`
 * holds the only split that may confirm a ledger, and its 41 golden vectors
 * are the contract. What this file exists for is narrower: settlement and
 * finance must not print three unrelated constants while calling the result
 * "sổ cái".
 *
 * ## Why this mirrors the server's rounding instead of picking its own
 *
 * The first version of this file rounded per line and handed the remainder to
 * whoever appeared first in the array. The server rounds ONCE per expense, by
 * largest remainder, tie-broken by `(-remainder, advancer first, id bytes)` --
 * `allocator.py:254-267`. Both rules keep money law 2 (Σ allocation = total),
 * so both look correct on a screen and in a sum. They disagree about WHO takes
 * the leftover đồng, and they disagree about the total per person whenever a
 * bill has more than one line, because summing per-line floors is not the same
 * arithmetic as flooring one sum.
 *
 * That disagreement is invisible until Pha B confirms an expense, and then the
 * number a person already read moves by a few đồng with nothing on screen to
 * explain it. So this file runs the server's algorithm rather than an algorithm
 * that merely also adds up.
 *
 * ## Integer đồng, and how exactness survives without `Fraction`
 *
 * Python has `Fraction`; JavaScript does not, and `/` here would be the float
 * money law 1 forbids. Instead every exact share is carried as an integer
 * numerator over one common denominator -- the lcm of the line headcounts --
 * so the arithmetic before the single rounding point is exact integer
 * arithmetic. `assertSafe` refuses the numbers rather than letting a numerator
 * drift past 2^53 and start lying quietly.
 */

export type DraftLine = {
  amount: number;
  /** Indexes into the roster passed alongside. Duplicates are ignored. */
  personIndexes: readonly number[];
};

export class DraftMoneyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DraftMoneyError";
  }
}

function assertDong(value: number, label: string): number {
  if (!Number.isInteger(value) || value < 0) {
    throw new DraftMoneyError(`${label} must be a non-negative integer dong, got ${String(value)}`);
  }
  return value;
}

/** Exactness is only exact while the integers stay exact. */
function assertSafe(value: number, label: string): number {
  if (!Number.isSafeInteger(value)) {
    throw new DraftMoneyError(`${label} left the exact integer range: ${String(value)}`);
  }
  return value;
}

function gcd(a: number, b: number): number {
  let x = a;
  let y = b;
  while (y !== 0) {
    const t = x % y;
    x = y;
    y = t;
  }
  return x;
}

function lcm(a: number, b: number): number {
  return assertSafe((a / gcd(a, b)) * b, "common denominator");
}

/** UTF-8 byte order, matching `participant.encode("utf-8")` in `rank`. */
const UTF8 = new TextEncoder();

function compareIdBytes(left: string, right: string): number {
  const a = UTF8.encode(left);
  const b = UTF8.encode(right);
  const shared = Math.min(a.length, b.length);
  for (let i = 0; i < shared; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

function uniqueIndexes(line: DraftLine, personCount: number): number[] {
  const unique: number[] = [];
  for (const index of line.personIndexes) {
    if (!Number.isInteger(index) || index < 0 || index >= personCount) {
      throw new DraftMoneyError(`person index ${String(index)} is outside 0..${personCount - 1}`);
    }
    if (!unique.includes(index)) unique.push(index);
  }
  if (unique.length === 0) {
    throw new DraftMoneyError("every line must be assigned to at least one person");
  }
  return unique;
}

export function lineTotal(lines: readonly { amount: number }[]): number {
  let total = 0;
  for (const line of lines) {
    total += assertDong(line.amount, "line amount");
  }
  return assertSafe(total, "line total");
}

/**
 * Exact per-person consumption, as integer numerators over one denominator.
 *
 * The mirror of `_exact_shares` in `allocator.py`, restricted to the one shape
 * the fixture screens use: whole lines, each shared equally by the people
 * assigned to it. No discounts, no surcharges -- "Phí phục vụ" is a line
 * everybody is on, not a surcharge, so it needs no separate stage.
 */
function exactShares(
  lines: readonly DraftLine[],
  personCount: number,
): { numerators: number[]; denominator: number } {
  let denominator = 1;
  for (const line of lines) {
    denominator = lcm(denominator, uniqueIndexes(line, personCount).length);
  }
  const numerators = Array.from({ length: personCount }, () => 0);
  for (const line of lines) {
    const amount = assertDong(line.amount, "line amount");
    const people = uniqueIndexes(line, personCount);
    const perPerson = assertSafe((amount * denominator) / people.length, "exact share numerator");
    for (const index of people) {
      numerators[index] = assertSafe(numerators[index] + perPerson, "exact share numerator");
    }
  }
  return { numerators, denominator };
}

/**
 * Largest remainder, the only rounding point -- `allocator.py:254-267`.
 *
 * The advancer wins ties only. A larger remainder always beats the advancer,
 * so "wins the tie-break" is not a global priority; winning means taking the
 * extra đồng, so the person who fronted the money absorbs the rounding.
 */
function apportion(
  total: number,
  numerators: readonly number[],
  denominator: number,
  personIds: readonly string[],
  advancerIndex: number | null,
): number[] {
  const floors = numerators.map((numerator) => Math.floor(numerator / denominator));
  const remainders = numerators.map((numerator, i) => numerator - floors[i] * denominator);
  const deficit = total - floors.reduce((sum, value) => sum + value, 0);
  if (deficit < 0 || deficit > numerators.length) {
    // Unreachable while `exactShares` sums to `total`. Kept because a silent
    // violation here would print allocations that do not sum to the bill.
    throw new DraftMoneyError(`apportionment deficit ${String(deficit)} is out of range`);
  }
  const ranked = numerators.map((_, i) => i).sort((left, right) => {
    if (remainders[left] !== remainders[right]) return remainders[right] - remainders[left];
    const leftIsAdvancer = advancerIndex !== null && left === advancerIndex;
    const rightIsAdvancer = advancerIndex !== null && right === advancerIndex;
    if (leftIsAdvancer !== rightIsAdvancer) return leftIsAdvancer ? -1 : 1;
    return compareIdBytes(personIds[left], personIds[right]);
  });
  const gainers = new Set(ranked.slice(0, deficit));
  return floors.map((value, i) => value + (gainers.has(i) ? 1 : 0));
}

/**
 * Per-person consumption of the given lines. Length === `personIds.length`.
 *
 * `advancerIndex` is who fronted the money for these lines, and it is required
 * rather than optional: leaving it out would silently change which person the
 * leftover đồng lands on, which is the exact difference this file exists to
 * remove. Pass `null` only when nobody fronted anything.
 */
export function sharesByPerson(
  lines: readonly DraftLine[],
  personIds: readonly string[],
  advancerIndex: number | null,
): number[] {
  if (personIds.length === 0) {
    throw new DraftMoneyError("personIds must name at least one person");
  }
  if (
    advancerIndex !== null &&
    (!Number.isInteger(advancerIndex) || advancerIndex < 0 || advancerIndex >= personIds.length)
  ) {
    throw new DraftMoneyError(`advancerIndex ${String(advancerIndex)} is out of range`);
  }
  const total = lineTotal(lines);
  const { numerators, denominator } = exactShares(lines, personIds.length);
  return apportion(total, numerators, denominator, personIds, advancerIndex);
}

export type DraftTransfer = {
  fromIndex: number;
  amount: number;
};

/**
 * Collector paid the bill. Everyone else owes their consumption share.
 * Collector's own share is not a transfer.
 */
export function transfersToCollector(
  shares: readonly number[],
  collectorIndex: number,
): DraftTransfer[] {
  if (!Number.isInteger(collectorIndex) || collectorIndex < 0 || collectorIndex >= shares.length) {
    throw new DraftMoneyError(`collectorIndex ${String(collectorIndex)} is out of range`);
  }
  const transfers: DraftTransfer[] = [];
  for (let i = 0; i < shares.length; i += 1) {
    if (i === collectorIndex) continue;
    const amount = assertDong(shares[i], `share[${i}]`);
    if (amount > 0) transfers.push({ fromIndex: i, amount });
  }
  return transfers;
}

export function collectorReceives(shares: readonly number[], collectorIndex: number): number {
  const own = assertDong(shares[collectorIndex], "collector share");
  let total = 0;
  for (const share of shares) total += assertDong(share, "share");
  return total - own;
}

export type DraftPicture = {
  billTotal: number;
  otherTotal: number;
  tripTotal: number;
  shares: number[];
  otherShares: number[];
  spent: number[];
  transfers: DraftTransfer[];
  collectorReceives: number;
};

/**
 * The one picture settlement and finance both read.
 *
 * Two buckets, apportioned separately, because they are two expenses: the Xóm
 * Lèo bill the collector fronted, and the rest of the trip. Rounding once per
 * expense is what the server does; rounding once across both would be a third
 * arithmetic that matches neither.
 */
export function draftPicture(input: {
  billLines: readonly DraftLine[];
  otherLines: readonly DraftLine[];
  personIds: readonly string[];
  collectorIndex: number;
}): DraftPicture {
  const billTotal = lineTotal(input.billLines);
  const otherTotal = lineTotal(input.otherLines);
  const shares = sharesByPerson(input.billLines, input.personIds, input.collectorIndex);
  // Nobody fronted the homestay and the petrol in this fixture, so there is no
  // advancer to absorb the rounding on that bucket.
  const otherShares = sharesByPerson(input.otherLines, input.personIds, null);
  const spent = shares.map((share, i) => share + otherShares[i]);
  const transfers = transfersToCollector(shares, input.collectorIndex);
  return {
    billTotal,
    otherTotal,
    tripTotal: billTotal + otherTotal,
    shares,
    otherShares,
    spent,
    transfers,
    collectorReceives: collectorReceives(shares, input.collectorIndex),
  };
}
