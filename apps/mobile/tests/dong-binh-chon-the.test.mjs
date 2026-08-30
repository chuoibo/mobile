/* Ai được thấy nút "Đóng bình chọn", và tấm thẻ nói gì sau khi đóng.
 *
 * `binh-chon.test.mjs` chứng minh phép gấp: ai đóng được, phiếu nào còn tính.
 * Nó không vẽ gì, nên nó không trả lời được câu "cái nút có ra tới màn không,
 * và có ra tới ĐÚNG người không". Đó là câu file này hỏi.
 *
 * Vì sao phải hỏi riêng: phép gấp đã bỏ thẻ đóng của người không phải người
 * mở, nên một tấm thẻ vẽ nút cho cả nhóm vẫn "đúng" về số liệu — nó chỉ mời
 * năm người bấm một cú không làm gì. Đó là hình dạng `onDong={() => {}}` mà
 * #402 tìm thấy ở cửa quét, chỉ khác chỗ đứng.
 *
 * CHỨNG MINH: nút có mặt cho người mở, vắng mặt cho người khác, vắng mặt sau
 * khi đóng; hàng phiếu khoá lại và NÓI RA là đã đóng; câu kết quả đổi thì.
 * KHÔNG CHỨNG MINH: bấm vào nó thì có gì đi lên máy chủ không (đó là
 * `duong-dong-binh-chon.test.mjs`, chạy trong Chrome thật), màu có đủ tương
 * phản không (`renderToStaticMarkup` không mang stylesheet theo — xem
 * `tools/man-ra-html.mjs`), hay native vẽ giống web.
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs
 *     node --test tests/dong-binh-chon-the.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  cardBoPhieu,
  cardDongBinhChon,
  cardMoBinhChon,
  tongHopBinhChon,
} from "../dist-test/screens/chat/binh-chon.js";
import { TheBinhChon } from "../dist-test/screens/chat/TheBinhChon.js";

const AN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const BINH = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

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
    created_at: `2026-08-31T04:00:${String(seq).padStart(2, "0")}Z`,
    cursor: `c${seq}`,
  };
}

const MO = cardMoBinhChon({
  pollId: "p1",
  cauHoi: "Ăn tối ngày 1 ở đâu nhỉ?",
  luaChon: [
    { optionId: "o1", nhan: "Tiệm nướng Xóm Lèo" },
    { optionId: "o2", nhan: "Lẩu gà lá é Tao Ngộ" },
  ],
});

/** Bình chọn do AN mở, BINH bỏ một phiếu cho o1. `dong` thì AN đóng nó. */
function ketQua({ dong = false } = {}) {
  const luong = [tin(AN, MO), tin(BINH, cardBoPhieu("p1", "o1"))];
  if (dong) luong.push(tin(AN, cardDongBinhChon("p1")));
  const [kq] = tongHopBinhChon(luong, BINH);
  return kq;
}

function ve(kq, laNguoiMo) {
  return renderToStaticMarkup(
    React.createElement(TheBinhChon, {
      ketQua: kq,
      soThanhVien: 4,
      dangGui: false,
      laNguoiMo,
      onChon: () => {},
      onDong: () => {},
    }),
  );
}

/** Số nút mang đúng nhãn này.
 *
 *  Đếm `<button>` chứ không đếm chuỗi: `Kit.Button` không đặt `aria-label`,
 *  tên đọc được của nó là chính chữ bên trong — nên một `includes("Đóng bình
 *  chọn")` cũng khớp với một dòng chữ thường, và một dòng chữ thì không bấm
 *  được. Đếm chứ không hỏi có/không: một bản sửa sau vẽ hai nút chồng nhau
 *  vẫn làm `includes` true trong khi người dùng nhìn thấy hai. */
function demNutDong(markup) {
  return [...markup.matchAll(/<button[^>]*>(?:(?!<\/button>).)*?Đóng bình chọn/gs)].length;
}

test("người MỞ thấy đúng một nút Đóng bình chọn khi bình chọn còn mở", () => {
  const markup = ve(ketQua(), true);
  assert.equal(demNutDong(markup), 1, `markup: ${markup.slice(-500)}`);
});

test("người KHÁC không thấy nút Đóng bình chọn", () => {
  // Cùng một `ketQua`, chỉ khác `laNguoiMo` — nên chênh lệch này là do đúng
  // cái biến đang xét, không phải do dữ liệu khác nhau.
  assert.equal(demNutDong(ve(ketQua(), false)), 0);
});

test("đóng rồi thì nút biến mất, kể cả với người mở", () => {
  assert.equal(demNutDong(ve(ketQua({ dong: true }), true)), 0);
});

test("thẻ đã đóng nói ĐÃ ĐÓNG và gọi tên bên được chọn", () => {
  const markup = ve(ketQua({ dong: true }), true);
  assert.ok(markup.includes("Đã đóng"), "thiếu chip/câu 'Đã đóng'");
  assert.ok(
    markup.includes("Tiệm nướng Xóm Lèo được chọn với 1 phiếu"),
    `thiếu câu kết quả, markup: ${markup.slice(0, 400)}`,
  );
});

test("thẻ còn mở KHÔNG nói đã đóng", () => {
  // Ca âm cho ca trên: nếu chip vẽ vô điều kiện thì ca trên vẫn xanh.
  assert.ok(!ve(ketQua(), true).includes("Đã đóng"));
});

test("hàng phiếu khoá lại sau khi đóng, và nói ra lý do cho trình đọc màn hình", () => {
  const markup = ve(ketQua({ dong: true }), false);
  const hang = [...markup.matchAll(/aria-label="([^"]*phiếu[^"]*)"/g)].map((m) => m[1]);
  assert.equal(hang.length, 2, `phải có 2 hàng lựa chọn, thấy ${hang.length}: ${hang}`);
  for (const nhan of hang) {
    assert.ok(
      nhan.includes("đã đóng, không chọn được"),
      `hàng "${nhan}" không nói ra là đã đóng — aria-disabled một mình không nói vì sao bấm không ăn`,
    );
  }
  // `disabled` trên Pressable của react-native-web ra `aria-disabled`. Kiểm
  // luôn, vì đó mới là thứ chặn cú bấm chứ không phải câu chữ ở trên.
  const khoa = markup.split('aria-disabled="true"').length - 1;
  assert.ok(khoa >= 2, `phải có ít nhất 2 hàng aria-disabled, thấy ${khoa}`);
});

test("hàng phiếu lúc còn mở KHÔNG bị khoá", () => {
  const markup = ve(ketQua(), false);
  assert.ok(!markup.includes("đã đóng, không chọn được"));
  assert.equal(markup.split('aria-disabled="true"').length - 1, 0);
});
