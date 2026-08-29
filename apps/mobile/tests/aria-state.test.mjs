/* Whether a toggle tells a screen reader which way it is set.
 *
 * The matrix on "Gợi ý chia" is the control that decides how much each person
 * pays. Every cell declared `accessibilityRole="checkbox"` with
 * `accessibilityState={{ checked }}`, which reads correctly and does nothing:
 * react-native-web 0.21.2 forwards no prop by that name, so the state was
 * dropped before it reached the element. Read out of a real Chromium, one cell
 * before and after being pressed:
 *
 *     <div aria-label="Nam, Bún bò Huế" role="checkbox" tabindex="0" class="…">
 *     <div aria-label="Nam, Bún bò Huế" role="checkbox" tabindex="0" class="…">
 *
 * -- same attributes, both times. Only the colour of the dot inside changed.
 * Someone using a screen reader could hear "checkbox", could press it, and was
 * never told whether they had just added a dish to their bill or taken one off.
 * axe-core called it `aria-required-attr`, critical, once per cell.
 *
 * These tests render the real screens through the real library rather than
 * asserting on the source text, because the source text was never wrong --
 * `accessibilityState={{ checked }}` is exactly what React Native documents.
 * The failure happened during the substitution to `react-native-web`, which is
 * only visible in the markup that comes out the other side. A source-level
 * assertion would have passed on the code that shipped broken. So would a test
 * that asserted on the props a component was called with.
 *
 * The last test is the cheap net under the expensive one: `accessibilityState`
 * is dead on this stack in every one of its forms, so no `.tsx` may carry it.
 * That rule is what stops the third occurrence; there have already been two,
 * found by two people a day apart, in files with no connection to each other.
 *
 * What none of this proves: anything about iOS or Android. Native reads the
 * same props through a different library. `aria-checked` is the spelling that
 * serves both -- `Pressable.js:229` resolves `ariaChecked ?? accessibilityState?.checked`
 * -- but only a device says whether TalkBack or VoiceOver speaks it.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Choice } from "../dist-test/ui/Kit.js";
import { GoiYChia } from "../dist-test/screens/GoiYChia.js";
import { everyoneShares, toggle } from "../dist-test/assignment.js";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/* ------------------------------------------------------------- markup --- */

/** Every element in `html`, as `{ name, attrs }`. Attribute order is React's,
 *  so tests compare sets and values, never the serialised string. */
function elements(html) {
  return [...html.matchAll(/<([a-z]+)\s([^>]*?)\/?>/g)].map(([, name, raw]) => ({
    name,
    attrs: Object.fromEntries(
      [...raw.matchAll(/([\w-]+)="([^"]*)"/g)].map(([, key, value]) => [key, value]),
    ),
  }));
}

function withRole(html, role) {
  return elements(html).filter((el) => el.attrs.role === role);
}

function render(component, props) {
  return renderToStaticMarkup(React.createElement(component, props));
}

/* ------------------------------------------------------------ fixtures --- */

function line(id, name, amount) {
  return {
    id,
    name,
    quantity: 1,
    lineTotalVnd: amount,
    read: { name, quantity: 1, lineTotalVnd: amount },
  };
}

const BUN_BO = line("mon-0", "Bún bò Huế", 65000);
const CHA_GIO = line("mon-1", "Chả giò", 45000);

const READING = {
  lines: [BUN_BO, CHA_GIO],
  printedTotalVnd: 110000,
  needsReview: false,
  warnings: [],
};

const ROSTER = {
  participants: [
    { id: "nam", name: "Nam" },
    { id: "ha", name: "Hà" },
  ],
};

const IDS = ROSTER.participants.map((p) => p.id);

function splitScreen(assignment) {
  return render(GoiYChia, {
    reading: READING,
    roster: ROSTER,
    assignment,
    preview: null,
    onBack: () => {},
    onReset: () => {},
    onToggle: () => {},
    onAddPerson: () => {},
    onRemovePerson: () => {},
    onSeeResults: () => {},
  });
}

/* --------------------------------------------- the matrix, screen #82 --- */

test("mỗi ô trong ma trận nói ra mình đang tích hay không", () => {
  const all = everyoneShares(READING.lines, IDS);
  const cells = withRole(splitScreen(all), "checkbox");

  // Two dishes times two people. The count is asserted so that a matrix that
  // silently stopped rendering cells cannot pass the attribute check by
  // having nothing to check.
  assert.equal(cells.length, 4);
  for (const cell of cells) {
    assert.ok(
      "aria-checked" in cell.attrs,
      `ô "${cell.attrs["aria-label"]}" không có aria-checked: ${JSON.stringify(cell.attrs)}`,
    );
    assert.equal(cell.attrs["aria-checked"], "true");
  }
});

test("bỏ tích một ô thì đúng ô đó đổi, ba ô kia giữ nguyên", () => {
  // The failure this replaces was not a missing attribute in one state; it was
  // an element that rendered identically in both. So the assertion is on the
  // difference between two renders of the same cell, not on one snapshot.
  const before = everyoneShares(READING.lines, IDS);
  const after = toggle(before, BUN_BO.id, "nam");

  const label = "Nam, Bún bò Huế";
  const state = (assignment) => {
    const cell = withRole(splitScreen(assignment), "checkbox")
      .find((el) => el.attrs["aria-label"] === label);
    assert.ok(cell, `không tìm thấy ô "${label}"`);
    return cell.attrs["aria-checked"];
  };

  assert.equal(state(before), "true");
  assert.equal(state(after), "false");

  const others = withRole(splitScreen(after), "checkbox")
    .filter((el) => el.attrs["aria-label"] !== label);
  assert.equal(others.length, 3);
  for (const cell of others) assert.equal(cell.attrs["aria-checked"], "true");
});

