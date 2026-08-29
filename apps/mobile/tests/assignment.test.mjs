/** Who ate which line — identity and attribution, never a split.
 *
 * The numbers this module touches are copies of `lineTotalVnd`. Dividing them
 * between people is the allocator's job, and a second implementation here is
 * how two screens end up showing two totals for one dinner.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  addPersonToAll,
  alignToRoster,
  blockingProblem,
  countOn,
  dropPerson,
  everyoneShares,
  isOn,
  itemsForWire,
  signature,
  syncLines,
  toggle,
} from "../dist-test/assignment.js";
import { itemsTotalVnd } from "../dist-test/receipt.js";

const HA = "ha";
const NAM = "nam";
const QUYEN = "quyen";

function line(id, name, amount) {
  return {
    id,
    name,
    quantity: 1,
    lineTotalVnd: amount,
    read: { name, quantity: 1, lineTotalVnd: amount },
  };
}

function readingOf(lines, extras = {}) {
  return {
    lines,
    printedTotalVnd: null,
    confidence: 92,
    warnings: [],
    ...extras,
  };
}

const SUON = line("mon-0", "Sườn nướng Mỹ", 219000);
const BA_CHI = line("mon-1", "Ba chỉ heo", 148000);
const TWO = readingOf([SUON, BA_CHI]);

test("everyoneShares cho mọi người vào mọi món", () => {
  const a = everyoneShares(TWO.lines, [HA, NAM]);
  assert.deepEqual(a["mon-0"], [HA, NAM]);
  assert.deepEqual(a["mon-1"], [HA, NAM]);
  assert.equal(isOn(a, "mon-0", HA), true);
  assert.equal(countOn(a, "mon-0"), 2);
});

test("toggle bật tắt một ô, không đụng món khác, và không sửa bản gốc", () => {
  const before = everyoneShares(TWO.lines, [HA, NAM]);
  const frozen = JSON.stringify(before);

  const off = toggle(before, "mon-0", NAM);
  assert.equal(isOn(off, "mon-0", NAM), false);
  assert.equal(isOn(off, "mon-0", HA), true);
  assert.equal(isOn(off, "mon-1", NAM), true, "món khác bị kéo theo");
  assert.equal(JSON.stringify(before), frozen, "toggle sửa tại chỗ");

  const back = toggle(off, "mon-0", NAM);
  assert.equal(isOn(back, "mon-0", NAM), true);
  assert.notEqual(off, before);
  assert.notEqual(back, off);
});

test("dropPerson xoá người khỏi mọi món, nếu không máy chủ trả UNKNOWN_PARTICIPANT", () => {
  const a = dropPerson(everyoneShares(TWO.lines, [HA, NAM, QUYEN]), NAM);
  assert.deepEqual(a["mon-0"], [HA, QUYEN]);
  assert.deepEqual(a["mon-1"], [HA, QUYEN]);
  assert.equal(isOn(a, "mon-0", NAM), false);
  assert.equal(isOn(a, "mon-1", NAM), false);
});

test("syncLines: món mới thì cả nhóm ăn, món xoá thì rời, gọi hai lần như nhau", () => {
  const people = [HA, NAM];
  const start = everyoneShares([SUON], people);
  const onlyNam = toggle(start, "mon-0", HA);

  const pepsi = line("mon-2", "Pepsi", 28000);
  const grown = readingOf([SUON, pepsi]);
  const once = syncLines(onlyNam, grown.lines, people);
  const twice = syncLines(once, grown.lines, people);

  assert.deepEqual(once["mon-0"], [NAM], "món cũ không bị reset");
  assert.deepEqual(once["mon-2"], [HA, NAM], "món mới phải cả nhóm");
  assert.equal(once["mon-1"], undefined);
  assert.deepEqual(once, twice);

  const shrunk = syncLines(once, [SUON], people);
  assert.equal(shrunk["mon-2"], undefined, "món xoá vẫn còn trong assignment");
  assert.deepEqual(shrunk["mon-0"], [NAM]);
});

test("addPersonToAll mặc định người mới ăn chung mọi món", () => {
  const a = addPersonToAll(everyoneShares(TWO.lines, [HA]), ["mon-0", "mon-1"], NAM);
  assert.equal(isOn(a, "mon-0", NAM), true);
  assert.equal(isOn(a, "mon-1", NAM), true);
  const again = addPersonToAll(a, ["mon-0", "mon-1"], NAM);
  assert.equal(countOn(again, "mon-0"), 2, "thêm hai lần thì trùng shared_by");
});

test("cùng nội dung khác thứ tự thì cùng chữ ký; đổi một ô tích thì khác", () => {
  const people = [HA, NAM];
  const a = everyoneShares(TWO.lines, people);
  const shuffledPeople = [NAM, HA];
  const shuffledLines = readingOf([BA_CHI, SUON]);
  const toggledOrder = toggle(toggle(everyoneShares(TWO.lines, people), "mon-0", HA), "mon-0", HA);

  assert.equal(signature(TWO, people, a), signature(shuffledLines, shuffledPeople, a));
  assert.equal(signature(TWO, people, a), signature(TWO, people, toggledOrder));

  const oneOff = toggle(a, "mon-1", HA);
  assert.notEqual(signature(TWO, people, a), signature(TWO, people, oneOff));
});

test("itemsForWire copy nguyên lineTotalVnd, tổng bằng itemsTotalVnd", () => {
  const a = everyoneShares(TWO.lines, [NAM, HA]);
  const items = itemsForWire(TWO, a);
  assert.equal(items.length, 2);
  assert.equal(items[0].item_id, "mon-0");
  assert.equal(items[0].label, "Sườn nướng Mỹ");
  assert.equal(items[0].amount_vnd, SUON.lineTotalVnd);
  assert.equal(items[1].amount_vnd, BA_CHI.lineTotalVnd);
  const sum = items.reduce((n, item) => n + item.amount_vnd, 0);
  assert.equal(sum, itemsTotalVnd(TWO));
  // Canonical order, not tick order. The preview reuses one idempotency key
  // per signature, so the same set of ticks must serialise identically.
  assert.deepEqual(items[0].shared_by, [HA, NAM]);
});

test("blockingProblem: nhóm rỗng, món không ai nhận, món 0đ, hợp lệ thì null", () => {
  const people = [HA, NAM];
  const ok = everyoneShares(TWO.lines, people);
  assert.equal(blockingProblem(TWO, people, ok), null);

  assert.equal(
    blockingProblem(TWO, [], ok),
    "Chưa có ai trong nhóm. Thêm người bằng nút + ở trên.",
  );

  const orphan = toggle(toggle(ok, "mon-0", HA), "mon-0", NAM);
  const orphaned = blockingProblem(TWO, people, orphan);
  assert.match(orphaned, /Sườn nướng Mỹ/);
  assert.match(orphaned, /chưa ai nhận/);

  const twoOrphans = toggle(toggle(orphan, "mon-1", HA), "mon-1", NAM);
  const counted = blockingProblem(TWO, people, twoOrphans);
  assert.match(counted, /2 món/);
  assert.match(counted, /chưa ai nhận/);

  const free = readingOf([line("mon-0", "Pepsi", 0), BA_CHI]);
  const zeroed = blockingProblem(free, people, everyoneShares(free.lines, people));
  assert.match(zeroed, /Pepsi/);
  assert.match(zeroed, /0đ/);
  assert.match(zeroed, /màn trước/);

  const nameless = readingOf([line("mon-0", "   ", 1000), BA_CHI]);
  const named = blockingProblem(nameless, people, everyoneShares(nameless.lines, people));
  assert.match(named, /chưa có tên/);
});

test("câu chữ chặn không dùng em-dash", () => {
  const people = [HA, NAM];
  const ok = everyoneShares(TWO.lines, people);
  const orphan = toggle(toggle(ok, "mon-0", HA), "mon-0", NAM);
  const free = readingOf([line("mon-0", "Pepsi", 0)]);
  const nameless = readingOf([line("mon-0", "", 1000)]);
  for (const sentence of [
    blockingProblem(TWO, [], ok),
    blockingProblem(TWO, people, orphan),
    blockingProblem(free, people, everyoneShares(free.lines, people)),
    blockingProblem(nameless, people, everyoneShares(nameless.lines, people)),
  ]) {
    assert.equal(sentence.includes("—"), false, `còn em-dash: ${sentence}`);
  }
});

test("assignment.ts không chứa phép chia tiền", () => {
  const source = readFileSync(new URL("../src/assignment.ts", import.meta.url), "utf8");
  const body = source.slice(source.indexOf("*/") + 2);
  for (const banned of ["Math.floor", "Math.ceil", "Math.round"]) {
    assert.ok(!body.includes(banned), `assignment.ts still uses ${banned}`);
  }
  // Imports mention "./receipt"; comments and strings may mention a path.
  // After those are gone, a leftover "/" is division, and division on this
  // file is a second allocator.
  const stripped = body
    .replace(/from "[^"]+"/g, "from \"\"")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/`[\s\S]*?`/g, "``")
    .replace(/"[^"]*"/g, "\"\"")
    .replace(/'[^']*'/g, "''");
  assert.equal(stripped.includes("/"), false, `còn dấu chia trên đường tiền:\n${stripped}`);
});

