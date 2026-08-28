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

export type Participant = { id: string; name: string };

export type Roster = {
  participants: Participant[];
  /** The person who paid up front, or null when nobody is chosen. */
  advancerId: string | null;
};

/** Monotonic, never reused. Callers may pass their own for deterministic tests. */
export function makeIdFactory(prefix = "p"): () => string {
  let seq = 0;
  return () => `${prefix}${++seq}`;
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
