/** Turning whatever was thrown into a sentence a person can read.
 *
 * `throw` in JavaScript takes any value, and libraries use that. The one that
 * reached a screen here was `expo-image-manipulator`, whose web build loads the
 * picked file through an `<img>` and, on a decode failure, does this
 * (`src/web/utils.web.ts`):
 *
 *     imageSource.onerror = () => reject(canvas);
 *
 * It rejects with the `HTMLCanvasElement` it was about to draw into. Both catch
 * sites on the bill flow ended with `String(problem)`, and `String` of a DOM
 * node is `[object HTMLCanvasElement]` -- which is what rd-qa-37 photographed,
 * twice on one screen, after picking a text file named `.jpg` (bug-010822).
 *
 * The `instanceof Error` half was never the problem. Every sentence this app
 * authors travels inside an `Error`, and `api.ts` already turns an unreachable
 * server into an `ApiError` whose message names the address it tried. So that
 * half is kept exactly as it was. What this module adds is that the OTHER half
 * cannot produce machine text, for any value, ever -- and it is a module rather
 * than a better ternary at each call site because there were two call sites and
 * the shared bug is precisely that each one had its own copy of the fallback.
 *
 * Deliberately NOT done here: printing the thrown value behind a "Chi tiết:"
 * label, the way `loi-may-chu.ts` does for a 5xx body. That excerpt is worth
 * showing because a server body sometimes carries a real explanation. A DOM
 * node carries none: there is no rendering of an `HTMLCanvasElement` that helps
 * the person holding the phone, so the honest thing is to say what we know and
 * stop.
 */

/** What to say when the thrown value explains nothing.
 *
 * Written to be true rather than reassuring. The app genuinely does not know
 * what happened at this point, and a sentence that guessed would send someone
 * to fix the wrong thing. It still ends with the one action that is always
 * available, because a dead end with no next step is how a screen strands
 * somebody.
 */
export const CAU_KHONG_RO = "Có gì đó hỏng ở bước này mà máy chưa nói rõ được. Thử lại giúp mình một lần nữa.";

/**
 * The sentence to show for a caught value.
 *
 * An `Error` with something in it speaks for itself. Anything else -- a DOM
 * node, a plain object, `null`, a symbol, an `Error` somebody constructed with
 * an empty message -- gets `CAU_KHONG_RO`, because there is no way to render
 * those that is better than admitting we do not know.
 *
 * Never returns an empty string. A blank error line reads as a screen that
 * broke rather than a refusal that was explained, and it is the one output that
 * would pass a "did we set an error?" check while showing nothing.
 */
export function moTaLoi(problem: unknown): string {
  const cau = chiTietLoi(problem);
  return cau !== "" ? cau : CAU_KHONG_RO;
}

/**
 * The app's own words out of a caught value, or an empty string.
 *
 * The difference from `moTaLoi` is the caller, not the safety. `moTaLoi` feeds
 * a line that is the WHOLE explanation, so it must always say something.
 * `chiTietLoi` feeds a "Chi tiết:" clause hanging off a sentence the screen
 * already wrote, and there the honest answer to "what else do we know" is
 * often nothing. Returning `CAU_KHONG_RO` into that slot would print
 * "Không kết nối được tới API. Chi tiết: Có gì đó hỏng ở bước này..." -- two
 * apologies where one sentence belongs. So this one is allowed to say nothing,
 * and `themChiTiet` in `loi-may-chu.ts` drops the label when it does.
 *
 * Sixteen call sites used to spell this `(e as Error).message`, which is a
 * *cast*: TypeScript believes it and the runtime does not. Measured, the three
 * ways it broke were all reachable from one `throw`:
 *
 *   - a string, a bare object, or the `HTMLCanvasElement` that
 *     `expo-image-manipulator` rejects with  ->  `detail` is `undefined`, and
 *     the screen prints "Chi tiết: undefined"
 *   - `null` or `undefined`  ->  reading `.message` THROWS inside the catch,
 *     so the error handler is the second thing to fail
 *   - an `Error` whose `.message` somebody set to a DOM node  ->
 *     "Chi tiết: [object HTMLCanvasElement]", which is bug-010822 again, on a
 *     screen the fix for it never touched
 *
 * Hence the two guards below rather than one. `instanceof Error` alone still
 * lets the third case through, because `.message` is only a string by
 * convention -- nothing enforces it, and `.trim()` on a canvas throws.
 */
export function chiTietLoi(problem: unknown): string {
  if (!(problem instanceof Error)) return "";
  const cau: unknown = problem.message;
  return typeof cau === "string" ? cau.trim() : "";
}
