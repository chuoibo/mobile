/* rd-qa-02 · Does somebody else's name appear on this guest envelope?
 *
 * Lives in its own module so it can be self-checked. The privacy assertions in
 * `screen-vs-server.mjs` are the only thing standing between a guest link and
 * "Hà also owes 246.913đ", and a privacy assertion nobody ever watched go red
 * is decoration.
 *
 * Scope, deliberately: TEXT CONTENT only. The `>[^<]*` prefix pins the match to
 * the run of characters after a tag closes, so a name inside an attribute value
 * (`aria-label`, `title`, `href`) is NOT looked at by this detector. That gap is
 * recorded in README.md under "ô CHƯA quét", not silently passed.
 */

/** Names are literals today, but a leak detector must never be the thing that
 * throws on its own input. */
function escapeRegExp(source) {
  return source.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/* What counts as "still inside a word", written in Unicode rather than in
 * ASCII. `\b` was the wrong tool here twice over: it is blind to "Hà " (à is
 * not \w, so no boundary exists after it) AND it fires on "Hàn Quốc" (à->n IS a
 * \w transition, so \bHà\b matches a page where Hà never appears). Letters,
 * combining marks and digits are all word-interior; anything else -- space, ·,
 * `<`, punctuation -- ends the word. */
const WORD_INTERIOR = "\\p{L}\\p{M}\\p{N}_";

/**
 * True when `name` appears as a standalone word inside the rendered text of
 * `html` -- i.e. this page leaks that person.
 *
 * Both sides are normalised to NFC first: the server and the browser are each
 * free to emit "Hà" precomposed (U+00E0) or decomposed (a + U+0300), and a
 * detector that only understands one form goes quiet on the other.
 */
export function nameAppearsInText(html, name) {
  const needle = escapeRegExp(name.normalize("NFC"));
  const pattern = new RegExp(
    `>[^<]*(?<![${WORD_INTERIOR}])${needle}(?![${WORD_INTERIOR}])`,
    "u",
  );
  return pattern.test(html.normalize("NFC"));
}
