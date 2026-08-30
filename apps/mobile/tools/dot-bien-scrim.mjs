/** Prove `soi-tuong-phan-anh.mjs` notices when the scrim it measures is gone.
 *
 * ## The claim this file discharges
 *
 * `soi-tuong-phan-anh.mjs` used to say in its own header that with `Scrim`
 * flattened the `PHEP_THU` row goes red and restored it passes. That sentence
 * was written by the same hand as the tool, run once, by hand, and never
 * re-run. A docstring vouching for its own teeth is the exact shape this repo
 * keeps paying for, so the claim is a command now.
 *
 *     cd apps/mobile && node tools/dot-bien-scrim.mjs
 *
 * ## Why a pair of rows, and not just the red one
 *
 * Review flattened `Scrim`'s alphas to `[0, 0, 0]` against the FIRST version of
 * the contrast tool, confirmed the mutant was in the bundle, and reported that
 * NOT ONE NUMBER MOVED -- every ratio in that table was about an opaque chip,
 * not about the photograph. That finding is why `PHEP_THU` exists.
 *
 * So a red row on its own would prove too little: a gate that reddens at
 * anything reads exactly the same. `S2` breaks the scrim identically and
 * measures it with the instrument as it behaved BEFORE the probe, and requires
 * GREEN. The pair says "this breakage is visible now and was invisible before".
 * Either row alone says much less.
 *
 * ## The control is reconstructed, and then checked against the real numbers
 *
 * The honest control would be the pre-review file itself, but that commit lived
 * on a branch that was squash-merged, so pinning its SHA would work here today
 * and fail for everyone else tomorrow -- a check nobody but its author can run
 * is not a check. `CONG_CU_CU` instead removes the three properties the old
 * instrument did not have, each named below.
 *
 * A reconstruction the author keeps editing until it goes green would be worse
 * than no control at all, so it is held to the pre-review run's OWN numbers
 * before it is allowed to vouch for anything: on a clean tree it must report
 * `CHU_TRUOC_REVIEW` texts across `MAN_TRUOC_REVIEW` screens, which is verbatim
 * what the pre-review tool printed in review ("DAT: 4 chu nam tren anh, tren 3
 * man, deu cach san AA"). Miss that and the run refuses rather than reports.
 *
 * ## Editing source is not enough, and that cost a round
 *
 * The measurement reads `.expo-build-check`, not `src/`. The first hand-run of
 * this mutation edited the `.tsx`, skipped the rebuild, and read a stale bundle:
 * the numbers held still for a completely different reason than the one being
 * reported. Measured directly, that false green is total -- source flattened,
 * bundle stale, `6.63:1` and `6.01:1` unchanged, exit 0, byte-identical to a
 * clean run. So every row here rebuilds and then asserts the mutant is IN THE
 * EMITTED BUNDLE before it is allowed to conclude anything.
 *
 * ## What it does not prove
 *
 * That any real caption is legible. `PHEP_THU` is a probe for a shape the
 * product does not ship today -- see the contrast tool's closing section. This
 * file proves the probe has teeth, not that the product needs them yet.
 */
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { moiMan } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE = path.resolve(HERE, "..");
const SOI = path.join(MOBILE, "tools/soi-tuong-phan-anh.mjs");
const ANH_DIA_DIEM = path.join(MOBILE, "src/screens/kham-pha/AnhDiaDiem.tsx");

/** How many texts the pre-review instrument counted as sitting on a photograph.
 *
 *  Frozen on purpose: this one is a fact about the OLD instrument's behaviour,
 *  and it moving means the reconstruction is not the old instrument. It is
 *  allowed to go stale, and when it does a person has to look -- a new screen
 *  that prints type across a picture is exactly the event worth stopping for.
 */
const CHU_TRUOC_REVIEW = 4;

