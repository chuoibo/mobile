/* What the outing (F13) and timeline (F15) logic is allowed to get wrong.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/buoi-di.test.mjs
 *
 * The server keeps the stop order the client sent. Sending 12:30 then 07:00
 * comes back as position 0 = 12:30. The client has to sort before PUT, and
 * that rule lives in a file that runs under bare node so it cannot hide
 * behind a screen.
 */
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { formatVnd } from "../../../packages/shared/money.mjs";
import tokens from "../../../packages/shared/tokens.json" with { type: "json" };

import { DIRECTION_CONTRACT_BUOI_DI } from "../dist-test/ui/direction.js";
import {
  kiemTraChang,
  kiemTraTaoBuoiDi,
  nhanKhoangNgay,
  nhanNganSach,
  sapXepChang,
  tongDuKien,
} from "../dist-test/screens/len-plan/buoi-di.js";
import { DongThoiGian } from "../dist-test/screens/len-plan/DongThoiGian.js";
import { TaoBuoiDi } from "../dist-test/screens/len-plan/TaoBuoiDi.js";

const LEN_PLAN_SRC = join(dirname(fileURLToPath(import.meta.url)), "../src/screens/len-plan");
const EM_DASH = "\u2014";
const EN_DASH = "\u2013";

function form(over = {}) {
  return {
    title: "Đà Lạt cuối tuần",
    starts_on: "2026-09-07",
    ends_on: "2026-09-08",
    headcount: "7",
    nganSach: "2500000",
    ...over,
  };
}

function buoi(over = {}) {
  return {
    id: "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
    context_id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    created_by_id: "46b55e67-932b-5415-a5ee-08fb2641a4ff",
    title: "Đà Lạt cuối tuần",
    starts_on: "2026-09-07",
    ends_on: "2026-09-08",
    headcount: 7,
    budget_per_person_vnd: 2_500_000,
    created_at: "2026-08-29T04:00:00Z",
    stops: [],
    ...over,
  };
}

function render(component, props) {
  return renderToStaticMarkup(React.createElement(component, props));
}

/* ------------------------------------------------ kiemTraTaoBuoiDi ------ */

test("kiemTraTaoBuoiDi nhận form hợp lệ và trả body khớp dây máy chủ", () => {
  const kq = kiemTraTaoBuoiDi(form());
  assert.equal(kq.ok, true);
  assert.deepEqual(kq.body, {
    title: "Đà Lạt cuối tuần",
    starts_on: "2026-09-07",
    ends_on: "2026-09-08",
    headcount: 7,
    budget_per_person_vnd: 2_500_000,
  });
});

test("kiemTraTaoBuoiDi từ chối title rỗng sau khi strip", () => {
  const kq = kiemTraTaoBuoiDi(form({ title: "   " }));
  assert.equal(kq.ok, false);
  assert.match(kq.loi, /tên/i);
  assert.ok(!kq.loi.includes(EM_DASH), kq.loi);
});

test("kiemTraTaoBuoiDi từ chối ngày sai định dạng", () => {
  const saiBatDau = kiemTraTaoBuoiDi(form({ starts_on: "07/09/2026" }));
  assert.equal(saiBatDau.ok, false);
  assert.match(saiBatDau.loi, /ngày/i);

  const saiKetThuc = kiemTraTaoBuoiDi(form({ ends_on: "2026-13-40" }));
  assert.equal(saiKetThuc.ok, false);
  assert.match(saiKetThuc.loi, /ngày/i);
});

test("kiemTraTaoBuoiDi từ chối ends_on trước starts_on, cho phép cùng ngày", () => {
  const truoc = kiemTraTaoBuoiDi(form({ starts_on: "2026-09-08", ends_on: "2026-09-07" }));
  assert.equal(truoc.ok, false);
  assert.match(truoc.loi, /kết thúc/i);

  const cungNgay = kiemTraTaoBuoiDi(form({ starts_on: "2026-09-07", ends_on: "2026-09-07" }));
  assert.equal(cungNgay.ok, true);
});

test("kiemTraTaoBuoiDi từ chối headcount <= 0 hoặc > 1000", () => {
  assert.equal(kiemTraTaoBuoiDi(form({ headcount: "0" })).ok, false);
  assert.equal(kiemTraTaoBuoiDi(form({ headcount: "-1" })).ok, false);
  assert.equal(kiemTraTaoBuoiDi(form({ headcount: "1001" })).ok, false);
  assert.equal(kiemTraTaoBuoiDi(form({ headcount: "1000" })).ok, true);
  assert.equal(kiemTraTaoBuoiDi(form({ headcount: "1" })).ok, true);
});

