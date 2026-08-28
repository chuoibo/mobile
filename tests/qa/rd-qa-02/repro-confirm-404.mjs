/* rd-qa-02 · Minimal repro: POST /expenses succeeds, the confirm right after it 404s.
 *
 * Two HTTP calls, no client library, no fixtures, fresh UUIDs every round so no
 * round can be confused with another. Reproduces on a freshly migrated,
 * otherwise-untouched database, which is what rules out interference from
 * another lane sharing the dev Postgres.
 *
 *     EXPO_PUBLIC_API_URL=http://127.0.0.1:PORT node tests/qa/rd-qa-02/repro-confirm-404.mjs 300
 *
 * Exit 0 means it did NOT reproduce this run. The failure is intermittent, so a
 * single clean run is not evidence the bug is gone -- the rate is roughly
 * 0.5-7% per attempt, so a few hundred rounds are needed to say anything.
 */
import { randomUUID } from "node:crypto";

const BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";
const CTX = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";
const rounds = Number(process.argv[2] ?? 300);

const headers = (id) => ({
  "Content-Type": "application/json",
  "X-Actor-ID": id,
  "X-Actor-Roles": "member,advancer,recipient,batch_owner",
  "X-Actor-Contexts": CTX,
});

let failures = 0;
for (let i = 0; i < rounds; i++) {
  const people = [randomUUID(), randomUUID(), randomUUID()];
  const created = await fetch(`${BASE}/expenses`, {
    method: "POST",
    headers: headers(people[0]),
    body: JSON.stringify({
      context_id: CTX,
      description: `repro ${i}`,
      recorded_by_id: people[0],
      paid_by_id: people[0],
      verification_scope: "totals_only",
      occurred_at: new Date().toISOString(),
      participants: people,
      total_amount_vnd: 100000,
      items: [],
      surcharges: [],
      discounts: [],
    }),
  });
  if (!created.ok) {
    console.log(`#${i} POST /expenses ${created.status}: ${await created.text()}`);
    failures += 1;
    continue;
  }
  const proposal = await created.json();
  const confirmed = await fetch(`${BASE}/expenses/${proposal.expense_id}/confirm`, {
    method: "POST",
    headers: headers(people[0]),
    body: JSON.stringify({
      proposal: proposal.proposal,
      expected_allocations: proposal.allocation.allocations,
      acknowledge_as_advancer: true,
    }),
  });
  if (!confirmed.ok) {
    failures += 1;
    console.log(
      `#${i} confirm ${confirmed.status} ${await confirmed.text()} (expense_id=${proposal.expense_id})`,
    );
  }
}
const rate = ((100 * failures) / rounds).toFixed(2);
console.log(`\n${failures}/${rounds} confirm thất bại (${rate}%) tại ${BASE}`);
process.exit(failures === 0 ? 0 : 1);
