/* rd-qa-34 — đối chứng #190 ở DOM sống, không ở source.
 *
 * The gate #190 ships is a SOURCE gate: a TypeScript AST walk over
 * apps/mobile/src. That is the right shape for a gate, but it cannot answer the
 * question a reviewer actually needs answered — does the em dash reach the DOM a
 * person reads, and does it leave. Source clean does not imply rendered clean:
 * copy can arrive from a file outside the walk, and a bundler can transform it.
 *
 * So this probe measures the built artifact instead. Point it at an expo web
 * export, and it walks the app the way a user does (past the person picker,
 * into the tab shell) and reports every `aria-label` and every visible line
 * carrying the character.
 *
 * RUN IT TWICE, and read the pre-fix run first. On an export built before the
 * fix it must report 4 — all four tab labels. If it reports 0 there, the probe
 * is blind (wrong export dir, Chrome missing, the walk never reached the shell)
 * and the 0 on the fixed export means nothing at all. That pairing is the whole
 * point: a scanner that cannot go red is not evidence, it is decoration.
 *
 *   node tests/qa/rd-qa-34/em-dash-dom-song.mjs <duong-dan-toi-expo-export>
 *
 * Measured 2026-08-29: before 2d61e39 -> 4 aria-labels carry it, head of #190
 * (0fe4be0) -> 0. Visible text: 0 on BOTH, which is why eyes never caught it.
 */
import { findChrome, launch, serve } from "../../../apps/mobile/tests/chrome-cdp.mjs";

const EXPORT_DIR = process.argv[2];
const EM_DASH = "—";
const EN_DASH = "–";
const BO_QUA = "Bỏ qua, vào app mà chưa chọn người";

if (!EXPORT_DIR) {
  console.error("dùng: node em-dash-dom-song.mjs <thư-mục-expo-export>");
  process.exit(2);
}

/** Runs inside the page, so it closes over nothing from this module. */
function readDom() {
  return {
    aria: [...document.querySelectorAll("[aria-label]")].map((el) => el.getAttribute("aria-label")),
    text: document.body.innerText,
  };
}

const bin = findChrome();
if (!bin) {
  // Loud, not a silent skip. A missing browser produces the same empty result
  // as a clean page, and that confusion is how a scan gets read as a pass.
  console.error("khong tim thay Chrome — probe nay se mu; dat CHROME_BIN roi chay lai");
  process.exit(2);
}

const server = await serve(EXPORT_DIR);
const page = await launch(bin);
let viPham = 0;
try {
  await page.viewport(390, 844);
  // readyFn is stringified into the page: pass the label as an arg rather than
  // closing over it, or every poll throws ReferenceError and the timeout looks
  // exactly like a page that never rendered.
  await page.goto(server.url, (label) => !!document.querySelector(`[aria-label="${label}"]`), BO_QUA);
  await page.clickLabel(BO_QUA);
  await page.waitFor(() => document.querySelectorAll('[role="tab"]').length === 4, { label: "bốn tab" });

  const { aria, text } = await page.evaluate(readDom);
  const ariaEm = aria.filter((a) => a.includes(EM_DASH));
  const textEm = text.split("\n").filter((l) => l.includes(EM_DASH));
  viPham = ariaEm.length + textEm.length;

  console.log(`=== ${EXPORT_DIR} ===`);
  console.log(`   aria-label đọc được:            ${aria.length}`);
  console.log(`   aria-label CÓ em-dash:          ${ariaEm.length}`);
  ariaEm.forEach((a) => console.log(`      ! ${a}`));
  console.log(`   dòng chữ HIỂN THỊ có em-dash:   ${textEm.length}`);
  textEm.slice(0, 8).forEach((l) => console.log(`      ! ${l.trim().slice(0, 88)}`));
  console.log(`   en-dash (CÓ Ý cho phép, không tính vi phạm): ${(text.split(EN_DASH).length - 1)}`);
  console.log(`   --- nhãn tab trình đọc màn hình đọc lên ---`);
  aria.filter((a) => /Khám phá|Lên plan|Tin nhắn|Cá nhân/.test(a)).forEach((a) => console.log(`      • ${a}`));
} finally {
  await page.close();
  await server.close();
}

process.exit(viPham === 0 ? 0 : 1);
