/**
 * The invitation a link arrived with, held between the router and the screen.
 *
 * ## Why this is not a route param
 *
 * The obvious shape is `router.replace({ pathname: "/moi", params: { ma } })`.
 * That puts a bearer secret into navigation state: into the history stack, into
 * whatever the router logs, and into a crash report if one is ever sent. The
 * secret is single-use and spending it is irreversible -- once redeemed, the
 * row's digest is cleared and the person is locked out until a member rotates
 * it for them -- so it is worth keeping out of every place a string can be
 * copied to by accident.
 *
 * So the link hands it here and the screen takes it. It never becomes part of
 * an address.
 *
 * ## Why reading clears it
 *
 * A code that stayed would be offered again the next time somebody opened the
 * screen, after it had already been spent. That reads as "your invitation is
 * invalid" for a person who did nothing wrong. One read, then gone.
 */

let dangCho: string | null = null;

export function datLoiMoiDen(ma: string): void {
  dangCho = ma === "" ? null : ma;
}

/** Take the pending code, if any. Reading consumes it. */
export function layLoiMoiDen(): string | null {
  const ma = dangCho;
  dangCho = null;
  return ma;
}
