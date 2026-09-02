/**
 * Turning the RuDi session into bytes, and back, without trusting the bytes.
 *
 * ## Why the reading half is this careful
 *
 * What comes back off the disk is not this build's data. It is whatever some
 * earlier build wrote, possibly half-written, possibly from a version of the
 * app that shaped `assignments` differently. And `assignments` is not a
 * cosmetic field: it feeds `draftPicture`, which throws `DraftMoneyError` on a
 * person index outside the roster. A blob with one bad index would crash the
 * settlement screen on launch, with no way for the person to get past it --
 * every cold start would land on the same crash.
 *
 * So nothing is cast. Every field is checked against the shape the seed has,
 * and a field that fails is REPLACED BY THE SEED rather than rejected wholesale.
 * A corrupt slot loses one slot; it does not lose the trip, and it does not
 * take the app down.
 *
 * ## Why this file imports nothing
 *
 * `AsyncStorage` and `SecureStore` are native modules: importing either one
 * pulls in a `requireNativeModule` that has no answer under bare `node`, so a
 * file that touches them cannot be compiled into `tsconfig.test.json` and cannot
 * be tested without a device. The device is exactly where a validator is
 * hardest to exercise with bad input.
 *
 * Everything that can be WRONG therefore lives here, as pure functions over a
 * string, and `src/rudi/kho.ts` is the four-line shim that owns the platform.
 */

/** Bump when the stored shape changes. An older blob is dropped, not migrated. */
export const PHIEN_BAN_LUU = 1;

export type SlotLichTrinh = {
  time: string;
  title: string;
  icon: string;
  color: string;
  placeId?: string;
};

export type NgayLichTrinh = {
  day: string;
  items: SlotLichTrinh[];
};

/**
 * The part of the session that outlives the process.
 *
 * Deliberately NOT everything. `enteredAsDemo` is a fact about how this launch
 * started, `itineraryEditing` / `profileNotice` / `inboxOpen` are open panels.
 * Restoring those would reopen a sheet somebody closed, days later, with no
 * action of theirs in between.
 */
export type PhienLuuDuoc = {
  displayName: string;
  bio: string;
  interests: string[];
  vibes: string[];
  savedPlaceIds: string[];
  itinerary: NgayLichTrinh[];
  tripName: string;
  destination: string;
  startDate: string;
  endDate: string;
  selectedMemberIds: string[];
  aiSuggest: boolean;
  chatMessages: string[];
  voteChoice: number | null;
  voteConfirmed: boolean;
  assignments: number[][];
  paidFromIndexes: number[];
  remindedPending: boolean;
  checkedInIds: string[];
  locationSharing: boolean;
  receiptPicked: boolean;
};

const KHOA_CHUOI = [
  "displayName",
  "bio",
  "tripName",
  "destination",
  "startDate",
  "endDate",
] as const;

const KHOA_MANG_CHUOI = [
  "interests",
  "vibes",
  "savedPlaceIds",
  "selectedMemberIds",
  "chatMessages",
  "checkedInIds",
] as const;

const KHOA_BOOL = ["aiSuggest", "voteConfirmed", "remindedPending", "locationSharing", "receiptPicked"] as const;

function laChuoi(value: unknown): value is string {
  return typeof value === "string";
}

function laMangChuoi(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(laChuoi);
}

/** A person index the roster can actually resolve. */
function laChiSoNguoi(value: unknown, soNguoi: number): value is number {
  return Number.isInteger(value) && (value as number) >= 0 && (value as number) < soNguoi;
}

function locLichTrinh(value: unknown, iconChoPhep: ReadonlySet<string>): NgayLichTrinh[] | null {
  if (!Array.isArray(value)) return null;
  const ngay: NgayLichTrinh[] = [];
  for (const raw of value) {
    if (typeof raw !== "object" || raw === null) return null;
    const day = (raw as { day?: unknown }).day;
    const items = (raw as { items?: unknown }).items;
    if (!laChuoi(day) || !Array.isArray(items)) return null;
    const slots: SlotLichTrinh[] = [];
    for (const item of items) {
      if (typeof item !== "object" || item === null) return null;
      const { time, title, icon, color, placeId } = item as Record<string, unknown>;
      if (!laChuoi(time) || !laChuoi(title) || !laChuoi(icon) || !laChuoi(color)) return null;
      // An icon name this build does not have renders as an empty box. Held to
      // the set the seed itself uses rather than to "is a string", so a blob
      // written by a build with a different icon set degrades to the seed
      // instead of putting a hole in the timeline.
      if (!iconChoPhep.has(icon)) return null;
      if (placeId !== undefined && !laChuoi(placeId)) return null;
      slots.push(placeId === undefined ? { time, title, icon, color } : { time, title, icon, color, placeId });
    }
    ngay.push({ day, items: slots });
  }
  return ngay;
}

function locAssignments(value: unknown, soDong: number, soNguoi: number): number[][] | null {
  if (!Array.isArray(value) || value.length !== soDong) return null;
  const ra: number[][] = [];
  for (const dong of value) {
    if (!Array.isArray(dong)) return null;
    const nguoi: number[] = [];
    for (const i of dong) {
      if (!laChiSoNguoi(i, soNguoi)) return null;
      if (!nguoi.includes(i)) nguoi.push(i);
    }
    // `sharesByPerson` refuses a line assigned to nobody, and refusing here is
    // how that refusal stays a bug report instead of a crash on launch.
    if (nguoi.length === 0) return null;
    ra.push(nguoi);
  }
  return ra;
}

