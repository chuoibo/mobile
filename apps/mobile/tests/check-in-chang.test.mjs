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
const STOP_A = "11111111-aaaa-4bbb-8ccc-00000000a001";
const STOP_B = "11111111-aaaa-4bbb-8ccc-00000000a002";
const TOI = "22222222-aaaa-4bbb-8ccc-00000000a001";
const NGUOI_KHAC = "22222222-aaaa-4bbb-8ccc-00000000a002";

test("danh sách rỗng gom ra bảng rỗng, không ném", () => {
  assert.deepEqual(nhomCheckInTheoChang([]), {});
});

/* ---------------------------------------------------------- nhanDaToi --- */

test("chưa ai tới thì không có nhãn nào", () => {
  assert.equal(nhanDaToi([]), null);
});