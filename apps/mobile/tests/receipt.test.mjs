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
 *
 * One field is not verbatim and has to be called out. The capture predates
 * ADR-0009 decision 4, so it carried a `confidence` the route no longer sends;
 * `needs_review: true` stands in its place, which is what the current route
 * answers for a bill whose lines disagree with its printed total. Whether the
 * key set as a whole is still the server's is not taken on trust here -- it is
 * read out of `schemas.py` and compared, by `serverScanFields` below.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  addLine,
  blockingProblem,
  disclosure,
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

const PACKAGE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const REPO_ROOT = dirname(dirname(PACKAGE_ROOT));
const SCHEMAS = join(REPO_ROOT, "services/api/app/api/schemas.py");
const SRC = join(PACKAGE_ROOT, "src");

/**
 * The field names `ReceiptScanResponse` declares, read out of the server itself.
 *
 * This is the part of the file that is not allowed to be a fixture. Every other
 * assertion here compares our code against numbers a person typed into this
 * file, and a hand-typed wire body can only ever agree with the hand-typed
 * expectation next to it -- which is exactly how `confidence: 98` sat in the
 * fixture below, got asserted back as 98, and kept 127 tests green while the
 * server had already removed the field. So the contract comes from
 * `schemas.py`, and the fixture is checked against it rather than against
 * itself. Parse the class body after its docstring; prose indented four spaces
 * otherwise reads as a field declaration.
 */
function serverScanFields() {
  const source = readFileSync(SCHEMAS, "utf8");
  const start = source.indexOf("class ReceiptScanResponse(ApiModel):");
  assert.notEqual(start, -1, "không tìm thấy ReceiptScanResponse trong schemas.py");
  const rest = source.slice(start);
  const end = rest.indexOf("\nclass ", 1);
  const body = end === -1 ? rest : rest.slice(0, end);
  const docOpen = body.indexOf('"""');
  const declarations =
    docOpen === -1 ? body : body.slice(body.indexOf('"""', docOpen + 3) + 3);
  const fields = [];
  for (const line of declarations.split("\n")) {
    const match = /^ {4}([a-z_][a-z0-9_]*)\s*:\s*\S/.exec(line);
    if (match) fields.push(match[1]);
  }
  assert.equal(fields.length > 0, true, "không đọc được trường nào của ReceiptScanResponse");
  return fields;
}

/** Every component in the app, including the ones nested a directory down. */
function renderedSources(dir = SRC) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...renderedSources(path));
    else if (entry.name.endsWith(".tsx")) {
      found.push({ name: entry.name, source: readFileSync(path, "utf8") });
    }
  }
  return found;
}

/** Style properties whose value is a fraction of the parent box, not a claim.
 *
 * Kept as an allow-list rather than inferred from the shape `prop: `…%``,
 * because the shape alone would also excuse `label: `${pct}%``, which is
 * exactly the thing being banned. A style property missing from this list
 * costs a false positive -- loud, and fixed by adding a word. Inferring from
 * shape would cost a false negative, which is silent.
 */
const LAYOUT_PROPS = [
  "left",
  "top",
  "right",
  "bottom",
  "width",
  "height",
  "maxWidth",
  "minWidth",
  "maxHeight",
  "minHeight",
  "flexBasis",
  "lineHeight",
  "fontSize",
  "borderRadius",
  "translateX",
  "translateY",
].join("|");

const CSS_PERCENT = new RegExp(`\\b(?:${LAYOUT_PROPS})\\s*:\\s*\`[^\`]*\``, "g");

/** Does this source tell the user a percentage the machine computed?
 *
 * `}` immediately followed by `%` is a computed value with a percent sign
 * after it, whatever the field ends up being called -- that bluntness is why
 * the check survives a rename of `confidence`. But two characters cannot tell
 * apart the two things that produce them:
 *
 *   <Text>AI suggested {reading.confidence}%</Text>   the machine rating itself
 *   left: `${x}%`                                     a map pin at 40% of a box
 *
 * The first is the defect this gate exists for. The second is DaiBanDo.tsx
 * placing pins, and it was failing this gate until the CSS values were taken
 * out of the picture first. A gate that cries wolf over layout code gets
 * deleted, and then it stops catching the pill too.
 */
function saysAPercentToTheUser(source) {
  return /\}\s*%/.test(source.replace(CSS_PERCENT, ""));
}

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
  needs_review: true,
  warnings: ["Tổng in trên bill chênh +162000 đồng so với tổng các dòng; giữ nguyên cả hai số."],
};