test("mỗi ô có tên riêng, nên nghe xong biết là món nào của ai", () => {
  const cells = withRole(splitScreen(everyoneShares(READING.lines, IDS)), "checkbox");
  const names = cells.map((c) => c.attrs["aria-label"]);
  assert.equal(new Set(names).size, names.length);
  for (const name of names) assert.match(name, /^(Nam|Hà), .+/);
});

test("hai chip kiểu chia là một nhóm chọn một, và nói ra chip nào đang chọn", () => {
  // They used to be `role="button"` carrying `selected`, which is invalid on a
  // button even where the prop is delivered: nothing would have announced it
  // on any platform.
  const html = splitScreen(everyoneShares(READING.lines, IDS));
  const chips = withRole(html, "radio");

  assert.equal(chips.length, 2);
  assert.deepEqual(chips.map((c) => c.attrs["aria-checked"]), ["true", "false"]);
  assert.equal(withRole(html, "radiogroup").length, 1);
});

/* ------------------------------------------------ the chips, screen #81 --- */

test("Choice: chip đang chọn nói true, chip còn lại nói false", () => {
  const options = [
    { id: "nuong", label: "Nướng" },
    { id: "lau", label: "Lẩu" },
    { id: "cafe", label: "Cà phê" },
  ];
  const at = (value) =>
    withRole(render(Choice, { label: "Loại quán", options, value, onChange: () => {} }), "radio")
      .map((el) => el.attrs["aria-checked"]);

  assert.deepEqual(at("nuong"), ["true", "false", "false"]);
  assert.deepEqual(at("lau"), ["false", "true", "false"]);
  // Nothing chosen yet is a state the chips can be in, and "no chip is on" has
  // to be audible as that rather than as silence.
  assert.deepEqual(at(null), ["false", "false", "false"]);
});

test("Choice: các chip nằm trong một radiogroup, và nhóm rỗng thì không giả vờ có", () => {
  const options = [{ id: "nuong", label: "Nướng" }];
  const filled = render(Choice, { label: "Loại quán", options, value: null, onChange: () => {} });
  assert.equal(withRole(filled, "radiogroup").length, 1);

  // A `radiogroup` with no `radio` inside it is its own axe violation
  // (`aria-required-children`), so the empty state must not carry the role.
  const empty = render(Choice, { label: "Loại quán", options: [], value: null, onChange: () => {} });
  assert.equal(withRole(empty, "radiogroup").length, 0);
  assert.equal(withRole(empty, "radio").length, 0);
});

/* ------------------------------------------------------------ the net --- */

test("không role bật/tắt nào trên hai màn thiếu aria-checked", () => {
  // Generic rather than per-component: the next checkbox somebody adds is
  // covered without anyone remembering to come back here.
  const screens = [
    splitScreen(everyoneShares(READING.lines, IDS)),
    render(Choice, {
      label: "Loại quán",
      options: [{ id: "a", label: "Nướng" }],
      value: "a",
      onChange: () => {},
    }),
  ];
  for (const html of screens) {
    for (const el of elements(html)) {
      if (!["checkbox", "radio", "switch"].includes(el.attrs.role)) continue;
      assert.ok(
        "aria-checked" in el.attrs,
        `role="${el.attrs.role}" thiếu aria-checked: ${JSON.stringify(el.attrs)}`,
      );
    }
  }
});

test("không màn nào còn dùng accessibilityState — trên nền này nó là prop chết", () => {
  // Cheap, and it reaches the files the render tests do not. `accessibilityState`
  // is not partially supported here: react-native-web 0.21.2 mentions it in
  // five places in its whole `dist`, all of them the deprecated
  // `TouchableWithoutFeedback` prop map and `isDisabled` -- none on the path
  // `Pressable` and `View` take. Every form of it (`checked`, `selected`,
  // `expanded`, `busy`) is dropped, so the fix is always the `aria-*` prop,
  // which React Native itself reads too.
  //
  // `disabled` is the one exception and it needs no `aria-*`: passing
  // `disabled` to a `Pressable` emits `aria-disabled` on web and overrides
  // `accessibilityState.disabled` on native.
  //
  // Comments are stripped first, so that the module explaining the bug can
  // quote the broken spelling without becoming an offender itself.
  const code = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  const offenders = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) walk(path);
      else if (path.endsWith(".tsx") || path.endsWith(".ts")) {
        if (code(readFileSync(path, "utf8")).includes("accessibilityState")) {
          offenders.push(relative(ROOT, path));
        }
      }
    }
  };
  walk(join(ROOT, "src"));

  assert.deepEqual(
    offenders,
    [],
    `còn dùng accessibilityState (không tới được DOM): ${offenders.join(", ")}. ` +
      "Dùng aria-checked / aria-selected / aria-expanded / aria-busy, hoặc " +
      "toggleState() trong src/ui/a11y.ts.",
  );
});
