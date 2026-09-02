/**
 * Draft display of who-owes-whom on the RuDi fixture screens.
 *
 * This is not the product allocator. `src/api.ts` must not grow a second
 * split: the server allocator (41 golden vectors) is the only one that may
 * confirm a ledger. Functions here exist so settlement and finance cannot
 * print three unrelated constants while calling the result "sổ cái".
 *
 * Integer dong only. Division is exact integer quotient via remainder:
 * `(amount - (amount % n)) / n`. No float, no Decimal.
 */

export type DraftLine = {
  amount: number;
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

/** Exact integer quotient of two positive integers. */
export function dongQuotient(amount: number, people: number): number {
  assertDong(amount, "amount");
  if (!Number.isInteger(people) || people <= 0) {
    throw new DraftMoneyError(`people must be a positive integer, got ${String(people)}`);
  }
  return (amount - (amount % people)) / people;
}

/**
 * Split one line across N people. Base share is the integer quotient;
 * the remainder of `amount % n` dong goes to the first remainder people
 * (one extra each). Sum of the returned array is exactly `amount`.
 */
export function splitLine(amount: number, people: number): number[] {
  const base = dongQuotient(amount, people);
  const remainder = assertDong(amount, "amount") % people;
  const shares: number[] = [];
  for (let i = 0; i < people; i += 1) {
    shares.push(base + (i < remainder ? 1 : 0));
  }
  return shares;
}

export function lineTotal(lines: readonly { amount: number }[]): number {
  let total = 0;
  for (const line of lines) {
    total += assertDong(line.amount, "line amount");
  }
  return total;
}

/** Per-person consumption of the given lines. Length === personCount. */
export function sharesByPerson(lines: readonly DraftLine[], personCount: number): number[] {
  if (!Number.isInteger(personCount) || personCount <= 0) {
    throw new DraftMoneyError(`personCount must be a positive integer, got ${String(personCount)}`);
  }
  const shares = Array.from({ length: personCount }, () => 0);
  for (const line of lines) {
    const amount = assertDong(line.amount, "line amount");
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
    const parts = splitLine(amount, unique.length);
    for (let i = 0; i < unique.length; i += 1) {
      shares[unique[i]] += parts[i];
    }
  }
  return shares;
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

export function draftPicture(input: {
  billLines: readonly DraftLine[];
  otherLines: readonly DraftLine[];
  personCount: number;
  collectorIndex: number;
}): DraftPicture {
  const billTotal = lineTotal(input.billLines);
  const otherTotal = lineTotal(input.otherLines);
  const shares = sharesByPerson(input.billLines, input.personCount);
  const otherShares = sharesByPerson(input.otherLines, input.personCount);
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
