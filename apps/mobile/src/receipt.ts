/** What the reader said a bill contains, and what a person changed about it.
 *
 * Two halves, on purpose:
 *
 *   - the wire half speaks `POST /receipts/scan` exactly as
 *     `services/api/app/api/schemas.py` declares it, snake_case and all;
 *   - the editable half is what the screen holds while somebody corrects it.
 *
 * They are separate because the reading is evidence and the edit is a
 * decision. Keeping the first transcription next to the corrected value is
 * what lets the screen say "you changed this" instead of quietly presenting a
 * human number as something the machine read.
 *
 * Money here obeys the same three laws as the rest of the product. Every
 * amount is an integer of dong; there is no `Number(text)` anywhere in this
 * file, because `parseAmountVnd` in `packages/shared/money.mjs` is the one
 * parser that checks the digit string before it becomes a double. And nothing
 * here divides anything between people: this module produces the *bill*, and
 * the allocator on the server produces the split. A second division in
 * TypeScript is how two screens end up showing two numbers for one dinner.
 *
 * One thing this module deliberately does NOT do: reconcile. If the item lines
 * add up to 1.129.000 and the paper says 1.125.000, both numbers survive and
 * `totalGapVnd` reports the distance. Silently adjusting either one would erase
 * the single most useful signal a receipt reader can give -- that it misread a
 * digit somewhere, and a person should look.
 */
import { parseAmountVnd } from "../../../packages/shared/money.mjs";

/* ------------------------------------------------------------------ wire */

/** One line as the server sends it. Field names are the wire's, not ours.
 *
 * `ApiModel` sets `extra="forbid"` and declares no alias generator, so these
 * are snake_case on the wire and stay snake_case here. Renaming them at the
 * type level would hide the day the server changes one.
 */
export type ReceiptItemWire = {
  name: string;
  quantity: number;
  unit_price_vnd: number | null;
  line_total_vnd: number;
};

/** The body of a 200 from `POST /receipts/scan`. */
export type ReceiptScanWire = {
  items: ReceiptItemWire[];
  items_total_vnd: number;
  total_vnd: number | null;
  totals_agree: boolean | null;
  total_difference_vnd: number | null;
  confidence: number;
  warnings: string[];
};

/* -------------------------------------------------------------- editable */

/** One row of the bill, as the screen holds it while it is being corrected. */
export type BillLine = {
  /** Stable for the life of the reading.
   *
   * Not the array index. A row's identity has to survive deleting the row
   * above it, and a keyed-by-index list hands the deleted row's text to its
   * neighbour -- which on this screen means someone's food ends up priced as
   * someone else's.
   */
  id: string;
  name: string;
  quantity: number;
  lineTotalVnd: number;
  /**
   * Exactly what the reader transcribed, never written to after the scan.
   *
   * `null` for a line somebody added by hand. There is no transcription behind
   * such a line, and the first version of this said so with a sentinel value --
   * a `read.name` of `" "` that nothing could equal. That is how a stray NUL
   * byte ended up inside a dish name and got as far as the repo guard. A field
   * that means "there is no reading" should be the absence of a reading.
   */
  read: {
    name: string;
    quantity: number;
    lineTotalVnd: number;
  } | null;
};

export type BillReading = {
  lines: BillLine[];
  /**
   * The total printed on the paper, when the reader found one.
   *
   * Never recomputed and never corrected. It is the independent check on our
   * own arithmetic: the moment we make it agree with the lines, it stops being
   * able to disagree, and it was only ever useful because it could.
   */
  printedTotalVnd: number | null;
  /** The reader's own estimate of how legible the paper was, 0-100. */
  confidence: number;
  /** Sentences from the server about what it was unsure of. Shown, not hidden. */
  warnings: string[];
};

/* Which of the three fields a person has moved away from the reading.
 *
 * Per field rather than per row, because the screen marks the field. A row-
 * level flag could only say "something here changed", which on a row with a
 * name, a count and an amount is not enough to be worth saying. A hand-added
 * line has no reading at all, so every field of it counts as the person's. */
export function nameEdited(line: BillLine): boolean {
  return line.read === null || line.name !== line.read.name;
}

export function quantityEdited(line: BillLine): boolean {
  return line.read === null || line.quantity !== line.read.quantity;
}

export function totalEdited(line: BillLine): boolean {
  return line.read === null || line.lineTotalVnd !== line.read.lineTotalVnd;
}

/** Has a person touched this row since the scan? */
export function isEdited(line: BillLine): boolean {
  return nameEdited(line) || quantityEdited(line) || totalEdited(line);
}

export function editedCount(reading: BillReading): number {
  return reading.lines.filter(isEdited).length;
}

/** Turn a scan response into something a person can correct.
 *
 * Ids are minted from the position at scan time rather than from the name.
 * Two lines of "Pepsi" on one bill is ordinary, and an id built from the name
 * would collide on exactly that ordinary case.
 */
export function readingFromWire(wire: ReceiptScanWire): BillReading {
  return {
    lines: wire.items.map((item, index) => ({
      id: `mon-${index}`,
      name: item.name,
      quantity: item.quantity,
      lineTotalVnd: item.line_total_vnd,
      read: {
        name: item.name,
        quantity: item.quantity,
        lineTotalVnd: item.line_total_vnd,
      },
    })),
    printedTotalVnd: wire.total_vnd,
    confidence: wire.confidence,
    warnings: wire.warnings,
  };
}

