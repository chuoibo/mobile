/* Forgetting to say who is calling must be a COMPILE error, not a CI error.
 *
 * `call<T>()` used to take `actorId?: string` on one shared options bag. A
 * call that left it out type-checked, ran, sent no `X-Actor-ID`, and came back
 * 401 -- which the screen then reported as a server fault. Three people walked
 * into it independently in a single day (#365, #379, and one before them).
 * Three people hitting the same hole is a fact about the shape, not about the
 * three people.
 *
 * `scripts/check_actor_headers.py` caught every one of them, and that gate is
 * still the one that reads whole call graphs. But it only speaks in CI, long
 * after the mistake was cheap to fix, and a compiler that already holds the
 * answer should not be deferring to a later gate.
 *
 * So the options bag is two types now: `ActorCallOptions`, where `actorId` is
 * required, and `AnonymousCallOptions`, where it is `never`. This guard pins
 * the half that cannot be observed from a passing build -- that the refusal
 * really happens.
 *
 * What this proves: `tsc` refuses a call to an actor-guarded route that names
 * no actor, and refuses it for that reason rather than by failing to resolve
 * an import or by tripping over unrelated damage in `src/`.
 *
 * What this does NOT prove: that every route needing an actor is called with
 * the RIGHT one, that the roles and contexts claimed are the ones the server
 * wants, or that any request is authorised. Impersonation is trivial here --
 * these headers are asserted by the client because no gateway exists to
 * overwrite them. `check_actor_headers.py` covers which routes get a header at
 * all; nothing in this repo yet covers whether the actor is who they say.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Compile the canary program and hand back what the compiler said. */
function compileCanary() {
  const run = spawnSync(
    "npx",
    ["tsc", "-p", "tsconfig.canary.json"],
    { cwd: MOBILE_ROOT, encoding: "utf8", timeout: 300_000 },
  );
  // `tsc` writes diagnostics to stdout, not stderr. Both are joined anyway so
  // a spawn failure (npx missing, timeout) shows up in the assertion message
  // rather than reading as a compiler that simply said nothing.
  return { status: run.status, output: `${run.stdout ?? ""}${run.stderr ?? ""}` };
}

test("quên actorId là lỗi biên dịch, không phải lỗi chỉ CI mới thấy", () => {
  const { status, output } = compileCanary();

  assert.notEqual(
    status,
    0,
    `tsc phải TỪ CHỐI tests/canary/quen-actor-id.ts. Nó biên dịch sạch, nghĩa là ` +
      `actorId đã tuỳ chọn trở lại và cái hố của #365/#379 đã mở lại.\n${output}`,
  );

  assert.match(
    output,
    /quen-actor-id\.ts/,
    `tsc đỏ nhưng không phải vì file canary — lý do khác đang che mất phép đo.\n${output}`,
  );

  // The reason matters as much as the refusal. A missing import or a typo in
  // the fixture would also exit non-zero, and would leave this guard reporting
  // a hole as closed while measuring nothing about actorId at all.
  assert.match(
    output,
    /actorId/,
    `tsc từ chối file canary vì một lý do KHÁC chứ không phải thiếu actorId.\n${output}`,
  );
});

test("chỉ mỗi canary đỏ — src/ vẫn biên dịch sạch trong cùng chương trình", () => {
  const { output } = compileCanary();

  // Every diagnostic line looks like `path/to/file.ts(12,34): error TS1234: ...`.
  // If any of them names a file outside tests/canary, then `src/` is broken and
  // the assertion above was reading somebody else's failure.
  const loi = output
    .split("\n")
    .filter((dong) => /^\S+\.tsx?\(\d+,\d+\): error/.test(dong))
    .filter((dong) => !dong.includes("tests/canary/"));

  assert.deepEqual(
    loi,
    [],
    `Ngoài canary còn file khác không biên dịch được, nên phép đo ở ca trên ` +
      `không nói được điều gì về actorId:\n${loi.join("\n")}`,
  );
});
