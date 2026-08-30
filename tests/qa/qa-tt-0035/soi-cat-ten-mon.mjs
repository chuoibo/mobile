/* Does a real Vietnamese dish name still fit the name column? (qa-tt-0035)
 *
 * #342 fixed a real defect -- the delete control was 28pt wide to a finger
 * because react-native-web drops `hitSlop` -- by widening that control to a
 * true 44. The column table in `KetQuaNhanDien.tsx` says the name field paid
 * for it: 154pt -> 138pt. That same file records that an earlier 110pt version
 * "truncated six of eight dishes", so this column has a history of clipping and
 * the fix just moved it 16pt back toward that history.
 *
 * Nothing measures it. The name cell is a `TextInput`, which on web is an
 * `<input>` -- it does NOT wrap, it clips, and the overflow is only reachable
 * by putting a caret in the field and scrolling it. The guard #342 shipped
 * (`vung-cham-va-ma-qr.test.mjs`) asserts the 44 and the QR fold; its fixture
 * holds "Lẩu thái", "Nước sâm", "Cơm rang" -- three names short enough that a
 * clipping column cannot show up in it.
 *
 * So this probe asks the rendered page, at the real width, on the real font:
 * how much of a name is actually on screen?
 *
 * Method, and its one honest limit. It walks to `ket-qua` through the same
 * `MAN_SAU_TAP` script the guard test walks, so both describe the same app. It
 * reads the name input's real content-box width from the layout, then measures
 * candidate strings with a canvas 2D context using that input's own computed
 * font. It does NOT type into React state: it measures text layout, which is a
 * property of the DOM and the font, not of the component's state. That is the
 * same question a person's eye asks and it is enough to decide whether a name
 * is on screen -- but it is not a keyboard-entry test, and it does not prove
 * what React would re-render if a user really typed.
 *
 * Run from the repo root, against a build you made yourself:
 *
 *     cd apps/mobile && npm run build:check && cd -
 *     node tests/qa/qa-tt-0035/soi-cat-ten-mon.mjs
 *
 * Exit 0 = every name fits. Exit 2 = at least one is clipped. No build or no
 * Chrome exits 1 and says which, rather than printing a clean 0.
 */
import { existsSync } from "node:fs";
import { readFileSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
// Relative, never absolute: qa-tt-0034 found 23 hard-coded machine paths across
// 17 QA files and put a gate on exactly this.
const MOBILE = join(HERE, "..", "..", "..", "apps", "mobile");

const { findChrome, launch, serve } = await import(join(MOBILE, "tests", "chrome-cdp.mjs"));
const { MAN_SAU_TAP, trangTuLai } = await import(join(MOBILE, "tools", "quet-man-sau-tap.mjs"));

const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(MOBILE, ".expo-build-check");
const RONG = 390;
const CAO = 844;

/* Real names off real Vietnamese menus, shortest first. The first three are the
 * fixture's own, kept so the table shows where the fixture sits on the scale --
 * they are the reason the shipped guard cannot see this. */
const TEN_THAT = [
  "Lẩu thái",
  "Nước sâm",
  "Cơm rang",
  "Bún bò Huế",
  "Gỏi cuốn tôm thịt",
  "Cá lóc nướng trui",
  "Lẩu thái hải sản chua cay",
  "Bún bò Huế đặc biệt tái nạm gân",
  "Cá lóc nướng trui cuốn bánh tráng",
];

if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  console.error(`khong co ban dung tai ${EXPORT_DIR} (chay: cd apps/mobile && npm run build:check)`);
  process.exit(1);
}
const chromeBin = findChrome();
if (!chromeBin) {
  console.error("khong tim thay Chrome (dat CHROME_BIN, hoac cai qua playwright)");
  process.exit(1);
}

/** Measured in-page: the name inputs' real content box, and how much of each
 *  candidate string fits in it at that element's own computed font. */
function doCatChu(tenThat) {
  const o = [...document.querySelectorAll("input")].filter((e) =>
    (e.getAttribute("aria-label") || "").startsWith("Tên món,"),
  );
  if (!o.length) return { tim: false };

  const el = o[0];
  const cs = getComputedStyle(el);
  // clientWidth excludes the border but INCLUDES padding; the text only gets
  // what is left after padding, so subtracting it is not a rounding detail.
  const dem = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const rongChu = el.clientWidth - dem;

  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = cs.font && cs.font !== "" ? cs.font : `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;

  const ket = tenThat.map((ten) => {
    const rong = ctx.measureText(ten).width;
    let hien = ten;
    if (rong > rongChu) {
      // Longest prefix that still fits -- what a person actually sees.
      let n = ten.length;
      while (n > 0 && ctx.measureText(ten.slice(0, n)).width > rongChu) n -= 1;
      hien = ten.slice(0, n);
    }
    return { ten, rong: Math.round(rong), cat: rong > rongChu, hien };
  });

  return {
    tim: true,
    so: o.length,
    hop: Math.round(el.getBoundingClientRect().width),
    rongChu: Math.round(rongChu),
    font: ctx.font,
    // The fixture's own values, straight off the live inputs, so the table can
    // be checked against what the screen is really showing right now.
    dangCo: o.map((e) => ({ gt: e.value, tran: e.scrollWidth > e.clientWidth + 1 })),
    ket,
  };
}

const server = await serve(EXPORT_DIR);
const page = await launch(chromeBin);
const tam = [];
let ma = 0;
try {
  const man = MAN_SAU_TAP.find((m) => m.step === "ket-qua");
  const ten = "__soi-cat-ten-mon.html";
  const duong = join(EXPORT_DIR, ten);
  writeFileSync(duong, trangTuLai(readFileSync(join(EXPORT_DIR, "index.html"), "utf8"), man.kichBan, null));
  tam.push(duong);

  await page.viewport(RONG, CAO);
  await page.goto(server.url + ten);
  await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
    timeout: 120000,
    label: 'di bo toi "ket-qua"',
  });
  const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
  if (lai.loi) throw new Error(`kich ban di bo HONG: ${lai.loi}`);

  // Needle first: a measurement of the wrong screen reports under the right name.
  const thay = await page.evaluate((n) => (document.body.innerText || "").includes(n), man.needle);
  if (!thay) throw new Error(`di bo xong nhung khong thay "${man.needle}" — dang do man khac`);

  const r = await page.evaluate(doCatChu, TEN_THAT);
  if (!r.tim) throw new Error("khong tim thay o nhap ten mon nao tren man ket qua");

  console.log(`man   : ket-qua @ ${RONG}x${CAO}  (needle "${man.needle}" OK)`);
  console.log(`o ten : ${r.so} o, hop ${r.hop}px, vung chu ${r.rongChu}px`);
  console.log(`font  : ${r.font}`);
  console.log(`fixture dang hien: ${r.dangCo.map((d) => `"${d.gt}"${d.tran ? " [TRAN]" : ""}`).join(", ")}`);
  console.log("");
  console.log("ten mon".padEnd(36) + "rong".padStart(6) + "  " + "ket qua");
  console.log("-".repeat(78));
  for (const k of r.ket) {
    const trang = k.cat ? `CAT -> hien "${k.hien}…"` : "vua";
    console.log(`${k.ten.padEnd(36)}${String(k.rong).padStart(5)}px  ${trang}`);
  }
  const cat = r.ket.filter((k) => k.cat);
  console.log("");
  console.log(`${cat.length}/${r.ket.length} ten bi cat o vung chu ${r.rongChu}px`);
  ma = cat.length ? 2 : 0;
} finally {
  await page.close();
  await server.close();
  for (const f of tam) rmSync(f, { force: true });
}
process.exit(ma);
