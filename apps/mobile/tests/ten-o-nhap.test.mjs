/* Whether an input still has a name once the placeholder is gone.
 *
 * Reported as bug-133250: `Field` renders a `Text` label above a `TextInput`,
 * and on react-native-web a `Text` comes out as a `div`, not a `<label for>`.
 * Nothing ties the two together. Where that holds, the only thing naming the
 * input is `placeholder`, which the accessible-name computation reaches only as
 * its last resort -- so a screen reader announces the phone field as
 * "09xx xxx xxx" instead of "Số điện thoại", and the first `Field` somebody
 * writes without a placeholder is an unnamed input outright (WCAG 4.1.2).
 *
 * That was true, and is not true now. `aria-label={label}` was added to `Field`
 * by 79d3e48 (#113). The report measured a bundle built from bed4dcb, a branch
 * cut before that commit and never rebased onto it, where `Field` carried no
 * `aria-label` and the sign-up screen's two fields were the reported
 * "1 violation / 2 node". On main the removal of `placeholder` changes nothing
 * about the name.
 *
 * So what is missing is not the fix, it is the thing that keeps the fix. The
 * accessible name of every input in this app rests on one line of one file, and
 * until now no test failed if that line were deleted. Deleting it is not exotic:
 * it reads like a duplicate of the visible label directly above it, which is
 * exactly what it is, and that is why it looks removable.
 *
 * These tests assert the property the report named as its unblocking criterion
 * -- take the placeholder away and the input is still named -- rather than
 * asserting that a particular attribute is spelled a particular way. A test that
 * only checked `aria-label` while a placeholder was present would have passed on
 * the code that shipped broken, because that code passed axe too.
 *
 * The last test is the cheap net under the expensive one, in the shape
 * `aria-state.test.mjs` already uses: it reaches the three `TextInput`s in
 * `KetQuaNhanDien.tsx` and the one in `chat/ONhap.tsx`, which no render test
 * here compiles.
 *
 * What none of this proves: anything about iOS or Android, which read these
 * props through a different library, and nothing about whether "Số điện thoại"
 * is the right words for the field. It proves there is a name and where it
 * comes from.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Field } from "../dist-test/ui/Kit.js";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/* ------------------------------------------------------------- markup --- */

