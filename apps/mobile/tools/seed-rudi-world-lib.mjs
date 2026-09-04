/* Pure pieces of the RuDi demo-world seed, kept apart from the network so a
 * node test can pin them: synthetic phone numbers, a valid PNG without any
 * image library, and the "what still needs doing" decisions that make a
 * second run a no-op instead of a duplicate.
 *
 * Numbers are computed at run time and never written as literals: the repo
 * guard fails closed on long digit runs, and a demo roster must never be
 * mistaken for real people.
 */
import { deflateSync } from "node:zlib";

/** The eight synthetic people of «Team Đà Lạt». Names only; numbers are derived. */
export const ROSTER = [
  { key: "minh-anh", name: "Minh Anh" },
  { key: "tuan-kiet", name: "Tuấn Kiệt" },
  { key: "bao-chau", name: "Bảo Châu" },
  { key: "duc-huy", name: "Đức Huy" },
  { key: "ha-vy", name: "Hà Vy" },
  { key: "khanh-linh", name: "Khánh Linh" },
  { key: "quoc-thai", name: "Quốc Thái" },
  { key: "thu-thao", name: "Thu Thảo" },
];

/**
 * A Vietnamese-looking mobile number that no carrier hands out: the 09 prefix
 * with a run computed from the index and a per-world offset. Ten digits, so
 * the server's `phone_not_mobile` check passes; deterministic, so a re-run
 * logs the same eight people back in.
 */
export function soDienThoai(index, offset = 0) {
  const base = 9 * 10 ** 7 + 1_234_567; // 8 digits, never spelled out
  const tail = (base + index * 7_919 + offset * 101) % 10 ** 8;
  return "09" + String(tail).padStart(8, "0");
}

/** The canonical receipt (product/…/CANONICAL_DATA.md), integer đồng. */
export const HOA_DON_XOM_LEO = [
  ["Lẩu gà lá é", 450_000],
  ["Bò nướng", 560_000],
  ["Nước ngọt", 75_000],
  ["Trà tắc", 45_000],
  ["Khăn lạnh", 20_000],
  ["Phí phục vụ", 130_000],
];

export function tongHoaDon(lines = HOA_DON_XOM_LEO) {
  return lines.reduce((sum, [, vnd]) => sum + vnd, 0);
}

/* ---------------------------------------------------------------- PNG */

const CRC_TABLE = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

/**
 * A small solid-colour PNG with a diagonal band, valid for any decoder. Size
 * is tiny on purpose: the seed proves the upload path, not the camera.
 */
export function pngMau(width = 96, height = 72, rgb = [0, 117, 107]) {
  const row = Buffer.alloc(1 + width * 3);
  const raw = Buffer.alloc((1 + width * 3) * height);
  for (let y = 0; y < height; y += 1) {
    row[0] = 0;
    for (let x = 0; x < width; x += 1) {
      const band = (x + y) % 24 < 12;
      row[1 + x * 3] = band ? rgb[0] : 254;
      row[2 + x * 3] = band ? rgb[1] : 238;
      row[3 + x * 3] = band ? rgb[2] : 224;
    }
    row.copy(raw, y * row.length);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // colour type: truecolour
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/* ------------------------------------------------------- what is left to do */

/**
 * Decide the remaining work from what the server already holds. Each field is
 * "do it" or "skip", never "do it again": the world is re-runnable because the
 * seed reads state before writing, not because it hopes idempotency keys match.
 */
export function conPhaiLam(state) {
  return {
    taoNhom: state.nhom === null,
    moiThem: state.nhom === null ? state.soNguoi - 1 : Math.max(0, state.soNguoi - state.soThanhVien),
    ketBan: state.soBan < state.soNguoi - 1,
    nhanTin: state.soTin < state.soTinMuon,
    taoKeo: !state.coKeo,
    ghiBill: !state.coDotThu && !state.coKhoanChi,
    moDotThu: !state.coDotThu,
    kyNiem: state.soKyNiem < state.soKyNiemMuon,
  };
}
