/** What these check, and what they deliberately do not.
 *
 * They check the fold: one person one vote, changing your mind, a tie stated
 * as a tie, percentages that add to 100, and every way a malformed card can
 * arrive. All of that is arithmetic over an array, so it is checked here
 * rather than by looking at a phone.
 *
 * They do NOT check that the server persists any of it, that a second member
 * sees the ballot, or that a non-member is refused. Those are HTTP facts and
 * the fake array below cannot prove one of them. `tests/e2e` and the live
 * layer are where that has to happen.
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  binhChonTuCard,
  cardBoPhieu,
  cardDongBinhChon,
  cardMoBinhChon,
  cauKetQua,
  diaDiemDaGoiY,
  phanTramTronVen,
  tongHopBinhChon,
} from "../dist-test/screens/chat/binh-chon.js";

const AN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const BINH = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const CUONG = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const DUNG = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

let seq = 0;
function tin(authorId, card) {
  seq += 1;
  return {
    id: `msg-${seq}`,
    context_id: "ctx",
    author_id: authorId,
    kind: "ai_card",
    body: null,
    image_url: null,
    card,
    created_at: `2026-08-29T10:00:${String(seq).padStart(2, "0")}Z`,
    cursor: `c${seq}`,
  };
}

const MO = cardMoBinhChon({
  pollId: "p1",
  cauHoi: "Ăn tối ngày 1 ở đâu nhỉ?",
  luaChon: [
    { optionId: "o1", nhan: "Tiệm nướng Xóm Lèo" },
    { optionId: "o2", nhan: "Lẩu gà lá é Tao Ngộ" },
    { optionId: "o3", nhan: "Bánh căn Nhà Chung" },
  ],
});

test("một người một phiếu: bỏ phiếu hai lần chỉ tính lần sau", () => {
  const [kq] = tongHopBinhChon(
    [tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o1")), tin(BINH, cardBoPhieu("p1", "o2"))],
    null,
  );
  assert.equal(kq.tongPhieu, 1, "hai thẻ phiếu của cùng một người vẫn là một phiếu");
  assert.equal(kq.ketQua.find((r) => r.optionId === "o1").phieu, 0);
  assert.equal(kq.ketQua.find((r) => r.optionId === "o2").phieu, 1);
  assert.equal(kq.soNguoiDaBoPhieu, 1);
});

test("HOÀ thì nói là hoà, và không trao vương miện cho ai", () => {
  const [kq] = tongHopBinhChon(
    [
      tin(AN, MO),
      tin(AN, cardBoPhieu("p1", "o1")),
      tin(BINH, cardBoPhieu("p1", "o2")),
      tin(CUONG, cardBoPhieu("p1", "o1")),
      tin(DUNG, cardBoPhieu("p1", "o2")),
    ],
    null,
  );
  assert.equal(kq.dangHoa, true);
  assert.deepEqual(kq.dienDau.sort(), ["o1", "o2"]);
  // Both leaders are marked leading. Neither is singled out as the winner.
  assert.equal(kq.ketQua.filter((r) => r.dangDan).length, 2);
  assert.match(cauKetQua(kq), /hoà/i);
  assert.match(cauKetQua(kq), /Tiệm nướng Xóm Lèo/);
  assert.match(cauKetQua(kq), /Lẩu gà lá é Tao Ngộ/);
});

test("một người dẫn rõ ràng thì không phải hoà", () => {
  const [kq] = tongHopBinhChon(
    [tin(AN, MO), tin(AN, cardBoPhieu("p1", "o1")), tin(BINH, cardBoPhieu("p1", "o1")), tin(CUONG, cardBoPhieu("p1", "o2"))],
    null,
  );
  assert.equal(kq.dangHoa, false);
  assert.deepEqual(kq.dienDau, ["o1"]);
  assert.equal(cauKetQua(kq), "Tiệm nướng Xóm Lèo đang dẫn với 2 phiếu");
});

test("chưa ai bỏ phiếu: không có ai dẫn, không phải hoà", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO)], null);
  assert.equal(kq.tongPhieu, 0);
  assert.deepEqual(kq.dienDau, []);
  assert.equal(kq.dangHoa, false, "0-0-0 là chưa ai bầu, không phải hoà ba bên");
  assert.equal(kq.ketQua.every((r) => r.dangDan === false), true);
  assert.equal(cauKetQua(kq), "Chưa có phiếu nào");
});

test("máy không có phiếu: thẻ phiếu không có tác giả bị bỏ", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(null, cardBoPhieu("p1", "o1"))], null);
  assert.equal(kq.tongPhieu, 0, "companion nói thì không được tính là một lá phiếu");
});

test("phiếu cho lựa chọn không tồn tại bị bỏ, không dồn sang hàng bên cạnh", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o-khong-co"))], null);
  assert.equal(kq.tongPhieu, 0);
  assert.equal(
    kq.ketQua.reduce((a, r) => a + r.phieu, 0),
    0,
  );
});

test("thẻ mở lại cùng poll_id không thay được lựa chọn đã có phiếu", () => {
  const doiY = cardMoBinhChon({
    pollId: "p1",
    cauHoi: "Câu hỏi khác hẳn",
    luaChon: [
      { optionId: "x1", nhan: "Quán lạ 1" },
      { optionId: "x2", nhan: "Quán lạ 2" },
    ],
  });
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o1")), tin(CUONG, doiY)], null);
  assert.equal(kq.cauHoi, "Ăn tối ngày 1 ở đâu nhỉ?");
  assert.equal(kq.ketQua.length, 3);
  assert.equal(kq.ketQua.find((r) => r.optionId === "o1").phieu, 1);
});

test("lựa chọn của tôi được đánh dấu, và chỉ của tôi", () => {
  const msgs = [tin(AN, MO), tin(AN, cardBoPhieu("p1", "o3")), tin(BINH, cardBoPhieu("p1", "o1"))];
  assert.equal(tongHopBinhChon(msgs, AN)[0].luaChonCuaToi, "o3");
  assert.equal(tongHopBinhChon(msgs, BINH)[0].luaChonCuaToi, "o1");
  assert.equal(tongHopBinhChon(msgs, CUONG)[0].luaChonCuaToi, null);
  assert.equal(tongHopBinhChon(msgs, null)[0].luaChonCuaToi, null);
});

test("phần trăm luôn cộng đúng 100 khi đã có phiếu", () => {
  // 1/3 each is the classic case where naive rounding prints 33+33+33 = 99.
  const ba = tongHopBinhChon(
    [tin(AN, MO), tin(AN, cardBoPhieu("p1", "o1")), tin(BINH, cardBoPhieu("p1", "o2")), tin(CUONG, cardBoPhieu("p1", "o3"))],
    null,
  )[0];
  assert.equal(
    ba.ketQua.reduce((a, r) => a + r.phanTram, 0),
    100,
  );

  // And 1/7 six ways, the shape the mockup draws.
  for (const counts of [[1, 1, 1], [4, 2, 1], [5, 1, 1], [1, 0, 0], [2, 2, 3], [1, 2, 4, 7, 9]]) {
    assert.equal(
      phanTramTronVen(counts).reduce((a, b) => a + b, 0),
      100,
      `tổng phần trăm của ${counts.join("-")} phải là 100`,
    );
  }
  assert.deepEqual(phanTramTronVen([0, 0, 0]), [0, 0, 0], "chưa có phiếu thì 0%, không phải chia đều");
});

test("số phiếu là sự thật: phần trăm không bao giờ làm một phiếu thật thành 0 hàng", () => {
  const counts = [1, 99];
  const p = phanTramTronVen(counts);
  assert.equal(p.reduce((a, b) => a + b, 0), 100);
  assert.equal(p[0], 1);
});

test("thẻ hỏng đọc ra null, không dựng lá phiếu rỗng", () => {
  for (const xau of [
    null,
    42,
    "poll",
    [],
    { kind: "poll" },
    { kind: "poll", payload: {} },
    { kind: "poll", payload: { poll_id: "p", question: "q" } },
    { kind: "poll", payload: { poll_id: "p", question: "q", options: [] } },
    // One option is not a choice.
    { kind: "poll", payload: { poll_id: "p", question: "q", options: [{ option_id: "a", label: "A" }] } },
    { kind: "itinerary", payload: { title: "x", stops: [] } },
  ]) {
    assert.equal(binhChonTuCard(xau, "m", null), null, `phải là null cho ${JSON.stringify(xau)}`);
  }
});

test("lựa chọn trùng option_id bị gộp, không đếm hai lần", () => {
  const the = binhChonTuCard(
    {
      kind: "poll",
      payload: {
        poll_id: "p",
        question: "q",
        options: [
          { option_id: "a", label: "A" },
          { option_id: "a", label: "A lần hai" },
          { option_id: "b", label: "B" },
        ],
      },
    },
    "m",
    null,
  );
  assert.equal(the.luaChon.length, 2);
});

test("lựa chọn lấy tên từ địa điểm khi thẻ không kèm label", () => {
  const the = binhChonTuCard(
    {
      kind: "poll",
      payload: {
        poll_id: "p",
        question: "q",
        options: [
          { option_id: "a", place: { id: "pl-1", name: "Tiệm nướng Xóm Lèo" } },
          { option_id: "b", place: { id: "pl-2", name: "Lẩu gà lá é" } },
        ],
      },
    },
    "m",
    null,
  );
  assert.equal(the.luaChon[0].nhan, "Tiệm nướng Xóm Lèo");
  assert.equal(the.luaChon[0].diaDiem.id, "pl-1");
});

test("nhiều bình chọn trong một luồng: đếm riêng, đúng thứ tự mở", () => {
  const mo2 = cardMoBinhChon({
    pollId: "p2",
    cauHoi: "Ngày 2: Hoạt động buổi sáng?",
    luaChon: [
      { optionId: "s1", nhan: "Săn mây đồi chè Cầu Đất" },
      { optionId: "s2", nhan: "Tham quan Thiền viện Trúc Lâm" },
    ],
  });
  const kq = tongHopBinhChon(
    [tin(AN, MO), tin(AN, cardBoPhieu("p1", "o1")), tin(AN, mo2), tin(AN, cardBoPhieu("p2", "s2"))],
    AN,
  );
  assert.equal(kq.length, 2);
  assert.equal(kq[0].pollId, "p1");
  assert.equal(kq[1].pollId, "p2");
  assert.equal(kq[0].luaChonCuaToi, "o1");
  assert.equal(kq[1].luaChonCuaToi, "s2");
  // A ballot in one poll must not leak into the other.
  assert.equal(kq[1].ketQua.find((r) => r.optionId === "s1").phieu, 0);
});

test("tin text và tin ảnh trong luồng không làm hỏng phép đếm", () => {
  const kq = tongHopBinhChon(
    [
      { ...tin(AN, null), kind: "text", body: "đi đâu nhỉ" },
      tin(AN, MO),
      { ...tin(BINH, null), kind: "text", body: "để tui bầu" },
      tin(BINH, cardBoPhieu("p1", "o1")),
    ],
    null,
  );
  assert.equal(kq.length, 1);
  assert.equal(kq[0].tongPhieu, 1);
});

/* --- diaDiemDaGoiY: where the ballot's options are allowed to come from ---
 *
 * The compose screen has no free-text field, so this function is the entire
 * supply of things a group can vote on. If it ever returned something the
 * server did not assert, the vote would be about a place that does not
 * exist -- and unlike a wrong percentage, that error survives the vote and
 * sends people somewhere. */

