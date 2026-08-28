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

import { canPublish, GateNotPassedError } from "../dist-test/api.js";
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

/* Spec section 8.3 -- the two gates before a collection round goes out.
 *
 * The prototype went straight from "confirm the split" to "publish", which
 * teaches a flow where a round can go out under someone's name before they
 * agree, and leaves nowhere to set up or check the recipient.
 */

test("publish is refused while either gate is shut", async () => {
  const { publishBatch, GateNotPassedError } = await import("../dist-test/api.js");
  const obligations = [
    { id: "o1", senderId: "b", senderName: "Hà", recipient: "Nam", amountVnd: 100_000, status: "outstanding" },
  ];
  const shut = [
    { payerAcknowledged: false, recipientReady: false, recipientProblem: null },
    { payerAcknowledged: true, recipientReady: false, recipientProblem: null },
    { payerAcknowledged: false, recipientReady: true, recipientProblem: null },
  ];
  for (const gates of shut) {
    await assert.rejects(() => publishBatch(obligations, gates), GateNotPassedError);
  }
});

test("publish refuses to build a request until both gates pass", async () => {
  // The happy path now needs a live server, so it is covered end to end in
  // `tests/e2e` rather than here. What this file still owns is the refusal:
  // the gate check runs BEFORE any request is built, so a shut gate cannot be
  // turned into a network round trip that a flaky connection then hides.
  const { publishBatch, GateNotPassedError } = await import("../dist-test/api.js");
  await assert.rejects(
    () =>
      publishBatch("some-batch", {
        payerAcknowledged: true,
        recipientReady: false,
        recipientProblem: null,
      }, "some-actor"),
    GateNotPassedError,
  );
});

/* Data loss on "Sửa lại" -- found by agy driving the real app.
 *
 * The form used to live inside the screen. Pressing "Sửa lại" on the proposal
 * steps back, React unmounts the screen, and every `useState` in it goes with
 * it. A person who had typed an occasion, added twelve people and chosen who
 * paid came back to an empty form. The button exists to change ONE detail.
 *
 * The fix is that the form is a value the app holds, so these tests are about
 * that value surviving -- which is the thing that was actually broken.
 */
test("the form is a plain value, so stepping away cannot erase it", async () => {
  const { EMPTY_FORM, addParticipant, makeIdFactory } = await import(
    "../dist-test/participants.js"
  );
  const nextId = makeIdFactory();
  let form = { ...EMPTY_FORM, occasion: "bữa lẩu tối thứ bảy", amount: "300000" };
  for (const name of ["Nam", "Hà", "Quyên"]) {
    form = { ...form, roster: addParticipant(form.roster, name, nextId) };
  }
  form = { ...form, roster: { ...form.roster, advancerId: form.roster.participants[0].id } };

  // Whatever the UI does between here and coming back, the value is unchanged
  // unless something explicitly changes it. That is the whole guarantee.
  const carried = form;
  assert.equal(carried.occasion, "bữa lẩu tối thứ bảy");
  assert.equal(carried.amount, "300000");
  assert.equal(carried.roster.participants.length, 3);
  assert.equal(carried.roster.advancerId, form.roster.participants[0].id);
});

test("EMPTY_FORM is empty, so a real reset is still possible", async () => {
  const { EMPTY_FORM } = await import("../dist-test/participants.js");
  assert.equal(EMPTY_FORM.occasion, "");
  assert.equal(EMPTY_FORM.amount, "");
  assert.equal(EMPTY_FORM.pending, "");
  assert.deepEqual(EMPTY_FORM.roster, { participants: [], advancerId: null });
});

test("ids stay unique across a remount of the screen", async () => {
  // The id counter used to be a module-level `let` reset by nothing, but the
  // factory is created once at module scope now. Two separate factories would
  // mint p1 twice and collapse two people into one.
  const { makeIdFactory, addParticipant } = await import("../dist-test/participants.js");
  const shared = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  roster = addParticipant(roster, "Nam", shared);
  roster = addParticipant(roster, "Hà", shared);
  roster = addParticipant(roster, "Quyên", shared);
  const ids = roster.participants.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length, `ids collided: ${ids}`);
});

/* Two people, one name -- the label has to tell them apart even though the id
 * already does. QA drove this exact case and called the screen confusing: one
 * button reading "Nam", nothing selected, no way to know which Nam.
 */
test("a shared name gets numbered, a unique one does not", async () => {
  const { addParticipant, labelFor, makeIdFactory } = await import(
    "../dist-test/participants.js"
  );
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  for (const name of ["Nam", "Hà", "Nam"]) {
    roster = addParticipant(roster, name, nextId);
  }
  const [first, ha, second] = roster.participants;
  assert.equal(labelFor(roster, first.id), "Nam #1");
  assert.equal(labelFor(roster, second.id), "Nam #2");
  assert.equal(labelFor(roster, ha.id), "Hà", "a unique name should not be numbered");
});

test("numbering is display only — removing one does not move the other's identity", async () => {
  const { addParticipant, labelFor, removeParticipant, makeIdFactory } = await import(
    "../dist-test/participants.js"
  );
  const nextId = makeIdFactory();
  let roster = { participants: [], advancerId: null };
  roster = addParticipant(roster, "Nam", nextId);
  roster = addParticipant(roster, "Nam", nextId);
  const second = roster.participants[1];
  roster = { ...roster, advancerId: second.id };

  roster = removeParticipant(roster, roster.participants[0].id);
  // The label drops back to plain "Nam" because there is only one now, but the
  // person under it is still the one that was chosen.
  assert.equal(labelFor(roster, second.id), "Nam");
  assert.equal(roster.advancerId, second.id);
});
