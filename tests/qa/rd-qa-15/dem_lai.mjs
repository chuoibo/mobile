/**
 * Fold the REAL server rows with the SHIPPED counter.
 *
 * `tests/binh-chon.test.mjs` folds a hand-written array of message objects the
 * author typed. That proves the arithmetic; it does not prove the arithmetic is
 * fed the shape the real route actually returns, and it cannot notice if the
 * server credits the wrong person. This reads `tin-nhan-that.json` -- rows
 * fetched over HTTP from the real route against real Postgres -- and runs
 * `tongHopBinhChon` from `dist-test`, the same build `npm test` runs.
 *
 * Deliberately does NOT recompute the tally. Re-deriving the counts here would
 * compare two implementations of the same idea and agree with itself. It states
 * the outcome the six probe cases must produce and checks the shipped counter
 * lands on it.
 *
 * Usage: node dem_lai.mjs   (run from this directory, after probe_binh_chon.py)
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const MOBILE = join(here, "..", "..", "..", "apps", "mobile");

const { tongHopBinhChon } = await import(
  join(MOBILE, "dist-test", "screens", "chat", "binh-chon.js")
);

const data = JSON.parse(readFileSync(join(here, "tin-nhan-that.json"), "utf8"));
const { messages, ids, poll_id: pollId } = data;

console.log("=".repeat(72));
console.log(`Nap ${messages.length} tin nhan THAT tu may chu (khong phai mang go tay).`);
for (const m of messages) {
  const k = m.card?.kind ?? m.kind;
  const opt = m.card?.payload?.option_id ?? "-";
  const who =
    m.author_id === ids.an ? "An" :
    m.author_id === ids.trang ? "Trang" :
    m.author_id === ids.minh ? "Minh" : m.author_id;
  const giaMao = m.card?.payload?.author_id
    ? `  <- card CO author_id gia = ${m.card.payload.author_id === ids.trang ? "Trang" : m.card.payload.author_id}`
    : "";
  console.log(`   ${k.padEnd(10)} author_id=${who.padEnd(6)} option=${String(opt).padEnd(4)}${giaMao}`);
}

// Run the shipped counter. `luaChonCuaToi` is from Minh's device.
const ketQua = tongHopBinhChon(messages, ids.minh);
const bc = ketQua.find((k) => k.pollId === pollId);
if (!bc) {
  console.log("KET QUA: FAIL - counter khong doc duoc cuoc binh chon nao");
  process.exit(1);
}

console.log();
console.log("Counter da ship tra ve:");
for (const r of bc.ketQua) {
  console.log(`   ${r.nhan.padEnd(24)} ${String(r.phieu)} phieu  ${r.phanTram}%  ${r.dangDan ? "(dang dan)" : ""}`);
}
console.log(`   tong ${bc.tongPhieu} phieu · ${bc.soNguoiDaBoPhieu} nguoi · hoa=${bc.dangHoa} · dienDau=[${bc.dienDau}]`);
console.log(`   lua chon cua Minh (may nay) = ${bc.luaChonCuaToi}`);

const phieu = Object.fromEntries(bc.ketQua.map((r) => [r.optionId, r.phieu]));
const sumPhanTram = bc.ketQua.reduce((a, r) => a + r.phanTram, 0);

// What the six probe cases must produce:
//   Trang -> o1 (accepted).  Minh -> o3 then o2; only the later counts.
//   Minh's o3 card carried a forged author_id=Trang, which must change nothing.
//   The stranger's and the forged-field ballots never reached the database.
const kiem = [
  ["o1 duoc dung 1 phieu (Trang)", phieu.o1 === 1],
  ["o2 duoc dung 1 phieu (Minh, la phieu SAU)", phieu.o2 === 1],
  ["o3 duoc 0 phieu — phieu truoc cua Minh bi thay", phieu.o3 === 0],
  ["tong 2 phieu, 2 nguoi — khong ai bo phieu ho ai", bc.tongPhieu === 2 && bc.soNguoiDaBoPhieu === 2],
  ["card gia KHONG cong phieu cho Trang", phieu.o1 === 1],
  ["HOA duoc bao la hoa", bc.dangHoa === true],
  ["hoa thi KHONG trao vuong mien cho mot ai", bc.dienDau.length === 2],
  ["Sigma phan tram = 100 dung", sumPhanTram === 100],
  ["may cua Minh thay dung lua chon cua Minh = o2", bc.luaChonCuaToi === "o2"],
];

console.log();
let hong = 0;
for (const [ten, ok] of kiem) {
  if (!ok) hong++;
  console.log(`   ${ok ? "dat " : "HONG"}  ${ten}`);
}
console.log("=".repeat(72));
if (hong) {
  console.log(`KET QUA: FAIL - ${hong}/${kiem.length} ca hong`);
  process.exit(1);
}
console.log(`KET QUA: PASS - ${kiem.length}/${kiem.length} ca dat`);
