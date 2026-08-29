/** F05. The code a person shows so somebody else can add them.
 *
 * Building and reading the payload live here rather than in a screen, for the
 * same reason `danh-tinh.ts` does: none of what matters is visual. What is in
 * the code, what is deliberately *not* in it, and what a reader is willing to
 * accept back are all rules, and rules that live inside a component are rules
 * nobody can test without mounting a screen.
 *
 * ## What the code carries, and the one thing it must never carry
 *
 * A person id and a display name. Not a telephone number.
 *
 * That is not a preference. `danh-tinh.ts` derives the id from the number
 * precisely so the digits stay off the wire, and it says plainly that the id
 * is *not* a defence against somebody who already holds it -- Vietnamese
 * mobile numbers are a small enough space to enumerate offline. Printing the
 * number into a square that gets photographed across a table, screenshotted
 * and forwarded would hand over directly what that whole derivation exists to
 * withhold. The name is different in kind: it is the thing the person is
 * already showing everyone in the group, and a profile without one is a UUID
 * being asked to make a friend.
 *
 * ## Why the payload is a fragment link
 *
 * The spec draws `ru-di.app/u/kiet`. That domain is not registered and this
 * build is not behind it, so encoding it would produce a square that scans
 * beautifully into a dead link -- the most convincing kind of broken.
 *
 * So the payload is built against wherever the app is actually being served,
 * with the person in the *fragment*: `<origin>/#ban=<id>&tenban=<name>`. A
 * static export answers `/` with `index.html`, `lien-ket.ts` reads the
 * fragment, and a phone's own camera app -- no in-app scanner needed -- opens
 * the running app on the friend's card. Off the web there is no `location`,
 * so it falls back to the spec's shape and says so.
 *
 * The reader is deliberately more forgiving than the writer: it accepts the
 * fragment form, the spec's `/u/<id>` path form, and a bare id pasted on its
 * own. Somebody reading a code aloud across a table is a real thing that
 * happens, and refusing the id by itself would make the feature depend on a
 * URL surviving a copy-paste.
 */

/** A person, as read off a code. Everything a friend card needs and no more. */
export type TheBan = {
  personId: string;
  /** Null when the code carried an id but no name -- which is what a bare id
   *  pasted by hand looks like. The screen renders the absence rather than
   *  inventing a placeholder that a person might mistake for their friend. */
  ten: string | null;
};

/** Canonical spelling of the ids this product mints.
 *
 * Not a version-specific pattern. `idTuSo` deliberately stamps version nibble
 * `8` (RFC 9562 "custom") while `idNgauNhien` produces a v4, and both are real
 * people; a regex demanding `4` here would refuse every account that signed in
 * with a phone number. Shape and hex are what matter, and the server's
 * `UUID()` is the thing that finally decides. */
const DANG_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** The domain the spec draws. Used only when there is no page to be served
 *  from -- on a phone. Stated as unregistered wherever it is shown. */
export const TEN_MIEN_SPEC = "https://ru-di.app";

/** Where this build is actually reachable, or null off the web. */
function goc(): string | null {
  const loc = (globalThis as { location?: { origin?: string } }).location;
  const origin = loc?.origin;
  // `about:blank` and `file://` both produce "null" as a *string* here, which
  // would otherwise be pasted into a link as if it were a host.
  if (!origin || origin === "null") return null;
  return origin;
}

/**
 * The payload for this person's square.
 *
 * Throws on an id this product could not have minted. A code is scanned once
 * and then acted on, so a malformed one has to fail where somebody can still
 * be told -- not on the far side of the camera, as an invite for a person who
 * does not exist.
 */
export function linkMaBan(personId: string, ten: string, base?: string): string {
  if (!DANG_ID.test(personId)) {
    throw new Error("Mã cá nhân chưa dựng được: id không đúng dạng.");
  }
  const nen = base ?? goc() ?? TEN_MIEN_SPEC;
  const params = new URLSearchParams({ ban: personId, tenban: ten.trim() });
  return `${nen}/#${params.toString()}`;
}

/** True when this build can produce a code that actually opens something. */
export function maMoDuocApp(): boolean {
  return goc() !== null;
}

/**
 * Read a code back, from any of the three shapes above.
 *
 * Returns null rather than guessing. A code that half-parses must not become
 * a friend request: the whole act this feeds is "add this person", and the
 * cost of getting it wrong is a stranger in a group that splits money.
 *
 * The name is length-capped on the way in for the same reason the server caps
 * it -- a code is attacker-supplied text, and 200 characters is what
 * `PersonRegistrationRequest` accepts. Longer is refused outright instead of
 * silently truncated into a different person's name.
 */
export function docMaBan(text: string): TheBan | null {
  const raw = text.trim();
  if (raw === "") return null;

  if (DANG_ID.test(raw)) return { personId: raw.toLowerCase(), ten: null };

  // Fragment form, with or without an origin in front of it.
  const bam = raw.indexOf("#");
  if (bam !== -1) {
    const params = new URLSearchParams(raw.slice(bam + 1));
    const id = params.get("ban");
    if (id !== null && DANG_ID.test(id)) {
      return { personId: id.toLowerCase(), ten: tenHopLeTuMa(params.get("tenban")) };
    }
    return null;
  }

  // The spec's path form: `<anything>/u/<id>` with an optional `?ten=`.
  const duong = raw.split("?");
  const truoc = duong[0] ?? "";
  const doan = truoc.split("/").filter(Boolean);
  const cuoi = doan[doan.length - 1];
  const ke = doan[doan.length - 2];
  if (ke === "u" && cuoi !== undefined && DANG_ID.test(cuoi)) {
    const query = new URLSearchParams(duong[1] ?? "");
    return { personId: cuoi.toLowerCase(), ten: tenHopLeTuMa(query.get("ten")) };
  }

  return null;
}

/** A name off a code is only a name if the server would accept it. */
function tenHopLeTuMa(raw: string | null): string | null {
  if (raw === null) return null;
  const t = raw.trim();
  if (t.length < 1 || t.length > 200) return null;
  return t;
}
