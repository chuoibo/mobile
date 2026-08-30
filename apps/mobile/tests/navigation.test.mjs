/* The shell's acceptance criteria, as assertions rather than as taps.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * rd-do-fe-02 asks for three things: five tab slots that each reach a screen,
 * a [+] that opens a menu of four, and an opening screen that does not pretend
 * to have signed anybody in. The first two are structural and are checked
 * here. What this file cannot check is that any of it *renders* -- that is the
 * `expo export` build plus the screenshots in the PR, and the split is the
 * point: a green run here is not a claim about pixels.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  CREATE_ACTIONS,
  DEFAULT_TAB,
  TABS,
  misroutedActions,
  tabById,
  unreachableTabs,
} from "../dist-test/navigation/tabs.js";
import { DEMO_PEOPLE, personById } from "../dist-test/navigation/nhom-demo.js";

/* ------------------------------------------------------------------ tabs --- */

test("bốn tab điều hướng, cộng nút [+] ở giữa là năm ô", () => {
  // The bar draws five slots; four of them are destinations and the middle
  // one is an action. Asserting four here is what keeps [+] from quietly
  // becoming a fifth tab that can be "selected" onto a blank screen.
  assert.equal(TABS.length, 4);
  assert.deepEqual(
    TABS.map((t) => t.label),
    ["Khám phá", "Lên plan", "Tin nhắn", "Cá nhân"],
  );
});

test("mỗi tab tới được một màn — không ô nào rơi vào khoảng trắng", () => {
  assert.deepEqual(unreachableTabs(), []);
  for (const tab of TABS) {
    assert.ok(tab.destination.screen, `${tab.id} không có màn`);
    assert.equal(typeof tab.destination.screen, "string");
  }
});

test("id tab không trùng nhau", () => {
  const ids = TABS.map((t) => t.id);
  assert.equal(new Set(ids).size, ids.length);
});

test("tab mặc định là một tab có thật", () => {
  assert.ok(tabById(DEFAULT_TAB), `${DEFAULT_TAB} không nằm trong TABS`);
});

test("tabById trả null cho id lạ, không ném và không đoán", () => {
  assert.equal(tabById("khong-co-tab-nay"), null);
});

test("mỗi tab có nhãn cho trình đọc màn hình, dài hơn nhãn hiển thị", () => {
  for (const tab of TABS) {
    assert.ok(tab.a11yLabel.length > tab.label.length, `${tab.id} thiếu mô tả`);
  }
});

test("màn còn là vỏ thì khai ra chủ và việc sẽ dựng nó", () => {
  // The honesty rule, enforced rather than trusted: a placeholder must name
  // who builds the real screen, so a tab cannot go stale as an anonymous stub.
  for (const tab of TABS) {
    if (tab.destination.kind !== "shell") continue;
    assert.ok(tab.destination.owner, `${tab.id} không nói ai dựng`);
    assert.ok(tab.destination.work, `${tab.id} không nói việc nào dựng`);
  }
});

/* The tab side of the rule #138 gave the [+] menu.
 *
 * For CREATE_ACTIONS the claim (`built`) and the mechanism (`route`) are two
 * fields that can disagree, and disagreeing is the failure. For TABS the claim
 * is `destination.kind` -- and until now nothing held the mechanism, so the
 * claim answered to nobody. It went stale exactly the way an unchecked claim
 * does: `kham-pha` and `ca-nhan` sat at `kind: "shell"`, each naming a devops
 * work item still owed, for the whole time `VoTab` was rendering their real
 * screens. rd-do-fe-09 shipped Cá nhân in #96 and rd-be-05 shipped Khám phá in
 * #81; the table said both were placeholders until rd-fe-16.
 *
 * Nothing about that was visible. `VoTab` renders by tab id and never consults
 * `destination`, so no screen looked wrong to a person tapping around -- the
 * only reader being lied to was the next engineer, plus the one rule that does
 * read it (`misroutedActions`: a [+] row may not land on a shell tab), which
 * would have refused a correct wiring to either tab.
 *
 * So the mechanism is read from `VoTab.tsx` itself rather than from a second
 * field somebody has to remember to set. That keeps the two statements
 * independent -- the shell's JSX is what actually decides what a tap shows --
 * and means deleting a screen out of the shell reddens this file rather than
 * leaving a tab pointing at a component that no longer renders.
 */
