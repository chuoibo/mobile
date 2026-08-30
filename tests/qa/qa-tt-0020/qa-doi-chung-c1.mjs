/* Control for row C1 of the QA independent table (qa-tt-0020).
 *
 * C1 replaced "re-read the wall" with "do the arithmetic locally" and the suite
 * stayed GREEN. Green has two possible causes and they are opposite:
 *
 *   (a) the suite genuinely cannot tell a server count from a local +1, or
 *   (b) my edit never reached the running code, and the green is the green of
 *       an unmutated build.
 *
 * This repo has been burned by (b) more than once, so the two rows below run
 * the SAME local-arithmetic mutation with a deliberately WRONG constant. If
 * those go red, the local path demonstrably executes and renders, which leaves
 * (a) as the only reading of C1's green. If they stay green too, C1 proves
 * nothing and must be withdrawn.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const HANG = "src/screens/ky-niem/TimVaBinhLuan.tsx";

const NEO_STATE =
  "  const daTha = kyNiem.viewer_has_reacted === true;\n  const soTim = kyNiem.reaction_count ?? 0;";
const THAY_STATE =
  "  const [buTay, setBuTay] = useState<{ d: boolean; s: number } | null>(null);\n" +
  "  const daTha = buTay ? buTay.d : kyNiem.viewer_has_reacted === true;\n" +
  "  const soTim = buTay ? buTay.s : kyNiem.reaction_count ?? 0;";

const NEO_GOI =
  "      if (daTha) await bo(contextId, kyNiem.id, personId);\n" +
  "      else await tha(contextId, kyNiem.id, personId);\n" +
  "      await onDoiTuong();";

const thayGoi = (buoc) =>
  "      if (daTha) {\n" +
  "        await bo(contextId, kyNiem.id, personId);\n" +
  `        setBuTay({ d: false, s: soTim - ${buoc} });\n` +
  "      } else {\n" +
  "        await tha(contextId, kyNiem.id, personId);\n" +
  `        setBuTay({ d: true, s: soTim + ${buoc} });\n` +
  "      }";

const ROWS = [
  { id: "C1", buoc: 1, kyVong: "đã đo: XANH — đây là hàng đang xét" },
  { id: "C1-x7", buoc: 7, kyVong: "phải ĐỎ nếu nhánh cộng tay thật sự chạy" },
  { id: "C1-x0", buoc: 0, kyVong: "phải ĐỎ: số đếm đứng yên sau khi bấm" },
];

function sh(c, a) {
  return execFileSync(c, a, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}
function restore() {
  sh("git", ["checkout", "--", HANG]);
}
function build() {
  execFileSync("npx", ["expo", "export", "--platform", "web", "--output-dir", ".expo-build-check", "--clear"], {
    stdio: "ignore",
    env: { ...process.env, EXPO_PUBLIC_API_URL: "http://api.build-check.invalid" },
  });
}
function doc(out) {
  const p = /^# pass (\d+)$/m.exec(out);
  const f = /^# fail (\d+)$/m.exec(out);
  if (!p || !f) return { pass: -1, fail: -1, raw: out.slice(-500) };
  const ten = [...out.matchAll(/^not ok \d+ - (.+)$/gm)].map((m) => m[1]);
  return { pass: Number(p[1]), fail: Number(f[1]), ten };
}
function run() {
  try {
    return doc(
      execFileSync("node", ["--test", "tests/tim-binh-luan.test.mjs"], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, MOBILE_REQUIRE_WEB_A11Y: "1" },
      }),
    );
  } catch (e) {
    return doc((e.stdout ?? "") + (e.stderr ?? ""));
  }
}

for (const row of ROWS) {
  restore();
  const src = readFileSync(HANG, "utf8");
  if (!src.includes(NEO_STATE) || !src.includes(NEO_GOI)) throw new Error(`${row.id}: neo không khớp`);
  writeFileSync(HANG, src.replace(NEO_STATE, THAY_STATE).replace(NEO_GOI, thayGoi(row.buoc)));
  const diff = sh("git", ["diff", "--stat", "--", HANG]).trim();
  if (diff === "") throw new Error(`${row.id}: file không đổi`);
  build();
  const r = run();
  console.log(
    `[${row.id}] cộng/trừ tại chỗ ±${row.buoc}  ->  ${r.pass} pass / ${r.fail} fail  ${r.fail > 0 ? "ĐỎ" : "XANH"}   (${row.kyVong})`,
  );
  if (r.ten?.length) for (const t of r.ten) console.log(`        đỏ ở: ${t}`);
}
restore();
build();
console.log("\nđã phục nguyên + dựng lại nền sạch");
