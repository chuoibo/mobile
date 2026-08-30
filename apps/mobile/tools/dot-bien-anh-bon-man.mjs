/** Prove `anh-bon-man-hero.mjs` is a gate and not decoration.
 *
 * On a clean tree that tool reports three findings, all of them tap targets.
 * Zero contrast findings, zero occlusion, zero overflow, and a VietQR that
 * decodes. Those zeros are the whole problem: a blind instrument prints exactly
 * the same thing, and this repo has shipped that mistake more than once --
 * `imp detect` returning `[]` with no browser installed, a `.tsx` file scan
 * scoring 0 on a fixture carrying three real defects.
 *
 * So each measurement is made to fail on purpose, one at a time, against a
 * defect written into the real source and carried through a real rebuild.
 *
 * ## One mutant per run, never four at once
 *
 * Four mutants in one build would turn the table all-red and prove less than it
 * looks: a single over-eager rule reddening on everything is indistinguishable
 * from four rules each catching their own defect. Each mutant here is applied
 * alone, and is required to produce ITS OWN finding shape -- a QR mutant that
 * reddened the contrast row would be reported as a failure, not a pass.
 *
 * ## The rebuild is not optional
 *
 * `dot-bien-scrim.mjs` records the trap: an earlier mutation edited the `.tsx`,
 * skipped the rebuild, measured a stale bundle and reported byte-identical
 * numbers with exit 0. The measurement reads the bundle, so the bundle is what
 * has to carry the mutant. Every mutant here rebuilds, and the colour mutants
 * additionally pin a hex that cannot occur in a clean bundle so "the mutant is
 * live" is checked rather than assumed.
 *
 *     cd apps/mobile && node tools/dot-bien-anh-bon-man.mjs
 */
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE = path.resolve(HERE, "..");
const BUILD = path.join(MOBILE, ".expo-build-check");

/**
 * Each mutant: where it goes, what it breaks, and which row must notice.
 *
 * `cho` is the finding shape required. `cam` is the shape that must NOT appear
 * -- it is what stops a mutant from passing because some unrelated rule fired.
 */
const DOT_BIEN = [
  {
    ten: "tuong-phan",
    man: "ket-qua",
    file: "src/ui/Kit.tsx",
    neo: `color: review ? c.warn : c.split, fontWeight: "600" }}>`,
    thay: `color: review ? c.warn : "#f4e7da", fontWeight: "600" }}>`,
    bundle: "#f4e7da",
    cho: /\[DUOI AA\][^\n]*Đã nhận diện/,
    vi: "chu thong bao doc bill doi sang mau gan bang nen -- mat mau, khong mat chu",
  },
  {
    ten: "diem-cham",
    man: "ket-qua",
    file: "src/screens/KetQuaNhanDien.tsx",
    neo: "width: W_DELETE,",
    thay: "width: 17,",
    cho: /\[DUOI WCAG 24\][^\n]*Xoá món/,
    vi: "nut xoa mon thu nho con 17px -- duoi ca WCAG 24 lan HIG 44",
  },
  {
    ten: "vietqr-trang",
    man: "ket-qua-thanh-toan",
    file: "src/ui/MaVietQr.tsx",
    neo: `backgroundColor: "#000000",`,
    thay: `backgroundColor: "#fffffe",`,
    bundle: "#fffffe",
    /* Either refusal shape counts, and the first draft of this line accepting
     * only one is why the mutant read as LOT on the first run. `cv2` reports an
     * unreadable symbol as a successful call returning "", so the tool answered
     * `[SAI PAYLOAD] giai ra 0 ky tu` -- a correct catch wearing the wrong
     * label. The tool now says `[KHONG GIAI DUOC]` for an empty decode; this
     * pattern stays wide so a future relabelling cannot quietly turn a caught
     * mutant into a missed one. */
    cho: /VietQR: \[(KHONG GIAI DUOC|SAI PAYLOAD)\]/,
    vi: "module QR ve gan nhu trang -- DOM van du hang tram View, chi pixel la mat",
  },
  {
    ten: "che-chu",
    man: "ket-qua-thanh-toan",
    file: "src/ui/MaVietQr.tsx",
    neo: `style={{ width: side, height: side, backgroundColor: "#ffffff" }}`,
    thay: `style={{ width: side, height: side, backgroundColor: "#ffffff", marginTop: -140, zIndex: 9999 }}`,
    cho: /\[CHE CHU\]/,
    vi: "khoi QR keo len 140px de len chu phia tren",
  },
];

