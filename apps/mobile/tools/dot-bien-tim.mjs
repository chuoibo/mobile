/* Mutation table for the hearts-and-comments gate (rd-fe-33).
 *
 * Run from `apps/mobile`:  node tools/dot-bien-tim.mjs
 *
 * Two kinds of row, and BOTH are needed. A table of only breaking mutations
 * proves the gate goes red when something moves; it cannot tell "measures the
 * property" apart from "notices anybody touched the file". The keep-the-property
 * rows are the ones that separate those: each is a change a person tidying up
 * would genuinely make, and a gate that reddens on them gets switched off
 * within a week.
 *
 * Every row verifies the edit actually landed before believing its result --
 * a `replace` that silently matched nothing reports GREEN and reads exactly
 * like a gate that is blind.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const API = "src/api.ts";
const MAN = "src/screens/ky-niem/KyNiem.tsx";
const HANG = "src/screens/ky-niem/TimVaBinhLuan.tsx";
const STUB = "tools/tab-snapshots.mjs";

const ROWS = [
  {
    id: 1,
    kind: "PHA",
    what: "Vẽ tim cho mọi hàng feed, bỏ phép kiểm máy chủ có bảng",
    file: MAN,
    from: "{coTuongTac(kyNiem) ? (",
    to: "{true ? (",
    rebuild: true,
  },
  {
    id: 2,
    kind: "PHA",
    what: "Bỏ nhánh 204, để response.json() chạy trên thân rỗng",
    file: API,
    from: "  if (response.status === 204) return undefined as T;\n",
    to: "",
    rebuild: true,
  },
  {
    id: 3,
    kind: "PHA",
    what: "Tim luôn gửi POST, không đọc viewer_has_reacted",
    file: HANG,
    from:
      "      if (daTha) await bo(contextId, kyNiem.id, personId);\n" +
      "      else await tha(contextId, kyNiem.id, personId);",
    to: "      await tha(contextId, kyNiem.id, personId);",
    rebuild: true,
  },
  {
    id: 4,
    kind: "PHA",
    what: "Gửi bình luận xong không đọc lại tường, số đếm đứng yên",
    file: HANG,
    // Removes the REAL call. The first draft of this row inserted a dead
    // `if (false) await onDoiTuong();` above the comment block and left the
    // live call below it untouched: a genuine diff, a no-op mutation, and a
    // GREEN that read exactly like a blind gate. The anchor now swallows the
    // call itself, which is the only edit that can change behaviour.
    from: "      await onDoiTuong();\n    } catch (error) {\n      setLoiGui(",
    to: "    } catch (error) {\n      setLoiGui(",
    rebuild: true,
  },
  {
    id: 5,
    kind: "PHA",
    what: "coTuongTac viết bằng truthiness: ảnh 0 tim mất nút",
    file: API,
    from: '  return typeof kyNiem.reaction_count === "number";',
    to: "  return Boolean(kyNiem.reaction_count);",
    rebuild: true,
  },
  {
    id: 6,
    kind: "GIU",
    what: "Đổi hình trái tim sang hình ngôi sao",
    file: HANG,
    from: '            {daTha ? "♥" : "♡"}',
    to: '            {daTha ? "★" : "☆"}',
    rebuild: true,
  },
  {
    id: 7,
    kind: "GIU",
    what: "Đổi câu chữ nhìn thấy trên nút gửi",
    file: HANG,
    from: '          {dangGui ? "Đang gửi…" : "Gửi"}',
    to: '          {dangGui ? "Đang gửi bình luận…" : "Gửi đi"}',
    rebuild: true,
  },
  {
    id: 8,
    kind: "GIU",
    what: "Đảo thứ tự hai ảnh mà tường đọc được",
    file: STUB,
    from: "        memories: fixtures.kyNiem.map((m) =>",
    to: "        memories: [...fixtures.kyNiem].reverse().map((m) =>",
    rebuild: false,
  },
];

function sh(cmd, args) {
  return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

function apply(row) {
  const before = readFileSync(row.file, "utf8");
  if (!before.includes(row.from)) {
    throw new Error(`đột biến ${row.id}: KHÔNG tìm thấy neo trong ${row.file}`);
  }
  const count = before.split(row.from).length - 1;
  if (count !== 1) {
    throw new Error(`đột biến ${row.id}: neo khớp ${count} chỗ, phải đúng 1`);
  }
  writeFileSync(row.file, before.replace(row.from, row.to));
  const diff = sh("git", ["diff", "--stat", "--", row.file]).trim();
  if (diff === "") throw new Error(`đột biến ${row.id}: file không đổi sau khi ghi`);
  return diff;
}

function restore() {
  sh("git", ["checkout", "--", API, MAN, HANG, STUB]);
}

function build() {
  execFileSync(
    "npx",
    ["expo", "export", "--platform", "web", "--output-dir", ".expo-build-check", "--clear"],
    { encoding: "utf8", stdio: "ignore", env: { ...process.env, EXPO_PUBLIC_API_URL: "http://api.build-check.invalid" } },
  );
}

function run() {
  try {
    const out = execFileSync("node", ["--test", "tests/tim-binh-luan.test.mjs"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return doc(out);
  } catch (e) {
    return doc((e.stdout ?? "") + (e.stderr ?? ""));
  }
}

/** Read ONLY the summary lines. Grepping the whole output picks up the
 *  docstrings of the cases that are failing, which is how a harness once
 *  reported "1527 passed" for a run of exactly one test. */
function doc(out) {
  const pass = /^# pass (\d+)$/m.exec(out);
  const fail = /^# fail (\d+)$/m.exec(out);
  if (!pass || !fail) return { pass: -1, fail: -1, raw: out.slice(-400) };
  return { pass: Number(pass[1]), fail: Number(fail[1]) };
}

restore();
console.log("== nền sạch ==");
build();
const nen = run();
console.log(`   ${nen.pass} pass / ${nen.fail} fail`);
if (nen.fail !== 0) {
  console.log("   nền đã đỏ, dừng: mọi hàng dưới đây sẽ vô nghĩa");
  process.exit(1);
}

const ket = [];
for (const row of ROWS) {
  restore();
  let diff;
  try {
    diff = apply(row);
  } catch (err) {
    console.log(`\n#${row.id} ${row.kind} ${row.what}\n   LỖI: ${err.message}`);
    ket.push({ ...row, ketQua: "KHÔNG ÁP ĐƯỢC" });
    continue;
  }
  if (row.rebuild) build();
  const r = run();
  const do_ = r.fail > 0;
  const dung = row.kind === "PHA" ? do_ : !do_;
  console.log(
    `\n#${row.id} ${row.kind} ${row.what}\n   diff: ${diff}\n   ${r.pass} pass / ${r.fail} fail  ->  ${do_ ? "ĐỎ" : "XANH"}  ${dung ? "ĐÚNG KỲ VỌNG" : "*** SAI KỲ VỌNG ***"}`,
  );
  ket.push({ ...row, pass: r.pass, fail: r.fail, do: do_, dung });
}

restore();
build();
console.log("\n== bảng ==");
for (const k of ket) {
  console.log(
    `| ${k.id} | ${k.kind === "PHA" ? "phá" : "GIỮ"} | ${k.what} | ${k.pass} pass / ${k.fail} fail | ${k.do ? "ĐỎ" : "XANH"} | ${k.dung ? "đúng" : "SAI"} |`,
  );
}
const sai = ket.filter((k) => !k.dung);
console.log(sai.length === 0 ? "\nTẤT CẢ ĐÚNG KỲ VỌNG" : `\n${sai.length} HÀNG SAI KỲ VỌNG`);
