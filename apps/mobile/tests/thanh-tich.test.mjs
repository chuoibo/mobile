/* Màn Thành tích: mỗi con số trên màn phải truy được về một dòng trong sổ.
 *
 * Rủi ro của màn này không phải là bố cục. Mockup 07.03 vẽ sẵn 12 chuyến đi, 34
 * check-in, 780/1000 điểm và sáu huy hiệu đang sáng; gõ thẳng những số đó vào
 * file là ra đúng cái ảnh, và không ai nhìn màn mà phân biệt được. Nên các ca ở
 * đây kiểm đúng một điều: đổi sổ thì số trên màn phải đổi theo, và thứ sổ không
 * trả lời được thì phải nói là chưa đo được chứ không phải là chưa đạt.
 *
 * KHÔNG có ca nào cộng trừ tiền. `outstanding_vnd` chỉ được so với 0.
 *
 * Chạy từ apps/mobile:  npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  DIEM_MOI_CAP,
  DIEM_MOI_KHOAN_CHI,
  DIEM_MOI_NHOM,
  huyHieuCuaNguoi,
  phanSo,
  soGiaoDichTrongTuan,
  soNhomDaChuyenTien,
  thuThachTuan,
  tiLe,
  tienDoCapDo,
} from "../dist-test/screens/thanh-tich/thanh-tich.js";

/** Mốc thời gian cố định cho mọi ca có cửa sổ 7 ngày.
 *
 * Đồng hồ thật sẽ làm các ca này đúng hôm nay và sai vào tuần sau, mà kiểu sai
 * đó lại đọc như "tính năng hỏng". Truyền mốc vào là cách duy nhất để cửa sổ
 * được kiểm chứ không phải được tin. */
const BAY_GIO = Date.parse("2026-08-31T00:00:00Z");
const NGAY = 24 * 60 * 60 * 1000;

const movement = (over = {}) => ({
  obligation_id: "o1",
  direction: "out",
  amount_vnd: 160_000,
  counterparty_id: "p2",
  counterparty_name: "Trang",
  context_id: "c1",
  context_name: "Hội Đà Lạt",
  occasion: "Lẩu gà lá é",
  occurred_at: new Date(BAY_GIO - NGAY).toISOString(),
  ...over,
});

const so = (over = {}) => ({
  person_id: "p1",
  display_name: "Minh",
  spend_vnd: 860_000,
  settled_vnd: 500_000,
  outstanding_vnd: 360_000,
  expense_count: 4,
  group_count: 2,
  movements: [movement()],
  ...over,
});

test("điểm là hàm của sổ, không phải hằng số trên màn", () => {
  const t = tienDoCapDo(so({ expense_count: 4, group_count: 2 }));
  assert.equal(t.diem, 4 * DIEM_MOI_KHOAN_CHI + 2 * DIEM_MOI_NHOM);
  // Người chưa làm gì vẫn có level, và là 1 chứ không phải 0.
  const trong = tienDoCapDo(so({ expense_count: 0, group_count: 0, movements: [] }));
  assert.equal(trong.diem, 0);
  assert.equal(trong.cap, 1);
  assert.equal(trong.diemTrongCap, 0);
  assert.equal(trong.capSau, 2);
});

test("thêm một khoản chi vào sổ thì điểm trên màn tăng", () => {
  const truoc = tienDoCapDo(so({ expense_count: 4 }));
  const sau = tienDoCapDo(so({ expense_count: 5 }));
  assert.equal(sau.diem - truoc.diem, DIEM_MOI_KHOAN_CHI);
});

test("qua mốc một level thì cap tăng và phần dư đếm lại từ đầu", () => {
  // 10 khoản chi = 100 điểm = đúng một level, không dư.
  const t = tienDoCapDo(so({ expense_count: 10, group_count: 0 }));
  assert.equal(t.diem, DIEM_MOI_CAP);
  assert.equal(t.cap, 2);
  assert.equal(t.diemTrongCap, 0);
  assert.equal(t.capSau, 3);
});

test("huy hiệu đo được thì mở theo sổ, không mở sẵn", () => {
  const ds = huyHieuCuaNguoi(so({ expense_count: 4, group_count: 2 }));
  const lay = (id) => ds.find((h) => h.id === id);
  // 4 khoản chi: đủ cho "mở hàng" (cần 1), chưa đủ Bill Hero (cần 5).
  assert.equal(lay("mo-hang").trangThai, "mo");
  assert.equal(lay("bill-hero").trangThai, "chua-dat");
  assert.equal(lay("bill-hero").daDat, 4);
  assert.equal(lay("bill-hero").can, 5);
  // Thêm một khoản chi nữa là mở.
  const sau = huyHieuCuaNguoi(so({ expense_count: 5 }));
  assert.equal(sau.find((h) => h.id === "bill-hero").trangThai, "mo");
});

test("Sòng phẳng chỉ mở khi hết nợ, và chỉ khi đã từng chia", () => {
  const conNo = huyHieuCuaNguoi(so({ outstanding_vnd: 360_000, expense_count: 4 }));
  assert.equal(conNo.find((h) => h.id === "song-phang").trangThai, "chua-dat");

  const hetNo = huyHieuCuaNguoi(so({ outstanding_vnd: 0, expense_count: 4 }));
  assert.equal(hetNo.find((h) => h.id === "song-phang").trangThai, "mo");

  // Người chưa chia khoản nào cũng có outstanding 0. Đó không phải sòng phẳng,
  // đó là chưa tham gia -- mở huy hiệu cho họ là khen một việc chưa xảy ra.
  const chuaLam = huyHieuCuaNguoi(so({ outstanding_vnd: 0, expense_count: 0 }));
  assert.equal(chuaLam.find((h) => h.id === "song-phang").trangThai, "chua-dat");
});

