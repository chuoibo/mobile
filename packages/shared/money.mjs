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
