/* Drive the real vertical slice and print the guest URLs it produces.
 *
 * QA needs a live guest page to look at with a browser and an axe scan; the
 * e2e test builds one and then throws it away. Same client, same HTTP, no
 * hand-rolled requests -- a URL invented here would prove nothing about what
 * the product actually serves. */
import {
  attemptFor, confirmExpense, openBatch, proposeSplit,
  publishBatch, registerPeople, saveBankRecipient,
} from "../../../apps/mobile/dist-test/api.js";
import { makeIdFactory } from "../../../apps/mobile/dist-test/participants.js";

const nextId = makeIdFactory();
const NAM = { id: nextId(), name: "Nam" };
const HA = { id: nextId(), name: "Hà" };
const QUYEN = { id: nextId(), name: "Quyên" };
// repo-guard: allow=long-number reason=synthetic-test-account-number
const SO_TAI_KHOAN = "0000000000TEST";

const draft = {
  participants: [NAM, HA, QUYEN],
  totalVnd: 300_000,
  advancerId: NAM.id,
  occasion: "bữa lẩu tối thứ bảy",
};
const lanBam = {};

await registerPeople(draft.participants, NAM.id, lanBam);
const proposal = await proposeSplit(draft, attemptFor(lanBam, "khoan-chi"));
const written = await confirmExpense(proposal, attemptFor(lanBam, "xac-nhan"));
await saveBankRecipient(
  NAM.id,
  { bankBin: "970418", accountNumber: SO_TAI_KHOAN, accountName: "NGUOI UNG TIEN" },
  NAM.id,
  attemptFor(lanBam, "tai-khoan-nhan"),
);
const batch = await openBatch(
  proposal, written.expenseVersionId, written.acknowledged,
  attemptFor(lanBam, "mo-dot-thu"),
);
const envelopes = await publishBatch(
  batch.batchId, batch.gates, NAM.id, attemptFor(lanBam, "phat"), draft.participants,
);

for (const e of envelopes) {
  console.log(`${e.senderName}\t${e.amountVnd}\t${e.url}`);
}
