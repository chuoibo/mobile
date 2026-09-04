/* Điểm đến (M10, ADR-0018): danh sách, lựa chọn, và bốn câu «gần tôi».
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-diem-den.test.mjs
 *
 * Điều đáng gác nhất là chỗ dễ nói dối nhất: khi máy chủ trả `nearest: null`
 * (không nơi nào đủ gần), màn KHÔNG được chọn đại nơi đầu danh sách. Kế đó là
 * luật ADR-0018: toạ độ chỉ đi trong đúng một request, và không nằm lại đâu.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  cauGanToi,
  cauKhoangCach,
  docDiemDen,
  dongPhuDiemDen,
} from "../dist-test/rudi/kham-pha/diem-den.js";

const DA_LAT = {
  id: "d-da-lat",
  name: "Đà Lạt",
  province: "Lâm Đồng",
  blurb: "Thành phố sương mù",
  lat: 11.94,
  lng: 108.45,
  distance_km: 4.2,
};

function traLoi(than) {
  return async (url, init) => {
    traLoi.daGoi.push({ url: String(url), init });
    return {
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => than,
      text: async () => JSON.stringify(than),
    };
  };
}

test("không gửi toạ độ thì đường dẫn không mang toạ độ", async () => {
  const goc = globalThis.fetch;
  traLoi.daGoi = [];
  globalThis.fetch = traLoi({ destinations: [DA_LAT], nearest: null });
  try {
    const ra = await docDiemDen();
    assert.equal(ra.diemDen.length, 1);
    assert.equal(ra.ganNhat, null);
  } finally {
    globalThis.fetch = goc;
  }
  assert.match(traLoi.daGoi[0].url, /\/destinations$/);
  assert.ok(!/lat=|lng=/.test(traLoi.daGoi[0].url));
});

test("toạ độ đi trong ĐÚNG một lời gọi, và chỉ ở đó", async () => {
  const goc = globalThis.fetch;
  traLoi.daGoi = [];
  globalThis.fetch = traLoi({ destinations: [DA_LAT], nearest: DA_LAT });
  try {
    const ra = await docDiemDen({ lat: 11.9, lng: 108.4 });
    assert.equal(ra.ganNhat.name, "Đà Lạt");
  } finally {
    globalThis.fetch = goc;
  }
  assert.equal(traLoi.daGoi.length, 1, "một lời gọi, không hơn");
  assert.match(traLoi.daGoi[0].url, /lat=11\.9&lng=108\.4/);
  // Không có body nào mang toạ độ đi tiếp, và không lời gọi thứ hai nào.
  assert.equal(traLoi.daGoi[0].init.body, undefined);
});

test("«không nơi nào đủ gần» là một câu riêng, không phải nơi đầu danh sách", () => {
  assert.match(
    cauGanToi({ kind: "xong", ganNhat: null }),
    /chưa nằm trong vùng RuDi biết/,
  );
  assert.match(cauGanToi({ kind: "xong", ganNhat: DA_LAT }), /Gần bạn: Đà Lạt/);
  assert.match(cauGanToi({ kind: "tu-choi" }), /Chưa bật vị trí/);
  assert.match(cauGanToi({ kind: "chua-hoi" }), /Dùng vị trí/);
  assert.match(cauGanToi({ kind: "dang-hoi" }), /Đang hỏi/);
});

test("khoảng cách chỉ hiện khi có người đo", () => {
  assert.equal(cauKhoangCach({ distanceKm: 4.2 }), "Cách bạn 4.2 km");
  assert.equal(cauKhoangCach({ distanceKm: null }), null);
});

test("dòng phụ ghép tỉnh với khoảng cách, bỏ phần rỗng", () => {
  const doc = (o) => ({
    id: o.id ?? "x",
    name: o.name ?? "X",
    province: o.province ?? null,
    blurb: null,
    lat: 0,
    lng: 0,
    distanceKm: o.distanceKm ?? null,
  });
  assert.equal(dongPhuDiemDen(doc({ province: "Lâm Đồng", distanceKm: 4.2 })), "Lâm Đồng · Cách bạn 4.2 km");
  assert.equal(dongPhuDiemDen(doc({ province: "Lâm Đồng" })), "Lâm Đồng");
  assert.equal(dongPhuDiemDen(doc({})), "");
});
