/* What the bill camera must do when things go wrong.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * These cover the three acceptance criteria of rd-do-02 that do not need a
 * phone, which is most of them:
 *
 *   - "Từ chối quyền -> có màn giải thích, không phải màn trắng"
 *   - "Ảnh tạm bị xoá sau khi đọc"
 *   - the web half of "camera thật", where there is no camera to be had
 *
 * The one criterion left over is "chụp được ảnh trên máy thật, ảnh tới được
 * API", which needs a phone and a hand. That is stated as untested rather than
 * approximated with a mock, because a mock of a camera proves nothing about a
 * camera.
 *
 * `native.ts` is deliberately absent here: it imports expo-camera, which the
 * node runner cannot load. Everything worth asserting was kept out of it, and
 * what remains is checked by `tsc --noEmit` and the web export build.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  DEFAULT_MESSAGES,
  assertNoBlankExplanation,
  readAccess,
} from "../dist-test/camera/access.js";
import {
  BillPhotoError,
  MAX_BYTES,
  MAX_EDGE,
  compressForReading,
  fitLongestEdge,
  withBillPhoto,
} from "../dist-test/camera/bill-photo.js";

const granted = { status: "granted", granted: true, canAskAgain: true };
const undetermined = { status: "undetermined", granted: false, canAskAgain: true };
const deniedAskable = { status: "denied", granted: false, canAskAgain: true };
const deniedFinal = { status: "denied", granted: false, canAskAgain: false };

/* ---------------------------------------------------------------- quyền --- */

test("mỗi trạng thái quyền đều có lời giải thích, không có màn trắng", () => {
  const cases = [null, undetermined, granted, deniedAskable, deniedFinal];
  for (const hasCamera of [true, false]) {
    for (const permission of cases) {
      const access = readAccess(permission, hasCamera);
      assert.notEqual(access.message.trim(), "", `trống ở ${access.state}`);
      assert.ok(access.nextAction, `không có hành động kế ở ${access.state}`);
    }
  }
});

test("bộ chữ mặc định phủ đủ mọi trạng thái", () => {
  assert.doesNotThrow(() => assertNoBlankExplanation(DEFAULT_MESSAGES));
});

test("frontend xoá mất một câu thì bị bắt, không im lặng ra màn trắng", () => {
  // The realistic way a blank explanation comes back: someone overrides the
  // copy and misses a state. This is the guard that makes that loud.
  const holes = { ...DEFAULT_MESSAGES, "tu-choi-phai-vao-cai-dat": "   " };
  assert.throws(() => assertNoBlankExplanation(holes), /tu-choi-phai-vao-cai-dat/);
});

test("từ chối nhưng còn hỏi lại được -> nút hỏi lại là nút thật", () => {
  const access = readAccess(deniedAskable, true);
  assert.equal(access.state, "tu-choi-hoi-lai-duoc");
  assert.equal(access.nextAction, "xin-quyen");
});

test("từ chối hẳn -> phải đẩy sang Cài đặt, KHÔNG được hỏi lại", () => {
  // The bug this pins: `canAskAgain: false` means the OS stops showing the
  // dialog, so a "cho phép" button there resolves instantly with another
  // denial and the user sees nothing happen at all.
  const access = readAccess(deniedFinal, true);
  assert.equal(access.state, "tu-choi-phai-vao-cai-dat");
  assert.equal(access.nextAction, "mo-cai-dat");
  assert.notEqual(access.nextAction, "xin-quyen");
});

test("lần render đầu (permission null) không được nháy màn từ chối", () => {
  const access = readAccess(null, true);
  assert.equal(access.state, "chua-hoi");
  assert.notEqual(access.nextAction, "mo-cai-dat");
});

test("web: không có camera thì đi đường chọn ảnh, kể cả khi quyền đã granted", () => {
  // Order matters. Checking the permission first would route a browser that
  // cannot open a camera to "mo-camera" and ship a black viewfinder.
  for (const permission of [null, undetermined, granted, deniedFinal]) {
    const access = readAccess(permission, false);
    assert.equal(access.state, "khong-co-camera");
    assert.equal(access.nextAction, "chon-anh");
  }
});

/* ------------------------------------------------------ vòng đời ảnh tạm --- */

/** A backend that records every call, so the tests can assert on cleanup. */
function fakeBackend(overrides = {}) {
  const calls = { captured: 0, picked: 0, compressed: 0, discarded: [] };
  return {
    calls,
    async capture() {
      calls.captured += 1;
      return { uri: "file:///cache/gốc.jpg", width: 3000, height: 4000 };
    },
    async pick() {
      calls.picked += 1;
      return { uri: "file:///cache/đã-chọn.jpg", width: 3000, height: 4000 };
    },
    async compress(source, maxEdge) {
      calls.compressed += 1;
      const fit = fitLongestEdge(source.width, source.height, maxEdge);
      return {
        uri: "file:///cache/nén.jpg",
        width: fit?.width ?? source.width,
        height: fit?.height ?? source.height,
        bytes: 400 * 1024,
      };
    },
    async discard(uri) {
      calls.discarded.push(uri);
    },
    ...overrides,
  };
}

