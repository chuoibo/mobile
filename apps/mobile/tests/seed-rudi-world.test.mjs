/* The pure half of the demo-world seed (M7).
 *
 * Run from apps/mobile:
 *     node --test tests/seed-rudi-world.test.mjs
 */
import assert from "node:assert/strict";
import { inflateSync } from "node:zlib";
import test from "node:test";

import { HOA_DON_XOM_LEO, ROSTER, conPhaiLam, pngMau, soDienThoai, tongHoaDon } from "../tools/seed-rudi-world-lib.mjs";

test("số điện thoại tổng hợp: 10 chữ số, đầu 09, khác nhau từng người, ổn định giữa hai lần chạy", () => {
  const so = ROSTER.map((_, i) => soDienThoai(i));
  assert.equal(new Set(so).size, ROSTER.length);
  for (const s of so) assert.match(s, /^09\d{8}$/);
  assert.deepEqual(so, ROSTER.map((_, i) => soDienThoai(i)));
  assert.notEqual(soDienThoai(0, 1), soDienThoai(0, 0));
});

test("hóa đơn Xóm Lèo cộng đúng tổng canonical 1.280.000đ bằng số nguyên", () => {
  assert.equal(tongHoaDon(), 1_280_000);
  for (const [, vnd] of HOA_DON_XOM_LEO) assert.ok(Number.isInteger(vnd) && vnd > 0);
});

test("pngMau là PNG hợp lệ: chữ ký, IHDR đúng kích thước, IDAT giải nén được", () => {
  const png = pngMau(8, 6);
  assert.deepEqual([...png.subarray(0, 8)], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  assert.equal(png.subarray(12, 16).toString("ascii"), "IHDR");
  assert.equal(png.readUInt32BE(16), 8);
  assert.equal(png.readUInt32BE(20), 6);
  const idatLen = png.readUInt32BE(33);
  assert.equal(png.subarray(37, 41).toString("ascii"), "IDAT");
  const raw = inflateSync(png.subarray(41, 41 + idatLen));
  assert.equal(raw.length, (1 + 8 * 3) * 6);
  assert.equal(png.subarray(png.length - 8, png.length - 4).toString("ascii"), "IEND");
});

test("conPhaiLam: lần hai trên thế giới đã dựng là no-op", () => {
  const xong = conPhaiLam({ nhom: {}, soNguoi: 8, soThanhVien: 8, soBan: 7, soTin: 12, soTinMuon: 12, coKeo: true, coDotThu: true, coKhoanChi: true, soKyNiem: 5, soKyNiemMuon: 5 });
  assert.deepEqual(Object.values(xong).filter((v) => v !== false && v !== 0), []);
  const moi = conPhaiLam({ nhom: null, soNguoi: 8, soThanhVien: 0, soBan: 0, soTin: 0, soTinMuon: 12, coKeo: false, coDotThu: false, coKhoanChi: false, soKyNiem: 0, soKyNiemMuon: 5 });
  assert.equal(moi.taoNhom, true);
  assert.equal(moi.moiThem, 7);
  assert.equal(moi.ghiBill, true);
});