const doc = (f) => fs.readFileSync(path.join(MOBILE, f), "utf8");
const ghi = (f, s) => fs.writeFileSync(path.join(MOBILE, f), s);

function dungLai() {
  execFileSync("npm", ["run", "build:check"], { cwd: MOBILE, stdio: "pipe", timeout: 600000 });
}

/** The bundle, concatenated, so a mutant can be looked for in what actually ships. */
function bundleText() {
  const dir = path.join(BUILD, "_expo/static/js/web");
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".js"))
    .map((f) => fs.readFileSync(path.join(dir, f), "utf8"))
    .join("\n");
}

function bundleHash() {
  return crypto.createHash("sha256").update(bundleText()).digest("hex").slice(0, 12);
}

function chay(man) {
  try {
    return execFileSync("node", [path.join(MOBILE, "tools/anh-bon-man-hero.mjs")], {
      cwd: MOBILE,
      encoding: "utf8",
      timeout: 900000,
      env: { ...process.env, ANH_MAN: man },
    });
  } catch (e) {
    // Exit 1 just means findings were reported, which is the point here.
    return `${e.stdout ?? ""}${e.stderr ?? ""}`;
  }
}

const goc = new Map();
for (const m of DOT_BIEN) if (!goc.has(m.file)) goc.set(m.file, doc(m.file));

// Anchors first: a mutation that silently matched nothing would rebuild, change
// nothing, and read as "the tool is blind" when the truth is "the edit missed".
for (const m of DOT_BIEN) {
  const n = goc.get(m.file).split(m.neo).length - 1;
  if (n !== 1) throw new Error(`${m.ten}: neo xuat hien ${n} lan trong ${m.file}, can dung 1`);
}

console.log("== dot bien anh-bon-man-hero.mjs ==\n");
const bang = [];
try {
  dungLai();
  const hashSach = bundleHash();
  console.log(`bundle sach: ${hashSach}\n`);

  for (const m of DOT_BIEN) {
    process.stdout.write(`-- ${m.ten}: ${m.vi}\n`);
    ghi(m.file, goc.get(m.file).replace(m.neo, m.thay));
    let hang;
    try {
      dungLai();
      const h = bundleHash();
      const bt = bundleText();
      if (h === hashSach) throw new Error("bundle KHONG doi sau khi dot bien -- dang do ban cu");
      if (m.bundle && !bt.includes(m.bundle)) {
        throw new Error(`dot bien KHONG vao bundle (thieu \`${m.bundle}\`)`);
      }
      const out = chay(m.man);
      const do_ = m.cho.test(out);
      const bay = m.cam ? m.cam.test(out) : false;
      hang = { ten: m.ten, man: m.man, bundle: h, do: do_, bay, dat: do_ && !bay };
      const dong = out.split("\n").find((l) => m.cho.test(l));
      console.log(`   bundle ${h}  ->  ${do_ ? "DO" : "XANH"}${dong ? `\n   ${dong.trim()}` : ""}`);
    } finally {
      ghi(m.file, goc.get(m.file));
    }
    bang.push(hang);
    console.log("");
  }
} finally {
  for (const [f, s] of goc) ghi(f, s);
  dungLai();
  console.log(`bundle khoi phuc: ${bundleHash()}`);
}

console.log("\n== bang ==");
for (const h of bang) {
  console.log(`  ${h.dat ? "DAT " : "HONG"}  ${h.ten.padEnd(14)} ${h.man.padEnd(20)} ${h.do ? "do dung cho" : "KHONG do"}`);
}
const hong = bang.filter((h) => !h.dat);
console.log(hong.length ? `\n${hong.length}/${bang.length} dot bien LOT -- cong nay mu o do` : `\n${bang.length}/${bang.length} dot bien bi bat`);
process.exit(hong.length ? 1 : 0);
