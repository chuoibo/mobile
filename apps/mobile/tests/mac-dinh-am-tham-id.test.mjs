/* No display value may fall back to a raw machine id.
 *
 * bug-050923 was patched four times. Each patch was found by looking at the
 * screen that had just been caught, and each time a fifth site turned up
 * somewhere else: the debt panel, then the payment screen's "Người chuyển"
 * chip, then `ChiaSe` and the share message, then two private helpers inside
 * `api.ts` that no screen could see. Lead's reading of the third repeat is the
 * one this file acts on: when the same defect surfaces a third time the
 * question stops being "how many are left" and becomes "what MINTS them".
 *
 * What mints them is a single expression shape. Every one of the sites ended
 * the same way:
 *
 *     roster.find((p) => p.id === id)?.name ?? id
 *
 * A lookup, and then the id itself as the fallback. It reads like a safe
 * default because the expression always produces a string, and that is exactly
 * the failure: when the lookup misses, the app does not say "I cannot name this
 * person", it prints the database key and lets it pass for a name. On a money
 * row, beside real names, in the sentence copied to somebody's clipboard.
 *
 * So this gate does not enumerate screens and it does not enumerate function
 * names. Both of those questions have already been asked and both answered
 * "clean" while a site was open -- `labelFor` call sites could never reach
 * `nameOf`/`nameFrom`, because those are private. It asks about the SHAPE, over
 * every source file the app has, so a helper written tomorrow inside a closure
 * is in scope the day it is written.
 *
 * The shape, precisely: a `??` or `||` whose fallback branch is an id-bearing
 * expression, or a ternary with an id-bearing branch. Ternaries are included
 * deliberately. A gate that reads `??` and `||` only is blind to `x ? x : id`,
 * which is the same default written differently, and "the gate did not know
 * that spelling" is not a defence anyone can act on.
 *
 * THREE CONTROLS, because a source-scanning gate dies silently. A changed
 * glob, a parse that throws into a catch, a node kind that stopped matching:
 * all three report zero findings, which is indistinguishable from clean.
 *
 *   1. A fixture carrying the shape three ways and two safe fallbacks. The
 *      walker must return exactly the three.
 *   2. The REAL defect: the whole pre-fix `api.ts`, byte for byte, checked in
 *      beside this file. The gate has to go red on it at the two lines the bug
 *      was actually filed about. A regression gate that cannot redden on the
 *      original proves nothing about the copy of the bug it was written
 *      against.
 *   3. Floors on files read and expressions examined, so a walk that read
 *      nothing cannot pass as a tree with nothing in it.
 *
 * The allowlist below is ids used AS ids -- selection state, navigation
 * arguments, a toggle comparing a row to the open row. None of them reach a
 * person's eyes. Entries are keyed by file plus the expression text rather than
 * by line, so editing a file above them does not silently re-bless a line, and
 * a NEW expression in an already-listed file still trips.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const MOBILE = fileURLToPath(new URL("..", import.meta.url));
const SRC = join(MOBILE, "src");

/*
 * The red control's material, and why it is a checked-in file rather than a
 * `git show`.
 *
 * The first version of this control ran `git show 0c04cb7:apps/mobile/src/
 * api.ts`. It went red on CI, and the red was correct behaviour by a control
 * written to fail hard rather than skip -- but what it had caught was its own
 * hidden dependency, not a defect. CI checks out shallow (`fetch-depth: 1`),
 * so the object is simply not in the clone:
 *
 *     not ok - phép quét ĐỎ được trên chính bản mã trước khi bug-050923...
 *       fatal: invalid object name "0c04cb7"
 *
 * Two separate things were wrong with reading history from a test. Clone depth
 * is one. The other is worse: this repo squash-merges, so any branch sha can
 * stop existing at all, and a control pinned to one would then be unrunnable
 * everywhere rather than only on CI. A negative control needs the old CONTENT.
 * It never needed the old COMMIT.
 *
 * So the content lives here, and provenance is kept by content-addressing
 * instead of by history. `OID_TRUOC_KHI_VA` is the git blob object id, and the
 * test below recomputes it from the bytes on disk -- sha1 over the `blob
 * <len>\0` header plus the content, which is what `git hash-object` does. Two
 * consequences worth stating:
 *
 *   - With no history whatsoever, `git hash-object <fixture>` reproduces this
 *     value, so an edited fixture cannot pass quietly.
 *   - With full history, `git rev-parse 0c04cb7:apps/mobile/src/api.ts` yields
 *     the same value, which is what ties the file to the commit it came from.
 *
 * Why a sibling file and not a template literal in this test: the blob holds
 * 298 backticks and 52 `${`. Inlining it means escaping it, and an escaped
 * copy is no longer the bytes the commit had -- which destroys precisely the
 * property the control exists for.
 *
 * The file is deliberately `.txt`. As `.ts` it would enter `tsc --noEmit` and
 * the tree walkers, and a stale copy of `api.ts` type-checked beside the real
 * one is the "two functions with the same name" failure this repo has already
 * paid for once. Note for anyone grepping later: this file is SUPPOSED to
 * contain `?? id`. It is the disease sample, not an outbreak.
 */
