/** The two halves of the #342 trade, measured on the same frame.
 *
 * `tests/ten-mon-bi-cat.test.mjs` gates the name side and `tests/vung-cham-va-ma-qr.test.mjs`
 * gates the button side, and each is right about its own half. Neither shows
 * that the fix took the 16pt from somewhere that was actually empty, because
 * neither can fail in a way that says "the button grew back into the name". So
 * this probe reads both off one render and prints them side by side:
 *
 *   - the name input's text area, and every corpus name measured against it
 *     with that element's own computed font;
 *   - the delete button's real border box, plus a hit test at its four corners
 *     and its centre. `hitSlop` is the reason the corner check exists: it made
 *     `getBoundingClientRect` report a box the finger could not reach, so a
 *     width alone is not evidence of a tap target. A negative margin does move
 *     the real box, and this is where that claim gets checked rather than
 *     asserted.
 *
 * It also shoots the 390x844 viewport, because the leader is going to hold a
 * phone up next to a bill and the numbers do not settle what that looks like.
 * The shot is a viewport clip on purpose: `captureBeyondViewport` on
 * react-native-web has handed back a frame from a different scroll position
 * than the one just measured, which is how 102 passing text assertions once
 * described a picture with no cards in it.
 *
 * Reads a build, never makes one. Point it at either side of a fix:
 *
 *     cd apps/mobile
 *     TEN_NHAN=truoc node tools/anh-ten-mon-bi-cat.mjs
 *
 * PNGs land in `TEN_ANH` (default /tmp/ten-mon-anh) and never in git: the repo
 * guard fails closed on new binaries and it is right to.
 */
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { findChrome, launch, serve } from "../tests/chrome-cdp.mjs";
import { MAN_SAU_TAP, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const OUT = process.env.TEN_ANH ?? "/tmp/ten-mon-anh";
const NHAN = process.env.TEN_NHAN ?? "nay";

const RONG = 390;
const CAO = 844;

/** Ordinary Vietnamese menu lines, longest last. Wider than the gate's corpus
 *  on purpose: the gate asserts on names that must fit, this prints the whole
 *  distribution so the count of clipped names is a number and not a vibe. */
const TEN = [
  "Lẩu thái",
  "Bò nhúng dấm",
  "Mì Quảng gà ta",
  "Chả giò hải sản",
  "Bia Sài Gòn lon",
  "Lẩu thái hải sản",
  "Gỏi cuốn tôm thịt",
  "Cá lóc nướng trui",
  "Canh chua cá bớp",
  "Nước ép cam tươi",
  "Gà nướng muối ớt",
  "Rau muống xào tỏi",
  "Bánh xèo miền Tây",
  "Bún bò Huế đặc biệt",
  "Tôm sú nướng bơ tỏi",
  "Cơm tấm sườn bì chả",
  "Nem nướng Nha Trang",
];

/** Put real menu lines into the three name fields, the way a person would.
 *
 * The fixture bill holds "Lẩu thái", "Nước sâm", "Cơm rang" -- all short, all
 * fitting in every version of this layout. Measuring against them proves
 * nothing and, worse, photographs as a screen with no problem. So the picture
 * is taken of names the length real ones run to.
 *
 * Assigning `el.value` alone would paint the string and leave React's state
 * holding the old one, so the next render would wipe it: React installs its own
 * `value` setter on the element. Going through the prototype's setter and then
 * dispatching `input` is what makes React see a real edit. The caller reads the
 * values back afterwards -- a name that did not stick must not be photographed
 * as though it had.
 */
function datTen(ten) {
  const o = [...document.querySelectorAll("input")].filter((e) =>
    (e.getAttribute("aria-label") || "").startsWith("Tên món,"),
  );
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  ).set;
  o.forEach((el, i) => {
    if (i >= ten.length) return;
    setter.call(el, ten[i]);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  return o.map((el) => el.value);
}

/** Text against box, and the delete button's box against a finger. */
function doCaHai(ungVien) {
  const oTen = [...document.querySelectorAll("input")].filter((e) =>
    (e.getAttribute("aria-label") || "").startsWith("Tên món,"),
  );
  if (!oTen.length) return { tim: false };

  const el = oTen[0];
  const cs = getComputedStyle(el);
  const rongChu = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);

  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = cs.font && cs.font !== "" ? cs.font : `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;

  const nut = [...document.querySelectorAll('[aria-label^="Xoá món"]')][0] ?? null;
  let cham = null;
  if (nut) {
    const r = nut.getBoundingClientRect();
    // Inset by 1px: the corner pixel itself belongs to whichever box rounds up,
    // and that ambiguity is not what is being measured.
    const diem = [
      ["giữa", r.left + r.width / 2, r.top + r.height / 2],
      ["trên-trái", r.left + 1, r.top + 1],
      ["trên-phải", r.right - 1, r.top + 1],
      ["dưới-trái", r.left + 1, r.bottom - 1],
      ["dưới-phải", r.right - 1, r.bottom - 1],
    ];
    cham = {
      hop: { rong: Math.round(r.width), cao: Math.round(r.height), phai: Math.round(r.right) },
      // A point "hits" when the button is the element under it or an ancestor
      // of it: the icon inside the button is a legitimate hit on the button.
      diem: diem.map(([ten, x, y]) => {
        const duoi = document.elementFromPoint(x, y);
        return { ten, trung: !!duoi && (duoi === nut || nut.contains(duoi)) };
      }),
    };
  }

  return {
    tim: true,
    soO: oTen.length,
    hop: Math.round(el.getBoundingClientRect().width),
    rongChu: Math.round(rongChu),
    font: ctx.font,
    rongMan: document.documentElement.clientWidth,
    ket: ungVien.map((ten) => {
      const rong = ctx.measureText(ten).width;
      return { ten, rong: Math.round(rong), cat: rong > rongChu };
    }),
    cham,
  };
}

const chromeBin = findChrome();
if (!chromeBin) throw new Error("không tìm thấy Chrome (đặt CHROME_BIN)");
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  throw new Error(`không có bản dựng web ở ${EXPORT_DIR} (chạy: npm run build:check)`);
}

mkdirSync(OUT, { recursive: true });
const server = await serve(EXPORT_DIR);
const page = await launch(chromeBin);
const tam = join(EXPORT_DIR, "__anh-ten-mon.html");

try {
  const man = MAN_SAU_TAP.find((m) => m.step === "ket-qua");
  if (!man) throw new Error('không có màn "ket-qua" trong MAN_SAU_TAP');
  writeFileSync(
    tam,
    trangTuLai(readFileSync(join(EXPORT_DIR, "index.html"), "utf8"), man.kichBan, null),
  );

  await page.viewport(RONG, CAO);
  await page.goto(server.url + "__anh-ten-mon.html");
  await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
    timeout: 120000,
    label: 'kịch bản đi bộ tới "ket-qua"',
  });
  const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
  if (lai.loi) throw new Error(`kịch bản đi bộ HỎNG: ${lai.loi}`);

  // Measuring the wrong screen reports under the right name.
  const thay = await page.evaluate((n) => (document.body.innerText || "").includes(n), man.needle);
  if (!thay) throw new Error(`đi bộ xong nhưng không thấy "${man.needle}" — đang đo màn khác`);

  const r = await page.evaluate(doCaHai, TEN);
  if (!r.tim) throw new Error("không thấy ô nhập tên món nào");

  console.log(`nhãn      : ${NHAN}`);
  console.log(`bản dựng  : ${EXPORT_DIR}`);
  console.log(`màn       : ${r.rongMan}px, ${r.soO} ô tên`);
  console.log(`ô tên     : hộp ${r.hop}px, vùng chữ ${r.rongChu}px`);
  console.log(`font      : ${r.font}`);
  if (r.cham) {
    const trung = r.cham.diem.filter((d) => d.trung).length;
    console.log(
      `nút Xoá   : ${r.cham.hop.rong}x${r.cham.hop.cao}px, mép phải ${r.cham.hop.phai}px, ` +
        `chạm trúng ${trung}/${r.cham.diem.length} điểm ` +
        `(${r.cham.diem.map((d) => `${d.ten}:${d.trung ? "trúng" : "TRẬT"}`).join(" ")})`,
    );
  } else {
    console.log("nút Xoá   : KHÔNG THẤY");
  }
  const cat = r.ket.filter((k) => k.cat);
  console.log(`tên bị cắt: ${cat.length}/${r.ket.length}`);
  for (const k of r.ket) {
    console.log(`  ${k.ten.padEnd(24)} ${String(k.rong).padStart(4)}px  ${k.cat ? "CẮT" : "vừa"}`);
  }

  // Photograph names of a realistic length, not the fixture's three short ones.
  // The pair at 121 and 124 is what #342 pushed off the screen; the third is
  // the longest name that fits after the fix, so the shot also shows the ceiling.
  const MUON = ["Gỏi cuốn tôm thịt", "Cá lóc nướng trui", "Rau muống xào tỏi"];
  const daDat = await page.evaluate(datTen, MUON);
  const lech = MUON.filter((t, i) => daDat[i] !== t);
  if (lech.length) throw new Error(`tên không vào được ô: ${JSON.stringify(daDat)}`);
  console.log(`tên trên ảnh: ${daDat.join(" · ")}`);

  const anh = await page.call("Page.captureScreenshot", { format: "png" });
  const duong = join(OUT, `ket-qua-${NHAN}.png`);
  writeFileSync(duong, Buffer.from(anh.data, "base64"));
  console.log(`ảnh       : ${duong}`);
} finally {
  rmSync(tam, { force: true });
  await page.close();
  await server.close();
}
