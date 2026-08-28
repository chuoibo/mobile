/* rd-qa-02 · Self-check for the name-leak detector.
 *
 *     node --test tests/qa/rd-qa-02/name-leak.selfcheck.mjs
 *
 * Why this file exists
 * --------------------
 * `screen-vs-server.mjs` asserts twelve times that one guest cannot see another
 * guest's name. Three of those twelve could never have failed. The detector was
 * spelled `new RegExp(`>[^<]*\\b${name}\\b`)`, and JavaScript's `\b` is defined
 * over `\w` == `[A-Za-z0-9_]` -- `à` is not a word character, so `/\bHà\b/`
 * cannot match "Hà" when the next character is a space, a `·` or a `<`:
 *
 *     node -e 'console.log(/\bHà\b/.test("· Hà ·"), /\bHa\b/.test("· Ha ·"))'
 *     -> false true
 *
 * Every name in the roster that ends in an accented vowel was un-checkable, and
 * the run still printed "0 lệch". This file plants each roster name into markup
 * shaped like the real guest page and asserts the detector FIRES. A check that
 * cannot fail is not a check -- so the check itself now has a check.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { nameAppearsInText } from "./name-leak.mjs";

/** The roster `screen-vs-server.mjs` drives the app with. */
const ROSTER = ["Nam", "Hà", "Quyên", "Dũng", "Linh"];

/** Shaped like the mutation that exposed the hole: a name spliced into the
 * occasion label of a real envelope block. */
const plantedIn = (name) =>
  `<p class="occasion">Bữa lẩu tối thứ bảy · ${name} · 1.234.567</p>`;

test("fires on every roster name planted in text content", async (t) => {
  for (const name of ROSTER) {
    await t.test(name, () => {
      assert.equal(
        nameAppearsInText(plantedIn(name), name),
        true,
        `"${name}" is on the page and the detector did not see it — ` +
          "this assertion in screen-vs-server.mjs cannot go red",
      );
    });
  }
});

test("fires regardless of what follows the name", async (t) => {
  // The ASCII-\b bug is a function of the NEXT character, so vary it.
  for (const after of [" ", "·", "<", ",", ".", ")", " ", ""]) {
    await t.test(`followed by ${JSON.stringify(after)}`, () => {
      assert.equal(nameAppearsInText(`<span>· Hà${after}</span>`, "Hà"), true);
    });
  }
});

test("fires regardless of what precedes the name", async (t) => {
  for (const before of ["", " ", "·", "(", " "]) {
    await t.test(`preceded by ${JSON.stringify(before)}`, () => {
      assert.equal(nameAppearsInText(`<span>${before}Hà ·</span>`, "Hà"), true);
    });
  }
});

test("fires on decomposed (NFD) markup for a precomposed (NFC) name", () => {
  // The server and the browser are each free to emit either normal form. If the
  // detector only understands one of them, it goes quiet on the other -- the
  // same silent-pass failure in a different costume.
  const nfd = plantedIn("Hà".normalize("NFD"));
  assert.notEqual(nfd, plantedIn("Hà"), "fixture is not actually decomposed");
  assert.equal(nameAppearsInText(nfd, "Hà".normalize("NFC")), true);
});

test("does not fire when the name is absent", () => {
  assert.equal(nameAppearsInText("<p>Bữa lẩu tối thứ bảy</p>", "Hà"), false);
  assert.equal(nameAppearsInText("<p>Quyên · Dũng</p>", "Linh"), false);
});

test("does not fire on a name embedded in a longer word", async (t) => {
  const cases = [
    ["Hà", "<p>Hàn Quốc</p>"],
    ["Hà", "<p>Thanh Hàng</p>"],
    ["Nam", "<p>Namibia</p>"],
    ["Nam", "<p>Việt-Namese</p>".replace("-", "")],
    ["Linh", "<p>Linhh</p>"],
    ["Dũng", "<p>Dũngg</p>"],
  ];
  for (const [name, html] of cases) {
    await t.test(`${name} in ${html}`, () => {
      assert.equal(nameAppearsInText(html, name), false);
    });
  }
});

test("does not fire on a name that only appears inside a tag", () => {
  // Documents the detector's scope: attributes are out of band. If this ever
  // needs to change, change it deliberately and update README.md.
  assert.equal(nameAppearsInText('<img alt="Hà" src="x.png">', "Hà"), false);
});

test("the ASCII-\\b spelling this detector replaces really is dead", () => {
  // Pinned so nobody "simplifies" the detector back to \b. This is a property
  // of the JS engine, not of our code: \w is [A-Za-z0-9_], full stop.
  assert.equal(/\bHà\b/.test("· Hà ·"), false, "\\b would have matched Hà");
  assert.equal(/\bHa\b/.test("· Ha ·"), true, "\\b works on ASCII only");
  assert.equal(nameAppearsInText("<span>· Hà ·</span>", "Hà"), true);
});