function theDiaDiem(places) {
  return { kind: "places", payload: { places } };
}

const QUAN_A = { id: "pl-a", name: "Tiệm nướng Xóm Lèo", address: "12 Xóm Lèo" };
const QUAN_B = { id: "pl-b", name: "Lẩu gà lá é Tao Ngộ" };
const QUAN_C = { id: "pl-c", name: "Bánh căn Nhà Chung" };

test("gom địa điểm từ thẻ places và thẻ itinerary, theo thứ tự luồng", () => {
  const ds = diaDiemDaGoiY([
    tin(null, theDiaDiem([QUAN_A, QUAN_B])),
    tin(null, {
      kind: "itinerary",
      payload: { title: "Đà Lạt 2N1Đ", stops: [{ time_text: "19:00", place: QUAN_C }] },
    }),
  ]);
  assert.deepEqual(
    ds.map((d) => d.id),
    ["pl-a", "pl-b", "pl-c"],
  );
  assert.equal(ds[0].ten, "Tiệm nướng Xóm Lèo");
  assert.equal(ds[0].diaChi, "12 Xóm Lèo");
});

test("một quán được nhắc lại chỉ ra một lựa chọn, giữ lần nhắc đầu", () => {
  // Two rows with the same id would put the same restaurant on the ballot
  // twice and split its votes between the copies.
  const ds = diaDiemDaGoiY([
    tin(null, theDiaDiem([QUAN_A, QUAN_B])),
    tin(null, theDiaDiem([QUAN_B, QUAN_A])),
  ]);
  assert.deepEqual(
    ds.map((d) => d.id),
    ["pl-a", "pl-b"],
  );
});

