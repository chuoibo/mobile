/* What a person is allowed to read when the server refuses.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * rd-fe-08 acceptance: "Không màn nào hiện mã lỗi thô của máy chủ." That is a
 * claim about the string that reaches a `<Text>`, so it is checked here on the
 * string, not on a screenshot. Two real leaks produced this file, and both were
 * measured against the running API rather than imagined:
 *
 *  1. **`detail` is not always a string.** FastAPI answers a malformed body
 *     with `RequestValidationError`, and the app has no handler for it, so the
 *     body is `{"detail": [{type, loc, msg, input}, ...]}` -- a LIST. Measured
 *     against `create_app()` with TestClient: `POST /expenses {"nope": 1}` came
 *     back 422 with three of those objects. `api.ts` assigned that list into an
 *     `Error` message, which stringifies it, and the banner in `App.tsx`
 *     rendered the result verbatim:
 *
 *         [object Object],[object Object],[object Object]
 *
 *  2. **The no-JSON fallback was written for a developer.** It read
 *     `` `${method} ${path} trả về ${response.status}` ``, so a crashed proxy
 *     put "POST /obligations/.../receipt-confirmations trả về 500" in front of
 *     somebody standing over their own money.
 *
 * The gate has to cut both ways, and the second direction is the one that keeps
 * it honest. The server's own refusals are already Vietnamese and already say
 * what to do next -- `SCAN_REFUSALS` and the publish table exist because those
 * sentences are good. A normaliser that threw them away in the name of safety
 * would replace specific, correct copy with a generic apology, so the last test
 * pins that they still arrive untouched.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { confirmReceipt, scanReceipt, thongDiepNguoiDoc } from "../dist-test/api.js";

/** Anything a machine says to another machine, and no person should ever read. */
const MAY_MOC = [
  "[object Object]",
  "Field required",
  "Internal Server Error",
  "Unprocessable",
  "Traceback",
  "null",
  "undefined",
];

/** Vietnamese carries diacritics. A "Vietnamese" sentence with none is English. */
const DAU_TIENG_VIET =
  /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụỳýỷỹỵ]/i;

function noiNhu(status, body, { json = true } = {}) {
  return async () =>
    new Response(json ? JSON.stringify(body) : body, {
      status,
      headers: { "Content-Type": json ? "application/json" : "text/html" },
    });
}

async function batLoi(work) {
  try {
    await work();
  } catch (problem) {
    return problem;
  }
  throw new Error("gọi xong mà không ném lỗi, test này không đo được gì");
}

function doiSach(message, ghiChu) {
  assert.equal(typeof message, "string", `${ghiChu}: phải là chuỗi`);
  for (const rac of MAY_MOC) {
    assert.equal(
      message.includes(rac),
      false,
      `${ghiChu}: lọt chữ của máy "${rac}" ra màn hình: ${message}`,
    );
  }
  assert.match(message, DAU_TIENG_VIET, `${ghiChu}: không phải tiếng Việt: ${message}`);
  // A raw route is the other half of leak 2. "POST /expenses" is not copy.
  assert.equal(
    /\b(GET|POST|PUT|PATCH|DELETE)\s+\//.test(message),
    false,
    `${ghiChu}: in ra method + path của máy chủ: ${message}`,
  );
}

const ANH = { uri: "file:///tmp/bill.jpg", bytes: 1234 };
// Hex letters on purpose. An all-digit UUID is 32 digits in a row, which the
// repo guard reads as a possible account number and blocks the commit over.
const LAN_BAM = { key: "a1b2c3d4-e5f6-4a1b-8c2d-e3f4a5b6c7d8", at: 0 };

test("422 với detail là một mảng không còn thành [object Object]", async () => {
  // The exact body measured from the real app, not an invented shape.
  const that = [
    { type: "missing", loc: ["body", "context_id"], msg: "Field required", input: { nope: 1 } },
    { type: "missing", loc: ["body", "paid_by_id"], msg: "Field required", input: { nope: 1 } },
  ];
  const goc = globalThis.fetch;
  globalThis.fetch = noiNhu(422, { detail: that });
  try {
    const loi = await batLoi(() => scanReceipt(ANH, "nguoi-quet"));
    doiSach(loi.message, "quét bill 422 mảng");
  } finally {
    globalThis.fetch = goc;
  }
});

test("500 không phải JSON không còn in method, path và mã số", async () => {
  const goc = globalThis.fetch;
  globalThis.fetch = noiNhu(500, "<html>502 Bad Gateway</html>", { json: false });
  try {
    const loi = await batLoi(() =>
      confirmReceipt("nghia-vu-1", 50000, "nguoi-nhan", LAN_BAM),
    );
    doiSach(loi.message, "báo tiền về 500 không JSON");
  } finally {
    globalThis.fetch = goc;
  }
});

test("detail tiếng Anh của máy chủ không đi thẳng ra màn hình", async () => {
  const goc = globalThis.fetch;
  globalThis.fetch = noiNhu(500, { detail: "Internal Server Error" });
  try {
    const loi = await batLoi(() =>
      confirmReceipt("nghia-vu-1", 50000, "nguoi-nhan", LAN_BAM),
    );
    doiSach(loi.message, "500 detail tiếng Anh");
  } finally {
    globalThis.fetch = goc;
  }
});

/* The other direction. A gate that only ever deletes is a gate that turns
 * good copy into a generic apology, and then somebody switches it off. */
test("câu tiếng Việt của máy chủ vẫn tới được người dùng nguyên vẹn", async () => {
  const cuaMayChu =
    "Chưa đọc được bill này. Chụp lại gần hơn một chút, để cả tờ bill nằm trong khung.";
  const goc = globalThis.fetch;
  globalThis.fetch = noiNhu(400, { code: "khong_ai_liet_ke", detail: cuaMayChu });
  try {
    const loi = await batLoi(() =>
      confirmReceipt("nghia-vu-1", 50000, "nguoi-nhan", LAN_BAM),
    );
    assert.equal(loi.message, cuaMayChu, "câu tiếng Việt đúng của máy chủ bị nuốt mất");
  } finally {
    globalThis.fetch = goc;
  }
});

test("thongDiepNguoiDoc: mảng, object và chuỗi rỗng đều bị từ chối", () => {
  for (const rac of [[{ msg: "Field required" }], { msg: "x" }, "", "   ", null, undefined, 42]) {
    doiSach(thongDiepNguoiDoc(422, rac), `detail = ${JSON.stringify(rac) ?? String(rac)}`);
  }
});

test("thongDiepNguoiDoc: mỗi nhóm mã trả về một việc để làm tiếp", () => {
  // Not "each status has words" -- each status has DIFFERENT words. One
  // sentence reused for every failure is the generic apology in disguise.
  const cau = new Map();
  for (const status of [400, 403, 404, 409, 429, 500, 503]) {
    const noi = thongDiepNguoiDoc(status, "Internal Server Error");
    doiSach(noi, `status ${status}`);
    assert.equal(String(status).includes(noi) || noi.includes(String(status)), false,
      `status ${status}: in mã số máy chủ ra màn hình: ${noi}`);
    cau.set(noi, (cau.get(noi) ?? 0) + 1);
  }
  assert.ok(cau.size >= 4, `chỉ có ${cau.size} câu khác nhau cho 7 nhóm mã, quá chung chung`);
});