test("huy hiệu không có bảng nào đo được thì mang trạng thái riêng, kèm lý do", () => {
  // Đây là ca giữ cho màn khỏi nói dối: "chưa đo được" phải khác "chưa đạt",
  // vì hai cái đó nói hai chuyện ngược nhau với người đọc.
  const ds = huyHieuCuaNguoi(so({ expense_count: 999, group_count: 999 }));
  const chuaDo = ds.filter((h) => h.trangThai === "chua-do-duoc");
  assert.equal(chuaDo.length, 4);
  for (const h of chuaDo) {
    // Sổ đầy tới đâu cũng không mở được, vì không có gì đếm chúng.
    assert.notEqual(h.trangThai, "mo");
    assert.ok(h.thieuGi && h.thieuGi.length > 0, `${h.id} phải nói thiếu bảng nào`);
    assert.equal(h.daDat, undefined);
  }
  // Và mọi huy hiệu đều in điều kiện, kể cả cái không đo được.
  for (const h of ds) assert.ok(h.dieuKien.length > 0);
});

test("cửa sổ 7 ngày đếm đúng các dòng trong cửa sổ", () => {
  const ds = [
    movement({ occurred_at: new Date(BAY_GIO - 1 * NGAY).toISOString() }),
    movement({ occurred_at: new Date(BAY_GIO - 6 * NGAY).toISOString() }),
    // Ngoài cửa sổ.
    movement({ occurred_at: new Date(BAY_GIO - 8 * NGAY).toISOString() }),
    // Ngày không đọc được: bỏ, không tính thành 0 mà cũng không nổ.
    movement({ occurred_at: "không-phải-ngày" }),
  ];
  assert.equal(soGiaoDichTrongTuan(ds, BAY_GIO), 2);
  assert.equal(soGiaoDichTrongTuan([], BAY_GIO), 0);
});

test("đếm nhóm đã chuyển tiền là đếm nhóm khác nhau, không đếm dòng", () => {
  const ds = [
    movement({ context_id: "c1" }),
    movement({ context_id: "c1" }),
    movement({ context_id: "c2" }),
  ];
  assert.equal(ds.length, 3);
  assert.equal(soNhomDaChuyenTien(ds), 2);
});

test("thử thách tuần đọc từ movements chứ không phải từ hằng số", () => {
  const ds = thuThachTuan(
    so({
      outstanding_vnd: 0,
      movements: [
        movement({ context_id: "c1", occurred_at: new Date(BAY_GIO - NGAY).toISOString() }),
        movement({ context_id: "c2", occurred_at: new Date(BAY_GIO - 2 * NGAY).toISOString() }),
      ],
    }),
    BAY_GIO,
  );
  const lay = (id) => ds.find((t) => t.id === id);
  assert.equal(lay("giao-dich-tuan").daDat, 2);
  assert.equal(lay("giao-dich-tuan").xong, true);
  assert.equal(lay("hai-nhom").daDat, 2);
  assert.equal(lay("hai-nhom").xong, true);
  assert.equal(lay("het-no").xong, true);
});

test("cùng một sổ, dời đồng hồ đi 30 ngày thì thử thách tuần về 0", () => {
  // Cửa sổ phải thật sự là cửa sổ. Nếu ca này vẫn xanh với mốc xa, nghĩa là
  // `bayGio` không được dùng và con số kia là số đếm cả đời.
  const soSach = so({ movements: [movement()] });
  assert.equal(thuThachTuan(soSach, BAY_GIO).find((t) => t.id === "giao-dich-tuan").daDat, 1);
  const xa = thuThachTuan(soSach, BAY_GIO + 30 * NGAY);
  assert.equal(xa.find((t) => t.id === "giao-dich-tuan").daDat, 0);
  assert.equal(xa.find((t) => t.id === "giao-dich-tuan").xong, false);
});

test("còn nợ thì thử thách hết nợ chưa xong", () => {
  const ds = thuThachTuan(so({ outstanding_vnd: 360_000 }), BAY_GIO);
  assert.equal(ds.find((t) => t.id === "het-no").xong, false);
  assert.equal(ds.find((t) => t.id === "het-no").daDat, 0);
});

test("phân số không bao giờ vượt mẫu, và tỉ lệ luôn nằm trong 0..1", () => {
  assert.equal(phanSo(0, 2), "0/2");
  assert.equal(phanSo(1, 2), "1/2");
  // Làm nhiều hơn yêu cầu vẫn in "2/2", không in "7/2".
  assert.equal(phanSo(7, 2), "2/2");
  assert.equal(tiLe(0, 100), 0);
  assert.equal(tiLe(50, 100), 0.5);
  assert.equal(tiLe(700, 100), 1);
  // Mẫu 0 trả 0 chứ không trả Infinity/NaN cho chiều rộng của thanh.
  assert.equal(tiLe(1, 0), 0);
});
