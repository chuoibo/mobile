/* Does the app's publish-refusal table match the codes the server actually sends?
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/
 *
 * There was a test for this before and it was green while all three gate codes
 * were wrong. It built its expectations from `Object.keys(PUBLISH_REFUSALS)`
 * and then mocked the server into returning those keys, so it proved the table
 * agreed with itself. Mutating a key kept it honest-looking -- test and table
 * moved together, because one author wrote both.
 *
 * So the codes here come from the server's source and nowhere else. See
 * `server-codes.mjs`: it parses `unmet_publish_gates()` and `publish_batch()`,
 * and throws rather than returning an empty list if the parse degrades.
 *
 * Two checks, and they fail for different reasons:
 *
 *   forward  -- every gate the server can refuse on has Vietnamese words.
 *               Catches a code the app never heard of. This is the one that
 *               was red: the table named `advancer_not_acknowledged`, which
 *               appears nowhere in `services/api/app`.
 *   backward -- every key in the table is a code publish can actually emit.
 *               Catches invented keys and keys borrowed from another endpoint,
 *               which read as coverage while translating nothing.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { publishApiCodes, publishGateCodes } from "./server-codes.mjs";

/** A fixed attempt, so these tests stay about refusals and names, not keys. */
const LAN_BAM = { key: "K-test", at: 1_700_000_000_000 };


/** Anything with a Vietnamese-only letter in it. */
const VIETNAMESE = /[ăâêôơưđàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]/i;

test("mọi cổng phát của máy chủ đều có câu tiếng Việt trong bảng của app", async () => {
  const { PUBLISH_REFUSALS } = await import("../dist-test/api.js");
  const gates = publishGateCodes();

  const missing = gates.filter((code) => !(code in PUBLISH_REFUSALS));
  assert.deepEqual(
    missing,
    [],
    `Ma may chu phat ra ma app khong dich duoc: ${missing.join(", ")}. ` +
      `Nguon: unmet_publish_gates() trong services/api/app/domain/collection.py. ` +
      `Bang cua app dang co: ${Object.keys(PUBLISH_REFUSALS).join(", ")}.`,
  );
});

test("bảng của app không chứa mã nào mà cổng phát không bao giờ gửi", async () => {
  const { PUBLISH_REFUSALS } = await import("../dist-test/api.js");
  const emittable = new Set([...publishGateCodes(), ...publishApiCodes()]);

  const invented = Object.keys(PUBLISH_REFUSALS).filter((key) => !emittable.has(key));
  assert.deepEqual(
    invented,
    [],
    `Bang co ma khong ai phat: ${invented.join(", ")}. ` +
      `Mot khoa chet la mot dong dich khong bao gio chay, va no doc ra nhu da phu song. ` +
      `Ma publish that su phat: ${[...emittable].join(", ")}.`,
  );
});

test("chạy thật từng mã cổng: người dùng thấy tiếng Việt, không thấy tiếng Anh của máy chủ", async () => {
  const { publishBatch, ApiError } = await import("../dist-test/api.js");
  const serverDetail = "A publish gate is not satisfied";
  const real = globalThis.fetch;

  try {
    for (const code of publishGateCodes()) {
      globalThis.fetch = async () =>
        new Response(JSON.stringify({ code, detail: serverDetail }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        });

      await assert.rejects(
        () => publishBatch("b", { payerAcknowledged: true }, "a", LAN_BAM),
        (problem) => {
          assert.ok(problem instanceof ApiError, `${code}: sai kieu loi`);
          // The code survives translation, otherwise a bug report cannot name
          // what happened.
          assert.equal(problem.code, code, `${code}: mat ma loi thi het truy duoc`);
          assert.notEqual(
            problem.message,
            serverDetail,
            `${code}: roi xuong nhanh lui, nguoi dung doc tieng Anh cua may chu`,
          );
          assert.match(problem.message, VIETNAMESE, `${code}: cau tra ve khong phai tieng Viet`);
          return true;
        },
      );
    }
  } finally {
    globalThis.fetch = real;
  }
});

test("đợt thu không tồn tại cũng đọc được", async () => {
  const { publishBatch, ApiError } = await import("../dist-test/api.js");
  const real = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ code: "batch_not_found", detail: "Batch does not exist" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  try {
    await assert.rejects(
      () => publishBatch("b", { payerAcknowledged: true }, "a", LAN_BAM),
      (problem) => {
        assert.ok(problem instanceof ApiError);
        assert.match(problem.message, /Không tìm thấy/);
        return true;
      },
    );
  } finally {
    globalThis.fetch = real;
  }
});