test("chữ người gõ không thành lựa chọn: chỉ thẻ máy chủ mới vào được lá phiếu", () => {
  const ds = diaDiemDaGoiY([
    { ...tin(AN, null), kind: "text", body: "quán Ốc Đêm ngon lắm, bầu đi" },
    tin(AN, MO),
    tin(AN, cardBoPhieu("p1", "o1")),
  ]);
  assert.deepEqual(ds, []);
});

/* ── Đóng bình chọn (F17) ────────────────────────────────────────────────────
 *
 * A close is a third card in the same thread, so every rule below is a rule
 * about the fold, not about a screen. They are here rather than in a render
 * test because "who may close" and "which ballots still count" are arithmetic
 * over an array, and a screen that draws them cannot prove them.
 *
 * The one that matters most is `phiếu bỏ SAU khi đóng không được tính`. Without
 * it, "đã đóng" is paint: a label over a tally that still moves.
 */

const DONG_P1 = cardDongBinhChon("p1");

test("người mở đóng được: thẻ đóng của chính tác giả làm bình chọn khép lại", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o1")), tin(AN, DONG_P1)], null);
  assert.equal(kq.daDong, true);
  assert.equal(kq.taoBoi, AN);
  assert.equal(kq.tongPhieu, 1);
});

test("bình chọn chưa ai đóng thì đang mở", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o1"))], null);
  assert.equal(kq.daDong, false);
});

