/** What the entry door can decide about a telephone number without asking.
 *
 * This is the client half of F01, and it is deliberately the smaller half. The
 * id itself is no longer minted here: `layIdTuSo` in `cong-api.ts` asks the
 * server for it, because the derivation is now keyed and a key the app holds
 * is not a key.
 *
 * ## Why the derivation left this file (bug-140342)
 *
 * It used to be FNV-1a through MurmurHash3's finaliser, right here, and every
 * property it was tested for held. 20,000 consecutive numbers gave 20,000
 * distinct ids; numbers one digit apart came out half a digest apart. What it
 * was never tested for is that an id cannot be turned back into its number,
 * and that is a different property: `GET /contexts/{id}/members` hands every
 * member's `person_id` to every member, and Vietnamese mobile numbers are a
 * space of about 5x10^8. Enumerate it and the ids match.
 *
 * That is not a worry, it is a measurement. Against the code that used to sit
 * in this file: 257,316 candidates per second in Node on one core, and a
 * number recovered from its id in 29.75 seconds. QA measured the same thing in
 * Python and put a full sweep at about an hour, or seconds in C.
 *
 * No amount of choosing a better hash fixes that while every input to it is in
 * the repository. Only a secret the attacker does not hold does, and the only
 * place this product has one is the server -- see
 * `services/api/app/api/person_identity.py` for the whole argument, including
 * what the move costs.
 *
 * ## What is left here, and why it is still worth having
 *
 * `chuanHoaSo` still runs on the device, and the server runs the identical
 * rule. That is not duplication for its own sake: the refusal has to be
 * explainable while somebody is still typing, and a round trip to be told
 * "that is a landline" is a round trip. The server's copy is the one that
 * decides; this one only lets the button stay off.
 *
 * Nothing here logs. `console.log(so)` in this file would put a real phone
 * number in a browser console during a demo.
 */

/**
 * The canonical spelling of a Vietnamese mobile number, or null.
 *
 * Canonical is `84` followed by nine digits. Everything a person actually
 * types collapses onto that: a trunk zero, a `+84`, a bare `84`, and any
 * mixture of spaces, dots, dashes and brackets between the digits all describe
 * one telephone and so must reach one account. Without this, the same person
 * typing their own number with a space one day and without it the next would
 * arrive at two different derived ids and two different halves of their own
 * money. `tests/danh-tinh.test.mjs` pins six spellings onto one id.
 *
 * No example number appears in this comment on purpose: `repo_guard.py`
 * refuses digit runs that look like telephone numbers, and it cannot tell an
 * illustrative one from a real one. The test file builds its fixtures from
 * short pieces for the same reason.
 *
 * Deliberately strict about the leading digit. Vietnamese mobile prefixes are
 * `03`, `05`, `07`, `08` and `09` after the trunk zero, so a nine-digit
 * remainder must start with 3, 5, 7, 8 or 9. Landlines and short codes are
 * refused rather than accepted-and-derived: an id derived from something that
 * is not a mobile number is an account nobody can log back into, and the
 * refusal has to happen where it can still be explained to the person typing.
 */
export function chuanHoaSo(raw: string): string | null {
  // Strip only the separators people use for legibility. Letters are not
  // stripped -- they make the input invalid, and quietly deleting them would
  // turn a typo into a different person's account.
  const goi = raw.replace(/[\s.\-()]/g, "");
  if (goi === "") return null;

  let so: string;
  if (goi.startsWith("+84")) so = goi.slice(3);
  else if (goi.startsWith("84")) so = goi.slice(2);
  else if (goi.startsWith("0")) so = goi.slice(1);
  else so = goi;

  // Nine digits, mobile prefix. Checked after the trunk/country prefix is
  // removed so all four spellings meet the same rule in one place.
  if (!/^[35789]\d{8}$/.test(so)) return null;
  return "84" + so;
}

/** True when this reads as a Vietnamese mobile number. */
export function soHopLe(raw: string): boolean {
  return chuanHoaSo(raw) !== null;
}

/**
 * A person id for somebody who is not holding this phone.
 *
 * F03 adds a friend by name, and a name is not an identity: two people called
 * Nam are two people, and `participants.ts` already carries the scar from
 * treating a label as an id. So a friend added here gets a random id, not one
 * derived from their name.
 *
 * The consequence is worth stating rather than discovering: the friend added
 * this way and the same friend later signing in with their own number are two
 * rows in `people`. Joining them needs a claim step -- the invited person
 * proving the number is theirs -- which is `invite_person_stub_claim` in
 * `app/domain/permissions.py`, already in the table and not yet routed. Until
 * that exists this app can add a friend or it can be a friend, and it cannot
 * merge the two, which is why the invite screen asks for a number when there
 * is one rather than defaulting to a stub.
 */
export function idNgauNhien(): string {
  const c = globalThis.crypto as { randomUUID?: () => string } | undefined;
  if (c?.randomUUID) return c.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** What a display name has to be before it is worth sending.
 *
 * The server asks for 1..200 characters and would refuse the rest, but a
 * refusal that arrives as an HTTP status is a round trip and a sentence about
 * the app being broken. Checked here so the button can simply stay off. */
export function tenHopLe(ten: string): boolean {
  const t = ten.trim();
  return t.length >= 1 && t.length <= 200;
}

/** Initials for the avatar, from a display name. No photographs of real
 *  people go into this repository, so the monogram is the avatar. */
export function chuDau(ten: string): string {
  const parts = ten.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const last = parts[parts.length - 1] as string;
  return [...last][0]?.toUpperCase() ?? "?";
}
