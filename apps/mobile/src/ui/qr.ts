/** Byte-mode QR encoder (ISO/IEC 18004), EC level M, versions 1–15.
 *
 * Turns a UTF-8 string — typically a server-built VietQR EMVCo payload — into
 * a module matrix the UI can paint with Views. No quiet zone is included.
 */

export type QrMatrix = {
  size: number;
  modules: boolean[][];
  version: number;
  mask: number;
};

export class QrError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "QrError";
  }
}

export function encodeQr(text: string): QrMatrix {
  const bytes = utf8Bytes(text);
  const version = chooseVersion(bytes.length);
  const codewords = interleave(buildDataCodewords(bytes, version), version);
  const size = 17 + 4 * version;
  const modules = grid(size, false);
  const reserved = grid(size, false);
  drawFinders(modules, reserved);
  drawTiming(modules, reserved);
  drawAlignments(modules, reserved, version);
  modules[4 * version + 9][8] = true;
  reserved[4 * version + 9][8] = true;
  reserveFormat(reserved);
  drawVersionInfo(modules, reserved, version);
  placeData(modules, reserved, codewords);

  let bestMask = 0;
  let bestPenalty = Infinity;
  let best = modules;
  for (let mask = 0; mask < 8; mask++) {
    const trial = cloneGrid(modules);
    applyMask(trial, reserved, mask);
    writeFormat(trial, mask);
    const score = penalty(trial);
    if (score < bestPenalty) {
      bestPenalty = score;
      bestMask = mask;
      best = trial;
    }
  }
  return { size, modules: best, version, mask: bestMask };
}

// --- Capacity (EC level M) ------------------------------------------------

/** [ecPerBlock, group1Blocks, group1Data, group2Blocks, group2Data] */
const EC_M: ReadonlyArray<readonly [number, number, number, number, number]> = [
  [0, 0, 0, 0, 0],
  [10, 1, 16, 0, 0],
  [16, 1, 28, 0, 0],
  [26, 1, 44, 0, 0],
  [18, 2, 32, 0, 0],
  [24, 2, 43, 0, 0],
  [16, 4, 27, 0, 0],
  [18, 4, 31, 0, 0],
  [22, 2, 38, 2, 39],
  [22, 3, 36, 2, 37],
  [26, 4, 43, 1, 44],
  [30, 1, 50, 4, 51],
  [22, 6, 36, 2, 37],
  [22, 8, 37, 1, 38],
  [24, 4, 40, 5, 41],
  [24, 5, 41, 5, 42],
];

const ALIGNMENT: ReadonlyArray<ReadonlyArray<number>> = [
  [],
  [],
  [6, 18],
  [6, 22],
  [6, 26],
  [6, 30],
  [6, 34],
  [6, 22, 38],
  [6, 24, 42],
  [6, 26, 46],
  [6, 28, 50],
  [6, 30, 54],
  [6, 32, 58],
  [6, 34, 62],
  [6, 26, 46, 66],
  [6, 26, 48, 70],
];

function dataCapacity(version: number): number {
  const spec = EC_M[version];
  return spec[1] * spec[2] + spec[3] * spec[4];
}

function countBits(version: number): number {
  return version <= 9 ? 8 : 16;
}

function chooseVersion(byteLen: number): number {
  for (let version = 1; version <= 15; version++) {
    if (version <= 9 && byteLen > 255) continue;
    const needed = 4 + countBits(version) + 8 * byteLen;
    if (needed <= dataCapacity(version) * 8) return version;
  }
  throw new QrError("PAYLOAD_TOO_LONG");
}

// --- UTF-8 (no TextEncoder — missing on older React Native) ---------------

function utf8Bytes(text: string): number[] {
  const out: number[] = [];
  for (let i = 0; i < text.length; i++) {
    let cp = text.charCodeAt(i);
    if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < text.length) {
      const lo = text.charCodeAt(i + 1);
      if (lo >= 0xdc00 && lo <= 0xdfff) {
        cp = ((cp - 0xd800) << 10) + (lo - 0xdc00) + 0x10000;
        i++;
      }
    }
    if (cp <= 0x7f) {
      out.push(cp);
    } else if (cp <= 0x7ff) {
      out.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    } else if (cp <= 0xffff) {
      out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    } else {
      out.push(
        0xf0 | (cp >> 18),
        0x80 | ((cp >> 12) & 0x3f),
        0x80 | ((cp >> 6) & 0x3f),
        0x80 | (cp & 0x3f),
      );
    }
  }
  return out;
}

