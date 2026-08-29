/**
 * Feed malformed ballot cards to the SHIPPED counter and check the chat screen
 * survives them.
 *
 * Case C in `probe_binh_chon.py` proved the server stores `card` as a free-form
 * dict without validating it. So these shapes are reachable in production, not
 * hypotheticals: an older client, a half-written AI card, a hand-rolled POST.
 *
 * Why one bad row is a whole-screen problem: `TinNhan.tsx:89` calls
 * `tongHopBinhChon(messages, ...)` ONCE for the entire thread, during render.
 * A throw there is not a broken bubble -- it is a blank chat screen, and the
 * Plan tab that reads the same array goes with it.
 *
 * Exit 0 = every shape survived. Exit 1 = at least one threw or mis-tallied.
 */

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const MOBILE = join(here, "..", "..", "..", "apps", "mobile");
const { tongHopBinhChon } = await import(
  join(MOBILE, "dist-test", "screens", "chat", "binh-chon.js")
);

// Letters on purpose: an all-digit UUID is 32 consecutive digits, which the
// repo guard's long-number rule blocks (it cannot tell a placeholder id from a
// bank account number, and it is right to fail closed).
const AN = "aaaaaaaa-1111-4aaa-8aaa-aaaaaaaaaaaa";
const TRANG = "bbbbbbbb-2222-4bbb-8bbb-bbbbbbbbbbbb";

/** A well-formed poll, so each junk row is judged next to a real one. */
const pollTot = {
  id: "m-poll", kind: "ai_card", author_id: AN, body: "Toi nay an o dau?",
  created_at: "2030-08-27T12:00:00Z",
  card: {
    kind: "poll",
    payload: {
      poll_id: "p1", question: "Toi nay an o dau?",
      options: [{ option_id: "o1", label: "Tiem nuong" },
                { option_id: "o2", label: "Lau ga" }],
    },
  },
};

const phieuTot = {
  id: "m-v1", kind: "ai_card", author_id: TRANG, body: "phieu",
  created_at: "2030-08-27T12:00:01Z",
  card: { kind: "poll_vote", payload: { poll_id: "p1", option_id: "o1" } },
};

const xau = (id, card, ghi) => ({
  ten: ghi,
  tin: { id, kind: "ai_card", author_id: TRANG, body: "x",
         created_at: "2030-08-27T12:00:02Z", card },
});

const CA = [
  xau("b1", null, "card = null"),
  xau("b2", undefined, "card = undefined"),
  xau("b3", {}, "card = {} (thieu kind va payload)"),
  xau("b4", { kind: "poll_vote" }, "poll_vote thieu han payload"),
  xau("b5", { kind: "poll_vote", payload: null }, "payload = null"),
  xau("b6", { kind: "poll_vote", payload: {} }, "payload rong"),
  xau("b7", { kind: "poll_vote", payload: { poll_id: "p1" } }, "thieu option_id"),
  xau("b8", { kind: "poll_vote", payload: { option_id: "o1" } }, "thieu poll_id"),
  // b9 moved out of this matrix: it is the ONE shape that changes the tally
  // rather than being ignored, so it gets its own scenario below where the
  // right expectation can be stated instead of lumped in with "must not throw".
  xau("b10", { kind: "poll_vote", payload: { poll_id: "KHONG-CO", option_id: "o1" } },
      "poll_id tro toi poll khong ton tai"),
  xau("b11", { kind: "poll", payload: { poll_id: "p2", question: "?", options: [] } },
      "poll KHONG co lua chon nao (chia 0)"),
  xau("b12", { kind: "poll", payload: { poll_id: "p3", question: "?", options: null } },
      "options = null"),
  xau("b13", { kind: "poll_vote", payload: { poll_id: "p1", option_id: 42 } },
      "option_id la so, khong phai chuoi"),
  xau("b14", { kind: "poll_vote", payload: [1, 2, 3] }, "payload la mang"),
  xau("b15", { kind: "poll", payload: { poll_id: "p1", question: "CUOP POLL",
       options: [{ option_id: "x", label: "cuop" }] } },
      "poll thu hai cung poll_id (cuop lua chon)"),
];

console.log(`   ${CA.length} hinh dang the xau, moi cai tha vao mot luong CO poll that`);

