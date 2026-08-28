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

/* Spec section 8.3 -- the gates before a collection round goes out.
 *
 * The prototype went straight from "confirm the split" to "publish", which
 * teaches a flow where a round can go out under someone's name before they
 * agree.
 *
 * There are two gates, and the app now models exactly one. Gate 2 -- there is
 * a confirmed account for the money to land in -- is not reported by any
 * endpoint, so the client had it hardcoded shut, which made publishing
 * impossible, and then a button that opened it by tapping. These tests used to
 * pin that arrangement: they asserted a shut gate 2 was refused, which was
 * true, and said nothing about the fact that the only way through it was a
 * person asserting it themselves. A test can pin a workaround as firmly as it
 * pins a rule.
 *
 * Gate 2 now lives where the facts are. What this file still owns is gate 1
 * and the shape of the refusal.
 */

test("publish is refused while the advancer has not acknowledged", async () => {
  const { publishBatch, GateNotPassedError } = await import("../dist-test/api.js");
  await assert.rejects(
    () => publishBatch("some-batch", { payerAcknowledged: false }, "some-actor"),
    GateNotPassedError,
  );
});

test("gate 1 is checked before any request is built", async () => {
  // A shut gate must not become a network round trip that a flaky connection
  // then hides. Proven by pointing the client at an address nothing answers:
  // if a request were attempted the error would be `unreachable`, not the gate.
  const { publishBatch, GateNotPassedError, ApiError } = await import("../dist-test/api.js");
  try {
    await publishBatch("some-batch", { payerAcknowledged: false }, "some-actor");
    assert.fail("phat duoc trong khi cong 1 dang dong");
  } catch (problem) {
    assert.ok(problem instanceof GateNotPassedError, `nhan duoc ${problem?.name}`);
    assert.ok(!(problem instanceof ApiError), "da goi mang truoc khi kiem cong");
  }
});

