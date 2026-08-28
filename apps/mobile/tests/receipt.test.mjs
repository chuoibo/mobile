/** The bill a person is allowed to correct, and the arithmetic under it.
 *
 * The fixture in here is not invented. It is the verbatim body of a real
 * `POST /receipts/scan` against a live server on 2026-08-29, reading a real
 * photograph of the mockup bill through Gemini. That matters for two of these
 * tests specifically: they assert that our own sum and our own gap agree with
 * `items_total_vnd` and `total_difference_vnd` as the server computed them. A
 * fixture written by hand could not fail those, because the same person would
 * have written both sides.
 *
 * It is also a genuinely imperfect reading, which is why it was kept. The
 * reader misread several digits off a blurry crop, so the lines add to 963.000
 * while the paper says 1.125.000. That is the whole reason the edit affordance
 * exists, and a fixture where the machine got everything right would have
 * tested none of it.
 */
import assert from "node:assert/strict";
import test from "node:test";
import {
  addLine,
  blockingProblem,
  editedCount,
  isEdited,
  itemsTotalVnd,
  readingFromWire,
  removeLine,
  renameLine,
  setLineTotal,
  setQuantity,
  totalGapVnd,
} from "../dist-test/receipt.js";

/** Captured live. Do not tidy the numbers; the mismatch is the point. */
const LIVE_SCAN = {
  items: [
    { name: "Sườn nướng Mỹ", quantity: 1, unit_price_vnd: 219000, line_total_vnd: 219000 },
    { name: "Ba chỉ heo", quantity: 1, unit_price_vnd: 148000, line_total_vnd: 148000 },
    { name: "Bò cuộn phô mai", quantity: 1, unit_price_vnd: 128000, line_total_vnd: 128000 },
    { name: "Lẩu kim chi", quantity: 1, unit_price_vnd: 198000, line_total_vnd: 198000 },
    { name: "Tokbokki phô mai", quantity: 1, unit_price_vnd: 79000, line_total_vnd: 79000 },
    { name: "Cơm chiên trứng", quantity: 1, unit_price_vnd: 79000, line_total_vnd: 79000 },
    { name: "Pepsi", quantity: 2, unit_price_vnd: 14000, line_total_vnd: 28000 },
    { name: "Tiger bạc", quantity: 3, unit_price_vnd: 28000, line_total_vnd: 84000 },
  ],
  items_total_vnd: 963000,
  total_vnd: 1125000,
  totals_agree: false,
  total_difference_vnd: 162000,
  confidence: 98,
  warnings: ["Tổng in trên bill chênh +162000 đồng so với tổng các dòng; giữ nguyên cả hai số."],
};

test("một phản hồi thật trở thành tám dòng sửa được", () => {
  const reading = readingFromWire(LIVE_SCAN);
  assert.equal(reading.lines.length, 8);
  assert.equal(reading.printedTotalVnd, 1125000);
  assert.equal(reading.confidence, 98);
  assert.equal(reading.warnings.length, 1);
  // Nothing is edited before anybody has touched it.
  assert.equal(editedCount(reading), 0);
  assert.equal(reading.lines.every((line) => !isEdited(line)), true);
});

test("tổng của client khớp items_total_vnd của máy chủ", () => {
  // Two implementations of one sum. If they ever disagree, one screen is
  // showing a number the server never computed.
  const reading = readingFromWire(LIVE_SCAN);
  assert.equal(itemsTotalVnd(reading), LIVE_SCAN.items_total_vnd);
});

test("khoảng lệch cùng dấu và cùng độ lớn với total_difference_vnd", () => {
  // The sign is the part that was actually at risk. `items - printed` reads
  // the same as `printed - items` right up until a minus sign lands on screen.
  const reading = readingFromWire(LIVE_SCAN);
  assert.equal(totalGapVnd(reading), LIVE_SCAN.total_difference_vnd);
  assert.equal(totalGapVnd(reading) > 0, true);
});

test("sửa một chữ số máy đọc nhầm thì khoảng lệch co lại đúng bằng số đó", () => {
  const reading = readingFromWire(LIVE_SCAN);
  const before = totalGapVnd(reading);
  // The paper says 149.000 for Ba chỉ heo; the reader saw 148.000.
  const fixed = setLineTotal(reading, "mon-1", "149000");
  assert.equal(fixed.ok, true);
  assert.equal(itemsTotalVnd(fixed.reading), 964000);
  assert.equal(totalGapVnd(fixed.reading), before - 1000);
});

