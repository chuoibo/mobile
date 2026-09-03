/* The tail of the hero path, which nothing covered.
 *
 * `vertical-slice.test.mjs` walks an expense as far as the guest page. The
 * product's last step is a different one and lives on a different route:
 * "Cá nhân thấy tài chính cập nhật" -- `App.tsx` reads
 * `docSoDu(CONTEXT_ID, ...)`, i.e. `GET /contexts/{id}/balances`. No test in
 * this repo had ever called that route through the client, so the fact that
 * it answers 403 for the group the app actually uses was invisible: the
 * vertical slice stops before it, and every unit test around balances runs
 * against a fake.
 *
 * Measured on main@bf3c757 against a live API:
 *
 *     GET /contexts/1aa00000-…-0000a0000001/balances -> 403 permission_denied
 *                                                       {"detail":"is_group_member"}
 *     GET /contexts/<a group the actor is in>/balances -> 200 {"balances":[…]}
 *
 * The refusal is correct server behaviour -- `get_context_balances` checks
 * `repository.is_member`, which reads the database rather than trusting the
 * caller's own `X-Actor-Contexts` header. What is wrong is the id the app
 * hands it: `CONTEXT_ID` has never had a row in `contexts`.
 *
 * Why this needs its own test rather than one more assertion in the slice:
 * the two failures have different causes and different owners. The slice
 * fails at `confirm` (`participant_not_in_context`); this fails at
 * `balances` (`permission_denied`). Fixing the expense flow alone turns the
 * slice green and leaves this red, and that is exactly the outcome this file
 * exists to make visible instead of silent.
 *
 * Silent is not a figure of speech. `App.tsx` reads the balance under
 * `.catch(() => setSoDu(null))` -- no error surface, no retry, no message.
 * On screen the group's finances simply do not appear, which reads as "we
 * have not spent anything yet" rather than as a failure.
 *
 * Needs a live server, same convention as the slice: `MOBILE_REQUIRE_E2E=1`
 * turns a missing server into a failure.
 */
import assert from "node:assert/strict";
import test from "node:test";

import * as api from "../../dist-test/api.js";
import { khoiDongNhom } from "../../dist-test/screens/chat/nhom.js";
import { personById } from "../../dist-test/navigation/nhom-demo.js";
import { batPhienE2E } from "./phien-e2e.mjs";

// The API this file talks to runs in `prod` and does not believe `X-Actor-ID`
// (ADR-0014). `scripts/e2e_slice.sh` mints a real session per demo person and
// names the file in MOBILE_E2E_SESSIONS; without it -- a `dev` server -- this
// returns null and changes nothing.
const NGUOI_DANG_NHAP = batPhienE2E(personById("minh")?.personId);

const { BASE_URL, docSoDu } = api;

async function serverIsUp() {
  try {
    const response = await fetch(`${BASE_URL}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

const REQUIRED = Boolean(process.env.MOBILE_REQUIRE_E2E);

async function skipWithoutServer(t) {
  if (await serverIsUp()) return false;
  if (REQUIRED) {
    assert.fail(
      `MOBILE_REQUIRE_E2E dat roi nhung khong co server tai ${BASE_URL}. ` +
        `Chay uvicorn tren cong do roi chay lai.`,
    );
  }
  t.skip(`khong co server tai ${BASE_URL} — chay uvicorn roi chay lai`);
  return true;
}

/**
 * The group the app hands to `docSoDu`.
 *
 * Read off the client rather than pasted in, so that when the fix lands this
 * test follows the app instead of pinning the broken value. If the constant
 * is gone -- the likeliest shape of the fix -- the app must be getting its
 * group from `khoiDongNhom`, so ask that for one and check the same route
 * against it. Either way the assertion below stays the same question: can
 * the app read the balances of the group it is showing?
 */
async function nhomAppDung() {
  if (typeof api.CONTEXT_ID === "string") {
    return { id: api.CONTEXT_ID, nguon: "CONTEXT_ID trong api.ts" };
  }
  const state = await nhomThat();
  return { id: state.contextId, nguon: "khoiDongNhom" };
}

/**
 * A group that genuinely exists, built the way the screens that got this
 * right already build one (`chat/nhom.ts`, `LenPlan.tsx`).
 *
 * `khoiDongNhom` never throws -- it reports failure as `kind: "hong"` -- so
 * the assertion has to read that discriminant. Left implicit, a broken
 * bootstrap would surface further down as `contextId === undefined` and be
 * blamed on the balances route.
 */
async function nhomThat() {
  // The person, not the slug (bug-223337): a bare string has no `.personId`.
  const state = await khoiDongNhom(personById("minh"));
  assert.equal(
    state?.kind,
    "xong",
    `khong dung duoc nhom that: ${state?.buoc ?? "?"} ${state?.status ?? ""} ${state?.detail ?? ""}`,
  );
  return state;
}

/** The signed-in person, as the screens read them off the bootstrapped group. */
function toiTrong(state) {
  const toi = state.members.find((m) => m.state === "active") ?? state.members[0];
  assert.ok(toi?.personId, "nhom that nhung khong co thanh vien nao");
  return toi.personId;
}

test("control: doc so du cua mot nhom co that thi duoc 200", async (t) => {
  if (await skipWithoutServer(t)) return;

  // Asserted first and on purpose. Without it, a failure below is
  // unreadable: a 403 from a broken route and a 403 from a wrong group look
  // identical from the client, and this file would be blaming the app for a
  // server that refuses everybody.
  const nhom = await nhomThat();

  const soDu = await docSoDu(nhom.contextId, toiTrong(nhom));
  // `docSoDu` returns the client's shape, not the wire's: `netByPerson`,
  // `transfers`, `provenMinimal`. Asserting `balances` here -- the field the
  // route answers with -- passed `undefined` through `Array.isArray` and
  // failed for a reason that had nothing to do with the group.
  assert.ok(
    soDu?.netByPerson && typeof soDu.netByPerson === "object",
    "nhom that ma khong doc duoc so du — route hong, khong phai nhom sai",
  );

  // Money rule 3, on the one route that derives balances from the ledger: a
  // closed group's net positions cancel. Checked against what the server
  // returned, not against anything recomputed here.
  const tong = Object.values(soDu.netByPerson).reduce((a, b) => a + b, 0);
  assert.equal(tong, 0, `so du cua ca nhom khong triet tieu: ${tong}`);
});

test("so du cua nhom app dang hien phai doc duoc, khong phai 403", async (t) => {
  if (await skipWithoutServer(t)) return;

  const nhom = await nhomThat();
  const toi = toiTrong(nhom);

  const { id, nguon } = await nhomAppDung();

  // The whole point. `App.tsx:392` makes exactly this call and drops the
  // error on the floor; here it has to answer.
  let soDu;
  try {
    soDu = await docSoDu(id, toi);
  } catch (loi) {
    assert.fail(
      `app doc so du cua nhom no dang hien (${nguon} = ${id}) va bi tu choi: ` +
        `${loi?.code ?? loi?.name} — ${loi?.message}. ` +
        `Man "Ca nhan" khong bao gio hien duoc tai chinh, va App.tsx nuot loi nay.`,
    );
  }

  assert.ok(
    soDu?.netByPerson && typeof soDu.netByPerson === "object",
    `doc so du cua ${nguon} khong tra ve so du nao`,
  );
});