// --- Bit stream + data codewords ------------------------------------------

function buildDataCodewords(bytes: number[], version: number): number[] {
  const capacityBits = dataCapacity(version) * 8;
  const bits: number[] = [];
  putBits(bits, 0b0100, 4);
  putBits(bits, bytes.length, countBits(version));
  for (const b of bytes) putBits(bits, b, 8);
  const leftover = capacityBits - bits.length;
  if (leftover > 0) putBits(bits, 0, leftover < 4 ? leftover : 4);
  while (bits.length % 8 !== 0) bits.push(0);
  let pad = 0xec;
  while (bits.length < capacityBits) {
    putBits(bits, pad, 8);
    pad = pad === 0xec ? 0x11 : 0xec;
  }
  return bitsToBytes(bits);
}

function putBits(bits: number[], value: number, width: number): void {
  for (let i = width - 1; i >= 0; i--) bits.push((value >> i) & 1);
}

function bitsToBytes(bits: number[]): number[] {
  const out: number[] = [];
  for (let i = 0; i < bits.length; i += 8) {
    let b = 0;
    for (let j = 0; j < 8; j++) b = (b << 1) | bits[i + j];
    out.push(b);
  }
  return out;
}

// --- Reed-Solomon over GF(256), primitive 0x11D, roots α^0..α^{n-1} -------

