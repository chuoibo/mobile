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
  BASE_URL,
  confirmExpense,
  openBatch,
  proposeSplit,
  publishBatch,
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

  const proposal = await proposeSplit(draft);

  // Money rule 2, checked against what the server actually returned rather
  // than against anything computed here.
  const total = Object.values(proposal.allocations).reduce((a, b) => a + b, 0);
  assert.equal(total, draft.totalVnd, "phần chia không cộng lại thành tổng");
  assert.equal(Object.keys(proposal.allocations).length, 3);
  for (const amount of Object.values(proposal.allocations)) {
    assert.ok(Number.isInteger(amount), `${amount} không phải số nguyên đồng`);
  }

  const written = await confirmExpense(proposal);
  assert.ok(written.expenseVersionId, "confirm không trả về version");
  assert.equal(written.acknowledged, true, "người ứng tiền chưa được ghi nhận");

  // Before the recipient exists the server refuses, and refusing is correct:
  // section 8.4 says an unready recipient is a decision somebody has to make
  // out loud. Asserted rather than assumed -- if this ever stops refusing, a
  // batch can freeze with nowhere to send the money.
  await assert.rejects(
    () => openBatch(proposal, written.expenseVersionId, written.acknowledged),
    (error) => error.code === "UNREADY_RECIPIENT_CHOICE_REQUIRED",
    "may chu phai doi hoi quyet dinh ve nguoi nhan chua san sang",
  );

  seedBankRecipient(NAM.id);

  const batch = await openBatch(proposal, written.expenseVersionId, written.acknowledged);
  assert.ok(batch.batchId);
  // Two people owe the advancer; the advancer does not owe themselves.
  assert.equal(batch.obligations.length, 2);
  assert.ok(!batch.obligations.some((o) => o.senderId === NAM.id));

  // Gate 1 came from the server. Gate 2 is not readable yet, so it is shut --
  // and publish must refuse while it is.
  assert.equal(batch.gates.payerAcknowledged, true);
  assert.equal(batch.gates.recipientReady, false);
  await assert.rejects(() => publishBatch(batch.batchId, batch.gates, NAM.id));

  const envelopes = await publishBatch(
    batch.batchId,
    { ...batch.gates, recipientReady: true, recipientProblem: null },
    NAM.id,
  );
  assert.equal(envelopes.length, 2);

  // The link is the product. If it does not render, nothing else mattered.
  const page = await fetch(envelopes[0].url);
  assert.equal(page.status, 200, `link khách trả về ${page.status}`);
  const html = await page.text();
  assert.ok(html.includes("Phần của"), "trang khách không hiện phần của ai");

  // The share is asserted present before the total is asserted absent, and the
  // order matters. "300.000 is not on the page" passes trivially if the page
  // prints no money at all, or prints it in some other format; finding this
  // person's own amount first proves the negative below is about a leak rather
  // than about a template that renders nothing.
  const share = envelopes[0].amountVnd.toLocaleString("vi-VN").replace(/,/g, ".");
  assert.ok(html.includes(share), `trang khách không hiện ${share}`);
  assert.ok(!html.includes("300.000"), "trang khách để lộ tổng của cả nhóm");
});