test("đọc xong thì cả ảnh gốc lẫn ảnh nén đều bị xoá", async () => {
  const backend = fakeBackend();
  const result = await withBillPhoto(backend, "camera", async (photo) => photo.uri);

  assert.equal(result, "file:///cache/nén.jpg");
  assert.deepEqual(backend.calls.discarded.sort(), [
    "file:///cache/gốc.jpg",
    "file:///cache/nén.jpg",
  ]);
});

test("UPLOAD HỎNG thì ảnh tạm vẫn bị xoá — đây mới là chỗ rò rỉ thật", async () => {
  // The happy path deleting files proves very little; the path nobody runs is
  // where a full-resolution bill stays on disk forever.
  const backend = fakeBackend();
  await assert.rejects(
    withBillPhoto(backend, "camera", async () => {
      throw new Error("mạng chết giữa chừng");
    }),
    /mạng chết giữa chừng/,
  );
  assert.deepEqual(backend.calls.discarded.sort(), [
    "file:///cache/gốc.jpg",
    "file:///cache/nén.jpg",
  ]);
});

test("nén hỏng thì ảnh gốc vẫn bị xoá, và lỗi ra ngoài là câu của mình", async () => {
  // This used to assert `/manipulator chết/`, i.e. that the platform's own
  // English string travelled out of here untouched. bug-010822 is exactly that
  // habit reaching a screen, so the expectation is now inverted: what leaves
  // this function is a sentence we wrote, and the platform error is kept where
  // a log can still reach it. The subject of the test -- the temp file is
  // deleted even on the failing path -- is unchanged and still the last line.
  const goc = new Error("manipulator chết");
  const backend = fakeBackend({
    async compress() {
      throw goc;
    },
  });
  const problem = await withBillPhoto(backend, "camera", async () => "không bao giờ tới đây").then(
    () => assert.fail("nén hỏng mà pipeline vẫn đi qua được"),
    (err) => err,
  );

  assert.ok(problem instanceof BillPhotoError);
  assert.equal(problem.code, "khong-doc-duoc");
  assert.doesNotMatch(problem.message, /manipulator/);
  // Kept, not discarded: whoever debugs this later needs the real cause, and
  // `cause` is the one place it can live without being rendered.
  assert.equal(problem.cause, goc);

  assert.deepEqual(backend.calls.discarded, ["file:///cache/gốc.jpg"]);
});

test("ảnh nén BỊ TỪ CHỐI vì quá lớn thì chính nó cũng phải bị xoá", async () => {
  // The gap the other cleanup tests leave open: `compress` here SUCCEEDS -- the
  // file is on disk -- and only then does the size tripwire reject it. The
  // rejected file is by definition the big one, so leaking it leaks the whole
  // full-resolution bill. This is the case the oversize guard exists for.
  const backend = fakeBackend({
    async compress(source, maxEdge) {
      const fit = fitLongestEdge(source.width, source.height, maxEdge);
      return {
        uri: "file:///cache/nén.jpg",
        width: fit?.width ?? source.width,
        height: fit?.height ?? source.height,
        bytes: 5 * 1024 * 1024,
      };
    },
  });
  await assert.rejects(
    withBillPhoto(backend, "camera", async () => "không bao giờ tới đây"),
    (error) => error instanceof BillPhotoError && error.code === "qua-lon",
  );
  assert.deepEqual(
    backend.calls.discarded.sort(),
    ["file:///cache/gốc.jpg", "file:///cache/nén.jpg"],
    "ảnh nén bị từ chối vẫn nằm lại trong cache",
  );
});

test("ảnh nén không đọc được (0 byte) thì cũng không được nằm lại", async () => {
  const backend = fakeBackend({
    async compress() {
      return { uri: "file:///cache/nén.jpg", width: 1600, height: 1200, bytes: 0 };
    },
  });
  await assert.rejects(
    withBillPhoto(backend, "camera", async () => "không bao giờ tới đây"),
    (error) => error instanceof BillPhotoError && error.code === "khong-doc-duoc",
  );
  assert.deepEqual(backend.calls.discarded.sort(), [
    "file:///cache/gốc.jpg",
    "file:///cache/nén.jpg",
  ]);
});

test("một lần xoá thất bại không được kéo theo các file còn lại", async () => {
  const discarded = [];
  const backend = fakeBackend({
    async discard(uri) {
      discarded.push(uri);
      if (uri.endsWith("gốc.jpg")) throw new Error("file bị khoá");
    },
  });
  const result = await withBillPhoto(backend, "camera", async () => "xong");

  assert.equal(result, "xong");
  assert.equal(discarded.length, 2, "file thứ hai bị bỏ qua sau lỗi đầu tiên");
});

