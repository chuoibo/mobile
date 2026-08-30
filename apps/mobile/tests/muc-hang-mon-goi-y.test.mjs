/* A dish row on `goi-y` has to put INK on the glass -- read off the picture.
 *
 * `mon-tren-goi-y.test.mjs` sits next to this file and gates the same screen by
 * geometry: the row's box inside the scroller's clip box, both from the DOM.
 * That is the gate that caught PH-3 and it should stay. This one exists because
 * the leader asked to SEE the screen, and because geometry and pixels are not
 * the same claim in this repo:
 *
 *   - A `full_page` capture on react-native-web has already been measured
 *     shooting a frame that was not on the glass: 102 text assertions passed
 *     against a picture holding no cards at all.
 *   - A box correctly inside its clip box still paints nothing when it is
 *     `opacity: 0`, the colour of its own ground, covered by a later sibling,
 *     or waiting on a font that never arrived. Every one of those is a pass to
 *     a `getBoundingClientRect` gate.
 *
 * So this file asks the pixel question and only the pixel question: shoot the
 * 390x844 viewport, hide one dish name, shoot it again, count what changed.
 * Pixels that change when a string is hidden are pixels that string was
 * painting, and they are inside the frame by construction.
 *
 * MEASURED, both states, both sides of #351 -- the numbers the threshold below
 * is set from:
 *
 *              A, nobody on bill        B, three added
 *   d4f6f91    0 / 0 / 0 px             0 / 0 / 0 px          (0/3 and 0/3)
 *   ba510d8    1125 / 1408 / 1303       1125 / 0 / 0          (3/3 and 1/3)
 *
 * A row that paints is never near the floor and a row that does not is exactly
 * zero, so the gate is not balanced on a close call. `MUC_TOI_THIEU` is set
 * well above a sliver and well below the smallest real row for the case the
 * commit for #351 describes: a draft that left "Cơm rang" lying ACROSS the clip
 * edge rather than under it. A row sliced two pixels deep out of a 27px glyph
 * run is about 83 changed pixels, and a person calls that invisible.
 *
 * What this proves: on the build in `MOBILE_WEB_EXPORT`, at 390x844, in this
 * Chrome, with this three-dish seven-person fixture. What it does not prove:
 * any other viewport, a longer bill, iOS or Android safe areas, or that a
 * person understands the screen once they can see it.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/muc-hang-mon-goi-y.test.mjs
 *
 * With no build and no Chrome it skips and says so; `MOBILE_REQUIRE_WEB_A11Y=1`
 * turns that skip into a failure. Same convention as its neighbour.
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { before, describe, test } from "node:test";

import { findChrome } from "./chrome-cdp.mjs";
import { MON, doMucHangMon } from "../tools/anh-hang-mon-goi-y.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const ANH = process.env.PH3_ANH ?? "/tmp/ph3-anh";
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** Changed device pixels below which a row is not on the glass for a reader.
 *  Set from the table above: 13x under the smallest row that paints, 4.8x over
 *  a two-pixel slice of one. */
const MUC_TOI_THIEU = 400;

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}

if (reasons.length && !REQUIRED) {
  test(`mực hàng món trên goi-y — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("mực của hàng món trên màn gợi ý, đọc từ ảnh chụp khung 390x844", () => {
    let ketQua;

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      // One walk, both states, so the two cases below cannot end up describing
      // two different renders of the same build.
      ketQua = await doMucHangMon({ build: EXPORT_DIR, nhan: "gate", anhDir: ANH });
    });

    /** Assert-and-report, so a failure carries the counts that explain it. */
    function chamDiem(nhan) {
      const ra = ketQua.find((r) => r.nhan === nhan);
      assert.ok(ra, `không có kết quả cho trạng thái ${nhan}`);

      // Guard 1: the frame has to have stopped moving. Without it, a page still
      // animating hands back pixel counts that are motion, not ink -- measured
      // on d4f6f91, where an unsettled frame read 5952 changed pixels for a row
      // the DOM put 270pt below the fold. A number taken off a moving frame is
      // not a lenient measurement, it is not a measurement.
      const dong = ra.hang.filter((h) => h.timThay && !h.yen).map((h) => h.ten);
      assert.deepEqual(dong, [], `${nhan}: khung chưa yên khi đo ${dong.join(", ")} — số đo vô nghĩa`);

      // Guard 2: three dishes have to be on the page at all. Otherwise a
      // fixture that stopped rendering dishes satisfies "no dish is missing
      // from the glass" and this file goes green on a blank card.
      const mat = ra.hang.filter((h) => !h.timThay).map((h) => h.ten);
      assert.deepEqual(mat, [], `${nhan}: không tìm thấy hàng món trong DOM: ${mat.join(", ")}`);

      const co = ra.hang.filter((h) => h.doi >= MUC_TOI_THIEU);
      assert.ok(
        co.length >= 1,
        `${nhan}: không hàng món nào để lại đủ mực trên khung 390x844 ` +
          `(ngưỡng ${MUC_TOI_THIEU}px) — thẻ trông như rỗng. Ảnh: ${ra.anh}. ` +
          `Đo được: ${ra.hang.map((h) => `${h.ten}=${h.doi}px`).join(", ")}`,
      );
      return co.length;
    }

    /* --- A. where the walk stops: nobody on the bill --- */

    test("chưa ai trên bill: có hàng món để lại mực trên khung", () => {
      const co = chamDiem("A-chua-ai");
      console.log(`    => ${co}/${MON.length} hàng món có mực`);
    });

    /* --- B. where the demo goes next: three of the group added --- */

    test("thêm 3 người: vẫn có hàng món để lại mực trên khung", () => {
      const co = chamDiem("B-ba-nguoi");
      console.log(`    => ${co}/${MON.length} hàng món có mực`);
    });
  });
}