test("người KHÁC không đóng được bình chọn của người mở", () => {
  // author_id is written by the server off the trusted actor header, so this
  // is the same field "một người một phiếu" is enforced against. A close card
  // from anybody else is dropped, not honoured with a different label.
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(BINH, DONG_P1)], null);
  assert.equal(kq.daDong, false);
});

test("máy không đóng được: thẻ đóng không có tác giả bị bỏ", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(null, DONG_P1)], null);
  assert.equal(kq.daDong, false);
});

test("bình chọn do máy mở thì không ai đóng được, kể cả người bỏ phiếu", () => {
  // `taoBoi` null means there is no person to match a close against. Letting
  // any member close it would hand the ballot to whoever pressed first.
  const [kq] = tongHopBinhChon([tin(null, MO), tin(AN, DONG_P1)], null);
  assert.equal(kq.taoBoi, null);
  assert.equal(kq.daDong, false);
});

test("phiếu bỏ SAU khi đóng không được tính", () => {
  const [kq] = tongHopBinhChon(
    [
      tin(AN, MO),
      tin(BINH, cardBoPhieu("p1", "o1")),
      tin(AN, DONG_P1),
      tin(CUONG, cardBoPhieu("p1", "o2")),
      tin(DUNG, cardBoPhieu("p1", "o2")),
    ],
    null,
  );
  assert.equal(kq.daDong, true);
  assert.equal(kq.tongPhieu, 1, "hai phiếu sau khi đóng vẫn được đếm");
  assert.deepEqual(kq.dienDau, ["o1"]);
});

