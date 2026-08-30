/** What these check, and what they deliberately do not.
 *
 * `ket-qua.ts` is the only place the server-backed vote screen is allowed to
 * turn a wire object into something drawable, so it is the only place a
 * fallback could quietly break a tie. These check that it does not: that the
 * winner comes from `decided_option_id` alone, that a tie names every side,
 * that an empty vote produces no NaN and no leader, and that the ballot's own
 * order survives.
 *
 * They do NOT check that the server tallies correctly, that a second member's
 * ballot lands, or that a non-member is refused. Those are HTTP facts and a
 * literal below cannot prove one of them -- `tests/postgres` and the live
 * layer are where that has to happen. Nor do they check that the screen
 * DRAWS any of this; `BinhChon.tsx` is where that could still go wrong, and
 * only a render can see it.
 */
import test from "node:test";
import assert from "node:assert/strict";

import { bangKetQuaTuWire } from "../dist-test/screens/binh-chon/ket-qua.js";

// Letters, not digits. An all-numeric uuid strips to 32 consecutive digits and
// the repo guard reads that as an account number -- the same `long-number` rule
// that blocks a real one. `binh-chon.test.mjs` spells its ids this way too.
const LAU = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const NUONG = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const CHAY = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

/** A vote with three options, tallies supplied by the caller. Everything the
 *  domain decides -- leading, tie, decided -- is passed in rather than derived
 *  here, because deriving it in the fixture would test the fixture. */
function cuoc({ phieu, leading, laHoa, chot, phieuCuaToi = null, daDong = true }) {
  return {
    id: "vote-1",
    context_id: "ctx-1",
    outing_id: null,
    created_by_id: "nguoi-mo",
    question: "Tối nay ăn gì?",
    created_at: "2026-08-30T12:00:00Z",
    closed_at: daDong ? "2026-08-30T13:00:00Z" : null,
    is_closed: daDong,
    options: [
      { id: LAU, position: 0, label: "Lẩu", place_name: "Quán Lẩu Cô Ba", ballot_count: phieu[0] },
      { id: NUONG, position: 1, label: "Nướng", place_name: null, ballot_count: phieu[1] },
      { id: CHAY, position: 2, label: "Chay", place_name: null, ballot_count: phieu[2] },
    ],
    total_ballots: phieu[0] + phieu[1] + phieu[2],
    leading_option_ids: leading,
    is_tie: laHoa,
    decided_option_id: chot,
    my_option_id: phieuCuaToi,
  };
}

test("hoà: không có bên nào được chọn, và cả hai bên bằng phiếu đều được gọi tên", () => {
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [2, 2, 0], leading: [LAU, NUONG], laHoa: true, chot: null }),
  );

  assert.equal(bang.laHoa, true);
  // The whole point. A tie has no winner, and the first of the leading list is
  // not a winner wearing a different name.
  assert.equal(bang.optionIdThang, null);
  assert.deepEqual(bang.tenCacBenHoa, ["Lẩu", "Nướng"]);
});

test("hoà ba bên: không bên nào bị bỏ khỏi danh sách cho gọn", () => {
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [1, 1, 1], leading: [LAU, NUONG, CHAY], laHoa: true, chot: null }),
  );

  assert.deepEqual(bang.tenCacBenHoa, ["Lẩu", "Nướng", "Chay"]);
  assert.equal(bang.optionIdThang, null);
});

test("các bên hoà được gọi tên theo thứ tự lá phiếu, không theo thứ tự máy chủ gửi", () => {
  // Server emits the leading ids in the other order. The ballot the group read
  // had Lẩu first, so the card must too.
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [2, 2, 0], leading: [NUONG, LAU], laHoa: true, chot: null }),
  );

  assert.deepEqual(bang.tenCacBenHoa, ["Lẩu", "Nướng"]);
});

test("hoà đọc từ is_tie, không đếm lại độ dài danh sách dẫn đầu", () => {
  // Today the server computes `is_tie = len(leading_option_ids) > 1`
  // (`domain/vote.py`), so on any real payload the two agree and a mutant that
  // recomputes it here passes every other test in this file. That is exactly
  // why this case is written by hand: the rule `ket-qua.ts` states is "read the
  // field", and a client holding a second definition of a tie is a second
  // definition that can drift the day the server's changes. The wire below
  // could not come off today's server, and that is the point.
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [2, 2, 0], leading: [LAU, NUONG], laHoa: false, chot: null }),
  );
  assert.equal(bang.laHoa, false);
  assert.deepEqual(bang.tenCacBenHoa, []);

  const nguoc = bangKetQuaTuWire(
    cuoc({ phieu: [3, 1, 0], leading: [LAU], laHoa: true, chot: null }),
  );
  assert.equal(nguoc.laHoa, true);
  assert.deepEqual(nguoc.tenCacBenHoa, ["Lẩu"]);
});

test("có người thắng: lấy đúng decided_option_id", () => {
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [3, 1, 0], leading: [LAU], laHoa: false, chot: LAU }),
  );

  assert.equal(bang.optionIdThang, LAU);
  assert.equal(bang.laHoa, false);
  assert.deepEqual(bang.tenCacBenHoa, []);
});

test("đã đóng mà máy chủ chưa chốt bên nào: vẫn là null, app không tự chọn", () => {
  // Not a tie and not decided. The screen has to be able to say "chưa có bên
  // nào được chọn"; if this fell back to the leader it would print a winner
  // the server refused to name.
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [3, 1, 0], leading: [LAU], laHoa: false, chot: null }),
  );

  assert.equal(bang.optionIdThang, null);
});

test("chưa ai bỏ phiếu: không chia cho 0, và không ai đang dẫn", () => {
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [0, 0, 0], leading: [], laHoa: false, chot: null, daDong: false }),
  );

  assert.equal(bang.tongPhieu, 0);
  for (const hang of bang.hang) {
    assert.equal(hang.phanTram, 0, `${hang.nhan} phải là 0 chứ không phải NaN`);
    assert.ok(Number.isFinite(hang.phanTram));
    assert.equal(hang.dangDan, false);
  }
  // An empty vote is not a draw. `is_tie` says so; list length would not.
  assert.equal(bang.laHoa, false);
});

test("phiếu của tôi được đánh dấu đúng một hàng", () => {
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [1, 1, 0], leading: [LAU, NUONG], laHoa: true, chot: null, phieuCuaToi: NUONG }),
  );

  assert.deepEqual(
    bang.hang.filter((h) => h.laPhieuCuaToi).map((h) => h.nhan),
    ["Nướng"],
  );
});

test("hàng giữ thứ tự position, và phần trăm chỉ để vẽ thanh", () => {
  const bang = bangKetQuaTuWire(
    cuoc({ phieu: [3, 1, 0], leading: [LAU], laHoa: false, chot: LAU }),
  );

  assert.deepEqual(bang.hang.map((h) => h.nhan), ["Lẩu", "Nướng", "Chay"]);
  assert.deepEqual(bang.hang.map((h) => h.phieu), [3, 1, 0]);
  assert.deepEqual(bang.hang.map((h) => h.phanTram), [75, 25, 0]);
  assert.deepEqual(bang.hang.map((h) => h.dangDan), [true, false, false]);
  assert.equal(bang.hang[0].tenDiaDiem, "Quán Lẩu Cô Ba");
});
