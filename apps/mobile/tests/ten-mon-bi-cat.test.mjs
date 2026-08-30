/* A clipping `<input>` does not overflow, so no overflow scanner can see it.
 *
 * The dish name on `KetQuaNhanDien` is a `TextInput`, which react-native-web
 * renders as an `<input>`. An `<input>` does not wrap: it CLIPS, and the part
 * that no longer fits is reachable only by putting a caret in the field and
 * scrolling inside it. The element's own box measures the same whether the name
 * fits or not, the row does not grow, nothing overflows its parent, and
 * `tools/overflow-check.mjs` is right to stay silent. The screen just quietly
 * starts reading like the machine misread the bill.
 *
 * That is how the regression this file guards got in and stayed in. #342 fixed
 * a real defect -- the delete control was 28pt wide to a finger, because
 * react-native-web drops `hitSlop` -- and paid for the missing 16pt out of the
 * name column, 154 -> 138pt of box. The PR argued 138 still beat the 110pt of a
 * first build that had truncated six of eight dishes. Both numbers are column
 * widths; neither was ever compared against a dish name. Measured on the
 * rendered page afterwards (qa-tt-0035), the name's TEXT area had gone 136px ->
 * 120px and the count of clipped names 3/9 -> 5/9, with "Gỏi cuốn tôm thịt"
 * (121px) and "Cá lóc nướng trui" (124px) newly falling off -- two ordinary
 * menu lines, on the screen whose whole job is showing that the reading is
 * right. Every gate in the repo stayed green through it.
 *
 * So this file asks the only question that has a different answer in the two
 * cases: how wide is the TEXT, against how wide is the BOX. It measures the
 * name input's real content box off the layout, then measures each candidate
 * string on a canvas using that same element's computed font. It is a
 * measurement of text layout -- a property of the DOM and the font -- not a
 * keyboard-entry test: it does not prove what React re-renders when a person
 * really types. It answers "is this name on screen", which is the thing that
 * regressed.
 *
 * The corpus is real Vietnamese menu lines rather than a pixel constant on
 * purpose. A threshold like "text area >= 138px" passes a font change that
 * clips every name, because the constant does not know what a name costs.
 *
 * CANARY, and it is not decoration: `NGƯỠNG_QUÁ_DÀI` is a string that MUST be
 * reported as clipped. If canvas measuring ever returns 0, or the font fails to
 * resolve, or the walk lands on a screen with no name inputs, every real name
 * "fits" and this gate goes green precisely when the screen is most broken.
 * A gate that cannot show you it still bites is not evidence.
 *
 * What this proves: the build in `MOBILE_WEB_EXPORT`, at 390x844, in this
 * Chrome. What it does not prove: iOS or Android, where the metrics and the
 * safe areas differ, or any narrower viewport -- the name column is elastic, so
 * every number here belongs to exactly one width.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/ten-mon-bi-cat.test.mjs
 *
 * With no build and no Chrome it skips and says which; `MOBILE_REQUIRE_WEB_A11Y=1`
 * turns that skip into a failure. Same convention as `vung-cham-va-ma-qr.test.mjs`,
 * deliberately -- the two measure the two halves of the same trade.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { MAN_SAU_TAP, trangTuLai } from "../tools/quet-man-sau-tap.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The phone the demo runs on. The name column is elastic, so both numbers
 *  below are load-bearing and cannot be generalised away. */
const RONG = 390;
const CAO = 844;

/** Ordinary Vietnamese menu lines that must be readable in full.
 *
 * The ceiling is deliberate: an app cannot promise every name fits, and
 * "Cá lóc nướng trui cuốn bánh tráng" at 244px never will inside a 390px phone
 * that also has to show quantity, money and a 44pt delete control. What it can
 * promise is the ordinary length, and these are the names that decide it --
 * the first two are exactly the pair #342 pushed off the screen. */
const TEN_PHAI_VUA = [
  "Lẩu thái",
  "Nước sâm",
  "Cơm rang",
  "Bún bò Huế",
  "Gỏi cuốn tôm thịt",
  "Cá lóc nướng trui",
];

/** The canary. Not a name anybody would type -- a string long enough that any
 *  live measurement must call it clipped. If this one comes back "fits", the
 *  measurement is dead and every green above it is meaningless. */
const NGUONG_QUA_DAI = "Cá lóc nướng trui cuốn bánh tráng ăn kèm rau rừng và bún tươi";

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}

/* ------------------------------------------------------ measurement, in-page --- */

/**
 * Text width against box width, on the live name inputs.
 *
 * `clientWidth` excludes the border but INCLUDES padding, and the text only
 * gets what is left after padding -- subtracting it is not a rounding detail,
 * it is 12 of the pixels this file exists to count. The font comes off the
 * element's own computed style rather than from the token file, so a change to
 * either one is visible here.
 */