test("đổi phiếu sau khi đóng không ghi đè phiếu đã bỏ trước đó", () => {
  // The hard half of the rule above: a late ballot must not merely fail to
  // add, it must not replace. Last-write-wins is what counts an open poll.
  const [kq] = tongHopBinhChon(
    [tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o1")), tin(AN, DONG_P1), tin(BINH, cardBoPhieu("p1", "o2"))],
    BINH,
  );
  assert.equal(kq.luaChonCuaToi, "o1");
  assert.equal(kq.ketQua.find((r) => r.optionId === "o1").phieu, 1);
  assert.equal(kq.ketQua.find((r) => r.optionId === "o2").phieu, 0);
});

test("đóng hai lần thì lần đầu tính, phiếu giữa hai thẻ đóng không sống lại", () => {
  const [kq] = tongHopBinhChon(
    [tin(AN, MO), tin(AN, DONG_P1), tin(BINH, cardBoPhieu("p1", "o1")), tin(AN, DONG_P1)],
    null,
  );
  assert.equal(kq.daDong, true);
  assert.equal(kq.tongPhieu, 0);
});

test("thẻ đóng gọi tên một bình chọn không tồn tại thì không đóng cái nào", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(AN, cardDongBinhChon("p-khong-co"))], null);
  assert.equal(kq.daDong, false);
});

test("thẻ đóng dị dạng bị bỏ, không đóng nhầm", () => {
  for (const xau of [
    { kind: "poll_close", payload: {} },
    { kind: "poll_close", payload: { poll_id: "  " } },
    { kind: "poll_close" },
    { kind: "poll_close", payload: null },
  ]) {
    const [kq] = tongHopBinhChon([tin(AN, MO), tin(AN, xau)], null);
    assert.equal(kq.daDong, false, `thẻ ${JSON.stringify(xau)} không được đóng bình chọn`);
  }
});

test("cardDongBinhChon dựng đúng hình dạng đường dây", () => {
  assert.deepEqual(cardDongBinhChon("p1"), { kind: "poll_close", payload: { poll_id: "p1" } });
});

test("câu kết quả của bình chọn đã đóng nói ĐÃ ĐÓNG và gọi tên bên được chọn", () => {
  const [kq] = tongHopBinhChon(
    [tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o2")), tin(AN, DONG_P1)],
    null,
  );
  const cau = cauKetQua(kq);
  assert.match(cau, /Đã đóng/);
  assert.match(cau, /Lẩu gà lá é Tao Ngộ/);
});

test("hoà lúc đóng vẫn là hoà: không bên nào được gọi là bên được chọn", () => {
  const [kq] = tongHopBinhChon(
    [
      tin(AN, MO),
      tin(BINH, cardBoPhieu("p1", "o1")),
      tin(CUONG, cardBoPhieu("p1", "o2")),
      tin(AN, DONG_P1),
    ],
    null,
  );
  assert.equal(kq.daDong, true);
  assert.equal(kq.dangHoa, true);
  assert.deepEqual(kq.dienDau.sort(), ["o1", "o2"]);
  assert.match(cauKetQua(kq), /Đã đóng/);
  assert.match(cauKetQua(kq), /[Hh]oà/);
});

test("đóng lúc chưa ai bỏ phiếu thì nói rõ chưa có phiếu nào, không gọi ai là bên thắng", () => {
  const [kq] = tongHopBinhChon([tin(AN, MO), tin(AN, DONG_P1)], null);
  assert.equal(kq.daDong, true);
  assert.deepEqual(kq.dienDau, []);
  assert.equal(kq.dangHoa, false);
  assert.match(cauKetQua(kq), /Đã đóng/);
  assert.match(cauKetQua(kq), /[Cc]hưa có phiếu nào/);
});

test("đóng bình chọn này không đụng bình chọn kia trong cùng luồng", () => {
  const MO2 = cardMoBinhChon({
    pollId: "p2",
    cauHoi: "Sáng mai ăn gì?",
    luaChon: [
      { optionId: "q1", nhan: "Bánh mì" },
      { optionId: "q2", nhan: "Phở" },
    ],
  });
  const [mot, hai] = tongHopBinhChon(
    [tin(AN, MO), tin(AN, MO2), tin(AN, DONG_P1), tin(BINH, cardBoPhieu("p2", "q1"))],
    null,
  );
  assert.equal(mot.daDong, true);
  assert.equal(hai.daDong, false);
  assert.equal(hai.tongPhieu, 1);
});
