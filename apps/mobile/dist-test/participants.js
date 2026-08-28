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
/** Monotonic, never reused. Callers may pass their own for deterministic tests. */
export function makeIdFactory(prefix = "p") {
    let seq = 0;
    return () => `${prefix}${++seq}`;
}
export function addParticipant(roster, name, nextId) {
    const trimmed = name.trim();
    if (!trimmed)
        return roster;
    return {
        participants: [...roster.participants, { id: nextId(), name: trimmed }],
        // Adding someone cannot change who was already chosen.
        advancerId: roster.advancerId,
    };
}
export function removeParticipant(roster, id) {
    return {
        participants: roster.participants.filter((person) => person.id !== id),
        // Removing the chosen person clears the choice. It never slides onto a
        // neighbour, because the id belongs to the person and not to the slot.
        advancerId: roster.advancerId === id ? null : roster.advancerId,
    };
}
export function moveParticipant(roster, from, to) {
    const participants = [...roster.participants];
    const [moved] = participants.splice(from, 1);
    if (!moved)
        return roster;
    participants.splice(to, 0, moved);
    return { participants, advancerId: roster.advancerId };
}
export function renameParticipant(roster, id, name) {
    return {
        participants: roster.participants.map((person) => person.id === id ? { ...person, name: name.trim() || person.name } : person),
        advancerId: roster.advancerId,
    };
}
/** The chosen person, or null. Never guesses from position. */
export function advancer(roster) {
    return roster.participants.find((p) => p.id === roster.advancerId) ?? null;
}
/** Display names that appear more than once. Not an error — just worth saying. */
export function duplicateNames(roster) {
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
export function labelFor(roster, id) {
    const person = roster.participants.find((p) => p.id === id);
    if (!person)
        return id;
    const sameName = roster.participants.filter((p) => p.name === person.name);
    if (sameName.length < 2)
        return person.name;
    return `${person.name} #${sameName.indexOf(person) + 1}`;
}
export const EMPTY_FORM = {
    occasion: "",
    pending: "",
    amount: "",
    roster: { participants: [], advancerId: null },
};