/**
 * What the lines add up to, right now.
 *
 * Computed on every read rather than stored. A cached total on a screen whose
 * whole purpose is editing is a number that is wrong for one render, and one
 * render is all it takes for somebody to press "Tiếp tục".
 */
export function itemsTotalVnd(reading: BillReading): number {
  return reading.lines.reduce((sum, line) => sum + line.lineTotalVnd, 0);
}

/**
 * How far the paper sits from our arithmetic. Positive means the lines are short.
 *
 * Signed the same way round as the server's `total_difference_vnd`
 * (`total_vnd - items_total_vnd`), and measured against a live scan: a blurry
 * crop of the mockup bill came back `items_total_vnd: 963000`,
 * `total_vnd: 1125000`, `total_difference_vnd: 162000`. Two conventions for one
 * quantity would put a minus sign on the screen that the server never meant,
 * so there is one, and it is the server's.
 *
 * Recomputed rather than carried from the response, because the response
 * describes the reading before anybody corrected it. The gap is the whole
 * reason to correct anything, so it has to move as they type.
 *
 * `null` when the reader found no printed total. That is not agreement, and
 * rendering it as a tick would claim a check that never ran.
 */
export function totalGapVnd(reading: BillReading): number | null {
  if (reading.printedTotalVnd === null) return null;
  return reading.printedTotalVnd - itemsTotalVnd(reading);
}

/* ----------------------------------------------------------------- edits */

function replace(
  reading: BillReading,
  id: string,
  change: (line: BillLine) => BillLine,
): BillReading {
  return {
    ...reading,
    lines: reading.lines.map((line) => (line.id === id ? change(line) : line)),
  };
}

export function renameLine(reading: BillReading, id: string, name: string): BillReading {
  return replace(reading, id, (line) => ({ ...line, name }));
}

/** Why the app refused a number somebody typed. */
export type EditRefusal = "empty" | "not-a-number" | "too-large" | "not-positive";

export type EditResult =
  | { ok: true; reading: BillReading }
  | { ok: false; reason: EditRefusal };

/**
 * Set a quantity from typed text.
 *
 * Quantity goes through the money parser too, and that is not laziness: it is
 * the only parser here that rejects a digit string past the safe-integer range
 * instead of silently rounding it. A quantity of zero is refused rather than
 * accepted as "remove this" -- deleting a line is a different intent with a
 * different control, and inferring it from a typed 0 would delete a row while
 * someone was midway through typing 10.
 */
export function setQuantity(reading: BillReading, id: string, typed: string): EditResult {
  const parsed = parseAmountVnd(typed);
  if (!parsed.ok) return { ok: false, reason: parsed.reason };
  if (parsed.value <= 0) return { ok: false, reason: "not-positive" };
  return { ok: true, reading: replace(reading, id, (line) => ({ ...line, quantity: parsed.value })) };
}

/**
 * Set what this line costs, from typed text.
 *
 * Zero is allowed here and refused above. A comped dish really does cost
 * nothing, and a bill that cannot express that forces somebody to delete the
 * row -- which loses the fact that the dish was eaten, which is exactly what
 * the next screen needs in order to ask who ate it.
 */
export function setLineTotal(reading: BillReading, id: string, typed: string): EditResult {
  const parsed = parseAmountVnd(typed);
  if (!parsed.ok) return { ok: false, reason: parsed.reason };
  return {
    ok: true,
    reading: replace(reading, id, (line) => ({ ...line, lineTotalVnd: parsed.value })),
  };
}

/** Drop a line the reader invented, or one nobody ordered. */
export function removeLine(reading: BillReading, id: string): BillReading {
  return { ...reading, lines: reading.lines.filter((line) => line.id !== id) };
}

/**
 * Add a row the reader missed.
 *
 * Empty rather than prefilled, and `read: null` because nothing read it. That
 * makes it edited from birth, which is what the screen marks: claiming the
 * machine produced this line would be a lie told by a default value.
 */
export function addLine(reading: BillReading, id: string): BillReading {
  return {
    ...reading,
    lines: [...reading.lines, { id, name: "", quantity: 1, lineTotalVnd: 0, read: null }],
  };
}

/* --------------------------------------------------------------- refusal */

/**
 * Whether this reading may be sent on, and what to say when it may not.
 *
 * The bar is deliberately low. This screen's job is to let a person fix a
 * misread digit, not to audit their dinner, so a bill whose lines disagree
 * with the printed total still passes -- the gap is shown, and choosing to
 * carry on with it is a legitimate answer to a tip or a rounding line the
 * reader did not model. What does not pass is a bill that cannot be split at
 * all: no lines, or a nameless line that would reach the next screen as a
 * blank someone is asked to claim.
 */
export function blockingProblem(reading: BillReading): string | null {
  if (reading.lines.length === 0) {
    return "Chưa có món nào để chia. Chụp lại bill, hoặc thêm món bằng tay.";
  }
  const nameless = reading.lines.filter((line) => line.name.trim() === "").length;
  if (nameless > 0) {
    return nameless === 1
      ? "Một món chưa có tên. Đặt tên cho nó trước, vì màn sau sẽ hỏi ai đã ăn món này."
      : `${nameless} món chưa có tên. Đặt tên cho chúng trước, vì màn sau sẽ hỏi ai đã ăn từng món.`;
  }
  return null;
}
