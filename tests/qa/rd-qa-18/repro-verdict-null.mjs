/**
 * rd-qa-18 minimal reproduction: F12 search results are refused by the app
 * whenever the AI actually writes a reason.
 *
 * Deterministic on purpose. The bug rides on a live model deciding to write a
 * `reason`, which makes the browser walk that found it a coin flip; this repro
 * replays a CAPTURED real response body, so it fails identically every run and
 * needs no API key, no network and no server.
 *
 * The contract break, in three lines that live in two different owners' files:
 *
 *   services/api/app/api/routes/places.py:399
 *     out.append(_card(place, reason, verdict=None))      # search: always null
 *
 *   services/api/app/api/routes/places.py:253
 *     source="ai" if reason else "none"                   # reason present -> "ai"
 *
 *   apps/mobile/src/screens/kham-pha/places.ts:201
 *     if ((source === "ai") !== (verdict !== null)) throw # client forbids that pair
 *
 * So a search card carrying a model-written sentence is always `source="ai"`
 * with `verdict=null`, which is exactly the combination the client rejects --
 * and `parsePlace` throws for the whole response, not for the one card, so the
 * user gets an error panel instead of the places that really did match.
 *
 * The invariant is not new and is not wrong: it predates #143 and is on main,
 * where it protects `GET /places` (browse), whose reason writer supplies a
 * verdict alongside every reason. #139 added a second producer that cannot
 * satisfy it.
 *
 * Run: node tests/qa/rd-qa-18/repro-verdict-null.mjs
 */

import { readFileSync } from "node:fs";
import { parsePlace } from "../../../apps/mobile/dist-test/screens/kham-pha/places.js";

// Captured verbatim from POST /places/search on 127.0.0.1:8232 (server built
// from origin/main @ 3c6d918), query: "quán cafe chill view đẹp cho nhóm 6
// người ngồi tối nay". Reproduced 3/3 consecutive calls.
//
// Loaded from the capture rather than retyped. The first version of this file
// hand-built the card, left out `travel_minutes`, and threw on THAT instead --
// which printed "NOT REPRODUCED" and would have retracted a real bug. A
// fixture that is not the real payload tests the fixture.
const CARD_FROM_REAL_SEARCH = JSON.parse(
  readFileSync(new URL("./the-tim-kiem-that.json", import.meta.url), "utf8")
);

// Control: the same card with no model sentence. This is the shape the screen
// renders happily today, and it is why the bug looks intermittent rather than
// broken -- a search the model declines to explain works fine.
// `reason` stays a non-empty sentence: when the model says nothing the server
// substitutes its own template line and labels it `source: "none"`. Blanking
// the string instead would trip a different rule and prove the wrong thing.
const CONTROL_NO_REASON = {
  ...CARD_FROM_REAL_SEARCH,
  match: {
    ...CARD_FROM_REAL_SEARCH.match,
    reason: "Hợp ngân sách và gần chỗ nhóm hẹn.",
    source: "none",
    verdict: null,
  },
};

function attempt(label, card) {
  try {
    parsePlace(card, "places[0]");
    console.log(`  ${label}: parsed OK`);
    return "ok";
  } catch (error) {
    console.log(`  ${label}: THREW -> ${error.message}`);
    return "threw";
  }
}

console.log("F12 search card carrying a model-written reason:");
const withReason = attempt("source=ai, verdict=null", CARD_FROM_REAL_SEARCH);

console.log("\nControl - same card, model wrote no reason:");
const withoutReason = attempt("source=none, verdict=null", CONTROL_NO_REASON);

console.log("\n" + "=".repeat(66));
if (withReason === "threw" && withoutReason === "ok") {
  console.log("REPRODUCED: the app refuses the whole search response exactly when");
  console.log("the AI succeeded at explaining the match. Feature works only when");
  console.log("the model stays silent.");
  process.exit(1);
}
console.log("NOT REPRODUCED — the contract may have been fixed; re-check before filing.");
process.exit(0);