/**
 * Pick the persisted subset explicitly, then serialise it.
 *
 * Field by field rather than spreading the session, so a field added to the
 * session later does not reach the disk merely by existing. `profileNotice` is
 * the shape of the thing being kept out: a sentence about something that just
 * happened, which would be restored days later as a notice about nothing.
 */
export function dongGoi(phien: PhienLuuDuoc): string {
  const chon: PhienLuuDuoc = {
    displayName: phien.displayName,
    bio: phien.bio,
    interests: phien.interests,
    vibes: phien.vibes,
    savedPlaceIds: phien.savedPlaceIds,
    itinerary: phien.itinerary,
    tripName: phien.tripName,
    destination: phien.destination,
    startDate: phien.startDate,
    endDate: phien.endDate,
    selectedMemberIds: phien.selectedMemberIds,
    aiSuggest: phien.aiSuggest,
    chatMessages: phien.chatMessages,
    voteChoice: phien.voteChoice,
    voteConfirmed: phien.voteConfirmed,
    assignments: phien.assignments,
    paidFromIndexes: phien.paidFromIndexes,
    remindedPending: phien.remindedPending,
    checkedInIds: phien.checkedInIds,
    locationSharing: phien.locationSharing,
    receiptPicked: phien.receiptPicked,
  };
  return JSON.stringify({ v: PHIEN_BAN_LUU, phien: chon });
}

/**
 * Rebuild a session from whatever was on disk, field by field.
 *
 * `seed` is both the fallback and the shape oracle: the roster size and the
 * icon set come from it, so this function needs no import to know what a valid
 * person index or icon is.
 */
export function moGoi<T extends PhienLuuDuoc>(raw: string | null | undefined, seed: T): T {
  if (!raw) return seed;
  let goi: unknown;
  try {
    goi = JSON.parse(raw);
  } catch {
    // Half-written blob. There is nothing to salvage and nothing to report to
    // a person about it; the seed is the honest answer.
    return seed;
  }
  if (typeof goi !== "object" || goi === null) return seed;
  const { v, phien } = goi as { v?: unknown; phien?: unknown };
  // An older shape is DROPPED rather than migrated. A half-migration that
  // guesses at a missing field is a worse answer than starting clean, and this
  // is a draft over a fixture -- there is nothing here somebody cannot redo.
  if (v !== PHIEN_BAN_LUU) return seed;
  if (typeof phien !== "object" || phien === null) return seed;

  const doc = phien as Record<string, unknown>;
  const ra: T = { ...seed };
  const soNguoi = seed.assignments.reduce(
    (max, dong) => dong.reduce((m, i) => Math.max(m, i + 1), max),
    seed.selectedMemberIds.length,
  );
  const iconChoPhep = new Set(seed.itinerary.flatMap((ngay) => ngay.items.map((item) => item.icon)));

  for (const khoa of KHOA_CHUOI) {
    if (laChuoi(doc[khoa])) ra[khoa] = doc[khoa] as T[typeof khoa];
  }
  for (const khoa of KHOA_MANG_CHUOI) {
    if (laMangChuoi(doc[khoa])) ra[khoa] = doc[khoa] as T[typeof khoa];
  }
  for (const khoa of KHOA_BOOL) {
    if (typeof doc[khoa] === "boolean") ra[khoa] = doc[khoa] as T[typeof khoa];
  }
  if (doc.voteChoice === null || laChiSoNguoi(doc.voteChoice, Number.MAX_SAFE_INTEGER)) {
    ra.voteChoice = doc.voteChoice as T["voteChoice"];
  }
  if (Array.isArray(doc.paidFromIndexes) && doc.paidFromIndexes.every((i) => laChiSoNguoi(i, soNguoi))) {
    ra.paidFromIndexes = doc.paidFromIndexes as T["paidFromIndexes"];
  }
  const lich = locLichTrinh(doc.itinerary, iconChoPhep);
  // `as T["itinerary"]` and not a wider cast: the runtime guard above is the
  // real check, and TypeScript cannot express "this parsed JSON carries the
  // icon union" without repeating the union in a second place that would drift.
  if (lich !== null) ra.itinerary = lich as T["itinerary"];
  const gan = locAssignments(doc.assignments, seed.assignments.length, soNguoi);
  if (gan !== null) ra.assignments = gan;
  return ra;
}

/**
 * The two truths about durability, in one place.
 *
 * Six sentences on five screens make a claim about whether closing the app
 * loses what you just did. Before AsyncStorage they all claimed it survived and
 * none of it did. Centralised so the claim tracks one flag instead of six
 * copies of a guess, and so a test can assert the two branches actually differ.
 *
 * `luuTruSong` is false while the disk is still being read AND when a write
 * failed, and both are honestly "not saved yet" from where a person is sitting.
 */
export function noiLuu(luuTruSong: boolean): string {
  return luuTruSong ? "lưu trên máy" : "chỉ sống trong lần mở app này";
}

/** Same claim, as a trailing phrase: "8 địa điểm trên máy". */
export function noiLuuNgan(luuTruSong: boolean): string {
  return luuTruSong ? "trên máy" : "trong lần mở app này";
}
