/* rd-qa-02 · Server-side money invariants, over real HTTP, through the app's own client.
 *
 * Run from apps/mobile with a live API:
 *     EXPO_PUBLIC_API_URL=http://127.0.0.1:PORT node --test ../../tests/qa/rd-qa-02/money-server-truth.mjs
 *
 * Every number asserted here comes back from the server. The harness never
 * divides, never rounds, never reconstructs a share. The only things it knows
 * up front are the bill total and the roster; the split is the server's answer.
 * That is the whole point -- a second allocator written in the test would only
 * prove two implementations agree on the same mistake.
 *
 * Invariants under test (task rd-qa-02):
 *   1. sum(allocations) === total, difference exactly 0
 *   2. every share is a non-negative integer dong
 *   3. proposing the same bill twice returns the identical split
 *   4. total debt === total credit across the opened batch
 *   5. the server refuses a confirm whose numbers are not the ones on screen
 *   6. correcting a mis-read digit re-splits correctly against the new total
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  BASE_URL,
  CONTEXT_ID,
  confirmExpense as confirmExpenseRaw,
  newAttempt,
  openBatch as openBatchRaw,
  proposeSplit as proposeSplitRaw,
} from "../../../apps/mobile/dist-test/api.js";
import { makeIdFactory } from "../../../apps/mobile/dist-test/participants.js";

// Every call below is a distinct press, never a retry, so each mints its own
// attempt. Sharing one key across two writes is exactly what the idempotency
// middleware exists to refuse; reusing it here would test the middleware by
// accident and hide whatever the allocator actually did.
const proposeSplit = (draft) => proposeSplitRaw(draft, newAttempt());
const confirmExpense = (proposal) => confirmExpenseRaw(proposal, newAttempt());
const openBatch = (proposal, versionId, acknowledged) =>
  openBatchRaw(proposal, versionId, acknowledged, newAttempt());

const nextId = makeIdFactory();

/** Roster big enough that remainder distribution has somewhere to go. */
const PEOPLE = ["Nam", "Hà", "Quyên", "Dũng", "Linh", "Tú", "Bảo"].map((name) => ({
  id: nextId(),
  name,
}));

const ADVANCER = PEOPLE[0];

/** Bill totals chosen to land on every remainder class for the party sizes used. */
const TOTALS = [
  1, 2, 3, 5, 7,
  100, 101, 999,
  82000, 100000, 100001, 100002,
  246000, 333333, 1000000, 1234567,
  1_000_000_000 - 1,
];

const PARTY_SIZES = [2, 3, 4, 5, 7];

