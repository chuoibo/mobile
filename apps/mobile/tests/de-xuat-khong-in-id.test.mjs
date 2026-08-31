/* The screen that writes money into the ledger never prints a database key.
 *
 * `DeXuat` is the confirm step: the whole allocation, the person who paid up
 * front, and a button that puts all of it in the ledger. It is the last screen
 * anybody reads before the numbers become real, which makes it the worst place
 * in the app for a name to be wrong.
 *
 * It carried two of the `?? id` fallbacks that bug-050923 is made of:
 *
 *     const advancerName = people.find((p) => p.id === advancerId)?.name ?? advancerId;
 *     const gainerNames  = roundingGainers.map((id) => people.find(...)?.name ?? id);
 *
 * and `advancerName` is printed three times on the screen -- the hint under the
 * title, the "Đã ghi tài khoản nhận của X" card, and the "N người sẽ cần gửi
 * tiền cho X" line -- while `gainerNames` is the sentence explaining who eats
 * the odd dong.
 *
 * WHAT THESE CASES ARE, said plainly, because it changes what they are worth.
 * `roundingGainers` is `allocation.rounding_gainers` off `POST /expenses`: the
 * SERVER decides who carries the odd dong, keyed against the roster it holds.
 * `advancerId` travels with the draft. On today's one call site both do resolve
 * inside `proposal.participants`, so these are not a fifth live sighting of the
 * leak; they are the SHAPE of it, on the screen where it would cost the most,
 * pinned so it cannot become one. `docChiaBill` in the same client already
 * answers "against the roster IT has" -- the day anything routes that answer
 * into this screen, the old code prints a UUID and the new code says a name.
 *
 * The cases are written against a person the group knows and the bill does not,
 * because that is the gap `labelInGroup` exists to close, plus a person neither
 * list can place, because "Thành viên" and a raw id are different answers and
 * only one of them is honest.
 */

import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { DeXuat } from "../dist-test/screens/DeXuat.js";
import { TEN_CHUA_BIET } from "../dist-test/screens/chat/tin-nhan.js";

/* The seeded group's real ids, the same ones the other three bug-050923 files
 * use, so a failure here reads against the same people. */
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f";
const NGOC = "e3a44e25-4547-508a-8f4d-9b2495c3325f";
/* In the group's ledger, absent from its active membership. */
const LA = "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8";

const HINH_DANG_UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/** The bill somebody typed. Ngọc is not on it. */
const TREN_BILL = [
  { id: MINH, name: "Minh" },
  { id: TRANG, name: "Trang" },
];

/** The group's active membership, which is what the server answers against. */
const TRONG_NHOM = [
  { id: MINH, name: "Minh" },
  { id: TRANG, name: "Trang" },
  { id: NGOC, name: "Ngọc" },
];

function ve({ advancerId = MINH, roundingGainers = [], nhom = TRONG_NHOM } = {}) {
  return renderToStaticMarkup(
    React.createElement(DeXuat, {
      proposal: {
        participants: TREN_BILL,
        allocations: { [MINH]: 505094, [TRANG]: 374262 },
        roundingGainers,
        totalVnd: 879356,
        advancerId,
        occasion: "bữa tối",
      },
      nhom,
      taiKhoanNhan: "Vietcombank ****1234",
      onConfirm: () => {},
      onBack: () => {},
    }),
  );
}

test("người trả trước mà máy chủ biết còn bill chưa có hiện ra bằng TÊN", () => {
  const html = ve({ advancerId: NGOC });

  assert.doesNotMatch(
    html,
    HINH_DANG_UUID,
    "màn chốt tiền in ra một id thô ở chỗ đáng lẽ là tên người",
  );
  assert.match(html, /Ngọc đã trả trước/);
  // The same name has to reach all three places it is printed, not just the
  // first one somebody looked at.
  assert.match(html, /Đã ghi tài khoản nhận của Ngọc/);
  assert.match(html, /cần gửi tiền cho Ngọc/);
});

test("người chịu đồng lẻ do máy chủ chọn hiện ra bằng TÊN", () => {
  const html = ve({ roundingGainers: [NGOC] });

  assert.doesNotMatch(html, HINH_DANG_UUID, "câu giải thích đồng lẻ in ra id thô");
  assert.match(html, /Chia không hết chẵn\. Ngọc chịu thêm 1đ lẻ/);
});

test("người không danh sách nào gọi tên được thì nói thẳng, không in id", () => {
  const html = ve({ advancerId: LA, roundingGainers: [LA] });

  assert.doesNotMatch(html, HINH_DANG_UUID, "người lạ bị in ra bằng id");
  assert.match(html, new RegExp(`${TEN_CHUA_BIET} đã trả trước`));
  assert.match(html, new RegExp(`${TEN_CHUA_BIET} chịu thêm 1đ lẻ`));
});

test("người trên bill vẫn hiện đúng tên khi nhóm rỗng", () => {
  // The floor. Without it, "no id on screen" could be satisfied by a screen
  // that stopped naming anybody at all.
  const html = ve({ advancerId: TRANG, roundingGainers: [MINH], nhom: [] });

  assert.doesNotMatch(html, HINH_DANG_UUID);
  assert.match(html, /Trang đã trả trước/);
  assert.match(html, /Minh chịu thêm 1đ lẻ/);
});