test("một phản hồi thật trở thành tám dòng sửa được", () => {
  const reading = readingFromWire(LIVE_SCAN);
  assert.equal(reading.lines.length, 8);
  assert.equal(reading.printedTotalVnd, 1125000);
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
import { DIRECTION_CONTRACT, DIRECTION_CONTRACT_GOI_Y } from "../dist-test/ui/direction.js";

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

test("hợp đồng màn gợi ý chia còn đủ năm khối và dòng FINISH", () => {
  for (const block of ["THESIS:", "OWN-WORLD:", "STORY:", "FIRST VIEWPORT:", "FORM:", "FINISH:"]) {
    assert.ok(DIRECTION_CONTRACT_GOI_Y.includes(block), `thiếu khối ${block}`);
  }
  assert.match(DIRECTION_CONTRACT_GOI_Y, /teal/);
  const words = DIRECTION_CONTRACT_GOI_Y.split(/\s+/).length;
  assert.ok(words <= 150, `hợp đồng gợi ý ${words} từ, quá 150 thì không ai đọc`);
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

/* -------------------------------------------------- hợp đồng /receipts/scan */

/* The four tests below exist because a green suite is not evidence that the
 * client and the server agree. `POST /receipts/scan` has never sent
 * `confidence`; ADR-0009 decision 4 refused it on the grounds that a
 * percentage invites an interface to auto-accept above a threshold. The client
 * declared the field anyway, cast the response to that lie without checking,
 * read `undefined` out of it, and rendered "AI suggested %" on top of a table
 * of real money -- a machine endorsement of numbers no machine had endorsed.
 *
 * What let it live for two pull requests was this file: the fixture supplied
 * `confidence: 98` and the test asserted 98 back. So these tests are pointed
 * at the two places the old ones were not -- the server's own declaration, and
 * the screens' own source. */

test("fixture khớp đúng hợp đồng máy chủ, và hợp đồng đó không có confidence", () => {
  const fields = serverScanFields();
  assert.equal(
    fields.includes("confidence"),
    false,
    "ReceiptScanResponse mọc lại confidence: ADR-0009 quyết định 4 từ chối trường này",
  );
  assert.equal(fields.includes("needs_review"), true);
  // Both directions. A missing field is how `needs_review` got dropped on the
  // floor; an extra one is how `confidence` got invented.
  assert.deepEqual([...Object.keys(LIVE_SCAN)].sort(), [...fields].sort());
});

test("reading mang theo needs_review, và không mang theo confidence", () => {
  const reading = readingFromWire(LIVE_SCAN);
  assert.equal(reading.needsReview, true);
  assert.equal("confidence" in reading, false);
});

test("thiếu needs_review thì rơi về phía phải kiểm lại, không phải phía yên tâm", () => {
  // The response is cast, not parsed, so a body missing the field reaches this
  // function as `undefined`. `undefined` is falsy, and the falsy branch is the
  // reassuring one -- which would turn a broken contract into a calm screen.
  const { needs_review: _dropped, ...missing } = LIVE_SCAN;
  assert.equal(readingFromWire(missing).needsReview, true);
});

test("dòng công bố không có phần trăm ở bất kỳ nhánh nào", () => {
  const flagged = readingFromWire({ ...LIVE_SCAN, needs_review: true });
  assert.deepEqual(disclosure(flagged), { tone: "review", text: "Cần bạn kiểm lại" });

  // `needs_review: false` means "không tín hiệu nào nổ", not "số này đúng", so
  // the calm branch is allowed to count and nothing else.
  const calm = readingFromWire({ ...LIVE_SCAN, needs_review: false });
  assert.deepEqual(disclosure(calm), { tone: "neutral", text: "Đã nhận diện 8 món" });

  // A row somebody typed was not recognised by anything, so it must not be
  // counted as though it had been.
  const withHandAdded = addLine(calm, "them-1");
  assert.equal(disclosure(withHandAdded).text, "Đã nhận diện 8 món");
  const fewer = removeLine(calm, "mon-0");
  assert.equal(disclosure(fewer).text, "Đã nhận diện 7 món");

  for (const reading of [flagged, calm, withHandAdded, fewer]) {
    assert.equal(disclosure(reading).text.includes("%"), false);
  }
});

test("không thành phần nào đọc .confidence hay in ra một phần trăm", () => {
  // The pure functions above can all be green while a component still renders
  // the percentage, because none of them render anything. This is the
  // assertion that would have gone red on the actual defect.
  //
  // The third pattern is the one that generalises; `saysAPercentToTheUser`
  // carries it, along with the reason it cannot be applied to raw source.
  const sources = renderedSources();
  assert.equal(sources.length > 0, true, "không quét được file .tsx nào");
  for (const { name, source } of sources) {
    assert.equal(/\.confidence\b/.test(source), false, `${name} vẫn đọc .confidence`);
    assert.equal(/AI suggested/.test(source), false, `${name} vẫn in nhãn "AI suggested"`);
    assert.equal(
      saysAPercentToTheUser(source),
      false,
      `${name} vẫn in một phần trăm tính ra từ dữ liệu`,
    );
  }
});

test("cổng phân biệt phần trăm nói với người dùng và phần trăm toạ độ CSS", () => {
  // Both halves are load-bearing. Only asserting the first would let the gate
  // be "fixed" by deleting it; only asserting the second would let it be
  // "fixed" by matching nothing at all.
  const pill = "<Text>AI suggested {reading.confidence}%</Text>";
  assert.equal(saysAPercentToTheUser(pill), true, "cổng phải bắt được pill thật");

  // Renaming the field must not buy a way through, which is why the pattern
  // keys on the shape and not on the word `confidence`.
  const renamed = "<Text>{Math.round(r.doTinCay * 100)}% khớp</Text>";
  assert.equal(saysAPercentToTheUser(renamed), true, "đổi tên trường không được lách cổng");

  // DaiBanDo.tsx, verbatim in shape: a pin at a fraction of its parent box.
  // Two characters identical to the pill, and no claim about data at all.
  const toaDo = "style={{ position: 'absolute', left: `${x}%`, top: `${y}%` }}";
  assert.equal(saysAPercentToTheUser(toaDo), false, "toạ độ CSS không phải lời khẳng định");

  // A percentage built into a label is a claim wearing a style property's
  // clothes, so the allow-list is by property name and not by shape.
  const nhan = "label: `${pct}%`";
  assert.equal(saysAPercentToTheUser(nhan), true, "phần trăm trong nhãn vẫn là lời khẳng định");
});