/** How many screens carry a photograph, read from the list the tool itself
 *  walks rather than frozen.
 *
 *  It used to be the literal `3`, a fingerprint of the tree on the day this
 *  control was written, and it went stale the moment F38 added a fourth screen
 *  with a picture on it -- the run went red saying "4 chu / 4 man" against a
 *  demand for "4 chu / 3 man", with nothing wrong anywhere. That is a false red
 *  about growth, and a control that reddens when the product gains a screen
 *  teaches people to rerun it until it is quiet.
 *
 *  `moiMan()` is the same source `soi-tuong-phan-anh.mjs` filters, so the two
 *  cannot disagree, and a screen silently dropped from that list is already
 *  caught by `tests/quet-du-tab.test.mjs`. The teeth of this check do not live
 *  in the screen count anyway -- they live in `CHU_TRUOC_REVIEW` above and in
 *  the blindness assertion below, both of which are properties of the
 *  instrument rather than of how big the app has grown. */
const MAN_TRUOC_REVIEW = moiMan().filter((m) => typeof m.anh === "number" && m.anh > 0).length;

/** Flatten the wash `AnhDiaDiem`'s docstring justifies. White body type then
 *  sits on the blown-out bottom of the photograph with nothing in between --
 *  the state the pre-review table reported four passing ratios in. */
const SCRIM_PHANG = {
  file: ANH_DIA_DIEM,
  neo: "      <Scrim alphas={[0, 0.18, 0.72]} />",
  thay: "      <Scrim alphas={[0, 0, 0]} /> {/* dot-bien: khong con lop wash */}",
};

/** How that mutation reads after minification. Source is not what gets
 *  measured, so the bundle is where the mutation has to be found. */
const BUNDLE_GOC = "alphas:[0,.18,.72]";
const BUNDLE_DOT = "alphas:[0,0,0]";

/** The three properties the instrument gained at review, removed. Together they
 *  are the old measure: no probe, ground inferred from geometry, and a screen
 *  with no text over its photograph treated as normal rather than as broken. */
const CONG_CU_CU = [
  {
    // 1. No probe. The old table only ever measured product text, and no
    //    product text sits on a photograph today -- which is why the scrim was
    //    free to break.
    file: SOI,
    neo: "    await datPhepThu(page, man);\n",
    thay: "    /* cong-cu-cu: khong dat probe */\n",
  },
  {
    // 2. Ground inferred from geometry. Overlapping a photograph counted as
    //    sitting on one, so a white chip's own fill was reported as the
    //    picture's ground.
    file: SOI,
    neo: "    return { co, tiLe, trenAnh: tiLe >= 0.5 };",
    thay: "    return { co, tiLe, trenAnh: true }; /* cong-cu-cu: hinh hoc suy ra nen */",
  },
  {
    // 3. A screen with nothing written across its photograph was a normal
    //    screen, not a broken instrument. With the probe gone that is true
    //    again, and without this the control would die on `ky-niem` for a
    //    reason that has nothing to do with the scrim.
    file: SOI,
    neo: "    if (!muc.muc.length) {\n      throw new Error(",
    thay:
      "    if (!muc.muc.length) {\n" +
      "      console.log(`  -- ${man.step}: ${muc.anhs} anh, khong chu nao nam tren anh (binh thuong)`);\n" +
      "      return;\n" +
      "    }\n" +
      "    if (false) {\n" +
      "      throw new Error(",
  },
];

const DOT_BIEN = [
  {
    ten: "S1 · hạ alphas của Scrim về [0,0,0], đo bằng công cụ HÔM NAY",
    kieu: "canBat",
    sua: [SCRIM_PHANG],
    /* Both photo frames, named separately. `kham-pha` alone would leave the
     * biggest frame in the app -- `dia-diem`, 248pt full bleed -- vouched for
     * by a screen the mutation never ran on. */
    manPhaiDo: ["kham-pha", "dia-diem"],
  },
  {
    ten: "S2 · CHỨNG: cùng vết đứt, đo bằng công cụ TRƯỚC khi có probe",
    kieu: "canMu",
    sua: [SCRIM_PHANG, ...CONG_CU_CU],
  },
];

function dung() {
  const r = spawnSync("npm", ["run", "build:check"], {
    cwd: MOBILE,
    encoding: "utf8",
    env: process.env,
    maxBuffer: 64 * 1024 * 1024,
  });
  if (r.status !== 0) {
    throw new Error(`build:check that bai (ma=${r.status})\n${(r.stderr ?? "").slice(-2000)}`);
  }
  const dir = path.join(MOBILE, ".expo-build-check/_expo/static/js/web");
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".js"))
    .map((f) => fs.readFileSync(path.join(dir, f), "utf8"))
    .join("\n");
}

