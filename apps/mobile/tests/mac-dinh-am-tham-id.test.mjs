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
 *   2. The REAL defect, read out of git. `0c04cb7` is the commit before the
 *      `api.ts` fix landed, and the gate has to go red on its `api.ts` at the
 *      two lines the bug was actually filed about. A regression gate that
 *      cannot redden on the pinned original proves nothing about the copy of
 *      the bug it was written against.
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
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const MOBILE = fileURLToPath(new URL("..", import.meta.url));
const SRC = join(MOBILE, "src");
const APP = join(MOBILE, "App.tsx");

/** The commit before `9e13f9f` fixed `api.ts`, used as the red control. */
const TRUOC_KHI_SUA = "0c04cb7";

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
  ["navigation/lien-ket.ts", [
    // Stripping the leading '#' off a URL fragment. Not a person.
    'hash.startsWith("#") ? hash.slice(1) : hash',
  ]],
  ["participants.ts", [
    // Clearing the advancer when that person is removed. Stored, never drawn.
    "roster.advancerId === id ? null : roster.advancerId",
  ]],
  ["screens/GoiYChia.tsx", [
    // Which person's row is open. Selection state.
    "selected ? null : person.id",
  ]],
  ["screens/ky-niem/KyNiem.tsx", [
    // Toggle: tapping the open memory closes it.
    "cu === m.id ? null : m.id",
  ]],
  ["screens/len-plan/LenPlan.tsx", [
    // Which outing and which group the planner has open.
    'cuaSo.pha === "tg" ? cuaSo.buoi.id : null',
    'nhom.kind === "xong" ? nhom.contextId : null',
    'cuaSo.pha === "moi" ? cuaSo.buoi.id : null',
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
  ["screens/quan-tri/QuanTriNhom.tsx", [
    // Which group is being administered, and which outing is preselected.
    'nhom.kind === "xong" ? nhom.contextId : null',
    "truoc ?? trang.outings[0]?.id",
  ]],
  ["screens/thanh-tich/ThanhTich.tsx", [
    // Toggle: tapping the open achievement closes it.
    "chon === h.id ? null : h.id",
  ]],
  ["screens/vao-cua/CaNhanHoa.tsx", [
    // Which taste chip is on. Selection state.
    "on ? null : k.id",
  ]],
]);

function quetCayNguon() {
  const files = [...sourceFiles(SRC), APP];
  const viPham = [];
  let seen = 0;
  for (const file of files) {
    const key = file === APP ? "App.tsx" : relative(SRC, file);
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

test("phép quét ĐỎ được trên chính bản mã trước khi bug-050923 được vá", () => {
  // Read out of git rather than copied into this repo: a copy of the defect is
  // a copy of what its author believed the defect was.
  let truoc;
  try {
    truoc = execFileSync("git", ["show", `${TRUOC_KHI_SUA}:apps/mobile/src/api.ts`], {
      cwd: MOBILE,
      encoding: "utf8",
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch (err) {
    // A hard failure, never a skip. A control that quietly does not run leaves
    // the gate below unproven while still printing green.
    assert.fail(
      `không đọc được ${TRUOC_KHI_SUA}:apps/mobile/src/api.ts, nên đối chứng đỏ KHÔNG chạy: ${err}`,
    );
  }

  const { hits } = fallbacksToId(truoc, "api.ts");
  const codes = hits.map((h) => h.code);

  assert.equal(hits.length, 2, `bản cũ phải còn đúng hai chỗ, thấy: ${JSON.stringify(codes)}`);
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