async function serverIsUp() {
  try {
    const response = await fetch(`${BASE_URL}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

const up = await serverIsUp();

/** Rows collected for the screen-vs-server table in the report. */
export const ledger = [];

function draftFor(totalVnd, size, occasion) {
  return {
    occasion,
    totalVnd,
    advancerId: ADVANCER.id,
    participants: PEOPLE.slice(0, size),
  };
}

test("rd-qa-02 server money invariants", { skip: up ? false : `no server at ${BASE_URL}` }, async (t) => {
  await t.test("sum of shares equals the bill, to the dong", async () => {
    let checked = 0;
    for (const size of PARTY_SIZES) {
      for (const totalVnd of TOTALS) {
        const proposal = await proposeSplit(
          draftFor(totalVnd, size, `sum ${totalVnd}/${size}`),
        );
        const shares = Object.values(proposal.allocations);
        const sum = shares.reduce((a, b) => a + b, 0);
        assert.equal(
          sum - totalVnd,
          0,
          `total ${totalVnd} across ${size}: server split sums to ${sum}, difference ${sum - totalVnd}`,
        );
        assert.equal(shares.length, size, `expected ${size} shares, got ${shares.length}`);
        checked += 1;
      }
    }
    assert.ok(checked === PARTY_SIZES.length * TOTALS.length);
    console.log(`  [sum] ${checked} bills, every difference exactly 0`);
  });

  await t.test("every share is a non-negative integer dong", async () => {
    let shares = 0;
    for (const size of PARTY_SIZES) {
      for (const totalVnd of TOTALS) {
        const proposal = await proposeSplit(
          draftFor(totalVnd, size, `int ${totalVnd}/${size}`),
        );
        for (const [id, amount] of Object.entries(proposal.allocations)) {
          assert.ok(
            Number.isInteger(amount),
            `share for ${id} on ${totalVnd}/${size} is not an integer: ${amount}`,
          );
          assert.ok(amount >= 0, `negative share ${amount} on ${totalVnd}/${size}`);
          shares += 1;
        }
      }
    }
    console.log(`  [integer] ${shares} shares, all integer and non-negative`);
  });

  await t.test("splitting the same bill twice returns the same numbers", async () => {
    // Not a cache check: each call writes a separate draft expense. The claim
    // is that the allocator is a function of its inputs, so a person who
    // re-enters the same bill sees the same answer rather than a new one.
    for (const size of PARTY_SIZES) {
      for (const totalVnd of [1, 7, 100001, 1234567, 1_000_000_000 - 1]) {
        const first = await proposeSplit(draftFor(totalVnd, size, `again-a ${totalVnd}/${size}`));
        const second = await proposeSplit(draftFor(totalVnd, size, `again-b ${totalVnd}/${size}`));
        assert.deepEqual(
          second.allocations,
          first.allocations,
          `re-split of ${totalVnd}/${size} disagreed with the first split`,
        );
        assert.deepEqual(second.roundingGainers, first.roundingGainers);
      }
    }
    console.log("  [determinism] 25 re-splits, all identical to the first answer");
  });

  await t.test("correcting a mis-read digit re-splits against the corrected total", async () => {
    // The OCR case: the bill is 820.000 and the reader dropped a zero to
    // 82.000. The person fixes the number and the split must follow it.
    const misread = 82000;
    const corrected = 820000;
    const size = 5;

    const wrong = await proposeSplit(draftFor(misread, size, "bill misread"));
    const wrongSum = Object.values(wrong.allocations).reduce((a, b) => a + b, 0);
    assert.equal(wrongSum, misread);

    const fixed = await proposeSplit(draftFor(corrected, size, "bill corrected"));
    const fixedSum = Object.values(fixed.allocations).reduce((a, b) => a + b, 0);
    assert.equal(fixedSum - corrected, 0, "corrected bill does not sum to the corrected total");
    assert.notDeepEqual(fixed.allocations, wrong.allocations, "correction changed nothing");

    ledger.push({ case: "ocr-correction", misread, corrected, wrongSum, fixedSum });
    console.log(
      `  [correction] ${misread} -> ${corrected}: shares re-summed to ${fixedSum}, difference 0`,
    );
  });

  await t.test("the server refuses numbers that were never on screen", async () => {
    // The client cannot push its own split. Confirm carries the allocation the
    // person looked at; the server recomputes and compares. Bend one share by a
    // single dong and it must refuse, or a client-side allocator could win.
    const proposal = await proposeSplit(draftFor(100000, 3, "tamper"));
    const ids = Object.keys(proposal.allocations);
    const tampered = { ...proposal.allocations };
    tampered[ids[0]] = tampered[ids[0]] + 1;
    tampered[ids[1]] = tampered[ids[1]] - 1; // still sums to the total

    await assert.rejects(
      () => confirmExpense({ ...proposal, allocations: tampered }),
      (error) => {
        assert.equal(error.code, "proposal_changed", `unexpected refusal code ${error.code}`);
        return true;
      },
      "server accepted an allocation the person never saw",
    );
    console.log("  [tamper] one dong moved between two people -> refused, proposal_changed");
  });

  await t.test("total debt equals total credit in the opened batch", async () => {
    const totalVnd = 1234567;
    const size = 5;
    const proposal = await proposeSplit(draftFor(totalVnd, size, "debt equals credit"));
    const written = await confirmExpense(proposal);

    // Give the advancer somewhere for money to land, over the real route.
    const bank = await fetch(`${BASE_URL}/bank-recipients`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": ADVANCER.id,
        "X-Actor-Roles": "member,advancer,recipient,batch_owner",
        "X-Actor-Contexts": CONTEXT_ID,
      },
      body: JSON.stringify({
        recipient_id: ADVANCER.id,
        bank_bin: "970418",
        account_number: "QATESTACCT",
        account_name: "NGUOI UNG TIEN",
      }),
    });
    assert.ok(bank.ok, `bank-recipients returned ${bank.status}: ${await bank.text()}`);

    const batch = await openBatch(proposal, written.expenseVersionId, written.acknowledged);

    const debts = batch.obligations.reduce((sum, o) => sum + o.amountVnd, 0);
    const advancerShare = proposal.allocations[ADVANCER.id];
    const credit = totalVnd - advancerShare;

    assert.equal(
      debts - credit,
      0,
      `debts ${debts} against credit ${credit}, difference ${debts - credit}`,
    );
    // Every obligation is owed to the person who fronted the money, and nobody
    // is ever billed by themselves.
    for (const o of batch.obligations) {
      assert.equal(o.recipient, ADVANCER.name, "an obligation points somewhere other than the advancer");
      assert.notEqual(o.senderId, ADVANCER.id, "the advancer owes themselves");
      assert.ok(Number.isInteger(o.amountVnd) && o.amountVnd > 0);
    }
    // And each debt is exactly that person's share -- no reshaping in between.
    for (const o of batch.obligations) {
      assert.equal(
        o.amountVnd,
        proposal.allocations[o.senderId],
        `obligation for ${o.senderName} is ${o.amountVnd}, share was ${proposal.allocations[o.senderId]}`,
      );
    }
    console.log(
      `  [debt=credit] ${batch.obligations.length} obligations, debts ${debts} = credit ${credit}, difference 0`,
    );
  });
});