function chay() {
  const r = spawnSync("node", [SOI], {
    cwd: MOBILE,
    encoding: "utf8",
    env: process.env,
    maxBuffer: 64 * 1024 * 1024,
  });
  return { ma: r.status, ra: `${r.stdout ?? ""}${r.stderr ?? ""}` };
}

function apDung(sua, ten) {
  for (const s of sua) {
    const trc = fs.readFileSync(s.file, "utf8");
    const soLan = trc.split(s.neo).length - 1;
    if (soLan !== 1) {
      // An anchor that is missing or doubled means this row did not test what
      // its name claims, so the run has no result to report.
      khoiPhuc();
      throw new Error(
        `${ten}: neo xuat hien ${soLan} lan trong ${path.basename(s.file)}, can dung 1`,
      );
    }
    fs.writeFileSync(s.file, trc.replace(s.neo, s.thay));
  }
}

function khoiPhuc() {
  // Safe only because the baseline is COMMITTED. Against a dirty tree this
  // deletes the very fix being measured -- that has happened in this repo.
  execFileSync("git", ["checkout", "--", ANH_DIA_DIEM, SOI], { cwd: MOBILE });
}

/** The two counts the summary carries, so the control can be held to the
 *  pre-review run's own numbers instead of to whatever it happens to print. */
function docTongKet(ra) {
  const m = ra.match(
    /DAT: (\d+) chu do TREN PIXEL ANH that, (\d+) chu do tren nen dac[^]*?tren (\d+) man/,
  );
  return m ? { trenAnh: Number(m[1]), nenDac: Number(m[2]), man: Number(m[3]) } : null;
}

/** Did the probe row fail on this screen, inside this screen's own block?
 *
 *  Section-aware on purpose: a global count of two `HONG ... [phep-thu]` lines
 *  could be one screen printing twice, which would let a row claim coverage of
 *  a frame it never reached. */
function probeDoOMan(ra, man) {
  const dong = ra.split("\n");
  const dau = dong.findIndex((l) => l.startsWith(`  -- ${man}:`));
  if (dau === -1) return { do: false, vi: `khong thay man ${man} trong dau ra` };
  let cuoi = dong.length;
  for (let i = dau + 1; i < dong.length; i += 1) {
    if (dong[i].startsWith("  -- ")) {
      cuoi = i;
      break;
    }
  }
  const hit = dong
    .slice(dau, cuoi)
    .find((l) => /^\s*HONG\s/.test(l) && l.includes("[phep-thu]"));
  return hit
    ? { do: true, vi: hit.trim() }
    : { do: false, vi: `${man}: khong co hang HONG nao cua [phep-thu]` };
}

if (!process.env.PUPPETEER_EXECUTABLE_PATH) {
  // Without a browser nothing renders, and a tool that cannot render has no
  // numbers to move. Refuse rather than report that as a result.
  throw new Error("can PUPPETEER_EXECUTABLE_PATH -- thieu Chrome thi khong do duoc gi");
}

const bundleSach = dung();
if (!bundleSach.includes(BUNDLE_GOC)) {
  throw new Error(
    `bundle sach khong chua \`${BUNDLE_GOC}\` -- lop Scrim da doi hinh dang, nen phep ` +
      "kiem 'dot bien da vao bundle' duoi day khong con y nghia.",
  );
}
const sach = chay();
console.log(`nen sach: ma=${sach.ma} (can 0)`);
if (sach.ma !== 0) {
  console.log(sach.ra.slice(-2000));
  throw new Error("nen sach da do san -- moi con so duoi deu vo nghia");
}

/* The control, before it is trusted to vouch for anything: on a clean tree it
 * has to reproduce the pre-review run's own two numbers. A reconstruction that
 * lands anywhere else is not the old instrument, and a green from it would be a
 * green about nothing. */