let hong = 0;
for (const { ten, tin } of CA) {
  const luong = [pollTot, phieuTot, tin];
  let ketQua;
  try {
    ketQua = tongHopBinhChon(luong, TRANG);
  } catch (e) {
    console.log(`   NEM   ${ten}  -> ${e && e.message}`);
    hong += 1;
    continue;
  }
  if (!Array.isArray(ketQua)) {
    console.log(`   HONG  ${ten}  -> khong tra ve mang`);
    hong += 1;
    continue;
  }
  const p1 = ketQua.find((k) => k.pollId === "p1");
  if (!p1) {
    console.log(`   HONG  ${ten}  -> poll that BIEN MAT khoi ket qua`);
    hong += 1;
    continue;
  }
  // The real vote from Trang must survive next to the junk row, and no junk
  // row may invent a ballot. Exactly one vote is correct here.
  if (p1.tongPhieu !== 1) {
    console.log(`   HONG  ${ten}  -> tongPhieu=${p1.tongPhieu}, doi 1`);
    hong += 1;
    continue;
  }
  const tongPhanTram = p1.ketQua.reduce((s, l) => s + (l.phanTram ?? 0), 0);
  if (p1.tongPhieu > 0 && Math.abs(tongPhanTram - 100) > 1) {
    console.log(`   HONG  ${ten}  -> Sigma phan tram = ${tongPhanTram}, doi 100`);
    hong += 1;
    continue;
  }
  console.log(`   dat   ${ten}`);
}

// A thread made only of junk, no real poll at all.
try {
  const r = tongHopBinhChon(CA.map((c) => c.tin), TRANG);
  console.log(`   dat   luong TOAN the xau -> tra ve mang ${r.length} muc, khong nem`);
} catch (e) {
  console.log(`   NEM   luong TOAN the xau -> ${e && e.message}`);
  hong += 1;
}

// ---------------------------------------------------------------------------
// The one shape that MOVES the count: a ballot for an option_id that is not in
// the poll. "Last write wins" keys on author_id, so such a ballot lands in the
// map and then counts for nothing -- it ERASES that person's earlier valid
// vote. Severity turns entirely on WHOSE vote can be erased, so measure both.
// ---------------------------------------------------------------------------
console.log();
console.log("   Phieu tro toi option_id KHONG thuoc poll — xoa phieu cua AI?");

const rac = (author, id) => ({
  id, kind: "ai_card", author_id: author, body: "x",
  created_at: "2030-08-27T12:00:03Z",
  card: { kind: "poll_vote", payload: { poll_id: "p1", option_id: "KHONG-CO" } },
});

// (a) Trang sends the junk ballot herself, after her own valid vote.
const tuXoa = tongHopBinhChon([pollTot, phieuTot, rac(TRANG, "r1")], TRANG)
  .find((k) => k.pollId === "p1");
console.log(`   tu minh gui   -> tongPhieu=${tuXoa.tongPhieu} (phieu o1 cua chinh Trang bien mat)`);

// (b) An sends the junk ballot. Trang's vote must be untouched: author_id is
//     written by the server from the actor header and cannot be forged
//     (probe_binh_chon.py case B rejected it 422, case C could not move it).
const nguoiKhac = tongHopBinhChon([pollTot, phieuTot, rac(AN, "r2")], TRANG)
  .find((k) => k.pollId === "p1");
const anToan = nguoiKhac.tongPhieu === 1;
console.log(`   nguoi KHAC gui -> tongPhieu=${nguoiKhac.tongPhieu}, phieu cua Trang ${anToan ? "CON NGUYEN" : "BI XOA"}`);
console.log(`   ${anToan ? "dat " : "HONG"}  khong ai xoa duoc phieu cua NGUOI KHAC`);
if (!anToan) hong += 1;
console.log("   ghi   tu xoa phieu CUA CHINH MINH: ghi nhan, khong chan merge");
console.log("         (nguoi dung von da doi duoc phieu cua chinh minh)");

// Degenerate inputs the screen can genuinely hand over on first paint.
for (const [ten, arg] of [["mang rong", []], ["null", null], ["undefined", undefined]]) {
  try {
    const r = tongHopBinhChon(arg, null);
    console.log(`   dat   messages = ${ten} -> ${Array.isArray(r) ? `mang ${r.length}` : typeof r}`);
  } catch (e) {
    // null/undefined are not shapes the screen actually passes (state is
    // seeded to []), so record it but do not fail the gate on it.
    const chetNguoi = ten === "mang rong";
    console.log(`   ${chetNguoi ? "NEM " : "ghi "}  messages = ${ten} -> ${e && e.message}`);
    if (chetNguoi) hong += 1;
  }
}

console.log(`   => ${hong === 0 ? "khong hinh dang nao lam vo man chat" : `${hong} hinh dang LAM VO`}`);
process.exit(hong === 0 ? 0 : 1);
