/* Deliberately does not compile. Driven by `tests/actor-id-bat-buoc.test.mjs`.
 *
 * This file is the mistake three people made in one day: a call to a route the
 * server guards with `X-Actor-ID`, written without saying who is making it.
 * Kept as a fixture rather than described in prose because the claim under
 * test is "the compiler refuses this", and only the compiler can settle that.
 *
 * Excluded from `tsconfig.json` and absent from `tsconfig.test.json`, so it is
 * compiled by `tsconfig.canary.json` and by nothing else. If it ever starts
 * compiling, the guard it feeds goes red.
 */
import { translatedAsActor } from "../../src/api";

export async function quenActorId(billId: string) {
  // `GET /bills/{id}` requires an actor server-side. None named here.
  return translatedAsActor<{ id: string }>({}, `/bills/${billId}`, { method: "GET" });
}
