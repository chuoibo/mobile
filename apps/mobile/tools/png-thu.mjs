/** A byte-real PNG, generated at scan time.
 *
 * Its own module, and not because `tab-snapshots.mjs` was crowded. That file
 * imports puppeteer from an absolute path on one machine, so anything that
 * wants to CHECK these bytes had to either drag a browser in or fall back to
 * grepping the generator's source text -- and a source grep cannot tell a
 * gradient that ends bright from one that ends dark. The property this file
 * exists to hold is a property of the pixels, so the pixels have to be
 * reachable without a browser. See `tests/anh.test.mjs`.
 */
import zlib from "node:zlib";

/**
 * Write a real PNG next to the bundle, so one card in the snapshot holds an
 * actual photograph rather than the drawn stand-in.
 *
 * The point is not decoration. Until `ui/Anh.tsx` landed the app rendered no
 * images at all, and the easy way to "add images" is to write an `<Image>`
 * branch that nothing ever reaches: `photo_url` is null on every row the
 * server sends today, so the frame would draw its stand-in forever and a
 * screenshot could not tell a working image path from a dead one. Serving a
 * byte-real PNG to exactly one of the two fixture rows makes the snapshot show
 * both states side by side -- one photo, one stand-in -- which is the only
 * version of this evidence that can fail.
 *
 * Generated at scan time and written into `.expo-build-check`, never
 * committed. The repo guard refuses binaries on sight and it is right to; this
 * is a build artifact in an ignored directory, not an asset.
 *
 * Hand-rolled because there is no image library here and adding one for four
 * chunks would be worse. A PNG is a signature plus length/type/data/CRC
 * chunks; `zlib.crc32` and `zlib.deflateSync` do the two hard parts.
 */
export function pngThuBytes(w = 480, h = 360, { dayChoi = false } = {}) {
  const raw = Buffer.alloc(h * (w * 3 + 1));
  let o = 0;
  for (let y = 0; y < h; y++) {
    raw[o++] = 0; // filter: none
    for (let x = 0; x < w; x++) {
      // A warm dusk wash with a lighter horizon band. Deliberately unlike the
      // drawn category marks, so nobody can mistake one for the other in a
      // screenshot.
      const t = (x / w) * 0.55 + (y / h) * 0.45;
      const band = Math.abs(y / h - 0.62) < 0.05 ? 42 : 0;
      let r = 232 - t * 96 + band;
      let g = 122 - t * 44 + band;
      let b = 96 + t * 78 + band;

      /* `dayChoi` blows the bottom third out to near-white.
       *
       * Not decoration, and not a random choice of picture. Every place card
       * prints its name in white over the bottom of this frame, and the only
       * thing holding that text above AA is `Scrim`'s wash. A mid-tone
       * photograph keeps the composite dark whatever the scrim does, so a scan
       * against one confirms the contrast rule RAN without ever putting it
       * under load -- a pass the surface did not earn.
       *
       * A bright bottom is the realistic worst case, not a contrived one: an
       * overexposed sky, a white wall, a window behind the counter. If white
       * type survives on top of THIS, the scrim is doing its job; if it does
       * not, the detector says so on the screen the demo opens with.
       */
      if (dayChoi) {
        // `y / (h - 1)`, not `y / h`: the last row must land on k = 1 at every
        // height. With `y / h` a 24px test image tops out at k = 0.88 while the
        // 360px one used in the scan reaches 0.99, so the small image would be
        // measurably darker at the bottom than the real one -- and a test that
        // holds the bright-bottom property would be holding it for a picture
        // nobody scans.
        const k = Math.max(0, (y / Math.max(1, h - 1) - 0.66) / 0.34);
        r += (252 - r) * k;
        g += (250 - g) * k;
        b += (246 - b) * k;
      }
      raw[o++] = Math.min(255, Math.round(r));
      raw[o++] = Math.min(255, Math.round(g));
      raw[o++] = Math.min(255, Math.round(b));
    }
  }

  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(zlib.crc32(body) >>> 0);
    return Buffer.concat([len, body, crc]);
  };

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // colour type: truecolour
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
