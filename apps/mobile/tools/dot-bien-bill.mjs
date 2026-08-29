/** Prove the `/bills` gate is a gate, by breaking the code it claims to guard.
 *
 * A green suite is not evidence. It is evidence only once the same suite has
 * been shown to go red, for the right reason, when the property it names is
 * actually violated. This repo has collected the failure modes the hard way:
 * a gate that read source text instead of behaviour stayed green with the
 * feature switched off (#201); mutations written against invented identifiers
 * went red with `ReferenceError` for forty cases and read exactly like a
 * working gate; mutations that also disturbed a neighbouring constant went red
 * for that constant instead of for the property under test.
 *
 * So each mutation here obeys three rules:
 *
 *   1. It is read out of the current source, never guessed. A mutation whose
 *      `from` string does not appear is a hard error, not a skip -- silently
 *      skipping is how "0 mutations survived" gets printed by a script that
 *      applied none of them.
 *   2. It stays syntactically and referentially valid. Every identifier it
 *      introduces already exists in scope, so red means "the assertion caught
 *      it", not "the module failed to load".
 *   3. It changes exactly one property, leaving every other constant alone.
 *
 * Run from `apps/mobile`:  node tools/dot-bien-bill.mjs
 */
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const SUITE = "tests/bill-gan-mon.test.mjs";

/** Each: the property it attacks, the file, and one exact substring swap. */
const DOT_BIEN = [
  {
    ten: "nguyenDong làm tròn thay vì ném",
    tinhChat: "luật 1: không float, kể cả ở giá trị trung gian",
    file: "src/bill.ts",
    tu: "    throw new RangeError(`${field} phải là số nguyên đồng, nhận được ${value}`);",
    thanh: "    return Math.round(value);",
  },
  {
    // Not `row.from_id`. That version is the one this code nearly shipped, but
    // it does not COMPILE -- the field is absent from the type -- so running it
    // measures tsc, not this suite. Swapping the two real fields is the same
    // defect (the arrow points the wrong way, so the screen tells the group
    // that the person owed money is the one who must pay) expressed in a way
    // the compiler accepts, which is what leaves the assertion to do the work.
    ten: "soDuFromWire đảo chiều người trả và người nhận",
    tinhChat: "chiều của một khoản chuyển tiền",
    file: "src/bill.ts",
    tu: "      fromId: row.sender_id,\n      toId: row.recipient_id,",
    thanh: "      fromId: row.recipient_id,\n      toId: row.sender_id,",
  },
  {
    // Same reason: the bare `=== null` fails to typecheck, because the body
    // below then reads a possibly-undefined value. Adding `!` is exactly what
    // a careless edit does to silence that, so this is the realistic shape of
    // the bug AND it compiles.
    ten: "moTaTrangThaiGan quay lại `=== null`, im lặng bằng `!`",
    tinhChat: "prop thiếu là sự vắng mặt, không phải trạng thái thứ ba",
    file: "src/bill.ts",
    // Every later use of `bill` needs the `!` too, not just the first: patching
    // one of them leaves tsc failing on the next line, which the runner would
    // report as "KHÔNG BIÊN DỊCH ĐƯỢC" and prove nothing either way.
    tu:
      "  if (bill == null) {\n" +
      "    return \"Chưa lưu được. Ô đã tích chỉ ở máy này.\";\n" +
      "  }\n" +
      "  const con = bill.suggested_item_keys.length;\n" +
      "  if (con === 0) {\n" +
      "    return \"Đã lưu. Nhóm đã chốt ai ăn món gì.\";\n" +
      "  }\n" +
      "  if (con === bill.items.length) {",
    thanh:
      "  if (bill === null) {\n" +
      "    return \"Chưa lưu được. Ô đã tích chỉ ở máy này.\";\n" +
      "  }\n" +
      "  const con = bill!.suggested_item_keys.length;\n" +
      "  if (con === 0) {\n" +
      "    return \"Đã lưu. Nhóm đã chốt ai ăn món gì.\";\n" +
      "  }\n" +
      "  if (con === bill!.items.length) {",
  },
  {
    ten: "billCreateBody lấy tên món làm item_key",
    tinhChat: "khoá dòng là id, nên hai món trùng tên không gộp làm một",
    file: "src/bill.ts",
    tu: "    item_key: line.id,\n    name: line.name,",
    thanh: "    item_key: line.name,\n    name: line.name,",
  },
  {
    ten: "assignmentsBody bỏ qua dòng chưa ai nhận",
    tinhChat: "mọi dòng đều được phát, kể cả dòng rỗng",
    file: "src/bill.ts",
    tu: "    assignments: reading.lines.map((line) => ({",
    thanh:
      "    assignments: reading.lines.filter((line) => whoOn(assignment, line.id).length > 0).map((line) => ({",
  },
  {
    ten: "chuaAiNhanVnd luôn trả 0",
    tinhChat: "câu chặn nói ra số tiền chưa ai nhận",
    file: "src/assignment.ts",
    tu: "  return reading.lines\n    .filter((line) => whoOn(a, line.id).length === 0)\n    .reduce((sum, line) => sum + line.lineTotalVnd, 0);",
    thanh: "  return reading.lines.length === 0 ? 0 : 0;",
  },
];

function chay() {
  // tsc first: a mutation that never reached dist-test would be measured as
  // "survived" while the tests ran against the clean build.
  execFileSync("npx", ["tsc", "-p", "tsconfig.test.json"], { stdio: "pipe" });
  execFileSync("node", ["tools/fixup-esm.mjs"], { stdio: "pipe" });
  execFileSync("node", ["--test", SUITE], { stdio: "pipe" });
}

let songSot = 0;
for (const m of DOT_BIEN) {
  const goc = readFileSync(m.file, "utf8");
  if (!goc.includes(m.tu)) {
    console.error(`LỖI SCRIPT: không tìm thấy chuỗi cần đổi trong ${m.file}`);
    console.error(`  ${JSON.stringify(m.tu.slice(0, 60))}`);
    process.exit(3);
  }
  writeFileSync(m.file, goc.replace(m.tu, m.thanh));
  let doRoi = false;
  let viSao = "";
  try {
    chay();
  } catch (loi) {
    doRoi = true;
    const ra = String(loi.stdout ?? "") + String(loi.stderr ?? "");
    // Report WHY it went red. A mutation that goes red because the module
    // stopped compiling proves nothing about the assertions.
    viSao = /error TS\d+/.test(ra)
      ? "KHÔNG BIÊN DỊCH ĐƯỢC (không tính là bắt được)"
      : /ReferenceError|is not defined/.test(ra)
        ? "ReferenceError (không tính là bắt được)"
        : `${(ra.match(/^# fail (\d+)$/m) ?? [])[1] ?? "?"} ca đỏ`;
  } finally {
    writeFileSync(m.file, goc);
  }
  const nhan = doRoi ? "BẮT ĐƯỢC" : "SỐNG SÓT";
  if (!doRoi) songSot += 1;
  console.log(`${nhan}  ${m.ten}`);
  console.log(`          tính chất: ${m.tinhChat}`);
  if (viSao) console.log(`          ${viSao}`);
}

// Rebuild clean so the tree is not left holding a mutated dist-test.
chay();
console.log(`\n${DOT_BIEN.length - songSot}/${DOT_BIEN.length} đột biến bị bắt.`);
process.exit(songSot === 0 ? 0 : 1);