apDung(CONG_CU_CU, "kiem chung cong cu cu");
const cuSach = chay();
const tkCu = docTongKet(cuSach.ra);
khoiPhuc();
if (
  cuSach.ma !== 0 ||
  !tkCu ||
  tkCu.trenAnh !== CHU_TRUOC_REVIEW ||
  tkCu.man !== MAN_TRUOC_REVIEW
) {
  console.log(cuSach.ra.slice(-1200));
  throw new Error(
    `cong cu cu dung lai khong khop ban truoc review: can ma=0 va ` +
      `${CHU_TRUOC_REVIEW} chu / ${MAN_TRUOC_REVIEW} man, nhan ma=${cuSach.ma} va ` +
      `${tkCu ? `${tkCu.trenAnh} chu / ${tkCu.man} man` : "khong doc duoc tong ket"}. ` +
      "Chua dung lai duoc phep do cu thi hang S2 khong chung duoc gi.",
  );
}

/* The defining blindness of the pre-review instrument, asserted rather than
 * assumed. It decided "on a photograph" from rectangle overlap alone, so it
 * could not tell a chip from a picture and filed EVERY overlap as `TREN ANH` --
 * precisely the flaw the review found, and why the scrim mutation moved nothing.
 * A reconstruction that reports even one text on an opaque ground has kept some
 * of the new discrimination and is not the old tool, however well its two counts
 * happen to line up. Unlike a screen count, this does not drift as the app
 * grows, which is why the check above was allowed to stop being a literal. */
if (tkCu.nenDac !== 0) {
  console.log(cuSach.ra.slice(-1200));
  throw new Error(
    `cong cu cu bao ${tkCu.nenDac} chu tren nen dac, can 0. Ban truoc review khong ` +
      "phan biet duoc nen dac voi anh -- no goi moi hop chong len anh la TREN ANH. " +
      "Con dem duoc nen dac nghia la ban dung lai VAN CON phep do moi, nen hang S2 " +
      "dang so ban moi voi chinh no.",
  );
}
console.log(
  `cong cu cu dung lai: ma=0, ${tkCu.trenAnh} chu / ${tkCu.man} man ` +
    `(khop ban truoc review)`,
);

let dat = 0;
for (const m of DOT_BIEN) {
  apDung(m.sua, m.ten);

  // The measurement reads the bundle, so the bundle is what has to carry the
  // mutation. A source-only edit produced a false green here once already.
  const bundle = dung();
  if (bundle.includes(BUNDLE_GOC) || !bundle.includes(BUNDLE_DOT)) {
    khoiPhuc();
    throw new Error(
      `${m.ten}: dot bien KHONG vao bundle (van con \`${BUNDLE_GOC}\`, hoac thieu ` +
        `\`${BUNDLE_DOT}\`). Ket qua duoi se la ve ban dung cu.`,
    );
  }

  const r = chay();
  let ket;
  if (m.kieu === "canMu") {
    const tk = docTongKet(r.ra);
    const dungSo = tk && tk.trenAnh === CHU_TRUOC_REVIEW && tk.man === MAN_TRUOC_REVIEW;
    ket =
      r.ma === 0 && dungSo
        ? "XANH dung du kien (cong cu cu MU voi vet dut nay)"
        : r.ma !== 0
          ? "DO ngoai du kien"
          : "XANH nhung sai so -- khong phai phep do cu";
    if (r.ma === 0 && dungSo) dat += 1;
    if (tk) {
      console.log(
        `    van bao ${tk.trenAnh} chu / ${tk.man} man dat chuan, trong khi lop wash da bi go han`,
      );
    }
  } else {
    const vs = m.manPhaiDo.map((man) => probeDoOMan(r.ra, man));
    const duLyDo = r.ma !== 0 && vs.every((v) => v.do);
    ket = r.ma === 0 ? "XANH (CONG MU)" : duLyDo ? "DO dung ly do" : "DO NHAM LY DO";
    if (duLyDo) dat += 1;
    for (const v of vs) console.log(`    ${v.do ? "" : "THIEU: "}${v.vi}`);
  }
  console.log(`${m.ten}\n    -> ${ket}  (ma=${r.ma})`);
  khoiPhuc();
}

const bundleLai = dung();
if (!bundleLai.includes(BUNDLE_GOC)) {
  throw new Error("khoi phuc xong ma bundle van khong co lop Scrim goc");
}
const lai = chay();
console.log(`\nsau khi khoi phuc: ma=${lai.ma} (can 0)`);
console.log(`dung du kien: ${dat}/${DOT_BIEN.length}`);
process.exitCode = dat === DOT_BIEN.length && lai.ma === 0 ? 0 : 1;
