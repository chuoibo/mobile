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

/**
 * True when `name` appears as a standalone word inside the rendered text of
 * `html` -- i.e. this page leaks that person.
 */
export function nameAppearsInText(html, name) {
  const pattern = new RegExp(`>[^<]*\\b${escapeRegExp(name)}\\b`);
  return pattern.test(html);
}