test("sửa hết cho khớp thì khoảng lệch về 0 và không có số lẻ nào sinh ra", () => {
  let reading = readingFromWire(LIVE_SCAN);
  // A set of corrections that closes the 162.000 gap exactly. Chosen so the
  // arithmetic is checkable by hand: +1.000 +1.000 +1.000 +10.000 +149.000.
  for (const [id, amount] of [
    ["mon-1", "149000"],
    ["mon-2", "129000"],
    ["mon-3", "199000"],
    ["mon-4", "89000"],
    ["mon-7", "233000"],
  ]) {
    const result = setLineTotal(reading, id, amount);
    assert.equal(result.ok, true, `sửa ${id} phải được chấp nhận`);
    reading = result.reading;
  }
  assert.equal(itemsTotalVnd(reading), 1125000);
  assert.equal(totalGapVnd(reading), 0);
  assert.equal(Number.isInteger(itemsTotalVnd(reading)), true);
  assert.equal(editedCount(reading), 5);
});

test("mọi số tiền sau khi sửa vẫn là số nguyên đồng", () => {
  let reading = readingFromWire(LIVE_SCAN);
  // Amounts a person plausibly types, including grouped ones.
  for (const [id, typed] of [["mon-0", "1.234.567"], ["mon-1", "12 000"], ["mon-2", "0"]]) {
    const result = setLineTotal(reading, id, typed);
    assert.equal(result.ok, true);
    reading = result.reading;
  }
  assert.equal(reading.lines[0].lineTotalVnd, 1234567);
  assert.equal(reading.lines[1].lineTotalVnd, 12000);
  // Zero is a comped dish, not a deletion. It survives as a line.
  assert.equal(reading.lines[2].lineTotalVnd, 0);
  assert.equal(reading.lines.length, 8);
  for (const line of reading.lines) {
    assert.equal(Number.isInteger(line.lineTotalVnd), true, `${line.name} phải là số nguyên`);
    assert.equal(Number.isInteger(line.quantity), true);
  }
  assert.equal(Number.isInteger(itemsTotalVnd(reading)), true);
});

test("số lượng từ chối 0, chữ, và ô trống, mỗi thứ một lý do riêng", () => {
  const reading = readingFromWire(LIVE_SCAN);
  assert.deepEqual(setQuantity(reading, "mon-0", "0"), { ok: false, reason: "not-positive" });
  assert.deepEqual(setQuantity(reading, "mon-0", "hai"), { ok: false, reason: "not-a-number" });
  assert.deepEqual(setQuantity(reading, "mon-0", "   "), { ok: false, reason: "empty" });
  // A refusal must not move the number that is already there.
  assert.equal(reading.lines[0].quantity, 1);
  const ok = setQuantity(reading, "mon-0", "3");
  assert.equal(ok.ok, true);
  assert.equal(ok.reading.lines[0].quantity, 3);
});

test("số quá lớn bị từ chối chứ không bị làm tròn âm thầm", () => {
  const reading = readingFromWire(LIVE_SCAN);
  // Past MAX_AMOUNT_VND. The parser checks the digit string before it ever
  // becomes a double, which is what stops a silent rounding here.
  // repo-guard: allow=long-number reason=synthetic-numeric-boundary-not-an-account
  const result = setLineTotal(reading, "mon-0", "99999999999999");
  assert.deepEqual(result, { ok: false, reason: "too-large" });
});

test("sửa số lượng không tự ý viết lại số tiền", () => {
  // Deliberate. A keystroke in the SL column silently rewriting an amount
  // somebody already corrected is how two screens end up disagreeing.
  const reading = readingFromWire(LIVE_SCAN);
  const result = setQuantity(reading, "mon-6", "5");
  assert.equal(result.ok, true);
  assert.equal(result.reading.lines[6].quantity, 5);
  assert.equal(result.reading.lines[6].lineTotalVnd, 28000);
  assert.equal(itemsTotalVnd(result.reading), 963000);
});

test("xoá một dòng không kéo giá của dòng khác sang chỗ trống", () => {
  // Identity is the id, never the position. Keyed by index, deleting row 1
  // hands its money to whatever slides up into slot 1.
  const reading = readingFromWire(LIVE_SCAN);
  const after = removeLine(reading, "mon-1");
  assert.equal(after.lines.length, 7);
  assert.equal(after.lines.find((l) => l.id === "mon-1"), undefined);
  assert.equal(after.lines.find((l) => l.id === "mon-2").name, "Bò cuộn phô mai");
  assert.equal(after.lines.find((l) => l.id === "mon-2").lineTotalVnd, 128000);
  assert.equal(itemsTotalVnd(after), 963000 - 148000);
});