/* Aligning the matrix to the roster must not undo the person's work.
 *
 * The first version of this ran `addPersonToAll` over every participant, so
 * every cleared box was re-ticked at the moment the expense was proposed. The
 * screen had already shown a preview of the matrix as built; the allocator
 * then received "everyone shares everything" and answered with different
 * numbers. A split that changes between looking and confirming is the exact
 * failure `expected_allocations` exists to catch, and here the app would have
 * been the one causing it.
 */
test("alignToRoster giữ nguyên ô người dùng đã bỏ tích", () => {
  const lines = [SUON, BA_CHI];
  const people = [HA, NAM];
  let a = everyoneShares(lines, people);
  a = toggle(a, "mon-0", NAM); // Nam khong an suon
  const aligned = alignToRoster(a, lines, people);

  assert.deepEqual(aligned["mon-0"], [HA], "o da bo tich bi tich lai");
  assert.equal(isOn(aligned, "mon-0", NAM), false);
  assert.equal(isOn(aligned, "mon-1", NAM), true);
});

test("alignToRoster bỏ người không còn trong nhóm", () => {
  const lines = [SUON, BA_CHI];
  let a = everyoneShares(lines, [HA, NAM, QUYEN]);
  const aligned = alignToRoster(a, lines, [HA, NAM]);
  for (const lineId of ["mon-0", "mon-1"]) {
    assert.equal(aligned[lineId].includes(QUYEN), false, "UNKNOWN_PARTICIPANT");
  }
});

test("alignToRoster cho người mới thêm ăn chung mọi món", () => {
  const lines = [SUON, BA_CHI];
  const a = everyoneShares(lines, [HA]);
  const aligned = alignToRoster(a, lines, [HA, QUYEN]);
  assert.equal(isOn(aligned, "mon-0", QUYEN), true);
  assert.equal(isOn(aligned, "mon-1", QUYEN), true);
});

test("alignToRoster không đổi gì khi gọi lại lần nữa", () => {
  const lines = [SUON, BA_CHI];
  const people = [HA, NAM];
  let a = everyoneShares(lines, people);
  a = toggle(a, "mon-1", HA);
  const once = alignToRoster(a, lines, people);
  assert.deepEqual(alignToRoster(once, lines, people), once);
});
