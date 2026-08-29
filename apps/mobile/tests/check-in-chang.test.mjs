/* F46 check-in theo chặng: bucketing, nhãn, và cái KHÔNG được lên màn.
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node --test tests/check-in-chang.test.mjs
 *
 * Hai loại ca ở đây:
 *
 * 1. Bucketing thuần. Một lỗi gom nhóm hiện check-in của người này dưới chặng
 *    của người khác — sai sự thật, và nhìn màn hình thì vẫn "có chữ" nên trông
 *    như đang chạy đúng. Chạy được dưới bare node nên nó không núp sau màn.
 * 2. Markup thật do react-native-web sinh ra. Tính chất cần giữ là một tính
 *    chất PHỦ ĐỊNH — không toạ độ nào lên màn — và một phủ định chỉ đáng khẳng
 *    định trên chuỗi mà trình duyệt thật sự nhận.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  daCheckIn,
  nhanDaToi,
  nhomCheckInTheoChang,
} from "../dist-test/screens/len-plan/buoi-di.js";
import { DongThoiGian } from "../dist-test/screens/len-plan/DongThoiGian.js";

const STOP_A = "11111111-aaaa-4bbb-8ccc-00000000a001";
const STOP_B = "11111111-aaaa-4bbb-8ccc-00000000a002";
const TOI = "22222222-aaaa-4bbb-8ccc-00000000a001";
const NGUOI_KHAC = "22222222-aaaa-4bbb-8ccc-00000000a002";

function ci(over = {}) {
  return {
    id: "33333333-aaaa-4bbb-8ccc-00000000a001",
    stop_id: STOP_A,
    person_id: TOI,
    display_name: "Minh Anh",
    created_at: "2026-08-29T04:00:00Z",
    ...over,
  };
}

function chang(over = {}) {
  return {
    id: STOP_A,
    position: 0,
    at: "07:00",
    label: "Khởi hành",
    place_name: null,
    ...over,
  };
}

function buoi(stops) {
  return {
    id: "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
    context_id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    created_by_id: TOI,
    title: "Đà Lạt cuối tuần",
    starts_on: "2026-09-07",
    ends_on: "2026-09-08",
    headcount: 7,
    budget_per_person_vnd: 2_500_000,
    created_at: "2026-08-29T04:00:00Z",
    stops,
  };
}

function render(props) {
  return renderToStaticMarkup(
    React.createElement(DongThoiGian, {
      buoi: buoi([chang(), chang({ id: STOP_B, position: 1, at: "12:00", label: "Ăn trưa" })]),
      onLuu: () => {},
      onQuayLai: () => {},
      ...props,
    }),
  );
}

/* ------------------------------------------------ nhomCheckInTheoChang -- */

test("gom check-in đúng chặng của nó, không lẫn sang chặng khác", () => {
  const theo = nhomCheckInTheoChang([
    ci({ id: "a", stop_id: STOP_A, person_id: TOI }),
    ci({ id: "b", stop_id: STOP_B, person_id: NGUOI_KHAC }),
    ci({ id: "c", stop_id: STOP_A, person_id: NGUOI_KHAC }),
  ]);

  assert.deepEqual(
    theo[STOP_A].map((c) => c.id),
    ["a", "c"],
  );
  assert.deepEqual(
    theo[STOP_B].map((c) => c.id),
    ["b"],
  );
});

test("chặng chưa ai tới không có khoá trong bảng gom", () => {
  const theo = nhomCheckInTheoChang([ci({ stop_id: STOP_A })]);
  assert.equal(theo[STOP_B], undefined);
});

test("danh sách rỗng gom ra bảng rỗng, không ném", () => {
  assert.deepEqual(nhomCheckInTheoChang([]), {});
});

test("trong một chặng, người tới trước đứng trước", () => {
  const theo = nhomCheckInTheoChang([
    ci({ id: "muon", created_at: "2026-08-29T09:00:00Z" }),
    ci({ id: "som", created_at: "2026-08-29T04:00:00Z" }),
  ]);
  assert.deepEqual(
    theo[STOP_A].map((c) => c.id),
    ["som", "muon"],
  );
});

