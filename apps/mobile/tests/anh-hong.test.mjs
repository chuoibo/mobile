/* A file that is not an image must read as a sentence, not as a JS value.
 *
 * bug-010822. rd-qa-37 fed `printf 'khong phai anh' > /tmp/gia.jpg` to the bill
 * picker on the web build and got the literal string `[object HTMLCanvasElement]`
 * in two places at once: the banner in the middle of the screen and the red
 * error bar along the bottom. Reproduced 3/3 on main@0889408.
 *
 * The path is short and every step of it is ordinary. `expo-image-manipulator`
 * on the web loads the picked file through an `<img>` and, in
 * `src/web/utils.web.ts`, does this:
 *
 *     imageSource.onerror = () => reject(canvas);
 *
 * It rejects with the `HTMLCanvasElement` it was going to draw into, not with
 * an `Error`. So `compress` rejects with a DOM node, the node travels up
 * untouched through `withBillPhoto`, and `App.tsx` finishes it off with
 *
 *     setError(problem instanceof Error ? problem.message : String(problem));
 *
 * The `instanceof Error` arm has been exercised by every other failure on this
 * flow. The `else` arm had never once been taken, so nobody had seen what it
 * produces. `String` on a DOM node is `[object HTMLCanvasElement]`.
 *
 * Two gates here, at the two layers that each own half of the answer, because
 * either one alone leaves the other half broken:
 *
 *   1. `compressForReading` has to turn a decode failure into a `BillPhotoError`
 *      that SAYS the file is not an image. Without this the screen can be made
 *      to stop printing `[object ` and still tell the person nothing useful.
 *   2. `moTaLoi` has to be unable to emit `[object ` for ANY thrown value.
 *      Without this the next library that rejects with a non-`Error` reopens
 *      the same hole somewhere else on the flow, and `App.tsx` has two of these
 *      catch sites, not one.
 *
 * What this file proves: the value that comes out of the photo pipeline when
 * the file will not decode, and the string the app derives from any thrown
 * value. What it does NOT prove: that `App.tsx` renders that string, because
 * `App.tsx` sits outside `tsconfig.test.json`'s `rootDir` and the node runner
 * cannot load it. The third block below closes that gap the only way available
 * from here, by parsing `App.tsx` and asserting neither catch site still owns a
 * `String(<the caught value>)` of its own. That is a source read and it is
 * weaker than a render, so it is written as a gate with a self-check rather
 * than trusted quietly.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";

import { BillPhotoError, withBillPhoto } from "../dist-test/camera/bill-photo.js";
import { moTaLoi } from "../dist-test/ui/loi-tren-man.js";

const APP_TSX = fileURLToPath(new URL("../App.tsx", import.meta.url));

/** What `expo-image-manipulator` rejects with on the web when a file will not decode.
 *
 * A real `HTMLCanvasElement` cannot exist under bare node, and importing a DOM
 * to get one would mean testing jsdom's `toString` rather than ours. What
 * actually matters about the rejected value is the single property that
 * produced the bug: `String()` of it is `[object HTMLCanvasElement]`. A
 * `Symbol.toStringTag` reproduces exactly that, and nothing else about a canvas
 * is on the path.
 */
function canvasGiaVo() {
  return { [Symbol.toStringTag]: "HTMLCanvasElement" };
}

/** A label for a thrown value, for use in an assertion message.
 *
 * `String(x)` is not total and cannot be used here. `Object.create(null)` has
 * no `toString` and no `Symbol.toPrimitive`, so converting it raises
 * `TypeError: Cannot convert object to primitive value` -- and node builds an
 * assertion message eagerly, on every iteration, whether or not the assertion
 * fails. So the unconvertible value did not merely produce an ugly label, it
 * threw out of the loop and dropped the ten values queued behind it, including
 * every `Error` case. The list read as fifteen values checked; five were.
 *
 * `Object.prototype.toString.call` is total, and it is also the more useful
 * label: it honours `Symbol.toStringTag`, so the fake canvas reports as
 * `[object HTMLCanvasElement]` -- the exact string this file exists to keep off
 * the screen.
 */
function nhan(thu) {
  return Object.prototype.toString.call(thu);
}

/** A backend whose compression fails the way the web one does. */
function backendHongOBuocNen(nem) {
  const daXoa = [];
  return {
    daXoa,
    async capture() {
      return { uri: "file:///cache/chup.jpg", width: 3000, height: 4000 };
    },
    async pick() {
      return { uri: "file:///cache/chon.jpg", width: 3000, height: 4000 };
    },
    async compress() {
      throw nem;
    },
    async discard(uri) {
      daXoa.push(uri);
    },
  };
}

