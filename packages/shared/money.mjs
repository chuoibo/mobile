/** Vietnamese money formatting, shared by every surface.
 *
 * Plain .mjs on purpose: the app imports it as TypeScript and the test runs it
 * under bare node, so there is exactly one implementation and the anti-drift
 * test is a real test rather than a promise.
 *
 * Deliberately not Intl.NumberFormat. Locale data varies by JS engine and by
 * Android build, and "82,000" on some phones against "82.000" in the link
 * would be a silent inconsistency in the one number this product exists to get
 * right. The rule is three digits, full stop. That is the whole rule.
 */

/**
 * @param {number} amountVnd integer dong, zero or more
 * @returns {string}
 */
export function formatVnd(amountVnd) {
  if (typeof amountVnd !== "number" || !Number.isInteger(amountVnd)) {
    throw new Error("AMOUNT_NOT_INTEGER");
  }
  if (amountVnd < 0) {
    throw new Error("NEGATIVE_AMOUNT");
  }
  const digits = String(amountVnd);
  let out = "";
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) out += ".";
    out += digits[i];
  }
  return out;
}

/** One thousand billion dong. Far above any group bill, far below 2^53. */
// repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
export const MAX_AMOUNT_VND = 1_000_000_000_000;

const MAX_DIGITS = String(MAX_AMOUNT_VND).length;

/**
 * Read a VND amount out of what a person typed, without ever guessing.
 *
 * The mobile app used to do `Number(typed.replace(/\D/g, ""))`. Two things go
 * wrong there. JavaScript numbers are doubles, so a digit string past
 * `Number.MAX_SAFE_INTEGER` is silently rounded to a different number --
 * repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
 * `Number("9007199254740993")` is `9007199254740992`, and `Number.isInteger`
 * still returns true, so the obvious guard never fires. And nothing rejected an
 * amount outside any sane range, so a typo could ride all the way into a
 * proposal.
 *
 * The bound is therefore checked on the DIGIT STRING, before any conversion.
 * By the time a value becomes a number here, a double already represents it
 * exactly.
 *
 * @param {string} typed
 * @returns {{ok: true, value: number} | {ok: false, reason: "empty" | "not-a-number" | "too-large"}}
 */
export function parseAmountVnd(typed) {
  if (typeof typed !== "string") {
    return { ok: false, reason: "not-a-number" };
  }
  const trimmed = typed.trim();
  if (trimmed === "") {
    return { ok: false, reason: "empty" };
  }
  // Grouping separators people actually type are noise. Any other character
  // means this is not a plain amount, and stripping it would invent intent.
  if (!/^[\d.,\s]+$/.test(trimmed)) {
    return { ok: false, reason: "not-a-number" };
  }
  const digits = trimmed.replace(/[.,\s]/g, "");
  if (digits === "") {
    return { ok: false, reason: "not-a-number" };
  }
  const significant = digits.replace(/^0+/, "");
  if (significant === "") {
    return { ok: true, value: 0 };
  }
  const tooLong = significant.length > MAX_DIGITS;
  const tooBig = significant.length === MAX_DIGITS && significant > String(MAX_AMOUNT_VND);
  if (tooLong || tooBig) {
    return { ok: false, reason: "too-large" };
  }
  return { ok: true, value: Number(significant) };
}