const VO_TAB_SRC = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "src", "navigation", "VoTab.tsx"),
  "utf8",
);

/** What the shell really renders, as `tab id -> component name`.
 *
 * Parsed from the source rather than imported, because the fact wanted here is
 * a statement `VoTab` makes about itself. Importing the component would only
 * prove it exists, which is the thing that was never in doubt. */
function screensVoTabRenders() {
  const found = new Map();
  // The `\(?` is not defensive padding. Prettier wraps a branch in parens the
  // moment its element grows past one line, so a screen gaining a prop rewrites
  // `? <KhamPha />` into `? (\n  <KhamPha ... />\n)` with no change in meaning.
  // #136 did exactly that to `kham-pha` while this branch was open, and the
  // guard below is what reported it rather than this file quietly reading three
  // branches and accusing a tab of rendering nothing.
  const pattern = /tab === "([a-z0-9-]+)"\s*\?\s*\(?\s*<([A-Za-z0-9_]+)/g;
  let m;
  while ((m = pattern.exec(VO_TAB_SRC)) !== null) found.set(m[1], m[2]);
  return found;
}

test("phép đọc VoTab bắt được các nhánh render, không phải khớp rỗng", () => {
  // Guard on the guard. A regex that silently stops matching would turn every
  // assertion below into "no tabs render anything", which passes by vacuum --
  // the failure mode this repo keeps finding in its own gates.
  const rendered = screensVoTabRenders();
  assert.ok(
    rendered.size >= 4,
    `chỉ đọc được ${rendered.size} nhánh render trong VoTab.tsx; regex hỏng hoặc shell đổi cách viết`,
  );
});

test("tab nào shell render thật thì khai built, tab nào không thì khai vỏ", () => {
  // Collected rather than asserted row by row, so one run names every stale
  // tab instead of the first. `misroutedActions` states the reason on the
  // menu side: a fix list is worth more than a fix.
  const rendered = screensVoTabRenders();
  const problems = [];
  for (const tab of TABS) {
    const component = rendered.get(tab.id);
    if (component && tab.destination.kind !== "built") {
      problems.push(`${tab.id}: VoTab render <${component} /> thật nhưng bảng còn khai là vỏ`);
    }
    if (!component && tab.destination.kind !== "shell") {
      problems.push(`${tab.id}: bảng khai đã dựng nhưng VoTab không render màn nào cho nó`);
    }
  }
  assert.deepEqual(problems, []);
});

test("tên màn trong bảng đúng bằng component shell render", () => {
  // Catches the rebase that keeps `kind: "built"` while the screen underneath
  // was renamed or swapped: reachable, built, and pointing at the wrong name.
  const rendered = screensVoTabRenders();
  for (const tab of TABS) {
    const component = rendered.get(tab.id);
    if (!component) continue;
    assert.equal(
      tab.destination.screen,
      component,
      `${tab.id}: bảng ghi "${tab.destination.screen}" nhưng VoTab render <${component} />`,
    );
  }
});

/* ------------------------------------------------------------ menu [+] --- */

test("nút [+] mở đúng năm mục, mỗi mục một nhãn riêng", () => {
  // Hand-written on purpose: it is a decision about the sheet, not a running
  // total of what happens to be wired. Four was rd-do-fe-02's number; F36/F37
  // made it five when "Album chuyến đi" went in, because the album is the one
  // screen in the shell that is neither a tab nor reachable from one -- and a
  // number that moves silently is a number that stops guarding anything.
  assert.equal(CREATE_ACTIONS.length, 5);
  for (const a of CREATE_ACTIONS) {
    assert.ok(a.label.trim(), `${a.id} không có nhãn`);
  }
  const labels = CREATE_ACTIONS.map((a) => a.label);
  assert.equal(new Set(labels).size, labels.length, "hai mục trùng nhãn");
});

test("mỗi mục có một dòng giải thích, không phải bốn động từ trần", () => {
  for (const a of CREATE_ACTIONS) {
    assert.ok(a.hint.trim(), `${a.id} không có gợi ý`);
  }
});

/* The three tests below replace one that hand-copied the list of wired ids.
 *
 * That copy was the same truth written twice -- once as `built` in tabs.ts,
 * once as an array here -- so the two could disagree, and every UI branch had
 * to rewrite the array. Worse, the copy made the gate decorative for the case
 * it was written for: setting `built: true` with nothing wired passed as soon
 * as somebody updated the array to match, which is exactly what a PR author
 * does when a test complains.
 *
 * What is asserted now is the relationship between the claim (`built`, which
 * is what `MenuTao` renders the "vỏ" chip from) and the mechanism (`route`,
 * which is what `VoTab.chonTao` navigates by). Neither is derived from the
 * other, so they can still disagree -- and disagreeing is the failure. Wiring
 * a new action means editing tabs.ts and nothing here.
 */

test("mục nhận đã nối thì phải có đường đi thật, và ngược lại", () => {
  assert.deepEqual(misroutedActions(), []);
});

test("mục đã nối có route, mục còn vỏ thì không", () => {
  // The same rule as above, stated per-action so a failure names the row
  // rather than only the list.
  for (const a of CREATE_ACTIONS) {
    assert.equal(
      a.route !== null,
      a.built,
      `${a.id}: built=${a.built} nhưng route=${JSON.stringify(a.route)}`,
    );
  }
});

test("route kiểu tab trỏ tới tab có thật, và tab đó không còn là vỏ", () => {
  // A menu row landing on a placeholder is reachable and still empty. This is
  // the case a rebase can create with no conflict marker: a branch cut before
  // a screen landed still calls that screen a shell.
  for (const a of CREATE_ACTIONS) {
    if (a.route?.kind !== "tab") continue;
    const tab = tabById(a.route.tab);
    assert.ok(tab, `${a.id} trỏ tới tab "${a.route.tab}" không có trong TABS`);
    assert.equal(tab.destination.kind, "built", `${a.id} trỏ tới tab còn là vỏ`);
  }
});

test("mọi mục còn vỏ đều có nhãn giải thích cho người bấm", () => {
  // The honest-shell rule from the tab side, applied to the sheet: a row that
  // does nothing has to say something. `MenuTao` renders the chip from
  // `built`, and the notice in `VoTab` from the missing route.
  for (const a of CREATE_ACTIONS) {
    if (a.built) continue;
    assert.equal(a.route, null, `${a.id} đeo nhãn vỏ mà vẫn đi được`);
    assert.ok(a.hint.trim(), `${a.id} không nói gì về việc chưa dựng`);
  }
});

/* ------------------------------------------------------------ nhóm demo --- */

test("nhóm demo có người, và mỗi người có tên lẫn chữ tắt", () => {
  assert.ok(DEMO_PEOPLE.length >= 2);
  for (const p of DEMO_PEOPLE) {
    assert.ok(p.name.trim(), `${p.id} không có tên`);
    assert.ok(p.initials.trim(), `${p.id} không có chữ tắt`);
  }
});

test("id người trong nhóm demo không trùng nhau", () => {
  const ids = DEMO_PEOPLE.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length);
});

test("id vẫn là slug, còn id thật đi riêng ở personId", () => {
  // Hai trường, không phải một. `id` là slug vì một UUID độn số không đọc
  // được ở chỗ gọi, và vì bản thân repo guard đọc dãy số dài như số tài
  // khoản. `personId` là hàng thật trong database đã gieo, và màn Cá nhân là
  // màn đầu tiên cần tới nó — đúng như ghi chú cũ trong nhom-demo.ts đoán.
  for (const p of DEMO_PEOPLE) {
    assert.doesNotMatch(p.id, /^[0-9a-f]{8}-[0-9a-f]{4}-/i, `${p.id} trông như UUID`);
    assert.match(
      p.personId,
      /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      `${p.id} thiếu personId dạng uuid5`,
    );
  }
});

test("personId không trùng nhau — hai người chung id là hai người chung ví tiền", () => {
  const ids = DEMO_PEOPLE.map((p) => p.personId);
  assert.equal(new Set(ids).size, ids.length);
});

test("personById trả null cho người không có", () => {
  assert.equal(personById("khong-ai"), null);
  assert.ok(personById(DEMO_PEOPLE[0].id));
});
