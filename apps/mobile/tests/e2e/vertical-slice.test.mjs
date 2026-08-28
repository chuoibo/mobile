/* The whole slice against a running API, using the client the app uses.
 *
 * Every other test in this repo proves a piece. This one proves the pieces
 * connect: propose, confirm, open a batch, publish, and read the guest page
 * that comes out the other end -- through `src/api.ts`, not through hand-rolled
 * requests, so a client that drifts from the contract fails here.
 *
 * Needs a live server. Skips loudly when there is not one, because a skip is
 * not a pass and this file exists precisely to catch what the fakes cannot.
 *
 *     cd services/api && MOBILE_DATABASE_URL=... uvicorn app.api.main:app --port 8099
 *     cd apps/mobile && npm run test:e2e
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import test from "node:test";

import {
  attemptFor,
  BASE_URL,
  newAttempt,
  confirmExpense,
  confirmReceipt,
  loadBoard,
  openBatch,
  proposeSplit,
  publishBatch,
  registerPeople,
} from "../../dist-test/api.js";
import { makeIdFactory } from "../../dist-test/participants.js";

const nextId = makeIdFactory();
const NAM = { id: nextId(), name: "Nam" };
const HA = { id: nextId(), name: "Hà" };
const QUYEN = { id: nextId(), name: "Quyên" };

/**
 * Give the advancer somewhere for the money to land.
 *
 * There is no HTTP route that writes `bank_recipients`, so nothing the app can
 * do produces a bank destination -- and without one the batch never freezes and
 * no envelope is ever built. Seeding the row here is a fixture standing in for
 * that missing route, not a stubbed API: every call below still goes over real
 * HTTP to the real service, and the moment the route exists this is deleted.
 *
 * Filed as a blocker, not silently worked around: see docs/team/ke-hoach-demo-b.md.
 */
function seedBankRecipient(recipientId) {
  execFileSync("python3", ["tests/e2e/seed_bank_recipient.py", recipientId], {
    stdio: "pipe",
  });
}

