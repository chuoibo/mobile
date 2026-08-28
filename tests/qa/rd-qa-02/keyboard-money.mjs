/* rd-qa-02 · Can the amount be reached and seen with a keyboard?
 *
 * Split out of `a11y-money-surfaces.mjs` because the two measurements it used
 * to carry were not measurements at all -- they were `console.log` calls that
 * never touched the failure counter. The script printed
 *
 *     phím Tab đầu tiên dừng ở: BUTTON:
 *     focus thấy được: outline=
 *
 * and then printed `0 vấn đề chặn` and exited 0, on a page where Tab landed on
 * the wrong control. README.md meanwhile listed "Tab đầu tiên dừng đúng ở nút
 * chép số tiền" in the results table as a check that had PASSED. It was a log
 * line wearing a check's clothes.
 *
 * The second measurement was broken twice over. `getComputedStyle(el, x)` takes
 * a pseudo-ELEMENT as its second argument; `:focus-visible` is a pseudo-CLASS,
 * so Chromium hands back an empty declaration. It returned `outlineStyle: ""`
 * on a page with a 2px focus ring and `outlineStyle: ""` on a page with
 * `outline: none` -- the same answer for the passing and the failing case, so
 * it could not have distinguished them even if somebody had asserted on it.
 * `keyboard-money.selfcheck.mjs` pins both facts so neither spelling comes back.
 *
 * What replaces it: put real keyboard focus on the control with Tab (Chromium
 * only grants `:focus-visible` to keyboard-driven focus, so a scripted
 * `el.focus()` would under-report), then read the ordinary computed style and
 * diff it against the resting style. A focus indicator that changes nothing
 * visible is not an indicator.
 */

/** Computed properties a visible focus indicator is allowed to live in.
 *
 * Anything the guest stylesheet might plausibly use to mark focus. The check is
 * "at least one of these changed", so a wider list is a WEAKER assertion --
 * keep it to properties that actually render a focus affordance. */
export const FOCUS_PROPS = [
  "outlineStyle",
  "outlineWidth",
  "outlineColor",
  "outlineOffset",
  "boxShadow",
  "backgroundColor",
  "borderColor",
];

/** How many Tab presses before we call the control unreachable. Generous: the
 * point is to separate "needs a few tabs" from "cannot be reached at all". */
export const MAX_TABS = 20;

/** Read the properties above off an element, unfocused or focused alike. */
function readStyle(el, props) {
  const s = getComputedStyle(el);
  return Object.fromEntries(props.map((p) => [p, s[p]]));
}

/** Drive Tab from a known starting point and report where the focus went.
 *
 * Returns a plain object so `gradeKeyboardProbe` -- and its unit tests -- never
 * need a browser.
 *
 * @param {import("playwright").Page} page
 * @returns {Promise<{reached: boolean, tabIndex: number|null, trail: string[],
 *   focusVisible: boolean|null, changed: string[], resting: object|null,
 *   focused: object|null}>}
 */
