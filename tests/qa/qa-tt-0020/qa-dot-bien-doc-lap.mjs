/* QA independent mutation table for rd-fe-33 (PR #278) -- qa-tt-0020.
 *
 * Written by the QA lane, NOT reusing tools/dot-bien-tim.mjs. The author's own
 * table is a statement that the gate reddens for the shapes the author thought
 * of. Lead's canary law says the shape a check is written in is the thing being
 * proven, so every breaking row here re-expresses one of the SAME violations in
 * a DIFFERENT shape. A row that goes green is a hole the author's table could
 * not see, not a difference of opinion.
 *
 * Run from `apps/mobile`:  node tools/qa-dot-bien-doc-lap.mjs
 */
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const API = "src/api.ts";
const MAN = "src/screens/ky-niem/KyNiem.tsx";
const HANG = "src/screens/ky-niem/TimVaBinhLuan.tsx";
const CDP = "tests/chrome-cdp.mjs";
const FILES = [API, MAN, HANG, CDP];

const ROWS = [
  {
    id: "A1",
    kind: "PHA",
    viPham: "tim vẽ khi máy chủ chưa giữ được (cùng vi phạm hàng #1/#5 của tác giả)",
    what: 'coTuongTac dùng `!== null`: undefined !== null nên luôn true',
    file: API,
    from: '  return typeof kyNiem.reaction_count === "number";',
    to: "  return kyNiem.reaction_count !== null;",
    rebuild: true,
  },
  {
    id: "A2",
    kind: "PHA",
    viPham: "tim vẽ khi máy chủ chưa giữ được",
    what: "màn đổi điều kiện sang một trường LUÔN có mặt (kyNiem.id)",
    file: MAN,
    from: "{coTuongTac(kyNiem) ? (",
    to: "{kyNiem.id ? (",
    rebuild: true,
  },
  {
    id: "B1",
    kind: "PHA",
    viPham: "204 không được đọc là thành công (cùng vi phạm hàng #2)",
    what: "giữ nguyên nhánh nhưng lệch mã: 204 -> 205",
    file: API,
    from: "  if (response.status === 204) return undefined as T;",
    to: "  if (response.status === 205) return undefined as T;",
    rebuild: true,
  },
  {
    id: "B2",
    kind: "PHA",
    viPham: "204 không được đọc là thành công",
    what: "nhánh còn nguyên nhưng vẫn gọi json() trên thân rỗng",
    file: API,
    from: "  if (response.status === 204) return undefined as T;",
    to: "  if (response.status === 204) return (await response.json()) as T;",
    rebuild: true,
  },
  {
    id: "C1",
    kind: "PHA",
    viPham: 'số đếm phải là số máy chủ trả về ("Không cộng trừ tại chỗ" — lời PR)',
    what: "cộng trừ tại chỗ, KHÔNG đọc lại tường (đúng bản tối ưu lạc quan mà PR nói đã từ chối)",
    file: HANG,
    from:
      "      if (daTha) await bo(contextId, kyNiem.id, personId);\n" +
      "      else await tha(contextId, kyNiem.id, personId);\n" +
      "      await onDoiTuong();",
    to:
      "      if (daTha) {\n" +
      "        await bo(contextId, kyNiem.id, personId);\n" +
      "        setBuTay({ d: false, s: soTim - 1 });\n" +
      "      } else {\n" +
      "        await tha(contextId, kyNiem.id, personId);\n" +
      "        setBuTay({ d: true, s: soTim + 1 });\n" +
      "      }",
    them: [
      {
        from: "  const daTha = kyNiem.viewer_has_reacted === true;\n  const soTim = kyNiem.reaction_count ?? 0;",
        to:
          "  const [buTay, setBuTay] = useState<{ d: boolean; s: number } | null>(null);\n" +
          "  const daTha = buTay ? buTay.d : kyNiem.viewer_has_reacted === true;\n" +
          "  const soTim = buTay ? buTay.s : kyNiem.reaction_count ?? 0;",
      },
    ],
    rebuild: true,
  },
  {
    id: "D1",
    kind: "PHA",
    viPham: "clickLabel phải cuộn tới trước khi đo (lỗi hạ tầng #2 PR khai đã sửa)",
    what: 'gỡ scrollIntoView, GIỮ phép chặn — nếu nút thật sự ngoài khung thì chặn phải nổ',
    file: CDP,
    from: '        el.scrollIntoView({ block: "nearest", inline: "nearest" });\n',
    to: "",
    rebuild: false,
  },
  {
    id: "D2",
    kind: "PHA",
    viPham: "clickLabel không được bấm vào hư không rồi trả về bình thường",
    what: "phục nguyên clickLabel TRƯỚC PR (không cuộn, không chặn) — bấm im lặng vào chỗ trống",
    file: CDP,
    from:
      '        el.scrollIntoView({ block: "nearest", inline: "nearest" });\n' +
      "        const r = el.getBoundingClientRect();\n" +
      "        const x = r.left + r.width / 2;\n" +
      "        const y = r.top + r.height / 2;\n" +
      "        return { x, y, trongMan: x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight };",
    to:
      "        const r = el.getBoundingClientRect();\n" +
      "        return { x: r.left + r.width / 2, y: r.top + r.height / 2, trongMan: true };",
    rebuild: false,
  },
  {
    id: "G1",
    kind: "GIU",
    viPham: "—",
    what: "đổi TÊN biến nội bộ soTim -> demTim (giữ nguyên mọi tính chất)",
    file: HANG,
    from: "  const soTim = kyNiem.reaction_count ?? 0;",
    to: "  const demTim = kyNiem.reaction_count ?? 0;",
    themSau: [{ from: /\bsoTim\b/g, to: "demTim" }],
    rebuild: true,
  },
  {
    id: "G2",
    kind: "GIU",
    viPham: "—",
    what: "đổi HẰNG SỐ phụ: viewport 390x844 -> 414x896 (khác hằng, giữ tính chất)",
    file: "tests/tim-binh-luan.test.mjs",
    from: "await page.viewport(390, 844);",
    to: "await page.viewport(414, 896);",
    rebuild: false,
  },
];