const TRUOC_KHI_VA = join(MOBILE, "tests/fixtures/bug-050923/api.ts.truoc-khi-va.txt");
const OID_TRUOC_KHI_VA = "008c141ab50d20759c512168cc8ae4e68af20602";
/** Where the fixture came from. Documentation: nothing below reads it. */
const COMMIT_TRUOC_KHI_VA = "0c04cb7";

/** `git hash-object` in pure JS, so the check needs no git and no history. */
function gitBlobOid(buf) {
  return createHash("sha1").update(`blob ${buf.length}\0`).update(buf).digest("hex");
}

/* An id-bearing name. Written against the snake_case form so that `sender_id`
 * from the wire and `senderId` from the app are one rule rather than two.
 * `key` is here because a `?? row.key` reads to a person exactly like the UUID
 * did; it has never been a display name in this app. */
const TEN_LA_ID = /(^|[._])(ids?|uuid|guid|token|slug|sha|hash|key)$/i;

function idBearing(node) {
  let name = null;
  if (ts.isIdentifier(node)) name = node.text;
  else if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.name)) name = node.name.text;
  else if (ts.isElementAccessExpression(node) && ts.isStringLiteral(node.argumentExpression)) {
    name = node.argumentExpression.text;
  }
  if (name === null) return null;
  const snake = name.replace(/([a-z0-9])([A-Z])/g, "$1_$2");
  return TEN_LA_ID.test(snake) ? name : null;
}

/**
 * Every fallback-to-an-id in one file, plus how many fallbacks were examined.
 *
 * The second number is what makes a zero readable. `hits: []` from a file with
 * `seen: 0` means the walk never met a `??` at all, which is a broken walk, not
 * a clean file.
 */
export function fallbacksToId(text, fileName) {
  const sf = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const hits = [];
  let seen = 0;
  const at = (node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
  const code = (node) => node.getText(sf).replace(/\s+/g, " ").trim();
  const walk = (node) => {
    if (ts.isBinaryExpression(node)) {
      const op = node.operatorToken.kind;
      if (op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken) {
        seen += 1;
        if (idBearing(node.right) !== null) hits.push({ line: at(node), code: code(node) });
      }
    } else if (ts.isConditionalExpression(node)) {
      seen += 1;
      if (idBearing(node.whenFalse) !== null || idBearing(node.whenTrue) !== null) {
        hits.push({ line: at(node), code: code(node) });
      }
    }
    ts.forEachChild(node, walk);
  };
  walk(sf);
  return { hits, seen };
}

function sourceFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...sourceFiles(p));
    else if (/\.tsx?$/.test(entry.name)) out.push(p);
  }
  return out.sort();
}

/* Ids used as ids. Each line says what the value is FOR, because "it is fine"
 * is not a reason anybody can re-check later. */
const CHO_PHEP = new Map([
  ["navigation/VoTab.tsx", [
    // Which group the tab shell is showing. An argument to navigation.
    "nhom?.id ?? nhomId",
  ]],
  ["participants.ts", [
    // Clearing the advancer when that person is removed. Stored, never drawn.
    "roster.advancerId === id ? null : roster.advancerId",
  ]],
  ["screens/kham-pha/tim-kiem.ts", [
    /* The one entry here that is a DISPLAY value, kept on the author's written
     * argument rather than silenced. These ids are catalogue slugs the reader
     * can still check against what they typed (`cafe`, `quan-an-local`), not
     * the opaque person keys bug-050923 was about, and dropping the row would
     * shrink the AI reading this panel exists to show back. What did change is
     * the `= []` default that used to let a caller turn the lookup off by
     * omission; `categories` is required now, so the only way to reach this
     * fallback is a real catalogue-versus-model disagreement. */
    "nhan.get(id) ?? id",
  ]],
  ["screens/len-plan/moi-vao-chuyen.ts", [
    // Keeping the invite token already held when the reply carries none.
    "sau.invite_token ?? m.invite_token",
  ]],
]);

