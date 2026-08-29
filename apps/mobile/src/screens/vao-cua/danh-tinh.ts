/** Turning a phone number somebody types into the person id the API stores.
 *
 * This is the whole of F01. It is kept out of the screen because the screen
 * unmounts and because none of what matters here is visual: two spellings of
 * one number must reach one account, two different numbers must never reach
 * the same one, and the digits must not leave the device.
 *
 * ## Why the id is derived rather than minted
 *
 * `PUT /people/{id}` names an id the caller already holds, and this app holds
 * no storage: there is no AsyncStorage, no SecureStore and no cookie in
 * `package.json`, so nothing survives a reload. A `crypto.randomUUID()` at the
 * sign-in button would therefore mint a *new* person on every launch -- the
 * same human would accumulate accounts, each with its own share of a dinner,
 * and "log in" would be a word for "lose everything". Deriving the id from the
 * number is what makes typing the same number twice arrive at the same person,
 * which is the only behaviour that makes the screen's own label true.
 *
 * ## What this does and does not protect
 *
 * The digits never reach the server. `PersonRegistrationRequest` has one field
 * and it is `display_name`, so there is no column for a phone number and this
 * file does not invent one; what crosses the wire is the derived id and a name
 * somebody chose to show. That is worth having and it is not privacy.
 *
 * Being blunt, because the alternative is a comment that flatters the code:
 * Vietnamese mobile numbers are a space of well under a billion, so anybody
 * holding an id and this file can enumerate that space offline and recover the
 * number. This derivation keeps the digits out of the database and out of the
 * logs. It is NOT a defence against someone who already has the id. When real
 * sessions arrive, the number moves server-side behind the login and this file
 * goes away with the header auth it was built on top of -- see `api/deps.py`,
 * which says the same thing about `X-Actor-ID`.
 *
 * Nothing here logs. `console.log(so)` in this file would put a real phone
 * number in a browser console during a demo, which is exactly the disclosure
 * the derivation exists to avoid.
 */

/** 64-bit mask. The hash below is written in `BigInt` because the arithmetic
 *  is 64-bit and doing it in doubles silently loses the low bits -- which is
 *  the failure that would collide two people onto one account. Hermes has had
 *  `BigInt` since React Native 0.70 and this runs on 0.86; it is called once,
 *  at a button press, so its cost is not worth a hand-rolled 32-bit version. */
const M64 = (1n << 64n) - 1n;

/** MurmurHash3's 64-bit finaliser.
 *
 * FNV-1a alone is not enough here and the reason is specific to this input.
 * Phone numbers differ from each other in one digit, and FNV-1a's avalanche
 * over near-identical short inputs is poor: neighbouring numbers come out as
 * neighbouring hashes. Feeding the result through `fmix64` is the standard
 * repair -- every input bit reaches every output bit. `tests/danh-tinh.test.mjs`
 * pins this by hashing a large block of consecutive numbers and asserting both
 * that none collide and that adjacent ones differ across roughly half their
 * bits.
 */
function fmix64(input: bigint): bigint {
  let z = input & M64;
  z = (z ^ (z >> 33n)) & M64;
  z = (z * 0xff51afd7ed558ccdn) & M64;
  z = (z ^ (z >> 33n)) & M64;
  z = (z * 0xc4ceb9fe1a85ec53n) & M64;
  z = (z ^ (z >> 33n)) & M64;
  return z;
}

function fnv1a64(bytes: Uint8Array, offset: bigint): bigint {
  let h = offset & M64;
  for (const byte of bytes) {
    h = (h ^ BigInt(byte)) & M64;
    h = (h * 0x100000001b3n) & M64;
  }
  return fmix64(h);
}

/** Two different starting constants, so the two 64-bit lanes are independent
 *  rather than two names for the same hash. The first is the published FNV-1a
 *  offset basis; the second is this product's own, and it is a salt in the
 *  sense that it separates these ids from any other FNV-1a in the world -- not
 *  in the sense that it is secret. It is in the repository. */
const LANE_A = 0xcbf29ce484222325n;
const LANE_B = 0x9ae16a3b2f90404fn;

function utf8(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

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
 * The person id for a number. Same number in, same id out, on every device.
 *
 * Version nibble `8` -- RFC 9562's "custom" version, which is what this is.
 * Claiming v4 would be a lie told to anybody reading a row in `people`, and
 * claiming v5 would be a lie about the digest. The variant nibble is forced
 * into `8..b` so the value is a well-formed UUID and Python's `UUID()` accepts
 * it at the route boundary.
 *
 * Throws on an unusable number rather than deriving from the raw text. A
 * fallback here would mint an id from " 0912 " that differs from the one for
 * "0912", which is the collision-by-whitespace this function exists to remove.
 */
export function idTuSo(raw: string): string {
  const so = chuanHoaSo(raw);
  if (so === null) {
    // The number itself is not in this message on purpose: it is thrown, and
    // a thrown message ends up in a console or a bug report.
    throw new Error("Số điện thoại không hợp lệ, không thể tạo danh tính.");
  }
  const bytes = utf8("ru-di:nguoi:" + so);
  const hex =
    fnv1a64(bytes, LANE_A).toString(16).padStart(16, "0") +
    fnv1a64(bytes, LANE_B).toString(16).padStart(16, "0");

  const variant = ((parseInt(hex[16] as string, 16) & 0x3) | 0x8).toString(16);
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    "8" + hex.slice(13, 16),
    variant + hex.slice(17, 20),
    hex.slice(20, 32),
  ].join("-");
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
