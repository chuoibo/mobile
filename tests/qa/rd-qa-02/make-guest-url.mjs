/* rd-qa-02 · Drive the real flow and print real guest URLs.
 *
 * The preview server injects its own state-switcher nav, which is QA
 * scaffolding rather than product markup -- scanning it reports defects
 * against a page no guest will ever load. This walks the actual vertical
 * slice against the live API and prints the envelope URLs the product itself
 * generated, so the accessibility scan runs on shipped markup only.
 *
 *     EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 node make-guest-url.mjs
 */
import {
  BASE_URL,
  CONTEXT_ID,
  confirmExpense,
  newAttempt,
  openBatch,
  proposeSplit,
  publishBatch,
} from "../../../apps/mobile/dist-test/api.js";
import { makeIdFactory } from "../../../apps/mobile/dist-test/participants.js";

const nextId = makeIdFactory();
const PEOPLE = ["Nam", "Hà", "Quyên", "Dũng", "Linh"].map((name) => ({ id: nextId(), name }));
const ADVANCER = PEOPLE[0];
const TOTAL = 1234567;

const draft = {
  occasion: "QA rd-qa-02 a11y",
  totalVnd: TOTAL,
  advancerId: ADVANCER.id,
  participants: PEOPLE,
};

const proposal = await proposeSplit(draft, newAttempt());
const written = await confirmExpense(proposal, newAttempt());

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
if (!bank.ok) throw new Error(`bank-recipients ${bank.status}: ${await bank.text()}`);

const batch = await openBatch(proposal, written.expenseVersionId, written.acknowledged, newAttempt());
const envelopes = await publishBatch(
  batch.batchId,
  { payerAcknowledged: written.acknowledged },
  ADVANCER.id,
  newAttempt(),
  PEOPLE,
);

for (const envelope of envelopes) {
  // Amount included so the scanner's printed-vs-copied check has a value to
  // compare against that came from the server, not from this script.
  console.log(`${envelope.url}\t${envelope.senderName}\t${envelope.amountVnd}`);
}