test("người dùng huỷ chọn ảnh -> null, không phải lỗi, không xoá gì", async () => {
  const backend = fakeBackend({
    async pick() {
      return null;
    },
  });
  const result = await withBillPhoto(backend, "thu-vien", async () => "không tới");

  assert.equal(result, null);
  assert.deepEqual(backend.calls.discarded, []);
});

test("chọn từ thư viện đi đúng đường pick, không bật camera", async () => {
  const backend = fakeBackend();
  await withBillPhoto(backend, "thu-vien", async () => null);
  assert.equal(backend.calls.picked, 1);
  assert.equal(backend.calls.captured, 0);
});

/* ------------------------------------------------------------- kích thước --- */

test("ảnh không nén được thật thì bị từ chối, không lặng lẽ gửi đi", async () => {
  // The tripwire for a compress() that silently returns its input.
  const backend = fakeBackend({
    async compress(source) {
      return { uri: source.uri, width: source.width, height: source.height, bytes: 6 * 1024 * 1024 };
    },
  });
  await assert.rejects(
    compressForReading(backend, { uri: "file:///a.jpg", width: 3000, height: 4000 }),
    (error) => error instanceof BillPhotoError && error.code === "qua-lon",
  );
});

test("không đo được kích thước thì từ chối, không đoán", async () => {
  const backend = fakeBackend({
    async compress(source) {
      return { uri: source.uri, width: 1, height: 1, bytes: 0 };
    },
  });
  await assert.rejects(
    compressForReading(backend, { uri: "file:///a.jpg", width: 10, height: 10 }),
    (error) => error instanceof BillPhotoError && error.code === "khong-doc-duoc",
  );
});

test("thu nhỏ giữ đúng tỉ lệ và không vượt cạnh dài", () => {
  const fit = fitLongestEdge(3000, 4000, MAX_EDGE);
  assert.equal(Math.max(fit.width, fit.height), MAX_EDGE);
  // A bill is tall. Squashing it to a square crops off either the items or
  // the total, and which one is lost depends on the phone.
  assert.equal(fit.width / fit.height > 0.74 && fit.width / fit.height < 0.76, true);
});

test("ảnh đã đủ nhỏ thì không thu nhỏ lần nữa", () => {
  // Re-encoding a small image only softens the printed digits.
  assert.equal(fitLongestEdge(800, 1200, MAX_EDGE), null);
  assert.equal(fitLongestEdge(MAX_EDGE, 900, MAX_EDGE), null);
});

test("ảnh nằm ngang cũng bị chặn đúng cạnh dài", () => {
  const fit = fitLongestEdge(4000, 3000, MAX_EDGE);
  assert.equal(fit.width, MAX_EDGE);
  assert.equal(fit.height, 1200);
});

/* ------------------------------------------------------------ riêng tư --- */

/** Source with comments removed.
 *
 * The guards below look for forbidden calls, and a docstring that explains why
 * a call is forbidden must not be read as the call itself -- the first version
 * of this failed on `bill-photo.ts` for saying "never call MediaLibrary". A
 * rule that punishes documenting the rule teaches people to stop documenting.
 *
 * Line comments are only stripped when `//` follows whitespace or a line
 * start, so `startsWith("file://")` survives intact.
 */
function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");
}

const cameraSources = ["access", "bill-photo", "native", "settings", "index"].map((name) => ({
  name,
  text: stripComments(
    readFileSync(new URL(`../src/camera/${name}.ts`, import.meta.url), "utf8"),
  ),
}));

test("không file nào trong src/camera đụng tới thư viện ảnh của máy", () => {
  // A bill is sensitive. Writing it into the camera roll puts it in every
  // cloud backup and every photo picker the phone has, which is not something
  // this app should ever do by accident.
  for (const { name, text } of cameraSources) {
    assert.equal(/MediaLibrary|saveToLibrary|CameraRoll/.test(text), false, name);
  }
});

test("EXIF bị tắt ở chỗ chụp — ảnh bill không mang theo toạ độ GPS", () => {
  const native = cameraSources.find((s) => s.name === "native").text;
  assert.match(native, /exif:\s*false/);
  assert.equal(/exif:\s*true/.test(native), false);
});

test("không file nào trong src/camera tự gửi ảnh đi đâu", () => {
  // Uploading belongs to api.ts, which knows exactly one host. A fetch here
  // would be a second, unreviewed exit for the bytes.
  for (const { name, text } of cameraSources) {
    if (name === "native") continue; // measures its own blob; asserted below
    assert.equal(/fetch\(|XMLHttpRequest|axios/.test(text), false, name);
  }
  const native = cameraSources.find((s) => s.name === "native").text;
  const fetches = native.match(/fetch\([^)]*\)/g) ?? [];
  assert.deepEqual(fetches, ["fetch(uri)"], "native.ts chỉ được fetch chính blob của nó");
});

test("ngưỡng kích thước là ngưỡng thật, không phải số trang trí", () => {
  assert.equal(MAX_BYTES, 2 * 1024 * 1024);
  assert.equal(MAX_EDGE, 1600);
});