test("kiemTraTaoBuoiDi đọc ngân sách bằng parseAmountVnd, không Number()", async () => {
  const src = await readFile(join(LEN_PLAN_SRC, "buoi-di.ts"), "utf8");
  assert.match(src, /parseAmountVnd/);
  assert.doesNotMatch(src, /Number\(.*nganSach/);

  assert.equal(kiemTraTaoBuoiDi(form({ nganSach: "2.500.000" })).body.budget_per_person_vnd, 2_500_000);
  assert.equal(kiemTraTaoBuoiDi(form({ nganSach: "0" })).body.budget_per_person_vnd, 0);
  assert.equal(kiemTraTaoBuoiDi(form({ nganSach: "" })).ok, false);
  assert.equal(kiemTraTaoBuoiDi(form({ nganSach: "abc" })).ok, false);
});

test("kiemTraTaoBuoiDi cắt title và cho phép ngân sách 0", () => {
  const kq = kiemTraTaoBuoiDi(form({ title: "  Đà Lạt  ", nganSach: "0" }));
  assert.equal(kq.ok, true);
  assert.equal(kq.body.title, "Đà Lạt");
  assert.equal(kq.body.budget_per_person_vnd, 0);
});

/* ------------------------------------------------ sapXepChang ----------- */

test("sapXepChang đưa 12:30 rồi 07:00 thành 07:00 rồi 12:30", () => {
  const ra = sapXepChang([
    { at: "12:30", label: "Ăn trưa", place_name: "Xóm Lèo" },
    { at: "07:00", label: "Khởi hành", place_name: null },
  ]);
  assert.deepEqual(
    ra.map((c) => c.at),
    ["07:00", "12:30"],
  );
  assert.equal(ra[0].label, "Khởi hành");
  assert.equal(ra[1].label, "Ăn trưa");
});

test("sapXepChang ổn định khi trùng giờ: thứ tự gốc được giữ", () => {
  const ra = sapXepChang([
    { at: "11:00", label: "A", place_name: null },
    { at: "07:00", label: "B", place_name: null },
    { at: "11:00", label: "C", place_name: null },
  ]);
  assert.deepEqual(
    ra.map((c) => c.label),
    ["B", "A", "C"],
  );
});

test("sapXepChang không sửa mảng đưa vào", () => {
  const vao = [
    { at: "12:30", label: "trưa", place_name: null },
    { at: "07:00", label: "sáng", place_name: null },
  ];
  sapXepChang(vao);
  assert.equal(vao[0].at, "12:30");
});

/* ------------------------------------------------ kiemTraChang ---------- */

test("kiemTraChang nhận HH:MM 24h và nhãn có chữ", () => {
  assert.equal(kiemTraChang("07:00", "Ăn sáng").ok, true);
  assert.equal(kiemTraChang("23:59", "Bar").ok, true);
  assert.equal(kiemTraChang("00:00", "Xuất phát").ok, true);
});

test("kiemTraChang từ chối giờ không phải HH:MM 24h", () => {
  assert.equal(kiemTraChang("7:00", "Ăn sáng").ok, false);
  assert.equal(kiemTraChang("24:00", "Ăn sáng").ok, false);
  assert.equal(kiemTraChang("12:60", "Ăn sáng").ok, false);
  assert.equal(kiemTraChang("", "Ăn sáng").ok, false);
});

test("kiemTraChang từ chối nhãn rỗng sau khi strip", () => {
  const kq = kiemTraChang("07:00", "   ");
  assert.equal(kq.ok, false);
  assert.match(kq.loi, /nhãn/i);
});

/* ------------------------------------------------ nhanKhoangNgay -------- */

test("nhanKhoangNgay gộp cùng tháng thành 07 - 08/09/2026, không em-dash", () => {
  const s = nhanKhoangNgay("2026-09-07", "2026-09-08");
  assert.equal(s, "07 - 08/09/2026");
  assert.ok(!s.includes(EM_DASH), s);
  assert.ok(!s.includes(EN_DASH), s);
});

test("nhanKhoangNgay cùng ngày thì một mốc, khác tháng thì ghi đủ tháng", () => {
  assert.equal(nhanKhoangNgay("2026-09-07", "2026-09-07"), "07/09/2026");
  assert.equal(nhanKhoangNgay("2026-08-07", "2026-09-08"), "07/08 - 08/09/2026");
  assert.equal(nhanKhoangNgay("2025-12-31", "2026-01-02"), "31/12/2025 - 02/01/2026");
});

test("nhanKhoangNgay không chứa em-dash với mọi cặp đã đo", () => {
  const cap = [
    ["2026-09-07", "2026-09-08"],
    ["2026-09-07", "2026-09-07"],
    ["2026-08-07", "2026-09-08"],
    ["2025-12-31", "2026-01-02"],
  ];
  for (const [a, b] of cap) {
    const s = nhanKhoangNgay(a, b);
    assert.ok(!s.includes(EM_DASH) && !s.includes(EN_DASH), s);
  }
});

/* ------------------------------------------------ ngân sách ------------- */

test("nhanNganSach dùng formatVnd và nói đây là số tham chiếu", () => {
  const s = nhanNganSach(2_500_000);
  assert.ok(s.includes(formatVnd(2_500_000)), s);
  assert.match(s, /tham chiếu/i);
  assert.ok(!s.includes(EM_DASH), s);
});

test("tongDuKien là tích nguyên đồng, không float", () => {
  assert.equal(tongDuKien(2_500_000, 7), 17_500_000);
  assert.equal(tongDuKien(0, 7), 0);
  assert.equal(Number.isInteger(tongDuKien(2_500_000, 7)), true);
});

/* ------------------------------------------------ hướng thiết kế -------- */

test("DIRECTION_CONTRACT_BUOI_DI có đủ 5 khối THESIS/OWN-WORLD/STORY/FIRST VIEWPORT/FORM", () => {
  for (const block of ["THESIS:", "OWN-WORLD:", "STORY:", "FIRST VIEWPORT:", "FORM:"]) {
    assert.ok(DIRECTION_CONTRACT_BUOI_DI.includes(block), `thiếu khối ${block}`);
  }
});

/* ------------------------------------------------ markup ---------------- */

test("DongThoiGian: ngân sách vượt không sinh màu warn", () => {
  const markup = render(DongThoiGian, {
    buoi: buoi({
      budget_per_person_vnd: 50_000_000,
      headcount: 8,
      stops: [
        { position: 0, at: "12:30", label: "Ăn trưa", place_name: "Tiệm nướng Xóm Lèo" },
        { position: 1, at: "07:00", label: "Khởi hành", place_name: null },
      ],
    }),
    onLuu: () => {},
    onQuayLai: () => {},
  });

  assert.match(markup, /tham chiếu/i);
  assert.ok(markup.includes(formatVnd(50_000_000)), markup.slice(0, 400));
  assert.ok(
    !markup.includes(tokens.color.light.warn),
    `markup mang token warn light ${tokens.color.light.warn}`,
  );
  assert.ok(
    !markup.includes(tokens.color.dark.warn),
    `markup mang token warn dark ${tokens.color.dark.warn}`,
  );
});

test("DongThoiGian sắp chặng theo giờ khi vẽ, dù máy chủ trả 12:30 trước 07:00", () => {
  const markup = render(DongThoiGian, {
    buoi: buoi({
      stops: [
        { position: 0, at: "12:30", label: "Ăn trưa", place_name: "Xóm Lèo" },
        { position: 1, at: "07:00", label: "Khởi hành", place_name: null },
      ],
    }),
    onLuu: () => {},
    onQuayLai: () => {},
  });
  const i07 = markup.indexOf("07:00");
  const i12 = markup.indexOf("12:30");
  assert.ok(i07 !== -1 && i12 !== -1, markup.slice(0, 300));
  assert.ok(i07 < i12, "07:00 phải đứng trước 12:30 trên ray");
});

test("TaoBuoiDi: mỗi ô có tên riêng, khác placeholder, không em-dash", () => {
  const markup = render(TaoBuoiDi, { onTao: () => {}, onHuy: () => {} });
  assert.ok(!markup.includes(EM_DASH), markup.slice(0, 200));

  const labels = ["Tên chuyến", "Ngày bắt đầu", "Ngày kết thúc", "Số người", "Ngân sách mỗi người"];
  for (const label of labels) {
    assert.ok(
      markup.includes(`aria-label="${label}"`),
      `thiếu aria-label cho "${label}": ${markup.slice(0, 200)}`,
    );
  }
  assert.ok(
    !markup.includes('aria-label="Đà Lạt cuối tuần"'),
    "placeholder đang đóng vai tên ô",
  );
});

test("không file nào trong screens/len-plan chứa chuỗi tiếng Việt có em-dash", async () => {
  const files = (await readdir(LEN_PLAN_SRC)).filter((n) => /\.(ts|tsx)$/.test(n));
  assert.ok(files.length >= 4, `thiếu file: ${files.join(", ")}`);
  const viet = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]/;
  const bad = [];
  for (const name of files) {
    const src = await readFile(join(LEN_PLAN_SRC, name), "utf8");
    const re = /(["'`])((?:\\.|(?!\1).)*)\1/g;
    let m;
    while ((m = re.exec(src))) {
      if (m[2].includes(EM_DASH) && viet.test(m[2])) bad.push(`${name}: ${m[2]}`);
    }
  }
  assert.deepEqual(bad, []);
});
