/* Câu chặn trên màn chia tiền phải trỏ tới nút CÓ THẬT trên màn đó.
 *
 * Lý do file này tồn tại. Khi chưa ai được thêm vào bữa, màn "Gợi ý chia theo
 * người" hiện câu chặn "Chưa có ai trong nhóm. Thêm người bằng nút + ở trên."
 * Nhưng chính ở trạng thái đó, nút "+" KHÔNG được dựng: `GoiYChia` chỉ vẽ nó
 * khi `people.length > 0 && conLai.length > 0`. Hai điều kiện loại trừ nhau —
 * câu chặn chỉ xuất hiện khi danh sách rỗng, mà danh sách rỗng thì không có
 * nút nào cả. Người dùng được bảo đi tìm một cái nút không tồn tại, trong khi
 * thứ họ cần (danh sách chọn người trong nhóm) đang mở sẵn ngay dưới.
 *
 * Đo tại main @ 6c7d2ab bằng trình duyệt thật trên bundle `build:check`:
 *
 *     câu hiện ra   : "Chưa có ai trong nhóm. Thêm người bằng nút + ở trên."
 *     phần tử vẽ "+": (không có)
 *     nút thật có   : "Thêm Minh vào nhóm", "Thêm Trang vào nhóm", ...
 *
 * Vì sao cả cây test cũ vẫn xanh. `tests/assignment.test.mjs` ghim ĐÚNG chuỗi
 * đó bằng `assert.equal`, nên nó khẳng định câu sai là đúng. Một phép đo chỉ
 * hỏi "câu chữ có đổi không" không bao giờ hỏi được "câu chữ có thật không".
 *
 * Nên phép đo ở đây bắc cầu giữa hai thứ: câu chặn LẤY TỪ MARKUP đã render, và
 * các nút LẤY TỪ CÙNG MARKUP ĐÓ. Không đọc mã nguồn, không ghim chuỗi cứng —
 * một bản sửa chỉ đổi lời mà vẫn trỏ vào hư không thì vẫn đỏ.
 *
 * Cái nó KHÔNG chứng minh: rằng câu chữ dễ hiểu với người thật, và rằng những
 * câu chặn khác (món chưa ai nhận, món 0đ) trỏ đúng chỗ — chúng nói về ô tích
 * trong bảng chứ không về một nút, nên nằm ngoài bất biến này.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GoiYChia } from "../dist-test/screens/GoiYChia.js";
import { everyoneShares } from "../dist-test/assignment.js";

/* Id dạng chuỗi thường, như `tests/assignment.test.mjs` vẫn dùng. Màn này chỉ
 * lấy id làm khoá, không gửi đi đâu, nên một UUID ở đây không chứng minh thêm
 * gì mà lại là một dãy 32 chữ số phải xin miễn ở repo guard. */
const NHOM = [
  { id: "minh", name: "Minh" },
  { id: "trang", name: "Trang" },
  { id: "hai", name: "Hải" },
];

function line(id, name, amount) {
  return {
    id,
    name,
    quantity: 1,
    lineTotalVnd: amount,
    read: { name, quantity: 1, lineTotalVnd: amount },
  };
}

const READING = {
  lines: [line("mon-0", "Lẩu thái", 280000), line("mon-1", "Cơm rang", 150000)],
  printedTotalVnd: null,
  needsReview: false,
  warnings: [],
};

/** Màn hình với đúng trạng thái sinh ra câu chặn: chưa ai trong bữa. */
function renderRong() {
  return renderToStaticMarkup(
    React.createElement(GoiYChia, {
      reading: READING,
      roster: { participants: [], advancerId: null },
      nhom: NHOM,
      assignment: everyoneShares(READING.lines, []),
      preview: null,
      onBack: () => {},
      onReset: () => {},
      onToggle: () => {},
      onAddMember: () => {},
      onRemovePerson: () => {},
      onSeeResults: () => {},
    }),
  );
}

/** Chữ người dùng đọc được, đã bỏ thẻ và gộp khoảng trắng. */
function chuTren(html) {
  return html
    .replace(/<[^>]*>/g, "")
    .split("")
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

/** Mọi nhãn nút trên màn, theo đúng thứ trình đọc màn hình đọc ra. */
function nhanNut(html) {
  return [...html.matchAll(/aria-label="([^"]*)"/g)].map((m) => m[1]);
}

test("câu chặn khi chưa ai trong bữa không trỏ tới nút '+' không tồn tại", () => {
  const html = renderRong();
  const cau = chuTren(html).find((s) => s.startsWith("Chưa có ai trong nhóm"));
  assert.ok(cau, "không thấy câu chặn nào khi danh sách rỗng");

  // Nút "+" là một phần tử lá có nội dung đúng bằng "+". Đây là cách chính
  // `GoiYChia` vẽ nó, nên nếu nó có mặt thì phép đo này thấy.
  const coNutCong = /<[^>]*>\s*\+\s*</.test(html);

  assert.equal(
    cau.includes("nút +"),
    coNutCong,
    coNutCong
      ? `câu chặn không nhắc nút "+" trong khi màn có vẽ nó: ${cau}`
      : `câu chặn bảo bấm nút "+" nhưng màn không vẽ nút nào như thế: ${cau}`,
  );
});

test("câu chặn trỏ tới thứ màn thật sự đang mở sẵn", () => {
  const html = renderRong();
  const cau = chuTren(html).find((s) => s.startsWith("Chưa có ai trong nhóm"));

  // Ở trạng thái rỗng, danh sách chọn người trong nhóm mở sẵn. Đó là hành động
  // duy nhất màn này có, nên câu chặn phải dẫn người dùng về đúng nó.
  const nhan = nhanNut(html);
  const nutThemNguoi = nhan.filter((l) => /^Thêm .+ vào nhóm$/.test(l));
  assert.equal(
    nutThemNguoi.length,
    NHOM.length,
    `mong đợi ${NHOM.length} nút chọn người, thấy ${nutThemNguoi.length}: ${nhan.join(" | ")}`,
  );

  assert.match(
    cau,
    /chọn/i,
    `câu chặn phải bảo người dùng CHỌN người trong nhóm, vì đó là nút đang có: ${cau}`,
  );
});

test("câu chặn không dùng em-dash", () => {
  const cau = chuTren(renderRong()).find((s) => s.startsWith("Chưa có ai trong nhóm"));
  assert.equal(cau.includes("—"), false, `còn em-dash: ${cau}`);
});
