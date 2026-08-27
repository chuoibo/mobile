/* What the offline demo is and is not allowed to do.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/
 *
 * Two blockers produced these tests, and both were about money rather than UI:
 *
 * PR13-02 — the client carried its own even split, `Math.floor(total / n)`,
 * in the same file whose docstring said "Nothing here computes money". A second
 * allocator can disagree with the server while looking perfectly convincing,
 * and `/` produces float intermediates, which the money rules forbid outright.
 *
 * PR13-03 — participant ids were `p${index + 1}`, rebuilt from a string on
 * every render, while the chosen advancer was held separately. Editing the list
 * moved the selection onto a different person in silence.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { FIXTURES, FixtureMissingError } from "../dist-test/api.js";
import {
  addParticipant,
  advancer,
  duplicateNames,
  makeIdFactory,
  moveParticipant,
  removeParticipant,
  renameParticipant,
} from "../dist-test/participants.js";

const source = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8");

test("the corpus is not empty, or every test below passes vacuously", () => {
  assert.ok(FIXTURES.length >= 5, `only ${FIXTURES.length} fixtures`);
});

test("every fixture's parts add up to its total", () => {
  // Money rule 2. A fixture that failed this would put a wrong number on
  // screen carrying the authority of the golden corpus.
  for (const fixture of FIXTURES) {
    const sum = Object.values(fixture.allocations).reduce((a, b) => a + b, 0);
    assert.equal(sum, fixture.totalVnd, `${fixture.id} sums to ${sum}`);
  }
});

test("every allocation is an integer number of dong", () => {
  for (const fixture of FIXTURES) {
    for (const [id, amount] of Object.entries(fixture.allocations)) {
      assert.ok(Number.isInteger(amount), `${fixture.id}/${id} is ${amount}`);
    }
  }
});

test("the client source contains no allocation arithmetic", () => {
  // Deliberately narrow: this asserts the specific shapes the removed splitter
  // used, so it fails when that code comes back rather than whenever anyone
  // types a slash. It is a backstop for the behavioural tests below, not a
  // substitute for them -- a string check cannot prove absence.
  const body = source.slice(source.indexOf("*/") + 2);
  for (const banned of ["Math.floor", "Math.ceil", "Math.round"]) {
    assert.ok(!body.includes(banned), `api.ts still uses ${banned}`);
  }
});

test("a draft that matches a fixture replays it exactly", async () => {
  const { proposeSplit } = await import("../dist-test/api.js");
  const fixture = FIXTURES[0];
  const proposal = await proposeSplit({
    participants: fixture.participants,
    totalVnd: fixture.totalVnd,
    advancerId: fixture.advancerId,
    occasion: fixture.occasion,
  });
  assert.deepEqual(proposal.allocations, fixture.allocations);
  assert.deepEqual(proposal.roundingGainers, fixture.roundingGainers);
});

test("a draft with no fixture is refused, never invented", async () => {
  const { proposeSplit } = await import("../dist-test/api.js");
  // 777_777 over these three people is not in the corpus. The old code would
  // have happily returned 259259/259259/259259 and hidden the remainder.
  await assert.rejects(
    () =>
      proposeSplit({
        participants: [
          { id: "a", name: "Nam" },
          { id: "b", name: "Hà" },
          { id: "c", name: "Quyên" },
        ],
        totalVnd: 777_777,
        advancerId: "a",
        occasion: "không có trong corpus",
      }),
    FixtureMissingError,
  );
});

test("adding someone never moves an existing choice", () => {
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  roster = addParticipant(roster, "Hà", nextId);
  roster = addParticipant(roster, "Nam", nextId);
  const chosen = roster.participants[1];
  roster = { ...roster, advancerId: chosen.id };

  roster = addParticipant(roster, "Quyên", nextId);
  assert.equal(advancer(roster)?.id, chosen.id);
  assert.equal(advancer(roster)?.name, "Nam");
});

test("reordering never moves the choice onto a neighbour", () => {
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  for (const name of ["Hà", "Nam", "Quyên"]) {
    roster = addParticipant(roster, name, nextId);
  }
  roster = { ...roster, advancerId: roster.participants[1].id };
  assert.equal(advancer(roster)?.name, "Nam");

  roster = moveParticipant(roster, 2, 0); // Quyên jumps to the front
  assert.equal(advancer(roster)?.name, "Nam", "reorder changed who paid");

  roster = moveParticipant(roster, 0, 2);
  assert.equal(advancer(roster)?.name, "Nam");
});

test("removing someone else leaves the choice alone", () => {
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  for (const name of ["Hà", "Nam", "Quyên"]) {
    roster = addParticipant(roster, name, nextId);
  }
  roster = { ...roster, advancerId: roster.participants[2].id };

  roster = removeParticipant(roster, roster.participants[0].id);
  assert.equal(advancer(roster)?.name, "Quyên");
});

test("removing the chosen person clears the choice instead of sliding it", () => {
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  for (const name of ["Hà", "Nam", "Quyên"]) {
    roster = addParticipant(roster, name, nextId);
  }
  const chosen = roster.participants[1];
  roster = { ...roster, advancerId: chosen.id };

  roster = removeParticipant(roster, chosen.id);
  assert.equal(roster.advancerId, null, "choice survived the person");
  assert.equal(advancer(roster), null);
});

test("two people with the same name stay two people", () => {
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  roster = addParticipant(roster, "Nam", nextId);
  roster = addParticipant(roster, "Nam", nextId);

  const [first, second] = roster.participants;
  assert.notEqual(first.id, second.id, "same name collapsed into one person");
  assert.deepEqual(duplicateNames(roster), ["Nam"]);

  roster = { ...roster, advancerId: second.id };
  roster = removeParticipant(roster, first.id);
  assert.equal(roster.participants.length, 1);
  assert.equal(advancer(roster)?.id, second.id, "wrong Nam survived");
});

test("renaming changes the label, not the person", () => {
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  roster = addParticipant(roster, "Nam", nextId);
  const id = roster.participants[0].id;
  roster = { ...roster, advancerId: id };

  roster = renameParticipant(roster, id, "Nam A");
  assert.equal(advancer(roster)?.id, id);
  assert.equal(advancer(roster)?.name, "Nam A");
});