export async function probeCopyControlKeyboard(
  page,
  { selector = "[data-copy]", maxTabs = MAX_TABS } = {},
) {
  const target = page.locator(selector).first();
  if ((await target.count()) === 0) {
    return {
      reached: false,
      tabIndex: null,
      trail: [],
      focusVisible: null,
      changed: [],
      resting: null,
      focused: null,
    };
  }

  // Resting style first: once focus lands we can no longer see the "before".
  const resting = await target.evaluate(readStyle, FOCUS_PROPS);

  // Start from a known place. Focus left behind by an earlier probe would shift
  // every Tab index below by one and make the first-Tab claim meaningless.
  await page.evaluate(() => {
    if (document.activeElement && document.activeElement !== document.body) {
      document.activeElement.blur();
    }
  });

  const trail = [];
  let tabIndex = null;
  for (let i = 1; i <= maxTabs; i += 1) {
    await page.keyboard.press("Tab");
    const here = await page.evaluate((sel) => {
      const el = document.activeElement;
      const wanted = document.querySelector(sel);
      if (!el || el === document.body) return { label: "body", isTarget: false };
      const label =
        el.tagName.toLowerCase() +
        (el.getAttribute("aria-label")
          ? `[${el.getAttribute("aria-label")}]`
          : el.getAttribute("data-copy") !== null
            ? `[data-copy=${el.getAttribute("data-copy")}]`
            : "");
      return { label, isTarget: el === wanted };
    }, selector);
    trail.push(here.label);
    if (here.isTarget) {
      tabIndex = i;
      break;
    }
  }

  if (tabIndex === null) {
    return {
      reached: false,
      tabIndex: null,
      trail,
      focusVisible: null,
      changed: [],
      resting,
      focused: null,
    };
  }

  const measured = await target.evaluate(
    (el, props) => ({
      // The pseudo-CLASS test that getComputedStyle could not do.
      focusVisible: el.matches(":focus-visible"),
      style: (() => {
        const s = getComputedStyle(el);
        return Object.fromEntries(props.map((p) => [p, s[p]]));
      })(),
    }),
    FOCUS_PROPS,
  );

  return {
    reached: true,
    tabIndex,
    trail,
    focusVisible: measured.focusVisible,
    changed: FOCUS_PROPS.filter((p) => resting[p] !== measured.style[p]),
    resting,
    focused: measured.style,
  };
}

/** Turn a probe into blocking problems. Pure: takes data, returns strings.
 *
 * Three separate claims, because they fail for different reasons and a report
 * that collapses them tells the reader nothing about what to fix.
 */
export function gradeKeyboardProbe(probe) {
  const problems = [];

  if (!probe.reached) {
    problems.push(
      probe.resting === null
        ? "không tìm thấy nút [data-copy] nào trên trang — không có gì để chép số tiền"
        : `nút chép số tiền KHÔNG tới được bằng bàn phím sau ${probe.trail.length} lần Tab ` +
          `(dừng lần lượt ở: ${probe.trail.join(" → ") || "không đâu cả"}) — WCAG 2.1.1 Keyboard`,
    );
    return { problems };
  }

  // README.md states this one as a fact in its results table, so it has to be
  // asserted or removed. If a skip link is ever added on purpose, this goes red
  // — change the expectation and that README row in the same commit.
  if (probe.tabIndex !== 1) {
    problems.push(
      `Tab đầu tiên dừng ở "${probe.trail[0]}", không phải nút chép số tiền ` +
        `(nút đó ở lần Tab thứ ${probe.tabIndex})`,
    );
  }

  if (!probe.focusVisible) {
    problems.push(
      "nút chép số tiền nhận được focus bàn phím nhưng không khớp :focus-visible — " +
        "trình duyệt sẽ không vẽ vòng focus mặc định cho nó",
    );
  }

  if (probe.changed.length === 0) {
    problems.push(
      "focus bàn phím không làm đổi bất kỳ thuộc tính nào trong " +
        `${FOCUS_PROPS.join("/")} — không có dấu hiệu focus nào thấy được (WCAG 2.4.7 Focus Visible)`,
    );
  }

  return { problems };
}

/** One-line summary for the run log. Reports the measured values so a reader
 * can see WHAT passed, not just that something did. */
export function describeKeyboardProbe(probe) {
  if (!probe.reached) {
    return `  bàn phím: KHÔNG tới được nút chép sau ${probe.trail.length} lần Tab`;
  }
  return (
    `  bàn phím: nút chép số tiền ở lần Tab thứ ${probe.tabIndex} ` +
    `(${probe.trail.join(" → ")}) · :focus-visible=${probe.focusVisible} · ` +
    `focus đổi: ${probe.changed.length ? probe.changed.map((p) => `${p} ${probe.resting[p]}→${probe.focused[p]}`).join(", ") : "KHÔNG ĐỔI GÌ"}`
  );
}