test("dòng thêm tay được đánh dấu là người nhập, không phải máy đọc", () => {
  const reading = readingFromWire(LIVE_SCAN);
  const after = addLine(reading, "mon-them-1");
  const added = after.lines.find((l) => l.id === "mon-them-1");
  assert.equal(isEdited(added), true);
  assert.equal(added.lineTotalVnd, 0);
  assert.equal(added.quantity, 1);
});

test("đổi tên rồi đổi lại thì không còn tính là đã sửa", () => {
  const reading = readingFromWire(LIVE_SCAN);
  const renamed = renameLine(reading, "mon-0", "Sườn nướng");
  assert.equal(editedCount(renamed), 1);
  const restored = renameLine(renamed, "mon-0", "Sườn nướng Mỹ");
  assert.equal(editedCount(restored), 0);
});

test("không có dòng nào, hoặc có dòng chưa đặt tên, thì chưa đi tiếp được", () => {
  const reading = readingFromWire(LIVE_SCAN);
  assert.equal(blockingProblem(reading), null);

  let empty = reading;
  for (const line of reading.lines) empty = removeLine(empty, line.id);
  assert.match(blockingProblem(empty), /Chưa có món nào/);

  const nameless = renameLine(reading, "mon-3", "   ");
  assert.match(blockingProblem(nameless), /Một món chưa có tên/);

  const twoNameless = renameLine(nameless, "mon-4", "");
  assert.match(blockingProblem(twoNameless), /2 món chưa có tên/);
});

test("bill không có dòng tổng cộng thì nói thẳng là không đối chiếu được", () => {
  // `null` is not agreement. Rendering it as a tick would claim a check that
  // never ran.
  const reading = readingFromWire({ ...LIVE_SCAN, total_vnd: null, total_difference_vnd: null });
  assert.equal(reading.printedTotalVnd, null);
  assert.equal(totalGapVnd(reading), null);
});

test("câu chữ hiện ra màn hình không dùng em-dash", () => {
  // The repo bans it in Vietnamese copy and there is a test for it elsewhere;
  // this module writes sentences of its own, so it owes the same check.
  const reading = readingFromWire(LIVE_SCAN);
  let empty = reading;
  for (const line of reading.lines) empty = removeLine(empty, line.id);
  const sentences = [
    blockingProblem(empty),
    blockingProblem(renameLine(reading, "mon-3", "")),
    blockingProblem(renameLine(renameLine(reading, "mon-3", ""), "mon-4", "")),
  ];
  for (const sentence of sentences) {
    assert.equal(sentence.includes("—"), false, `còn em-dash: ${sentence}`);
  }
});

/* The direction contract.
 *
 * The web build emits it into `dist/index.html` through `public/index.html`,
 * which is where a reviewer of the artifact reads it. The native build emits no
 * HTML at all, so this source copy is the one the screens are written against,
 * and this test is what keeps it from quietly ceasing to describe anything: a
 * block that goes missing fails rather than just stops being true.
 */
import { DIRECTION_CONTRACT } from "../dist-test/ui/direction.js";

test("hợp đồng thiết kế còn đủ năm khối và dòng FINISH", () => {
  for (const block of ["THESIS:", "OWN-WORLD:", "STORY:", "FIRST VIEWPORT:", "FORM:", "FINISH:"]) {
    assert.ok(DIRECTION_CONTRACT.includes(block), `thiếu khối ${block}`);
  }
  // The tone rule it commits to is the one DESIGN.md sets. If somebody makes
  // the confirm button orange again, this sentence is what they contradicted.
  assert.match(DIRECTION_CONTRACT, /teal/);
  // Impeccable caps the contract at 150 words. A contract nobody finishes
  // reading is not a contract.
  const words = DIRECTION_CONTRACT.split(/\s+/).length;
  assert.ok(words <= 150, `hợp đồng ${words} từ, quá 150 thì không ai đọc`);
});

test("không file nguồn nào chứa byte NUL", async () => {
  // Not paranoia. `addLine` once marked a hand-added row with a sentinel
  // `read.name`, and what landed in the file was a NUL rather than the space
  // that was meant. `tsc` compiled it, every other test passed, and the byte
  // travelled inside a dish name until the repo guard refused the commit.
  // Nothing in this app's source is binary, so this is cheap to assert.
  const { readdir, readFile } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const found = [];
  async function walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) await walk(path);
      else if (/\.(ts|tsx|mjs|json)$/.test(entry.name)) {
        if ((await readFile(path)).includes(0)) found.push(path);
      }
    }
  }
  await walk("src");
  await walk("tests");
  assert.deepEqual(found, []);
});
