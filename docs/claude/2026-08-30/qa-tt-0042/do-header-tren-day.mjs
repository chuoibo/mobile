/**
 * Measure the WIRE, not the source: does `docChiaBill` actually send X-Actor-ID?
 *
 * The actor-header gate reads TypeScript text. This reads the request the
 * compiled client hands to `fetch`. When the two disagree, this one is the one
 * that decides, because it is the one the server sees.
 *
 * Build the client first, then run from the repo root:
 *
 *     cd apps/mobile && npm test          # produces dist-test/api.js
 *     node docs/claude/2026-08-30/qa-tt-0042/do-header-tren-day.mjs
 *
 * Exit 0 = the header is on the wire. Exit 1 = the gate was right and this is
 * a real client bug.
 */

import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../../..");
const CLIENT = path.join(REPO, "apps/mobile/dist-test/api.js");

const { docChiaBill } = await import(CLIENT);

const seen = [];
// Stub only the transport. Nothing inside the client is patched, so whatever
// it decides to put in `headers` is what a real server would receive.
globalThis.fetch = async (url, init) => {
  seen.push({ url, method: init.method, headers: init.headers, body: init.body });
  return {
    ok: true,
    status: 200,
    json: async () => ({
      allocation: {
        allocations: { a: 100 },
        exact_shares: { a: "100" },
        rounding_gainers: [],
        warnings: [],
      },
      assignment_state: "confirmed",
      suggested_item_keys: [],
      total_amount_vnd: 100,
    }),
  };
};

await docChiaBill("bill-xyz", "ACTOR-UUID-1234", "ctx-9", { key: "k1", at: 0 });

const req = seen[0];
console.log("URL     :", req.url);
console.log("METHOD  :", req.method);
console.log("HEADERS :", JSON.stringify(req.headers, null, 2));
console.log("BODY    :", req.body);

const actor = req.headers["X-Actor-ID"];
if (actor === "ACTOR-UUID-1234") {
  console.log("\nX-Actor-ID CO tren day:", actor);
  console.log("=> cong bao vi pham la bao nham. San pham dung.");
  process.exit(0);
}
console.log("\nX-Actor-ID KHONG co tren day — day la bug client that.");
process.exit(1);
