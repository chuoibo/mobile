/** Who is in the group, and which of them paid — kept as data, not as layout.
 *
 * This is separated from the screen so the invariant can actually be tested.
 * The invariant is about money, not about lists: the advancer wins the rounding
 * tie-break and receives every obligation, so if editing the list can silently
 * move `advancerId` onto a different person, the app can send a collection
 * round in the wrong person's name and hand them everyone else's money.
 *
 * The earlier version rebuilt ids as `p${index + 1}` from a comma-separated
 * string on every render. Select `p2`, insert a name above them, and `p2` now
 * refers to someone else while the selection still validates -- because a `p2`
 * still exists. Position is not identity. An id is minted once, for one person,
 * and never derived from order or display name.
 */

import { TEN_CHUA_BIET } from "./screens/chat/tin-nhan";

export type Participant = { id: string; name: string };

export type Roster = {
  participants: Participant[];
  /** The person who paid up front, or null when nobody is chosen. */
  advancerId: string | null;
};

/**
 * A fresh id per person. UUIDs, because the API only accepts UUIDs.
 *
 * These were `p1`, `p2` -- readable, stable, and rejected by every endpoint.
 * Tests pass their own factory so ids stay predictable there; nothing else may
 * derive an id from a name or a position.
 */
export function makeIdFactory(prefix?: string): () => string {
  if (prefix !== undefined) {
    let seq = 0;
    return () => `${prefix}${++seq}`;
  }
  return () => {
    // `crypto.randomUUID` exists in Hermes and in every browser this runs in.
    // The fallback is for older runtimes and produces the same shape; it is
    // not a security boundary, only an identity that must not collide.
    const c = globalThis.crypto as { randomUUID?: () => string } | undefined;
    if (c?.randomUUID) return c.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
      const r = (Math.random() * 16) | 0;
      return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  };
}

export function addParticipant(
  roster: Roster,
  name: string,
  nextId: () => string,
): Roster {
  const trimmed = name.trim();
  if (!trimmed) return roster;
  return {
    participants: [...roster.participants, { id: nextId(), name: trimmed }],
    // Adding someone cannot change who was already chosen.
    advancerId: roster.advancerId,
  };
}

/**
 * Somebody the group already has an identity for.
 *
 * The distinction from `Participant` is the whole point of this type: a
 * participant is a row on this bill, a member is a person the database has
 * heard of. `id` is the `people` row, never a slug and never minted here.
 */
export type GroupMember = { id: string; name: string };

/**
 * The group, in the shape the split screen adds people from.
 *
 * The demo group carries two ids per person -- a readable slug and the seeded
 * `people` row -- and only one of them may leave the app. Picking the wrong
 * one is silent: every screen still renders, the allocator still balances to
 * the dong, and the money lands on somebody who does not exist. So the
 * projection is one function rather than a `.map` at each call site.
 */
export function groupMembers(
  people: { personId: string; name: string }[],
): GroupMember[] {
  return people.map((person) => ({ id: person.personId, name: person.name }));
}

/** Members not on this bill yet. */
export function availableMembers(roster: Roster, members: GroupMember[]): GroupMember[] {
  const already = new Set(roster.participants.map((person) => person.id));
  return members.filter((member) => !already.has(member.id));
}

/**
 * Put a known member on the bill, keeping the id they already had.
 *
 * This is the fix for bug-125301 in one line: the id comes in with the person
 * instead of being minted from what somebody typed. Typing "Hải" used to
 * produce a fresh UUID, so the ledger recorded a correct split against a
 * stranger who happened to share a name, and the real Hải's screen never
 * moved. Names are not identity; a name typed twice is two people, and a
 * person's row is theirs before this screen ever opens.
 *
 * Adding twice is a no-op rather than a second column: the caller is a list of
 * buttons, and a double tap must not put somebody on the bill twice.
 */
export function addMember(roster: Roster, member: GroupMember): Roster {
  if (roster.participants.some((person) => person.id === member.id)) return roster;
  return {
    participants: [...roster.participants, { id: member.id, name: member.name }],
    // Same rule as `addParticipant`: adding somebody cannot change who was
    // already chosen to have paid.
    advancerId: roster.advancerId,
  };
}

export function removeParticipant(roster: Roster, id: string): Roster {
  return {
    participants: roster.participants.filter((person) => person.id !== id),
    // Removing the chosen person clears the choice. It never slides onto a
    // neighbour, because the id belongs to the person and not to the slot.
    advancerId: roster.advancerId === id ? null : roster.advancerId,
  };
}

export function moveParticipant(roster: Roster, from: number, to: number): Roster {
  const participants = [...roster.participants];
  const [moved] = participants.splice(from, 1);
  if (!moved) return roster;
  participants.splice(to, 0, moved);
  return { participants, advancerId: roster.advancerId };
}

