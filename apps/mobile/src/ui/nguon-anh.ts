/** Which image addresses this app is willing to fetch, and why almost none.
 *
 * An image URL is not like the other strings the server sends. Every other
 * field is drawn; this one is *dialled*. The moment a `<Image>` receives it the
 * device opens a connection to whoever owns that host, before anybody has
 * tapped anything, and that connection carries the reader's IP and the exact
 * moment they opened the screen.
 *
 * Today `image_url` on a memory and on a message, and `photo_url` on a place,
 * are strings the *client* declares. The server checks their length and nothing
 * else. So the address is chosen by whoever wrote the row, which in a shared
 * group is any member:
 *
 *     A writes image_url pointing at a host A controls
 *     -> B opens the group -> B's phone fetches it
 *     -> A learns B read it, when, and from which IP.
 *
 * That was harmless while the app rendered no images at all. This branch is the
 * one that turns `<Image>` on, so it is also the one that has to close it.
 *
 * The rule is deliberately narrow: an address is fetchable only if it lives on
 * the same API this app is already talking to. Anything else renders the
 * caller's stand-in and issues no request whatsoever. Refusing to *fetch* is
 * the point -- refusing to *display* would still leak, because the leak is the
 * request, not the pixels.
 *
 * ## Why string comparison and not `new URL()`
 *
 * A parser invites the mistake of comparing a parsed `host` while the fetch
 * uses the original string, and any disagreement between the two parsers -- the
 * one here and the one inside the image loader -- is a bypass. Matching the
 * literal prefix the loader will use removes that gap. The separator does the
 * real work; see the two cases below, both of which start with the base string.
 *
 * ## What this file is not
 *
 * Not a permission check. It says "this address belongs to our API", not "this
 * reader may see this photo" -- only the server knows that, and it enforces it
 * (403 for a non-member). Nor does it make an unvalidated `image_url` safe to
 * store: this is the second layer, and the server owning the first was asked
 * for separately.
 *
 * Pure on purpose: no React, no `fetch`, no module-level environment read. The
 * base is passed in so that both callers -- the place parser and the `Anh`
 * frame -- apply one rule instead of two that drift.
 */

/**
 * Resolve a server-supplied image address to something safe to fetch.
 *
 * @param raw  Whatever arrived on the wire. Any type: callers hand this straight
 *             from parsed JSON, so a number or `null` is a normal input, not a bug.
 * @param goc  Base URL of the API this app talks to, e.g. `http://localhost:8099`.
 * @returns    An absolute URL on `goc`, or `null` when the address must not be
 *             fetched. `null` is not an error state; it is the ordinary answer
 *             for "no photo", and callers already draw a stand-in for it.
 */
export function nguonAnhAnToan(raw: unknown, goc: string): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim();
  if (s === "") return null;

  // Control characters and inner whitespace are smuggling tools, not parts of a
  // real address: a newline splits headers, and a tab is ignored by some URL
  // parsers but not others, which is exactly the disagreement to avoid. Nothing
  // legitimate the server sends contains them, so failing closed costs nothing.
  if (/[\u0000-\u0020\u007f]/.test(s)) return null;

  // A trailing slash on the configured base would otherwise produce `//` in the
  // middle of the path, which some servers treat as a different resource.
  const base = goc.replace(/\/+$/, "");

  if (s.startsWith("/")) {
    // `//host/x.png` opens with a slash and reads as relative to a human, but a
    // browser resolves it as "same scheme, DIFFERENT host". It is the classic
    // way past a gate that only checks the first character. `/\host/x.png` is
    // the same trick with the separator browsers also accept.
    if (s[1] === "/" || s[1] === "\\") return null;
    return base + s;
  }

  // Absolute. The `/` after the base is doing the load-bearing work here, and
  // both of the cases it stops begin with the base string verbatim:
  //
  //   http://localhost:8099.evil.example/x.png   -> host is evil.example
  //   http://localhost:8099 followed by "@" then evil.example/x.png
  //                                              -> everything before the "@"
  //                                                 is userinfo, so the real
  //                                                 host is evil.example
  //
  // (The second is spelled out rather than written literally because the
  // literal form is an email address to the repo guard, which is correct of it.)
  //
  // Requiring the separator means the next character can only be a path.
  if (s.startsWith(base + "/")) return s;

  return null;
}
