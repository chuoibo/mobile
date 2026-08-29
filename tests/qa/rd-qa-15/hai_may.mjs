/**
 * Fold the rows machine A actually received, with the shipped counter, through
 * the same reversal the screen applies. This is what A's screen would draw.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const MOBILE = join(here, "..", "..", "..", "apps", "mobile");
const { tongHopBinhChon } = await import(join(MOBILE, "dist-test/screens/chat/binh-chon.js"));
const { tinHienThiLanDau } = await import(join(MOBILE, "dist-test/screens/chat/tin-nhan.js"));

const { messages, ids, poll_id: pollId } = JSON.parse(
  readFileSync(join(here, "hai-may-rows.json"), "utf8"),
);

// A's screen holds the page oldest-first; the raw route pages newest-first.
const bc = tongHopBinhChon(tinHienThiLanDau(messages), ids.an).find((k) => k.pollId === pollId);

let hong = 0;
const check = (ok, ten) => { console.log(`   ${ok ? "dat " : "HONG"}  ${ten}`); if (!ok) hong += 1; };

if (!bc) {
  console.log("   HONG  man hinh A khong dung duoc cuoc binh chon nao");
  process.exit(1);
}

const o2 = bc.ketQua.find((l) => l.optionId === "o2");
const o1 = bc.ketQua.find((l) => l.optionId === "o1");
console.log(`   A thay: ${bc.ketQua.map((l) => `${l.nhan}=${l.phieu}`).join("  ")}`);
console.log(`   tong ${bc.tongPhieu} phieu · ${bc.soNguoiDaBoPhieu} nguoi · dienDau=[${bc.dienDau}]`);

check(o2?.phieu === 1, "la phieu cua B (o2) hien tren man hinh A = 1");
check(o1?.phieu === 0, "o1 khong co phieu nao");
check(bc.tongPhieu === 1 && bc.soNguoiDaBoPhieu === 1, "dung 1 phieu cua dung 1 nguoi");
check(bc.dienDau.length === 1 && bc.dienDau[0] === "o2", "o2 dan mot minh");
// A opened the poll but has not voted. A's own device must not show a choice.
check(bc.luaChonCuaToi === null, "may A chua bo phieu -> luaChonCuaToi = null");

process.exit(hong === 0 ? 0 : 1);