export function renameParticipant(roster: Roster, id: string, name: string): Roster {
  return {
    participants: roster.participants.map((person) =>
      person.id === id ? { ...person, name: name.trim() || person.name } : person,
    ),
    advancerId: roster.advancerId,
  };
}

/** The chosen person, or null. Never guesses from position. */
export function advancer(roster: Roster): Participant | null {
  return roster.participants.find((p) => p.id === roster.advancerId) ?? null;
}

/** Display names that appear more than once. Not an error — just worth saying. */
export function duplicateNames(roster: Roster): string[] {
  const names = roster.participants.map((p) => p.name);
  return [...new Set(names.filter((name, i) => names.indexOf(name) !== i))];
}

/**
 * A label that tells two people apart when they share a name.
 *
 * QA drove the app with two people both called Nam, chose the second, removed
 * the first, and reported the screen as confusing: one button reading "Nam"
 * with nothing selected, and no way to tell whether that was the Nam they had
 * picked. The ids were right the whole time -- the labels were not.
 *
 * Numbering is by position in the list, which is what a person sees, and it is
 * only for reading. Nothing keys off it: identity stays with the id.
 */
export function labelFor(roster: Roster, id: string): string {
  const person = roster.participants.find((p) => p.id === id);
  if (!person) return id;
  const sameName = roster.participants.filter((p) => p.name === person.name);
  if (sameName.length < 2) return person.name;
  return `${person.name} #${sameName.indexOf(person) + 1}`;
}

/**
 * A label for somebody the SERVER named, who need not be on this bill.
 *
 * `labelFor` answers about the bill, and returning the id when it cannot place
 * one is the right shape for its callers: they iterate the roster, so a miss
 * there is a bug worth seeing. Anything drawn from a server reply is a
 * different question. `/contexts/{id}/balances` answers for the ledger of the
 * whole group and `POST /bills/{id}/split` answers against the roster the
 * server holds, so both routinely name people who are legitimately absent from
 * the bill somebody is typing -- and `labelFor`'s fallback then prints a UUID
 * on a money row, next to a real name, in the same block. That was
 * bug-050923: "e3a44e25-4547-508a-8f4d-9b2495c3325f trả Minh 505.094đ" above
 * "Trang trả Minh 374.262đ", where `e3a44e25` was Ngọc and the app was holding
 * her name the whole time.
 *
 * So the lookup widens to the group before it gives up. `members` is the
 * active membership the screen already has for its "thêm vào nhóm" buttons;
 * nothing new is fetched.
 *
 * Numbering counts across both lists rather than within either. A Nam on the
 * bill and a Nam who is only in the group are two people, and one unnumbered
 * "Nam" on a money row is exactly the ambiguity `labelFor` numbers to remove.
 *
 * A person in neither list is genuinely unknown to this client -- a member who
 * left still owes what they owed, and the ledger keeps them. They get the same
 * word the chat bubble and the member list use. Never a sliced id: eight hex
 * characters look like something the reader ought to recognise, which is worse
 * than saying nothing.
 */
export function labelInGroup(roster: Roster, members: GroupMember[], id: string): string {
  const onBill = new Set(roster.participants.map((person) => person.id));
  const known: Roster = {
    participants: [
      ...roster.participants,
      ...members
        // A member the server sent without a display name is not a name; the
        // blank would render as an empty cell where a person goes.
        .filter((member) => !onBill.has(member.id) && member.name.trim() !== "")
        .map((member) => ({ id: member.id, name: member.name })),
    ],
    advancerId: roster.advancerId,
  };
  if (!known.participants.some((person) => person.id === id)) return TEN_CHUA_BIET;
  return labelFor(known, id);
}

/** Everything the "new expense" screen is holding while a person fills it in.
 *
 * This lives outside the screen because the screen unmounts. Pressing "Sửa lại"
 * on the proposal moves the app back a step, React tears the screen down, and
 * every `useState` inside it goes with it -- so a person who had typed an
 * occasion, added twelve people and chosen who paid came back to an empty form.
 * The button exists to change one detail; it was erasing everything instead.
 *
 * Holding the form here, and letting the screen render it rather than own it,
 * makes losing it impossible rather than unlikely.
 */
export type DraftForm = {
  occasion: string;
  /** The name half-typed in the "add someone" box, kept so it is not lost either. */
  pending: string;
  /** What the person typed for the amount, before parsing. Their text, not our number. */
  amount: string;
  roster: Roster;
};

export const EMPTY_FORM: DraftForm = {
  occasion: "",
  pending: "",
  amount: "",
  roster: { participants: [], advancerId: null },
};