const EXP: number[] = new Array(512);
const LOG: number[] = new Array(256);
{
  let x = 1;
  for (let i = 0; i < 255; i++) {
    EXP[i] = x;
    LOG[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11d;
  }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
}

function gfMul(a: number, b: number): number {
  if (a === 0 || b === 0) return 0;
  return EXP[LOG[a] + LOG[b]];
}

/** Generator coefficients without the leading x^degree term (always 1). */
function rsDivisor(degree: number): number[] {
  const result = new Array<number>(degree).fill(0);
  result[degree - 1] = 1;
  let root = 1;
  for (let i = 0; i < degree; i++) {
    for (let j = 0; j < degree; j++) {
      result[j] = gfMul(result[j], root);
      if (j + 1 < degree) result[j] ^= result[j + 1];
    }
    root = gfMul(root, 2);
  }
  return result;
}

function rsRemainder(data: number[], divisor: number[]): number[] {
  const result = new Array<number>(divisor.length).fill(0);
  for (const b of data) {
    const factor = b ^ result[0];
    for (let i = 0; i < result.length - 1; i++) result[i] = result[i + 1];
    result[result.length - 1] = 0;
    if (factor !== 0) {
      for (let i = 0; i < result.length; i++) result[i] ^= gfMul(divisor[i], factor);
    }
  }
  return result;
}

function interleave(data: number[], version: number): number[] {
  const spec = EC_M[version];
  const ecPer = spec[0];
  const divisor = rsDivisor(ecPer);
  const blocks: { data: number[]; ecc: number[] }[] = [];
  let offset = 0;
  for (let group = 0; group < 2; group++) {
    const count = spec[group === 0 ? 1 : 3];
    const dataLen = spec[group === 0 ? 2 : 4];
    for (let i = 0; i < count; i++) {
      const slice = data.slice(offset, offset + dataLen);
      offset += dataLen;
      blocks.push({ data: slice, ecc: rsRemainder(slice, divisor) });
    }
  }
  const out: number[] = [];
  const maxData = Math.max(spec[2], spec[4]);
  for (let i = 0; i < maxData; i++) {
    for (const block of blocks) {
      if (i < block.data.length) out.push(block.data[i]);
    }
  }
  for (let i = 0; i < ecPer; i++) {
    for (const block of blocks) out.push(block.ecc[i]);
  }
  return out;
}

// --- Function patterns ----------------------------------------------------

function grid(size: number, fill: boolean): boolean[][] {
  const out: boolean[][] = [];
  for (let i = 0; i < size; i++) out.push(new Array<boolean>(size).fill(fill));
  return out;
}

function cloneGrid(src: boolean[][]): boolean[][] {
  return src.map((row) => row.slice());
}

function drawFinders(modules: boolean[][], reserved: boolean[][]): void {
  const size = modules.length;
  const corners: [number, number][] = [
    [0, 0],
    [0, size - 7],
    [size - 7, 0],
  ];
  for (const [row0, col0] of corners) {
    for (let r = -1; r <= 7; r++) {
      for (let c = -1; c <= 7; c++) {
        const row = row0 + r;
        const col = col0 + c;
        if (row < 0 || col < 0 || row >= size || col >= size) continue;
        const onRing = r >= 0 && r <= 6 && c >= 0 && c <= 6 && (r === 0 || r === 6 || c === 0 || c === 6);
        const inCore = r >= 2 && r <= 4 && c >= 2 && c <= 4;
        modules[row][col] = onRing || inCore;
        reserved[row][col] = true;
      }
    }
  }
}

function drawTiming(modules: boolean[][], reserved: boolean[][]): void {
  const size = modules.length;
  for (let i = 0; i < size; i++) {
    if (!reserved[6][i]) {
      modules[6][i] = i % 2 === 0;
      reserved[6][i] = true;
    }
    if (!reserved[i][6]) {
      modules[i][6] = i % 2 === 0;
      reserved[i][6] = true;
    }
  }
}

function overlapsFinder(row: number, col: number, size: number): boolean {
  if (row <= 8 && col <= 8) return true;
  if (row <= 8 && col >= size - 9) return true;
  if (row >= size - 9 && col <= 8) return true;
  return false;
}

function drawAlignments(modules: boolean[][], reserved: boolean[][], version: number): void {
  const size = modules.length;
  const centers = ALIGNMENT[version];
  for (const row of centers) {
    for (const col of centers) {
      if (overlapsFinder(row, col, size)) continue;
      for (let dr = -2; dr <= 2; dr++) {
        for (let dc = -2; dc <= 2; dc++) {
          const onRing = dr === -2 || dr === 2 || dc === -2 || dc === 2;
          modules[row + dr][col + dc] = onRing || (dr === 0 && dc === 0);
          reserved[row + dr][col + dc] = true;
        }
      }
    }
  }
}

function reserveFormat(reserved: boolean[][]): void {
  const size = reserved.length;
  for (let i = 0; i < 9; i++) {
    reserved[8][i] = true;
    reserved[i][8] = true;
  }
  for (let i = 0; i < 8; i++) {
    reserved[8][size - 1 - i] = true;
    reserved[size - 1 - i][8] = true;
  }
}

function versionInfo(version: number): number {
  let rem = version << 12;
  for (let i = 17; i >= 12; i--) {
    if ((rem >>> i) & 1) rem ^= 0x1f25 << (i - 12);
  }
  return (version << 12) | (rem & 0xfff);
}

function drawVersionInfo(modules: boolean[][], reserved: boolean[][], version: number): void {
  if (version < 7) return;
  const size = modules.length;
  const bits = versionInfo(version);
  let k = 0;
  for (let i = 0; i < 6; i++) {
    for (let j = 0; j < 3; j++) {
      const dark = ((bits >> k) & 1) === 1;
      modules[i][size - 11 + j] = dark;
      reserved[i][size - 11 + j] = true;
      modules[size - 11 + j][i] = dark;
      reserved[size - 11 + j][i] = true;
      k++;
    }
  }
}

/** BCH(15,5) on (ecM=00 << 3 | mask), then XOR the 0x5412 mask. */
function formatInfo(mask: number): number {
  const data = mask;
  let rem = data << 10;
  for (let i = 14; i >= 10; i--) {
    if ((rem >>> i) & 1) rem ^= 0x537 << (i - 10);
  }
  return ((data << 10) | (rem & 0x3ff)) ^ 0x5412;
}

function writeFormat(modules: boolean[][], mask: number): void {
  const size = modules.length;
  const bits = formatInfo(mask);
  const bit = (i: number): boolean => ((bits >> i) & 1) === 1;
  for (let i = 0; i <= 5; i++) modules[i][8] = bit(i);
  modules[7][8] = bit(6);
  modules[8][8] = bit(7);
  modules[8][7] = bit(8);
  for (let i = 9; i <= 14; i++) modules[8][14 - i] = bit(i);
  for (let i = 0; i <= 7; i++) modules[8][size - 1 - i] = bit(i);
  for (let i = 8; i <= 14; i++) modules[size - 15 + i][8] = bit(i);
  modules[size - 8][8] = true;
}

function placeData(modules: boolean[][], reserved: boolean[][], codewords: number[]): void {
  const size = modules.length;
  const dataBits = codewords.length * 8;
  let i = 0;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    for (let vert = 0; vert < size; vert++) {
      for (let j = 0; j < 2; j++) {
        const col = right - j;
        const upward = ((right + 1) & 2) === 0;
        const row = upward ? size - 1 - vert : vert;
        if (reserved[row][col]) continue;
        let dark = false;
        if (i < dataBits) {
          dark = ((codewords[i >> 3] >> (7 - (i & 7))) & 1) === 1;
        }
        modules[row][col] = dark;
        i++;
      }
    }
  }
}