/** Run the whole photo lifecycle and hand back whatever it threw. */
async function batLoi(backend, source = "thu-vien") {
  try {
    await withBillPhoto(backend, source, async () => "khong bao gio toi day");
    assert.fail("pipeline phải hỏng ở bước nén, nhưng nó đi qua được");
  } catch (problem) {
    return problem;
  }
}

/* ------------------------------------------- 1. lỗi mang theo câu của mình --- */

test("file không giải mã được thì lỗi nói ra là không phải ảnh", async () => {
  const backend = backendHongOBuocNen(canvasGiaVo());
  const problem = await batLoi(backend);

  // The point of the assertion: a caller has something it can read. Before the
  // fix this is the raw rejected object, and every one of these lines fails.
  assert.ok(
    problem instanceof BillPhotoError,
    `lỗi phải là BillPhotoError, nhận được ${Object.prototype.toString.call(problem)}`,
  );
  assert.equal(problem.code, "khong-doc-duoc");
  assert.match(problem.message, /không phải/i);
  assert.match(problem.message, /ảnh/i);
});

test("câu đó là tiếng Việt cho người thường, không phải chuỗi của máy", async () => {
  const problem = await batLoi(backendHongOBuocNen(canvasGiaVo()));
  const tren_man = moTaLoi(problem);

  // The acceptance criterion of bug-010822, asserted on the string the screen
  // is handed rather than on the shape of the error.
  assert.ok(!tren_man.includes("[object "), `màn vẫn hiện chuỗi máy: ${tren_man}`);
  assert.match(tren_man, /không phải/i);
  assert.match(tren_man, /ảnh/i);
  // A sentence, not a token. The old output was 25 characters of `[object ...]`
  // and passed any "is it non-empty" check.
  assert.ok(tren_man.trim().length > 20, `câu quá ngắn để đọc: ${tren_man}`);
});

test("ảnh tạm vẫn bị xoá khi file hỏng ở bước nén", async () => {
  // `withBillPhoto` deletes in a `finally`, so wrapping `compress` in a
  // try/catch must not change who ends up owning the capture. This is the
  // regression the fix could plausibly cause and the reason it is asserted
  // here rather than left to `camera.test.mjs`.
  const backend = backendHongOBuocNen(canvasGiaVo());
  await batLoi(backend);
  assert.deepEqual(backend.daXoa, ["file:///cache/chon.jpg"]);
});

test("lỗi đã có câu của mình thì đi qua nguyên vẹn, không bị đè", async () => {
  // A `BillPhotoError` raised deeper down already says the right thing. The
  // normaliser must not flatten every failure into one sentence, or the size
  // tripwire ("ảnh bill quá lớn") would start reading as a decode failure.
  const rieng = new BillPhotoError("qua-lon", "Ảnh bill quá lớn để gửi đi.");
  const problem = await batLoi(backendHongOBuocNen(rieng));
  assert.equal(problem, rieng);
  assert.equal(moTaLoi(problem), "Ảnh bill quá lớn để gửi đi.");
});

/* ------------------------------------------------ 2. không lối nào ra [object --- */

test("moTaLoi không bao giờ trả về chuỗi [object ...], với bất kỳ thứ gì bị ném", () => {
  // Everything here is a value some library really does throw. The canvas is
  // the one that shipped; the rest are the same failure waiting on a different
  // dependency, which is why the gate is written over the class and not over
  // the one case rd-qa-37 happened to find.
  const nhungThuBiNem = [
    canvasGiaVo(),
    { [Symbol.toStringTag]: "HTMLImageElement" },
    {},
    { message: "trông như Error nhưng không phải" },
    Object.create(null),
    [1, 2, 3],
    null,
    undefined,
    0,
    NaN,
    "",
    "   ",
    Symbol("khong-doc-duoc"),
    new Error(""),
    new Error("   "),
  ];

  let daKiem = 0;
  for (const thu of nhungThuBiNem) {
    const cau = moTaLoi(thu);
    assert.equal(typeof cau, "string", `không trả về chuỗi cho ${nhan(thu)}`);
    assert.ok(!cau.includes("[object "), `rò chuỗi máy cho ${nhan(thu)}: ${cau}`);
    assert.ok(cau.trim().length > 0, "câu rỗng thì màn hình trống, không phải lỗi được giải thích");
    daKiem += 1;
  }

  // The loop above already threw once, at value 5 of 15, while building an
  // assertion message -- and a loop that dies partway is indistinguishable from
  // a loop that passed, once someone fixes whatever made it red. Counting is
  // the cheap way to make coverage of this list a thing the gate asserts rather
  // than a thing the reader assumes.
  assert.equal(daKiem, nhungThuBiNem.length, "vòng lặp bỏ dở, không kiểm hết danh sách");
});