async function serverIsUp() {
  try {
    const response = await fetch(`${BASE_URL}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

test("một khoản chi đi hết đường tới link của khách", async (t) => {
  if (!(await serverIsUp())) {
    t.skip(`khong co server tai ${BASE_URL} — chay uvicorn roi chay lai`);
    return;
  }

  const draft = {
    participants: [NAM, HA, QUYEN],
    totalVnd: 300_000,
    advancerId: NAM.id,
    occasion: "bữa lẩu tối thứ bảy",
  };

  // Filed the way App.tsx files them, so this exercises the client's real
  // retry behaviour rather than a shape invented for the test.
  const lanBam = {};

  // Names before anything refers to the ids, which is the order App.tsx uses.
  // `PUT /people/{id}` is the only way a name enters this product, and it
  // shipped as a route with no caller: the server had it, the client never
  // called it, and the guest page went on printing UUIDs while every screen in
  // the app still showed the typed name. Asserted at the bottom of this test
  // against the rendered page rather than here, because a 201 from this call
  // proves the request was accepted, not that a reader ever sees the name.
  await registerPeople(draft.participants, NAM.id, lanBam);

  const proposal = await proposeSplit(draft, attemptFor(lanBam, "khoan-chi"));

  // Money rule 2, checked against what the server actually returned rather
  // than against anything computed here.
  const total = Object.values(proposal.allocations).reduce((a, b) => a + b, 0);
  assert.equal(total, draft.totalVnd, "phần chia không cộng lại thành tổng");
  assert.equal(Object.keys(proposal.allocations).length, 3);
  for (const amount of Object.values(proposal.allocations)) {
    assert.ok(Number.isInteger(amount), `${amount} không phải số nguyên đồng`);
  }

  const written = await confirmExpense(proposal, attemptFor(lanBam, "xac-nhan"));
  assert.ok(written.expenseVersionId, "confirm không trả về version");
  assert.equal(written.acknowledged, true, "người ứng tiền chưa được ghi nhận");

  // Before the recipient exists the server refuses, and refusing is correct:
  // section 8.4 says an unready recipient is a decision somebody has to make
  // out loud. Asserted rather than assumed -- if this ever stops refusing, a
  // batch can freeze with nowhere to send the money.
  await assert.rejects(
    () => openBatch(proposal, written.expenseVersionId, written.acknowledged, attemptFor(lanBam, "mo-dot-thu")),
    (error) => error.code === "UNREADY_RECIPIENT_CHOICE_REQUIRED",
    "may chu phai doi hoi quyet dinh ve nguoi nhan chua san sang",
  );

  seedBankRecipient(NAM.id);

  // The same attempt as the refused call above, deliberately. The server
  // releases a key when its handler errors, so the retry after seeding must be
  // allowed to run -- and this is the app's own behaviour, since `attemptFor`
  // returns one attempt per thing being written.
  const batch = await openBatch(
    proposal,
    written.expenseVersionId,
    written.acknowledged,
    attemptFor(lanBam, "mo-dot-thu"),
  );
  assert.ok(batch.batchId);
  // Two people owe the advancer; the advancer does not owe themselves.
  assert.equal(batch.obligations.length, 2);
  assert.ok(!batch.obligations.some((o) => o.senderId === NAM.id));

  // Gate 1 is the server's answer, carried through confirm. Gate 2 is the
  // server's to enforce and is not modelled here at all.
  assert.equal(batch.gates.payerAcknowledged, true);
  await assert.rejects(
    () => publishBatch(batch.batchId, { payerAcknowledged: false }, NAM.id, attemptFor(lanBam, "phat")),
    (error) => error.name === "GateNotPassedError",
    "phat duoc trong khi nguoi ung tien chua xac nhan",
  );

  const envelopes = await publishBatch(
    batch.batchId,
    batch.gates,
    NAM.id,
    attemptFor(lanBam, "phat"),
    draft.participants,
  );
  assert.equal(envelopes.length, 2);

  // The organiser has to be able to tell which link goes to whom. Against a
  // real server this is where ids leak in, because ids are all it sends back.
  for (const envelope of envelopes) {
    assert.ok(
      ["Hà", "Quyên"].includes(envelope.senderName),
      `phong bi ghi "${envelope.senderName}" thay vi ten nguoi`,
    );
  }

  // The link is the product. If it does not render, nothing else mattered.
  const page = await fetch(envelopes[0].url);
  assert.equal(page.status, 200, `link khách trả về ${page.status}`);
  const html = await page.text();
  assert.ok(html.includes("Phần của"), "trang khách không hiện phần của ai");

  // ...and it has to name a person, which the line above never checked. It
  // asserts the words "Phần của" are on the page; it stayed green for the
  // entire life of this file while the sentence underneath read "Phần của
  // a5b2c277-9b99-4699-a875-ed324e886237". The words were there. The person
  // was not.
  //
  // The guest page is the one screen somebody outside the group ever sees, and
  // it is asking them for money. A machine id in that sentence tells the reader
  // neither who is asking nor which of their own debts this is, so the two
  // things the page exists to say are exactly the two it fails to say. Checked
  // against the rendered page rather than against the view model, because the
  // ids reach the reader through the template and nothing in between was
  // looking.
  const quyen = envelopes.find((envelope) => envelope.senderId === QUYEN.id);
  assert.ok(quyen, "khong tim thay phong bi cua Quyên");
  const guestHtml = await (await fetch(quyen.url)).text();
  // Script and style bodies survive tag-stripping and are not read by anyone,
  // so they are removed first; what is left is what a person actually sees.
  const visible = guestHtml
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ");

  const strayId = visible.match(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
  );
  assert.equal(
    strayId?.[0] ?? null,
    null,
    `trang khách hiện mã máy "${strayId?.[0]}" ở chỗ đáng lẽ là tên người`,
  );
  assert.ok(
    visible.includes(`Phần của ${QUYEN.name}`),
    `trang khách không nói phần này của ai — không thấy "Phần của ${QUYEN.name}"`,
  );
  assert.ok(
    visible.includes(`${NAM.name} đã ghi`),
    `trang khách không nói ai ghi khoản chi — không thấy "${NAM.name} đã ghi"`,
  );

  // The share is asserted present before the total is asserted absent, and the
  // order matters. "300.000 is not on the page" passes trivially if the page
  // prints no money at all, or prints it in some other format; finding this
  // person's own amount first proves the negative below is about a leak rather
  // than about a template that renders nothing.
  const share = envelopes[0].amountVnd.toLocaleString("vi-VN").replace(/,/g, ".");
  assert.ok(html.includes(share), `trang khách không hiện ${share}`);
  assert.ok(!html.includes("300.000"), "trang khách để lộ tổng của cả nhóm");

  // The other half of the round, which the app had no way to reach until now:
  // the money comes back. Publishing is not the end of anything -- an
  // organiser still has to see who paid and say it arrived.
  const before = await loadBoard(batch.batchId, NAM.id, draft.participants);
  assert.equal(before.obligations.length, 2);
  assert.ok(
    before.obligations.every((o) => o.status === "outstanding"),
    "co nghia vu da xong truoc khi ai tra tien",
  );
  assert.ok(
    before.obligations.every((o) => ["Hà", "Quyên"].includes(o.senderName)),
    "bang doc ra id thay vi ten",
  );

  const owed = before.obligations[0];
  const receipt = await confirmReceipt(
    owed.id,
    owed.amountVnd,
    NAM.id,
    attemptFor(lanBam, `bao-tien-ve:${owed.id}`),
  );
  assert.equal(receipt.status, "confirmed");

  // Read it back rather than trusting the reply: the board is what an
  // organiser looks at, and it derives status from the ledger rather than
  // storing it. If those two ever disagree, this is where it shows.
  const after = await loadBoard(batch.batchId, NAM.id, draft.participants);
  const settled = after.obligations.find((o) => o.id === owed.id);
  assert.equal(settled.status, "confirmed", "bang khong thay tien da ve");
  assert.equal(
    after.obligations.filter((o) => o.status === "outstanding").length,
    1,
    "xac nhan mot nghia vu lam doi trang thai nghia vu khac",
  );
});

test("bấm hai lần chỉ ghi một khoản chi", async (t) => {
  if (!(await serverIsUp())) {
    t.skip(`khong co server tai ${BASE_URL} — chay uvicorn roi chay lai`);
    return;
  }

  // The reported bug, end to end. Two identical `POST /expenses` with no
  // `Idempotency-Key` left two rows in `expenses`; the client sent no such
  // header on any route, so the server-side protection was installed and never
  // engaged. Counted from the client here rather than from the database: two
  // presses that return one `expense_id` are one row, and that is the fact an
  // organiser's ledger depends on.
  const draft = {
    participants: [NAM, HA, QUYEN],
    totalVnd: 420_000,
    advancerId: NAM.id,
    occasion: "bấm hai lần",
  };

  const lanBam = {};
  const attempt = attemptFor(lanBam, "khoan-chi");
  const first = await proposeSplit(draft, attempt);
  const again = await proposeSplit(draft, attempt);

  assert.equal(
    again.expenseId,
    first.expenseId,
    "bam lai sinh ra khoan chi thu hai; mot bua an dang nam hai lan trong so",
  );

  // The control, and it is not optional: without it this test also passes on a
  // server that returns the same id for everything. A genuinely different
  // press has to write a genuinely different expense.
  const khac = await proposeSplit(draft, newAttempt());
  assert.notEqual(
    khac.expenseId,
    first.expenseId,
    "hai lan bam that su khac nhau bi gop lam mot, mat mot khoan chi",
  );
});