function sh(cmd, args) {
  return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

function apply(row) {
  const targets = [row.file];
  let before = readFileSync(row.file, "utf8");
  if (!before.includes(row.from)) throw new Error(`${row.id}: KHÔNG thấy neo trong ${row.file}`);
  const n = before.split(row.from).length - 1;
  if (n !== 1) throw new Error(`${row.id}: neo khớp ${n} chỗ, phải đúng 1`);
  let after = before.replace(row.from, row.to);
  for (const t of row.them ?? []) {
    if (!after.includes(t.from)) throw new Error(`${row.id}: neo phụ không khớp`);
    after = after.replace(t.from, t.to);
  }
  for (const t of row.themSau ?? []) after = after.replace(t.from, t.to);
  writeFileSync(row.file, after);
  const diff = sh("git", ["diff", "--stat", "--", ...targets]).trim();
  if (diff === "") throw new Error(`${row.id}: file không đổi sau khi ghi`);
  return diff;
}

function restore() {
  sh("git", ["checkout", "--", ...FILES, "tests/tim-binh-luan.test.mjs"]);
}

function build() {
  execFileSync("npx", ["expo", "export", "--platform", "web", "--output-dir", ".expo-build-check", "--clear"], {
    encoding: "utf8",
    stdio: "ignore",
    env: { ...process.env, EXPO_PUBLIC_API_URL: "http://api.build-check.invalid" },
  });
}

/** Only the summary lines. Grepping the whole output reads the docstrings of
 *  the FAILING cases back as numbers -- this repo has been bitten by that. */
function doc(out) {
  const p = /^# pass (\d+)$/m.exec(out);
  const f = /^# fail (\d+)$/m.exec(out);
  const s = /^# skipped (\d+)$/m.exec(out);
  if (!p || !f) return { pass: -1, fail: -1, skip: -1, raw: out.slice(-600) };
  return { pass: Number(p[1]), fail: Number(f[1]), skip: s ? Number(s[1]) : -1 };
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

restore();
console.log("== nền sạch (MOBILE_REQUIRE_WEB_A11Y=1, nên bỏ qua = đỏ) ==");
build();
const nen = run();
console.log(`   ${nen.pass} pass / ${nen.fail} fail / ${nen.skip} skipped`);
if (nen.fail !== 0 || nen.pass !== 6) {
  console.log("   nền KHÔNG phải 6 pass / 0 fail — dừng, mọi hàng dưới vô nghĩa");
  if (nen.raw) console.log(nen.raw);
  process.exit(1);
}

const ket = [];
for (const row of ROWS) {
  restore();
  let diff;
  try {
    diff = apply(row);
  } catch (err) {
    console.log(`\n[${row.id}] ${row.kind} — KHÔNG ÁP ĐƯỢC: ${err.message}`);
    ket.push({ ...row, ketQua: "KHÔNG ÁP ĐƯỢC" });
    continue;
  }
  if (row.rebuild) build();
  const r = run();
  const do_ = r.fail > 0;
  const dung = row.kind === "PHA" ? do_ : !do_;
  console.log(
    `\n[${row.id}] ${row.kind} ${row.what}\n   vi phạm: ${row.viPham}\n   diff: ${diff.replace(/\n/g, " ")}\n   ${r.pass} pass / ${r.fail} fail  ->  ${do_ ? "ĐỎ" : "XANH"}   ${dung ? "đúng kỳ vọng" : "*** SAI KỲ VỌNG — CHỖ MÙ ***"}`,
  );
  ket.push({ ...row, pass: r.pass, fail: r.fail, do: do_, dung });
}

restore();
console.log("\n== bảng QA độc lập ==");
for (const k of ket) {
  console.log(
    `| ${k.id} | ${k.kind} | ${k.what} | ${k.ketQua ?? `${k.pass} pass / ${k.fail} fail`} | ${k.do === undefined ? "?" : k.do ? "ĐỎ" : "XANH"} | ${k.dung === undefined ? "?" : k.dung ? "đúng" : "CHỖ MÙ"} |`,
  );
}
const sai = ket.filter((k) => k.dung === false || k.ketQua);
console.log(sai.length === 0 ? "\nKHÔNG CÓ CHỖ MÙ" : `\n${sai.length} HÀNG CẦN GIẢI THÍCH: ${sai.map((s) => s.id).join(", ")}`);