function quetCayNguon() {
  const files = sourceFiles(SRC);
  const viPham = [];
  let seen = 0;
  for (const file of files) {
    const key = relative(SRC, file);
    const duocPhep = CHO_PHEP.get(key) ?? [];
    const result = fallbacksToId(readFileSync(file, "utf8"), file);
    seen += result.seen;
    for (const hit of result.hits) {
      if (duocPhep.includes(hit.code)) continue;
      viPham.push(`${key}:${hit.line}  ${hit.code.slice(0, 96)}`);
    }
  }
  return { files, viPham, seen };
}

test("phép quét nhận ra hình dạng, và không bắn oan chỗ có mặc định đọc được", () => {
  const fixture = [
    "const a = roster.find((p) => p.id === id)?.name ?? id;",
    "const b = tim(x)?.name || row.sender_id;",
    "const c = ten ? ten : person.uuid;",
    'const d = ten ?? "Thành viên";',
    "const e = soTien ?? 0;",
  ].join("\n");

  const { hits, seen } = fallbacksToId(fixture, "fixture.tsx");

  assert.equal(hits.length, 3, `phải bắt đúng ba dòng đầu, bắt được: ${JSON.stringify(hits)}`);
  assert.deepEqual(hits.map((h) => h.line), [1, 2, 3]);
  assert.equal(seen, 5, "phải soi cả năm biểu thức, kể cả hai chỗ lành");
});

test("bản mã trước khi vá còn nguyên là bản đã ra khỏi git, không phải bản chép tay", () => {
  // Runs before the control below and asserts nothing about the defect. Its
  // whole job is to say whether the material the control is about to read is
  // still the material it was written against. A hand-edited fixture would
  // otherwise let that control pass on a defect nobody ever shipped.
  let bytes;
  try {
    bytes = readFileSync(TRUOC_KHI_VA);
  } catch (err) {
    // A hard failure, never a skip. A control that quietly does not run leaves
    // the gate below unproven while still printing green.
    assert.fail(`không đọc được fixture ${TRUOC_KHI_VA}, nên đối chứng đỏ KHÔNG chạy: ${err}`);
  }

  assert.equal(
    gitBlobOid(bytes),
    OID_TRUOC_KHI_VA,
    `fixture đã bị sửa: nội dung không còn là blob ${OID_TRUOC_KHI_VA} ` +
      `(${COMMIT_TRUOC_KHI_VA}:apps/mobile/src/api.ts). Kiểm lại bằng: ` +
      `git hash-object apps/mobile/tests/fixtures/bug-050923/api.ts.truoc-khi-va.txt`,
  );
});

test("phép quét ĐỎ được trên chính bản mã trước khi bug-050923 được vá", () => {
  const truoc = readFileSync(TRUOC_KHI_VA, "utf8");

  const { hits } = fallbacksToId(truoc, "api.ts");
  const codes = hits.map((h) => h.code);

  assert.equal(hits.length, 2, `bản cũ phải còn đúng hai chỗ, thấy: ${JSON.stringify(codes)}`);
  // The lines the bug was filed about. Pinnable because the fixture is pinned:
  // counting two is not the same as finding the right two.
  assert.deepEqual(
    hits.map((h) => h.line),
    [1039, 1167],
    `đúng hai chỗ nhưng sai dòng, thấy: ${JSON.stringify(hits)}`,
  );
  for (const code of codes) assert.match(code, /\?\? id$/);
  assert.ok(
    codes.some((c) => c.includes("proposal.participants")),
    `thiếu chỗ nameOf trong openBatch: ${JSON.stringify(codes)}`,
  );
  assert.ok(
    codes.some((c) => c.includes("roster.find")),
    `thiếu chỗ nameFrom trong sendPublish: ${JSON.stringify(codes)}`,
  );
});

test("phép quét thật sự đọc hết cây nguồn", () => {
  const { files, seen } = quetCayNguon();

  assert.ok(files.length >= 100, `chỉ thấy ${files.length} file nguồn, nghi phép quét hỏng`);
  assert.ok(seen >= 200, `chỉ soi được ${seen} biểu thức mặc định, nghi phép quét hỏng`);
});

test("không giá trị hiển thị nào lấy id thô làm mặc định", () => {
  const { viPham } = quetCayNguon();

  assert.deepEqual(
    viPham,
    [],
    `còn ${viPham.length} chỗ lấy id làm mặc định:\n${viPham.join("\n")}`,
  );
});
