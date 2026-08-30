/* Ba con số của mockup 07.02 CÓ THẬT trên markup, không chỉ có trong module.
 *
 * `tai-chinh.test.mjs` kiểm các hàm thuần: định dạng tiền, câu tình trạng,
 * ghi chú giới hạn. Cả bộ đó vẫn xanh khi thẻ trên màn không in ra con số nào
 * -- nó không nạp một dòng JSX nào. Đó đúng là hình dạng đã để lọt một lần
 * trong repo này: một địa chỉ được định tuyến, cổng xanh, và không có gì render
 * ở đó.
 *
 * Nên file này render qua react-native-web -- đúng phép thế mà bản web của Expo
 * dùng -- rồi đọc chuỗi markup. Cái được chứng minh: con số máy chủ gửi tới có
 * mặt trên màn, đúng chiều, kèm chữ nói chiều đó. Cái KHÔNG được chứng minh:
 * màn hình thật trên điện thoại, tương phản màu, hay việc người đọc hiểu.
 *
 * Vì sao render `TaiChinh` chứ không render cả `CaNhan`: `CaNhan` chỉ tới được
 * trạng thái "xong" qua `useEffect`, mà `renderToStaticMarkup` không chạy
 * effect. Render cả màn thì luôn chỉ ra cái spinner, và ba con số có thể vắng
 * mặt hoàn toàn trong khi mọi ca ở đây vẫn xanh.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { TaiChinh } from "../dist-test/screens/ca-nhan/CaNhan.js";

function so(over = {}) {
  return {
    person_id: "p-an",
    display_name: "An",
    spend_vnd: 2_100_000,
    settled_vnd: 1_980_000,
    outstanding_vnd: 120_000,
    receivable_vnd: 530_000,
    expense_count: 4,
    group_count: 2,
    movements: [],
    ...over,
  };
}

function ve(over = {}) {
  return renderToStaticMarkup(
    React.createElement(TaiChinh, {
      trang: { pha: "xong", so: so(over) },
      onThuLai: () => {},
      coNguoi: true,
    }),
  );
}

test("cả ba con số của mockup đều nằm trên markup", () => {
  const html = ve();
  assert.match(html, /2\.100\.000đ/, "Đã trả");
  assert.match(html, /530\.000đ/, "Còn nhận");
  assert.match(html, /120\.000đ/, "Còn phải trả");
});

test("ba nhãn của mockup được viết ra, không phải chỉ có số", () => {
  const html = ve();
  for (const nhan of ["Đã trả", "Còn nhận", "Còn phải trả"]) {
    assert.ok(html.includes(nhan), `thiếu nhãn "${nhan}"`);
  }
});

/* Đây là ca chịu lực. Hai ô cạnh nhau, một xanh một cam, và ai đọc lướt cũng
 * chỉ thấy hai con số. Chữ dưới mỗi ô là thứ duy nhất còn sống trên một ảnh
 * chụp trắng đen, và cũng là thứ duy nhất nói được ô nào là chiều nào. */
test("chiều tiền được nói bằng chữ, không chỉ bằng màu", () => {
  const html = ve();
  assert.ok(html.includes("Người khác nợ bạn"), "ô Còn nhận thiếu chữ chỉ chiều");
  assert.ok(html.includes("Bạn còn nợ người khác"), "ô Còn phải trả thiếu chữ chỉ chiều");
});

/* Đột biến dễ nhất và khó thấy nhất: đổi chỗ hai biến. Markup vẫn có đủ hai
 * con số, đủ hai nhãn, và nói ngược. Ca này neo vào THỨ TỰ xuất hiện, nên nó
 * đỏ khi 530.000đ rơi vào ô "Còn phải trả". */
test("số nào vào ô nấy — hoán đổi hai ô thì ca này đỏ", () => {
  const html = ve();
  const viNhan = html.indexOf("Còn nhận");
  const viTra = html.indexOf("Còn phải trả");
  assert.ok(viNhan > 0 && viTra > viNhan, "hai ô phải theo thứ tự của mockup");
  const oNhan = html.slice(viNhan, viTra);
  const oTra = html.slice(viTra);
  assert.ok(oNhan.includes("530.000đ"), "ô Còn nhận không mang số của nó");
  assert.ok(!oNhan.includes("120.000đ"), "số của ô kia lọt sang ô Còn nhận");
  assert.ok(oTra.includes("120.000đ"), "ô Còn phải trả không mang số của nó");
});

test("câu tình trạng nằm trên màn, không chỉ nằm trong module", () => {
  assert.match(ve().replace(/<[^>]*>/g, ""), /Bạn còn nợ 120\.000đ và người khác nợ bạn 530\.000đ/);
});

test("sạch nợ hai chiều thì màn nói ra, và không in số 0 nào thành nợ", () => {
  const html = ve({ receivable_vnd: 0, outstanding_vnd: 0, settled_vnd: 2_100_000 });
  assert.match(html.replace(/<[^>]*>/g, ""), /không nợ ai/);
  // Hai ô vẫn còn, vẫn in 0đ. Giấu ô đi khi bằng 0 sẽ làm màn đổi hình dạng
  // giữa hai lần mở và người đọc mất chỗ neo mắt.
  assert.ok(html.includes("Còn nhận"));
  assert.ok(html.includes("0đ"));
});

/* Bốn cái cột bịa sẽ đọc y hệt như ba con số thật ở trên nó. Màn nói ra là
 * chưa tách được, và ca này giữ câu đó ở lại: gỡ nó ra thì mockup có một
 * phần vắng mặt mà không ai được báo. */
test("phần chưa dựng được nói ra chứ không im lặng biến mất", () => {
  const chu = ve().replace(/<[^>]*>/g, "");
  assert.match(chu, /Chưa tách được theo nhóm chi/);
  // Và tuyệt đối không có bốn danh mục nào kèm số tiền: đó sẽ là bịa.
  for (const bia of ["Ăn uống", "Di chuyển"]) {
    assert.ok(!chu.includes(`${bia} `) || !/\d\.\d{3}/.test(chu.split(bia)[1] ?? ""), bia);
  }
});

test("máy chủ im lặng thì không có số nào được vẽ ra", () => {
  const html = renderToStaticMarkup(
    React.createElement(TaiChinh, {
      trang: { pha: "loi", loi: "Máy chủ đang lỗi, chưa đọc được sổ." },
      onThuLai: () => {},
      coNguoi: true,
    }),
  );
  assert.ok(!/\d\.\d{3}đ/.test(html), `số cũ còn trên màn lúc lỗi: ${html.slice(0, 200)}`);
  assert.match(html, /Thử lại/);
});