test("moTaLoi giữ nguyên câu của một Error thật", () => {
  // The `instanceof Error` arm is the one that already worked, and it carries
  // every sentence the app authored on this flow. The fix must not touch it.
  const that = new Error("Không kết nối được tới máy chủ 10.0.0.4:8000.");
  assert.equal(moTaLoi(that), "Không kết nối được tới máy chủ 10.0.0.4:8000.");
});

/* -------------------------------------------------- 3. App.tsx không tự chế --- */

/** Every `String(x)` where `x` is a value the code just caught.
 *
 * Two bindings count as caught, because App.tsx has one of each and the bug
 * shipped in both: the parameter of a `catch (x)` clause, and the parameter of
 * a `.catch(x => ...)` callback. A gate that knew only the first would have
 * reported App.tsx clean while line 374 still held the identical line, which is
 * how one of these two got fixed once before and the other did not.
 *
 * Returns line numbers, so a failure names where to look instead of saying that
 * something somewhere is wrong.
 */
function stringHoaBienBat(source, fileName) {
  const tree = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found = [];

  /** The binding a `.catch(...)` callback introduces, if it takes a plain one. */
  const tenTuCallbackCatch = (node) => {
    if (!ts.isCallExpression(node)) return undefined;
    const goi = node.expression;
    if (!ts.isPropertyAccessExpression(goi) || goi.name.text !== "catch") return undefined;
    const cb = node.arguments[0];
    if (cb === undefined) return undefined;
    if (!ts.isArrowFunction(cb) && !ts.isFunctionExpression(cb)) return undefined;
    const tham = cb.parameters[0];
    if (tham === undefined || !ts.isIdentifier(tham.name)) return undefined;
    return tham.name.text;
  };

  const walk = (node, tenBienBat) => {
    let tenHienTai = tenBienBat;
    if (ts.isCatchClause(node) && node.variableDeclaration !== undefined) {
      const ten = node.variableDeclaration.name;
      if (ts.isIdentifier(ten)) tenHienTai = ten.text;
    }
    tenHienTai = tenTuCallbackCatch(node) ?? tenHienTai;
    if (
      tenHienTai !== undefined &&
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "String" &&
      node.arguments.length === 1 &&
      ts.isIdentifier(node.arguments[0]) &&
      node.arguments[0].text === tenHienTai
    ) {
      found.push(tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1);
    }
    ts.forEachChild(node, (child) => walk(child, tenHienTai));
  };

  walk(tree, undefined);
  return found;
}

test("bộ dò của cổng này thật sự nhìn thấy cả hai khuôn đang bị cấm", () => {
  // Without this the gate below is worth nothing: a walker that quietly stops
  // matching reports zero findings, which reads exactly like a clean file. So
  // it is run against both lines as they were actually written in App.tsx
  // before the fix, plus three shapes that must NOT be flagged.
  const nhuCu = [
    "async function guard(work) {",
    "  try { await work(); }",
    "  catch (problem) {",
    "    setError(problem instanceof Error ? problem.message : String(problem));",
    "  }",
    "}",
    "previewSplit(a, b).then(ok).catch((problem) => {",
    "  setError(problem instanceof Error ? problem.message : String(problem));",
    "});",
    "const nhan = String(soTien);", // not caught at all
    "try { g(); } catch (problem) { setError(String(khac)); }", // a different value
    "chuoi.catch(() => setError(String(khac)));", // callback takes no binding
  ].join("\n");

  assert.deepEqual(stringHoaBienBat(nhuCu, "fixture.tsx"), [4, 8]);
});

test("App.tsx không còn tự biến thứ bị ném thành chuỗi", () => {
  // The behaviour is asserted above, on `moTaLoi`. This only pins that the two
  // catch sites in App.tsx go through it instead of each keeping a private
  // fallback -- which is how the bug got into one of them and not the other.
  const source = readFileSync(APP_TSX, "utf8");
  const dong = stringHoaBienBat(source, "App.tsx");
  assert.deepEqual(
    dong,
    [],
    `App.tsx còn String(<biến bắt được>) ở dòng ${dong.join(", ")}; dùng moTaLoi thay cho nó`,
  );
});