function doChuVsO(ungVien) {
  const o = [...document.querySelectorAll("input")].filter((e) =>
    (e.getAttribute("aria-label") || "").startsWith("Tên món,"),
  );
  if (!o.length) return { tim: false };

  const el = o[0];
  const cs = getComputedStyle(el);
  const dem = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const rongChu = el.clientWidth - dem;

  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = cs.font && cs.font !== "" ? cs.font : `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;

  return {
    tim: true,
    so: o.length,
    hop: Math.round(el.getBoundingClientRect().width),
    rongChu: Math.round(rongChu),
    font: ctx.font,
    ket: ungVien.map((ten) => {
      const rong = ctx.measureText(ten).width;
      return { ten, rong: Math.round(rong), cat: rong > rongChu };
    }),
  };
}

/* -------------------------------------------------------------------- gate --- */

if (reasons.length && !REQUIRED) {
  test(`tên món bị cắt — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("tên món trên màn Kết quả nhận diện, đo chữ chứ không đợi tràn", () => {
    let page;
    let server;
    const daTao = [];

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      for (const f of daTao) rmSync(f, { force: true });
    });

    /** Same walk as `vung-cham-va-ma-qr.test.mjs` and the qa-tt-0035 probe:
     *  `ket-qua` has no fragment, you reach it by pressing through the bill
     *  flow. Restating the walk would let the three drift into describing
     *  different apps. */
    async function diToiKetQua() {
      const man = MAN_SAU_TAP.find((m) => m.step === "ket-qua");
      assert.ok(man, 'không có màn "ket-qua" trong MAN_SAU_TAP');
      const ten = "__ten-mon-bi-cat.html";
      const duong = join(EXPORT_DIR, ten);
      writeFileSync(
        duong,
        trangTuLai(readFileSync(join(EXPORT_DIR, "index.html"), "utf8"), man.kichBan, null),
      );
      daTao.push(duong);

      await page.viewport(RONG, CAO);
      await page.goto(server.url + ten);
      await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
        timeout: 120000,
        label: 'kịch bản đi bộ tới "ket-qua"',
      });
      const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
      assert.equal(lai.loi, null, `kịch bản đi bộ tới "ket-qua" HỎNG: ${lai.loi}`);
      assert.equal(lai.xong, true, 'kịch bản đi bộ tới "ket-qua" chưa xong');

      // A measurement of the wrong screen reports under the right name.
      const thay = await page.evaluate(
        (n) => (document.body.innerText || "").includes(n),
        man.needle,
      );
      assert.ok(thay, `đi bộ xong nhưng không thấy "${man.needle}" — đang đo màn khác`);
      return man;
    }

    test("tên món dài bình thường hiện đủ chữ, và phép đo tự chứng minh là còn sống", async () => {
      await diToiKetQua();
      const r = await page.evaluate(doChuVsO, [...TEN_PHAI_VUA, NGUONG_QUA_DAI]);

      assert.equal(r.tim, true, "không thấy ô nhập tên món nào trên màn kết quả nhận diện");
      // The fixture bill holds three dishes. Asserting the count first is what
      // stops "no inputs found" from passing as "nothing is clipped".
      assert.equal(r.so, 3, `mong 3 ô tên món, thấy ${r.so}`);

      console.log(`  ô tên : ${r.so} ô, hộp ${r.hop}px, vùng chữ ${r.rongChu}px`);
      console.log(`  font  : ${r.font}`);
      for (const k of r.ket) {
        console.log(`  ${k.ten.padEnd(62)} ${String(k.rong).padStart(4)}px  ${k.cat ? "CẮT" : "vừa"}`);
      }

      // Canary FIRST. Everything under it is only worth reading if the
      // measurement can still return "clipped" at all.
      const canary = r.ket.find((k) => k.ten === NGUONG_QUA_DAI);
      assert.equal(
        canary.cat,
        true,
        `PHÉP ĐO ĐÃ CHẾT: chuỗi ${canary.rong}px được báo là vừa trong vùng chữ ` +
          `${r.rongChu}px. Mọi kết quả "vừa" bên dưới là vô nghĩa.`,
      );

      const cat = r.ket.filter((k) => k.cat && k.ten !== NGUONG_QUA_DAI);
      assert.deepEqual(
        cat.map((k) => `${k.ten} (${k.rong}px)`),
        [],
        `tên món độ dài bình thường bị cắt trong vùng chữ ${r.rongChu}px. ` +
          "Ô tên là <input>: nó CẮT chứ không xuống dòng, nên không có tràn nào để " +
          "máy quét bắt và màn sẽ trông như máy đọc sai. Đừng lấy thêm bề ngang của " +
          "cột tên -- xem bảng cột đầu file KetQuaNhanDien.tsx.",
      );
    });
  });
}