/** The single `<input>` `Field` emits, as `{ name, attrs }`. */
function inputOf(html) {
  const tag = html.match(/<input\s([^>]*?)\/?>/);
  assert.ok(tag, `không tìm thấy <input> trong markup: ${html.slice(0, 200)}`);
  return Object.fromEntries(
    [...tag[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(([, key, value]) => [key, value]),
  );
}

function field(props) {
  return inputOf(
    renderToStaticMarkup(
      React.createElement(Field, { value: "", onChangeText: () => {}, ...props }),
    ),
  );
}

/** What a browser would announce, restricted to the sources an input actually
 *  has here. `aria-labelledby` is included because pointing at the visible
 *  `Text` is the other legitimate fix, and this gate must not force one of the
 *  two spellings. `placeholder` is deliberately absent: it is the fallback
 *  whose use is the defect. */
function accessibleName(attrs) {
  return attrs["aria-label"] ?? (attrs["aria-labelledby"] ? "(labelledby)" : undefined);
}

const LABEL = "Số điện thoại";
const PLACEHOLDER = "09xx xxx xxx";

/* ----------------------------------------------------- the criterion --- */

test("gỡ placeholder ra thì ô nhập vẫn còn tên", () => {
  // The unblocking criterion from the report, verbatim: this is the render that
  // measured 1 violation / 2 node on the branch that predated the fix.
  const attrs = field({ label: LABEL });

  assert.equal(
    attrs.placeholder,
    undefined,
    "ca này phải dựng ô KHÔNG có placeholder, nếu không nó chứng minh nhầm thứ",
  );
  const name = accessibleName(attrs);
  assert.ok(
    name !== undefined && name !== "",
    `<input> không có tên khả truy cập nào: ${JSON.stringify(attrs)}. ` +
      "Nhãn nhìn thấy là một <Text>, và react-native-web phát nó ra thành <div>, " +
      "không phải <label for>, nên nó không đặt tên cho ô. Đặt aria-label từ prop " +
      "`label` trong Field (src/ui/Kit.tsx), hoặc nối bằng aria-labelledby.",
  );
});

test("tên của ô không đổi khi có hay không có placeholder", () => {
  // The sharper form of the same property. An input whose name is the
  // placeholder passes "has a name" while a placeholder is present, which is
  // how the broken version scored 0 violations. Only the comparison between the
  // two renders separates a real name from the fallback.
  const withHint = field({ label: LABEL, placeholder: PLACEHOLDER });
  const without = field({ label: LABEL });

  assert.equal(withHint.placeholder, PLACEHOLDER);
  // Both renders must be named before comparing them. Without this line the
  // comparison passes on the exact bug the file is about: with no `aria-label`
  // at all, both sides are `undefined` and `undefined === undefined` holds, so
  // the assertion would report green on the broken code. Measured -- this test
  // passed against a `Field` with the line deleted until the check was added.
  assert.ok(accessibleName(withHint), "ô có placeholder không có tên khả truy cập");
  assert.ok(accessibleName(without), "ô không placeholder không có tên khả truy cập");
  assert.equal(
    accessibleName(withHint),
    accessibleName(without),
    "tên khả truy cập đổi theo placeholder, tức là placeholder đang đóng vai cái tên",
  );
});

test("tên nghe thấy đúng bằng nhãn nhìn thấy, không phải ví dụ trong ô", () => {
  // WCAG 2.5.3. Someone saying "Số điện thoại" to a voice control has to reach
  // the field labelled that; a name of "09xx xxx xxx" is one example value, and
  // it changes meaning the moment the placeholder copy is edited.
  const attrs = field({ label: LABEL, placeholder: PLACEHOLDER });

  assert.equal(attrs["aria-label"], LABEL);
  assert.notEqual(
    attrs["aria-label"],
    attrs.placeholder,
    "tên khả truy cập trùng placeholder, nghĩa là nó lấy ví dụ làm tên",
  );
});

test("nhãn nào cũng thành tên, không chỉ cái nhãn có sẵn trong ca thử", () => {
  // Guards against a fix that hard-codes one string rather than reading `label`,
  // which a single-fixture assertion above would not notice.
  for (const label of ["Tổng tiền", "Tên nhóm", "Ngân hàng"]) {
    assert.equal(field({ label })["aria-label"], label);
  }
});

/* ------------------------------------------------------------ the net --- */

test("không TextInput nào trong src thiếu nhãn khả truy cập", () => {
  // Generic rather than per-component, and it reaches the files no render test
  // here compiles: the three inputs on KetQuaNhanDien.tsx and the message box
  // in chat/ONhap.tsx. Two of those three have no placeholder at all, so for
  // them the fallback the other tests describe does not even exist -- without a
  // label they would be unnamed outright.
  //
  // Both spellings are accepted: react-native-web 0.21.2 forwards
  // `accessibilityLabel` to `aria-label` on TextInput, View and Pressable
  // (measured, unlike `accessibilityState`, which it drops -- see
  // `aria-state.test.mjs`). `placeholder` is not accepted and that is the point.
  //
  // Comments are stripped first, so the module explaining the bug can quote the
  // broken shape without becoming an offender itself.
  const code = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");

  /** The opening `<TextInput …>` tag starting at `start`, brace-aware so that a
   *  `>` inside `style={{…}}` or an arrow function does not end it early. */
  const openingTag = (source, start) => {
    let depth = 0;
    for (let i = start; i < source.length; i++) {
      const ch = source[i];
      if (ch === "{") depth++;
      else if (ch === "}") depth--;
      else if (ch === ">" && depth === 0) return source.slice(start, i + 1);
    }
    return source.slice(start);
  };

  const offenders = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) walk(path);
      else if (path.endsWith(".tsx")) {
        const source = code(readFileSync(path, "utf8"));
        for (const match of source.matchAll(/<TextInput[\s/>]/g)) {
          const tag = openingTag(source, match.index);
          if (!/\baria-label\b/.test(tag) && !/\baccessibilityLabel\b/.test(tag)) {
            const line = source.slice(0, match.index).split("\n").length;
            offenders.push(`${relative(ROOT, path)}:${line}`);
          }
        }
      }
    }
  };
  walk(join(ROOT, "src"));

  assert.deepEqual(
    offenders,
    [],
    `TextInput không có nhãn khả truy cập: ${offenders.join(", ")}. ` +
      "placeholder KHÔNG đặt tên cho ô: nó là phương án cuối của phép tính tên, " +
      "và nó biến mất ngay khi người ta gõ. Thêm accessibilityLabel hoặc aria-label.",
  );
});

test("cổng này bắt được ô nhập không nhãn — tự kiểm trên mẫu dựng sẵn", () => {
  // The gate above passes today, which on its own is indistinguishable from a
  // gate that cannot fail. This runs its two decisions over fixtures instead of
  // over the tree, so "it went green" carries information.
  //
  // Named exception in the same shape as the mockup's own gates: the check is
  // the pair of decisions, not the file walk, so it stays honest without a
  // fixture file that someone would later have to keep in sync.
  const code = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  const named = (tsx) => {
    const source = code(tsx);
    const at = source.indexOf("<TextInput");
    if (at === -1) return null;
    let depth = 0;
    let tag = source.slice(at);
    for (let i = at; i < source.length; i++) {
      const ch = source[i];
      if (ch === "{") depth++;
      else if (ch === "}") depth--;
      else if (ch === ">" && depth === 0) { tag = source.slice(at, i + 1); break; }
    }
    return /\baria-label\b/.test(tag) || /\baccessibilityLabel\b/.test(tag);
  };

  // Must be caught: a placeholder is the only thing naming this one.
  assert.equal(named(`<TextInput value={v} placeholder="Tên món" />`), false);
  // Must be caught: nothing names this one at all.
  assert.equal(named(`<TextInput value={v} style={{ flex: 1 }} />`), false);
  // Must pass: both spellings that actually reach the DOM.
  assert.equal(named(`<TextInput value={v} aria-label="Tên món" />`), true);
  assert.equal(named(`<TextInput value={v} accessibilityLabel="Tên món" />`), true);
  // Must pass: a `>` inside style must not end the tag early and hide the label.
  assert.equal(
    named(`<TextInput style={{ width: w > 3 ? 1 : 2 }} accessibilityLabel="Số lượng" />`),
    true,
  );
  // Must be caught: the same shape, but with the label genuinely absent.
  assert.equal(named(`<TextInput style={{ width: w > 3 ? 1 : 2 }} placeholder="0" />`), false);
  // Must pass: a commented-out mention of the broken shape is not an offender.
  assert.equal(named(`<TextInput /* placeholder only */ accessibilityLabel="A" />`), true);
});
