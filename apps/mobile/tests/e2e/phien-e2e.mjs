/* Sessions for the e2e slice, because the API it talks to runs in `prod`.
 *
 * `scripts/e2e_slice.sh` starts uvicorn with no `MOBILE_AUTH_MODE`, so the
 * server does not believe `X-Actor-ID` (ADR-0014). It then mints one real
 * session per demo person with `scripts/genesis_session.py` and hands the map
 * over in `MOBILE_E2E_SESSIONS`.
 *
 * ## The one thing this file fakes, and the one thing it must not
 *
 * The product signs in **one** person per device: `datTokenPhien` holds a
 * single token, and that is correct. The slice drives three people through one
 * node process, which is three devices pretending to be one. Something has to
 * bridge that, and the choice matters:
 *
 * - The global token is set to the person the slice mostly acts as. Their
 *   requests get their bearer from `actorHeaders` in `src/api.ts` -- the real
 *   client path, exercised for real.
 * - `fetch` is wrapped only to *correct* a request whose `X-Actor-ID` names
 *   somebody else. That is the second and third phone.
 *
 * `daVa()` reports how many requests the wrapper had to correct, per person.
 * The slice asserts it is zero for the signed-in person: if the client stopped
 * attaching the bearer itself, this harness would paper over it and the slice
 * would stay green while the app was broken on a real host.
 */
import { readFileSync } from "node:fs";

import { datTokenPhien } from "../../dist-test/api.js";

let phien = null;
let daSua = new Map();
let fetchGoc = null;

/** `{personId: token}` from the harness, or null when running without one. */
export function banDoPhien() {
  return phien;
}

/** How many requests the wrapper had to correct, for one person. */
export function daVa(personId) {
  return daSua.get(personId) ?? 0;
}

/**
 * `fetch` with the wrapper stepped over.
 *
 * For the one case that has to reach the server exactly as written: a forged
 * `X-Actor-ID` and no bearer. Through the wrapper that request would be
 * repaired into a valid one and would prove the opposite of what it says.
 */
export function fetchTho(url, init) {
  return (fetchGoc ?? globalThis.fetch)(url, init);
}

function docHeader(init, ten) {
  const h = init?.headers;
  if (!h) return undefined;
  if (typeof h.get === "function") return h.get(ten) ?? undefined;
  for (const [k, v] of Object.entries(h)) {
    if (k.toLowerCase() === ten.toLowerCase()) return v;
  }
  return undefined;
}

function datHeader(init, ten, gia) {
  const h = init.headers;
  if (h && typeof h.set === "function") {
    h.set(ten, gia);
    return;
  }
  init.headers = { ...(h ?? {}), [ten]: gia };
}

/**
 * Turn the harness's sessions on. Returns the person the client is signed in
 * as, or null when `MOBILE_E2E_SESSIONS` is unset (a `dev` server, where the
 * headers still work and none of this is needed).
 */
export function batPhienE2E(nguoiChinh) {
  const duong = process.env.MOBILE_E2E_SESSIONS;
  if (!duong) return null;

  phien = JSON.parse(readFileSync(duong, "utf8"));
  daSua = new Map();

  const chinh = nguoiChinh && phien[nguoiChinh] ? nguoiChinh : Object.keys(phien)[0];
  datTokenPhien(phien[chinh]);

  if (fetchGoc === null) {
    fetchGoc = globalThis.fetch;
    globalThis.fetch = async (url, init = {}) => {
      const actor = docHeader(init, "X-Actor-ID");
      const token = actor ? phien[actor] : undefined;
      if (token) {
        const mang = docHeader(init, "Authorization");
        if (mang !== `Bearer ${token}`) {
          const next = { ...init };
          datHeader(next, "Authorization", `Bearer ${token}`);
          daSua.set(actor, (daSua.get(actor) ?? 0) + 1);
          return fetchGoc(url, next);
        }
      }
      return fetchGoc(url, init);
    };
  }
  return chinh;
}