/* ---------------------------------------------------------- daCheckIn --- */

test("daCheckIn đúng khi chính mình đã tới", () => {
  assert.equal(daCheckIn([ci({ person_id: TOI })], TOI), true);
});

test("daCheckIn sai khi chỉ người khác đã tới", () => {
  assert.equal(daCheckIn([ci({ person_id: NGUOI_KHAC })], TOI), false);
});

test("daCheckIn sai khi chưa biết mình là ai", () => {
  assert.equal(daCheckIn([ci({ person_id: TOI })], null), false);
});

/* ---------------------------------------------------------- nhanDaToi --- */

test("chưa ai tới thì không có nhãn nào", () => {
  assert.equal(nhanDaToi([]), null);
});

test("một người thì gọi tên", () => {
  assert.equal(nhanDaToi([ci({ display_name: "Minh Anh" })]), "Minh Anh đã tới");
});

test("hai người thì gọi cả hai tên", () => {
  assert.equal(
    nhanDaToi([ci({ display_name: "Minh Anh" }), ci({ display_name: "Quyên" })]),
    "Minh Anh, Quyên đã tới",
  );
});

test("từ ba người trở lên thì đếm, không đẩy kế hoạch khỏi màn", () => {
  assert.equal(
    nhanDaToi([ci(), ci(), ci()]),
    "3 người đã tới",
  );
});

test("thiếu tên hiển thị thì đọc 'Một người', không phải một id", () => {
  const nhan = nhanDaToi([ci({ display_name: null })]);
  assert.equal(nhan, "Một người đã tới");
  assert.ok(!nhan.includes(TOI), "id lọt vào chỗ đáng lẽ là tên");
});

/* ------------------------------------------------------------ markup ---- */

test("dòng thời gian nói ai đã tới chặng nào", () => {
  const markup = render({
    checkins: [ci({ stop_id: STOP_A, display_name: "Minh Anh" })],
    toiId: NGUOI_KHAC,
    onCheckIn: () => {},
  });

  assert.ok(markup.includes("Minh Anh đã tới"), markup.slice(0, 400));
});

test("chặng chưa ai tới không mang nhãn của chặng khác", () => {
  const markup = render({
    checkins: [ci({ stop_id: STOP_A, display_name: "Minh Anh" })],
    toiId: NGUOI_KHAC,
    onCheckIn: () => {},
  });

  // Đúng một lần, không phải một lần mỗi chặng.
  const soLan = markup.split("Minh Anh đã tới").length - 1;
  assert.equal(soLan, 1);
});

test("chưa tới thì nút mời bấm; đã tới rồi thì nút tự nói và tắt", () => {
  const chuaToi = render({ checkins: [], toiId: TOI, onCheckIn: () => {} });
  assert.ok(chuaToi.includes("Đã tới"), chuaToi.slice(0, 400));
  assert.ok(!chuaToi.includes("Bạn đã tới"));

  const roi = render({
    checkins: [ci({ stop_id: STOP_A, person_id: TOI })],
    toiId: TOI,
    onCheckIn: () => {},
  });
  assert.ok(roi.includes("Bạn đã tới"), roi.slice(0, 400));
});

test("không có onCheckIn thì không dựng nút chết", () => {
  const markup = render({ checkins: [], toiId: TOI });
  assert.ok(!markup.includes("Đã tới"), markup.slice(0, 400));
});

test("không toạ độ nào lên màn, kể cả khi máy chủ lỡ gửi kèm", () => {
  // Cố tình nhét toạ độ vào dữ liệu vào, để ca này đo màn hình chứ không đo
  // kiểu TypeScript — kiểu bị xoá lúc chạy, còn màn hình thì không.
  const markup = render({
    checkins: [
      ci({
        stop_id: STOP_A,
        display_name: "Minh Anh",
        lat: 11.9404,
        lng: 108.4383,
      }),
    ],
    toiId: TOI,
    onCheckIn: () => {},
  });

  for (const dau of ["11.9404", "108.4383", "lat", "lng"]) {
    assert.ok(!markup.includes(dau), `toạ độ lên màn: ${dau}`);
  }
});
