/** Why this file exists at all: the first real request this screen sends is
 *  under a person's name, and that person's id is not a constant we are
 *  allowed to write down.
 *
 * `scripts/seed_demo_data.py` mints every demo person as
 * `uuid5(da1ada1a-…, "person:<slug>")`. `nhom-demo.ts` already carries the
 * resulting ids, copied by hand. Copied values in two files drift, and the
 * drift is silent -- the screen asks about a person the database has never
 * heard of and renders a truthful, correct, empty thread. The seed script's
 * own comment also rules out writing the ids as padded UUID literals: a long
 * digit run looks like an account number to the repo guard, which blocks it
 * on sight and is right not to try telling the two apart.
 *
 * So this screen derives the id the same way the seed does, from the slug the
 * opening screen already picked. That only works if SHA-1 here matches
 * Python's `uuid.uuid5` byte-for-byte, including the UTF-8 encoding of the
 * name. A latin-1 encode of "Đức Ngọc" hashes to a different person. The
 * test file pins both the RFC 4122 DNS vector (`python.org`) and the
 * Vietnamese name against Python's own output, because those two failures
 * look identical on screen and this is the only place they can be told apart.
 *
 * No npm dependency. React Native has no `node:crypto`, and adding one so a
 * demo group can log in would be the wrong kind of clever.
 */

/** The namespace `scripts/seed_demo_data.py` uses for every demo id. */
export const KHONG_GIAN_DEMO = "da1ada1a-da1a-da1a-da1a-da1ada1ada1a";

/** RFC 4122 Appendix C, name-based UUID using SHA-1 (version 5). */
export const KHONG_GIAN_DNS = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

function rotl(n: number, s: number): number {
  return ((n << s) | (n >>> (32 - s))) >>> 0;
}

/**
 * SHA-1 of an arbitrary byte string, 20 bytes out.
 *
 * Written out rather than imported because the phone bundle has no Node
 * crypto, and a wrong hash here does not throw -- it just names a person
 * who does not exist.
 */
export function sha1(message: Uint8Array): Uint8Array {
  const ml = message.length;
  const padded = new Uint8Array((ml + 9 + 63) & ~63);
  padded.set(message);
  padded[ml] = 0x80;
  const view = new DataView(padded.buffer);
  // SHA-1 length is a 64-bit big-endian bit count. Demo names are tiny; the
  // high word stays zero and writing only the low word is the whole encoding.
  view.setUint32(padded.length - 4, ml * 8, false);

  let h0 = 0x67452301;
  let h1 = 0xefcdab89;
  let h2 = 0x98badcfe;
  let h3 = 0x10325476;
  let h4 = 0xc3d2e1f0;
  const w = new Uint32Array(80);

  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i++) {
      w[i] = view.getUint32(offset + i * 4, false);
    }
    for (let i = 16; i < 80; i++) {
      w[i] = rotl(w[i - 3]! ^ w[i - 8]! ^ w[i - 14]! ^ w[i - 16]!, 1);
    }
    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    for (let i = 0; i < 80; i++) {
      let f: number;
      let k: number;
      if (i < 20) {
        f = (b & c) | (~b & d);
        k = 0x5a827999;
      } else if (i < 40) {
        f = b ^ c ^ d;
        k = 0x6ed9eba1;
      } else if (i < 60) {
        f = (b & c) | (b & d) | (c & d);
        k = 0x8f1bbcdc;
      } else {
        f = b ^ c ^ d;
        k = 0xca62c1d6;
      }
      const temp = (rotl(a, 5) + f + e + k + w[i]!) >>> 0;
      e = d;
      d = c;
      c = rotl(b, 30);
      b = a;
      a = temp;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }

  const out = new Uint8Array(20);
  const outView = new DataView(out.buffer);
  outView.setUint32(0, h0, false);
  outView.setUint32(4, h1, false);
  outView.setUint32(8, h2, false);
  outView.setUint32(12, h3, false);
  outView.setUint32(16, h4, false);
  return out;
}

function hexByte(n: number): string {
  return n.toString(16).padStart(2, "0");
}

function bytesOfUuid(value: string): Uint8Array {
  const hex = value.replace(/-/g, "").toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(hex)) {
    throw new Error(`namespace phải là UUID, nhận được ${JSON.stringify(value)}`);
  }
  const out = new Uint8Array(16);
  for (let i = 0; i < 16; i++) {
    out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

function formatUuid(bytes: Uint8Array): string {
  const h = [...bytes].map(hexByte).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20, 32)}`;
}

/**
 * RFC 4122 name-based UUID, version 5, variant 10.
 *
 * The name is encoded as UTF-8 *before* hashing. Passing the string through
 * as latin-1 (or as a JS string hashed per-code-unit) is the exact bug the
 * Vietnamese test vector exists to catch.
 */
export function uuid5(namespace: string, name: string): string {
  const nsBytes = bytesOfUuid(namespace);
  const nameBytes = new TextEncoder().encode(name);
  const joined = new Uint8Array(nsBytes.length + nameBytes.length);
  joined.set(nsBytes);
  joined.set(nameBytes, nsBytes.length);
  const hash = sha1(joined);
  // Version 5 in the high nibble of byte 6, RFC variant in the high bits of
  // byte 8. The other 122 bits stay as the hash produced them.
  hash[6] = (hash[6]! & 0x0f) | 0x50;
  hash[8] = (hash[8]! & 0x3f) | 0x80;
  return formatUuid(hash.subarray(0, 16));
}

/** The people-row id the seed script would mint for this slug. */
export function idNguoi(slug: string): string {
  return uuid5(KHONG_GIAN_DEMO, `person:${slug}`);
}

/** A write-key the seed script would mint, so a retry replays instead of doubling. */
export function khoaGhi(slug: string): string {
  return uuid5(KHONG_GIAN_DEMO, `write:${slug}`);
}