// --- Masks + penalty (ISO 18004 §8.8) -------------------------------------

function masked(mask: number, row: number, col: number): boolean {
  switch (mask) {
    case 0:
      return (row + col) % 2 === 0;
    case 1:
      return row % 2 === 0;
    case 2:
      return col % 3 === 0;
    case 3:
      return (row + col) % 3 === 0;
    case 4:
      return (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0;
    case 5:
      return ((row * col) % 2) + ((row * col) % 3) === 0;
    case 6:
      return (((row * col) % 2) + ((row * col) % 3)) % 2 === 0;
    default:
      return (((row + col) % 2) + ((row * col) % 3)) % 2 === 0;
  }
}

function applyMask(modules: boolean[][], reserved: boolean[][], mask: number): void {
  const size = modules.length;
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      if (!reserved[row][col] && masked(mask, row, col)) {
        modules[row][col] = !modules[row][col];
      }
    }
  }
}

function penalty(modules: boolean[][]): number {
  return penaltyN1(modules) + penaltyN2(modules) + penaltyN3(modules) + penaltyN4(modules);
}

function penaltyN1(modules: boolean[][]): number {
  const size = modules.length;
  let score = 0;
  for (let row = 0; row < size; row++) score += runPenalty(modules[row]);
  for (let col = 0; col < size; col++) {
    const line: boolean[] = new Array(size);
    for (let row = 0; row < size; row++) line[row] = modules[row][col];
    score += runPenalty(line);
  }
  return score;
}

function runPenalty(line: boolean[]): number {
  let score = 0;
  let run = 1;
  for (let i = 1; i < line.length; i++) {
    if (line[i] === line[i - 1]) {
      run++;
    } else {
      if (run >= 5) score += run - 2;
      run = 1;
    }
  }
  if (run >= 5) score += run - 2;
  return score;
}

function penaltyN2(modules: boolean[][]): number {
  const size = modules.length;
  let score = 0;
  for (let row = 0; row < size - 1; row++) {
    for (let col = 0; col < size - 1; col++) {
      const v = modules[row][col];
      if (v === modules[row][col + 1] && v === modules[row + 1][col] && v === modules[row + 1][col + 1]) {
        score += 3;
      }
    }
  }
  return score;
}

function penaltyN3(modules: boolean[][]): number {
  const size = modules.length;
  let score = 0;
  for (let row = 0; row < size; row++) score += finderLikePenalty(modules[row]);
  for (let col = 0; col < size; col++) {
    const line: boolean[] = new Array(size);
    for (let row = 0; row < size; row++) line[row] = modules[row][col];
    score += finderLikePenalty(line);
  }
  return score;
}

/** 1:1:3:1:1 finder-like run with 4 light modules on either side. */
function finderLikePenalty(line: boolean[]): number {
  let score = 0;
  let bits = 0;
  for (let i = 0; i < line.length; i++) {
    bits = ((bits << 1) & 0x7ff) | (line[i] ? 1 : 0);
    if (i >= 10 && (bits === 0x05d || bits === 0x5d0)) score += 40;
  }
  return score;
}

function penaltyN4(modules: boolean[][]): number {
  const size = modules.length;
  const total = size * size;
  let dark = 0;
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      if (modules[row][col]) dark++;
    }
  }
  return Math.floor((Math.abs(dark * 2 - total) * 10) / total) * 10;
}
