/* No em dash in anything a person reads.
 *
 * The house rule is in CLAUDE.md: Vietnamese copy does not use the em dash.
 * Until now exactly one gate enforced it, `DesignDiscipline.test_no_em_dash_
 * anywhere` in `services/api/tests/web/test_guest_page.py`, and it only ever
 * looked at the guest page's rendered HTML and CSS. The mobile app -- which is
 * the whole demo path, and the only surface anyone will actually be shown --
 * had no gate at all. It had drifted to 22 of them, spread over 12 files,
 * including all four tab `a11yLabel`s, which is the copy a screen reader reads
 * out loud and the copy nobody ever sees while testing by eye.
 *
 * Why the check is an AST walk rather than a `grep` for the character. Comments
 * and docstrings in this repo are written in English, where the em dash is
 * ordinary punctuation and several files use it correctly. A grep cannot tell
 * a docstring reading `Khám phá — the tab the app opens on` from a label, so a
 * grep-shaped gate would have to be either wrong or disabled. Parsing gives the
 * distinction for free: string literals, template chunks and JSX text are
 * collected, comments are not, because comments are not nodes.
 *
 * Deliberately NOT banned here, unlike the guest page's stricter rule: the en
 * dash `–`. In this app it carries ranges that the mockup itself sets in it --
 * `~200–250k/người`, `Nhóm 4–8 người`, `21 – 23/08/2030` -- and that is correct
 * typography, not drift. Banning it would force those into a worse rendering to
 * satisfy a gate. The guest page has no ranges, so banning both there costs
 * nothing and is right there.
 *
 * The first test is the one that keeps the other two honest. A source-scanning
 * gate has a specific way of dying quietly: the walk collects nothing -- a
 * changed glob, a parse that silently fails, a node kind that stopped matching
 * -- and reports zero findings, which is indistinguishable from clean. So the
 * collector is run against a fixture that contains the character twice in a
 * comment and once in a string, and it has to return exactly the one. That
 * asserts both directions, and it fails if the walker ever goes blind.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const SRC = fileURLToPath(new URL("../src", import.meta.url));
const EM_DASH = "\u2014";

function sourceFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...sourceFiles(p));
    else if (/\.tsx?$/.test(entry.name)) out.push(p);
  }
  return out.sort();
}

/** Text that can reach a screen: string literals, template chunks, JSX text.
 * Comments are absent by construction -- they are trivia, not nodes. */
function readableChunks(text, fileName) {
  const sf = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const chunks = [];
  const take = (node, value) => {
    const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf));
    chunks.push({ line: line + 1, value });
  };
  const walk = (node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) take(node, node.text);
    else if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) take(node, node.text);
    else if (ts.isJsxText(node)) take(node, node.text);
    ts.forEachChild(node, walk);
  };
  walk(sf);
  return chunks;
}

test("phép đọc phân biệt được chuỗi người dùng đọc với chú thích tiếng Anh", () => {
  const fixture = [
    `/* Comment carrying an ${EM_DASH} the way English prose does. */`,
    `const nhan = "Khám phá ${EM_DASH} gợi ý chỗ đi";`,
    `// trailing comment ${EM_DASH} also ignored`,
  ].join("\n");

  const hit = readableChunks(fixture, "fixture.tsx").filter((c) => c.value.includes(EM_DASH));

  assert.equal(hit.length, 1, "phải bắt đúng chuỗi, và bỏ qua hai chú thích");
  assert.equal(hit[0].line, 2);
  assert.match(hit[0].value, /Khám phá/);
});

test("phép đọc thật sự đi hết cây nguồn, không trả rỗng vì hỏng", () => {
  const files = sourceFiles(SRC);
  const chunks = files.flatMap((f) => readableChunks(readFileSync(f, "utf8"), f));

  // Bare floors. They are here so that "0 findings" can never be produced by a
  // walk that read nothing, which is how a source gate dies without a sound.
  assert.ok(files.length >= 60, `chỉ thấy ${files.length} file nguồn, nghi phép quét hỏng`);
  assert.ok(chunks.length >= 500, `chỉ đọc được ${chunks.length} đoạn chữ, nghi phép quét hỏng`);
});

test("không còn dấu gạch dài trong chữ người dùng đọc", () => {
  const viPham = [];
  for (const file of sourceFiles(SRC)) {
    for (const { line, value } of readableChunks(readFileSync(file, "utf8"), file)) {
      if (value.includes(EM_DASH)) {
        viPham.push(`${relative(SRC, file)}:${line}  ${value.trim().slice(0, 72)}`);
      }
    }
  }
  assert.deepEqual(viPham, [], `còn ${viPham.length} chỗ dùng dấu gạch dài:\n${viPham.join("\n")}`);
});