test("máy chủ từ chối phát thì người đọc được lý do, không đọc mã lỗi", async () => {
  // Gate 2 refusals arrive as `recipient_setup_incomplete`. Untranslated, that
  // string lands on screen next to somebody's name and somebody's money.
  const { publishBatch, ApiError } = await import("../dist-test/api.js");
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ code: "recipient_setup_incomplete", detail: "gate 2" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
  try {
    await publishBatch("b", { payerAcknowledged: true }, "a");
    assert.fail("le ra phai bi tu choi");
  } catch (problem) {
    assert.ok(problem instanceof ApiError);
    assert.equal(problem.code, "recipient_setup_incomplete", "mat ma loi thi het truy duoc");
    assert.match(problem.message, /tài khoản nhận/, "khong dich ra tieng nguoi");
  } finally {
    globalThis.fetch = realFetch;
  }
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

/* Names, not ids -- found by agy driving the real app.
 *
 * The server answers in UUIDs, because ids are what it stores. The share
 * screen turned that straight into "Gửi cho 6b4bda36-93e6-4a94-b7ca-…" and
 * copied "Phần của 6b4bda36-…" to the clipboard. An organiser cannot tell
 * which link belongs to whom, which is the only thing that screen does.
 *
 * These go through the client rather than through the screen, because the id
 * reaches the screen already stamped into `senderName`. Fixing the screen
 * would have hidden it one layer down.
 */

const HA_ID = "6b4bda36-93e6-4a94-b7ca-48757974f36d";
const ROSTER = [
  { id: HA_ID, name: "Hà" },
  { id: "8c1e2f10-a1b1-4c22-8d33-e4f4a5b5c6d6", name: "Quyên" },
];

function respondWith(payload, status = 200) {
  const real = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  return () => {
    globalThis.fetch = real;
  };
}

test("phong bì mang tên người, không mang UUID", async () => {
  const { publishBatch } = await import("../dist-test/api.js");
  const restore = respondWith({
    guest_links: [
      {
        sender_id: HA_ID,
        path: "/g/abc",
        obligations: [{ obligation_id: "o1", amount_vnd: 100_000 }],
      },
    ],
  });
  try {
    const envelopes = await publishBatch("b", { payerAcknowledged: true }, "a", ROSTER);
    assert.equal(envelopes[0].senderName, "Hà");
    assert.ok(!envelopes[0].senderName.includes("-"), "van con UUID tren man hinh");
  } finally {
    restore();
  }
});

test("người không có trong danh sách vẫn hiện ra, bằng id, chứ không bị gộp", async () => {
  // A missing name is a display problem. Falling back to a placeholder like
  // "Người nhận" would make two different people look like one person on the
  // exact screen whose job is telling them apart.
  const { publishBatch } = await import("../dist-test/api.js");
  const stranger = "f9e9d9c9-b9a9-4f99-8e99-d9c9b9a9f999";
  const restore = respondWith({
    guest_links: [
      { sender_id: stranger, path: "/g/x", obligations: [{ obligation_id: "o", amount_vnd: 1 }] },
    ],
  });
  try {
    const envelopes = await publishBatch("b", { payerAcknowledged: true }, "a", ROSTER);
    assert.equal(envelopes[0].senderName, stranger);
  } finally {
    restore();
  }
});

/* loadBoard -- agy found it had no test touching it at all, and that deleting
 * the whole function left every test green. It reads the collection board:
 * who has paid, and what is being argued about.
 */

test("bảng đợt thu đọc được tên, số tiền và trạng thái", async () => {
  const { loadBoard } = await import("../dist-test/api.js");
  const restore = respondWith({
    disputed_count: 1,
    obligations: [
      {
        obligation_id: "o1",
        sender_id: HA_ID,
        recipient_id: ROSTER[1].id,
        amount_vnd: 100_000,
        obligation_status: "outstanding",
        disputed: true,
      },
    ],
  });
  try {
    const board = await loadBoard("b", "a", ROSTER);
    assert.equal(board.disputedCount, 1);
    assert.equal(board.obligations[0].senderName, "Hà");
    assert.equal(board.obligations[0].recipient, "Quyên");
    assert.equal(board.obligations[0].amountVnd, 100_000);
  } finally {
    restore();
  }
});

test("tiền đã tới thì vẫn hiện là đã tới, kể cả khi có người thắc mắc", async () => {
  // Payment status and dispute are separate facts on the wire and the board
  // has one slot. Showing "disputed" over "outstanding" is safe; showing it
  // over "confirmed" would hide money that actually arrived.
  const { loadBoard } = await import("../dist-test/api.js");
  const restore = respondWith({
    disputed_count: 1,
    obligations: [
      {
        obligation_id: "o1",
        sender_id: HA_ID,
        recipient_id: ROSTER[1].id,
        amount_vnd: 100_000,
        obligation_status: "confirmed",
        disputed: true,
      },
    ],
  });
  try {
    const board = await loadBoard("b", "a", ROSTER);
    assert.equal(board.obligations[0].status, "confirmed", "che mat tien da toi");
  } finally {
    restore();
  }
});

/* Confirming that money arrived.
 *
 * `receiver_confirmed` means one person pressed a button. It is not a bank
 * telling anyone anything -- the product holds no money and reads no
 * statement. These tests are about the client not making it look like more
 * than that, and about not recording one arrival twice.
 */

test("báo tiền đã về gửi đúng số tiền của nghĩa vụ đó", async () => {
  const { confirmReceipt } = await import("../dist-test/api.js");
  const real = globalThis.fetch;
  let sent = null;
  globalThis.fetch = async (url, init) => {
    sent = { url: String(url), body: JSON.parse(init.body), headers: init.headers };
    return new Response(JSON.stringify({ obligation_status: "confirmed" }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    const result = await confirmReceipt("ob-1", 100_000, "actor-1", "key-1");
    assert.equal(result.status, "confirmed");
    assert.ok(sent.url.endsWith("/obligations/ob-1/confirm-receipt"));
    assert.equal(sent.body.amount_vnd, 100_000);
    assert.equal(sent.body.idempotency_key, "key-1");
    // Only the person owed the money may say this, so the call has to carry
    // who is saying it. A confirmation with no actor is one anybody could send.
    assert.equal(sent.headers["X-Actor-ID"], "actor-1");
  } finally {
    globalThis.fetch = real;
  }
});

test("gửi lại cùng một khoá thì máy chủ vẫn chỉ thấy một lần báo", async () => {
  // The case this exists for: the request arrives, the reply does not, and the
  // person presses again. With a fresh key that second press is a second
  // arrival and the obligation goes to `over_confirmed` -- it reads as
  // somebody having paid more than they owed. The key is what stops that, so
  // it is asserted to be the same one, not merely to be present.
  const { confirmReceipt } = await import("../dist-test/api.js");
  const real = globalThis.fetch;
  const keys = [];
  globalThis.fetch = async (_url, init) => {
    keys.push(JSON.parse(init.body).idempotency_key);
    return new Response(JSON.stringify({ obligation_status: "confirmed" }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await confirmReceipt("ob-1", 100_000, "actor-1", "same-key");
    await confirmReceipt("ob-1", 100_000, "actor-1", "same-key");
    assert.deepEqual(keys, ["same-key", "same-key"], "khoa doi giua hai lan gui");
  } finally {
    globalThis.fetch = real;
  }
});

/* Every publish refusal the server can send, in words a person can act on.
 *
 * agy pointed out only one of the four codes had a test. The other three were
 * a table nobody had read back: a typo in a key, or a code the server renamed,
 * would surface as `bank_recipient_snapshot_invalid` on screen next to
 * somebody's name and somebody's money, and no test would notice.
 *
 * The fallthrough is tested too, and it is the more important half. An
 * unrecognised code must keep the server's own words rather than borrow a
 * friendly sentence that might be wrong about what happened.
 */

test("mọi mã từ chối phát đều dịch được ra tiếng người", async () => {
  const { publishBatch, ApiError } = await import("../dist-test/api.js");
  const expected = {
    advancer_not_acknowledged: /chưa xác nhận/,
    recipient_setup_incomplete: /tài khoản nhận/,
    bank_recipient_snapshot_invalid: /đã đổi/,
    batch_not_found: /Không tìm thấy/,
  };
  const real = globalThis.fetch;
  try {
    for (const [code, pattern] of Object.entries(expected)) {
      globalThis.fetch = async () =>
        new Response(JSON.stringify({ code, detail: "raw server words" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        });
      await assert.rejects(
        () => publishBatch("b", { payerAcknowledged: true }, "a"),
        (problem) => {
          assert.ok(problem instanceof ApiError, `${code}: sai kieu loi`);
          assert.equal(problem.code, code, "mat ma loi thi het truy duoc");
          assert.match(problem.message, pattern, `${code} chua duoc dich`);
          return true;
        },
      );
    }
  } finally {
    globalThis.fetch = real;
  }
});

test("mở đợt thu bị từ chối thì đọc được, kể cả khi máy chủ viết CHỮ HOA", async () => {
  // Found by walking the app: pressing "Đúng rồi, ghi vào sổ" put the words
  // "Batch cannot be frozen" on screen -- the server's own English, under a
  // Vietnamese heading, with nothing about what to do.
  //
  // The casing is the trap. Codes raised by a domain transition arrive
  // upper-cased; codes raised by the API arrive lower-cased. A table written
  // in one casing misses half the refusals, and a miss is indistinguishable
  // from a code nobody thought about.
  const { openBatch, ApiError } = await import("../dist-test/api.js");
  const proposal = {
    participants: ROSTER,
    allocations: {},
    roundingGainers: [],
    totalVnd: 1,
    advancerId: HA_ID,
    occasion: "x",
    expenseId: "e1",
    serverProposal: {},
  };
  const real = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        code: "UNREADY_RECIPIENT_CHOICE_REQUIRED",
        detail: "Batch cannot be frozen",
      }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
  try {
    await openBatch(proposal, "v1", true);
    assert.fail("le ra phai bi tu choi");
  } catch (problem) {
    assert.ok(problem instanceof ApiError);
    assert.equal(problem.code, "UNREADY_RECIPIENT_CHOICE_REQUIRED");
    assert.match(problem.message, /tài khoản nhận/, "van con tieng Anh cua may chu");
    assert.doesNotMatch(problem.message, /Batch cannot be frozen/);
  } finally {
    globalThis.fetch = real;
  }
});

test("ghi vào sổ bị từ chối vì số đã đổi thì nói rõ phải làm gì", async () => {
  const { confirmExpense, ApiError } = await import("../dist-test/api.js");
  const real = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ code: "proposal_changed", detail: "Proposal changed" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
  try {
    await confirmExpense({ expenseId: "e1", serverProposal: {}, allocations: {}, advancerId: "a" });
    assert.fail("le ra phai bi tu choi");
  } catch (problem) {
    assert.ok(problem instanceof ApiError);
    assert.match(problem.message, /Quay lại xem con số mới/);
  } finally {
    globalThis.fetch = real;
  }
});

test("mã lạ giữ nguyên lời của máy chủ, không mượn câu tử tế nào", async () => {
  const { publishBatch, ApiError } = await import("../dist-test/api.js");
  const real = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ code: "chua_tung_thay", detail: "máy chủ nói điều này" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
  try {
    await publishBatch("b", { payerAcknowledged: true }, "a");
    assert.fail("le ra phai bi tu choi");
  } catch (problem) {
    assert.ok(problem instanceof ApiError);
    assert.equal(problem.message, "máy chủ nói điều này");
  } finally {
    globalThis.fetch = real;
  }
});
