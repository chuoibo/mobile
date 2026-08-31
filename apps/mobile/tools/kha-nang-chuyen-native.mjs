/** Which of this lane's measuring tools survive the move to a native build?
 *
 * ## Why this exists
 *
 * Every UI number this lane has reported was measured on React Native Web in
 * Chrome. The product ships to Android and iOS. So before anyone spends a day
 * porting, the question worth answering is not "how good is the UI" but "how
 * many of our measuring instruments still read anything at all once the DOM is
 * gone" -- because an instrument that silently returns nothing reads exactly
 * like a clean result.
 *
 * ## Why direct imports are the wrong unit
 *
 * Grepping each tool for `puppeteer` under-counts badly. The mutation drivers
 * (`dot-bien-*.mjs`) import none of it: they spawn OTHER tools, and those tools
 * drive Chrome. `dot-bien-quet-duong-di.mjs` names no browser package and is
 * entirely browser-bound, because it runs `quet-man-sau-tap.mjs` and
 * `screen-snapshots.mjs`. Counting direct imports alone reports such a file as
 * portable, which is the optimistic direction -- the dangerous one.
 *
 * So this walks the call graph: static relative imports PLUS child-process
 * invocations, which in this tree appear as plain path literals
 * (`execFileSync("node", ["tools/fixup-esm.mjs"])`, `const SUITE =
 * "tests/bill-gan-mon.test.mjs"`). A file is web-bound if it reaches a web
 * surface marker over any number of hops.
 *
 * ## What this does NOT prove
 *
 * This is a STATIC read of source text, not a behavioural measurement. It
 * proves a file mentions a path or a package; it cannot prove the code on that
 * path actually executes at run time. It is deliberately biased toward
 * reporting MORE breakage: a file that merely names another file is treated as
 * depending on it. Read the output as "at least this many break", never as an
 * exact count, and never as "the rest are proven to work on device" -- nothing
 * here has been run against a device.
 *
 * The `--doi-chung` self-check is what makes the number worth reading: it
 * plants a two-hop web-bound file and an isolated portable file and requires
 * the classifier to get both right. If the transitive walk ever regresses to a
 * direct-import grep, the two-hop canary flips to portable and this exits 1.
 *
 * Usage, from `apps/mobile`:
 *   node tools/kha-nang-chuyen-native.mjs              # table + counts
 *   node tools/kha-nang-chuyen-native.mjs --json       # machine readable
 *   node tools/kha-nang-chuyen-native.mjs --chi-truc-tiep   # direct imports only
 * Exit 0 report produced, 1 self-check failed or nothing discovered.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MOBILE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Packages and local helpers that only exist because a DOM does. */
const WEB_SURFACE = [
  "puppeteer",
  "playwright",
  "jsdom",
  "react-native-web",
  "react-dom",
  "renderToStaticMarkup",
  "getStyleElement",
  "chrome-cdp",
];

const DIRS = ["tools", "tests"];

/** Strip comments so a package named in prose is not read as a dependency. */
function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

/** Every .mjs under the measured directories, discovered rather than listed. */
function discover() {
  const out = [];
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name === "node_modules" || e.name.startsWith(".")) continue;
        walk(full);
      } else if (e.name.endsWith(".mjs")) {
        out.push(path.relative(MOBILE_ROOT, full));
      }
    }
  };
  for (const d of DIRS) walk(path.join(MOBILE_ROOT, d));
  return out.sort();
}

/** Local .mjs files this one names, by import or by child-process path literal. */
function edgesOf(rel, src) {
  const code = stripComments(src);
  const found = new Set();

  // Relative imports: import x from "./y.mjs", import("../tools/z.mjs")
  for (const m of code.matchAll(/(?:from|import|require)\s*\(?\s*["'`](\.[^"'`]+\.mjs)["'`]/g)) {
    const abs = path.resolve(path.dirname(path.join(MOBILE_ROOT, rel)), m[1]);
    found.add(path.relative(MOBILE_ROOT, abs));
  }
  // Child-process targets appear as bare repo-relative literals.
  for (const m of code.matchAll(/["'`]((?:tools|tests)\/[\w./-]+\.mjs)["'`]/g)) {
    found.add(m[1]);
  }
  found.delete(rel);
  return [...found];
}

/** Does this file's own text name a web surface? */
function touchesWebDirectly(src) {
  const code = stripComments(src);
  return WEB_SURFACE.filter((m) => code.includes(m));
}

/** Build the graph, then close it transitively over the edges. */
function classify(files, read, { directOnly = false } = {}) {
  const direct = new Map();
  const edges = new Map();
  for (const f of files) {
    const src = read(f);
    direct.set(f, touchesWebDirectly(src));
    edges.set(f, directOnly ? [] : edgesOf(f, src).filter((e) => files.includes(e)));
  }

  const verdict = new Map();
  const seenStack = new Set();
  const resolve = (f) => {
    if (verdict.has(f)) return verdict.get(f);
    if (seenStack.has(f)) return null; // cycle: let the other frame decide
    seenStack.add(f);
    let why = direct.get(f).length ? { via: f, markers: direct.get(f) } : null;
    if (!why) {
      for (const e of edges.get(f)) {
        const r = resolve(e);
        if (r) {
          why = { via: e, markers: r.markers };
          break;
        }
      }
    }
    seenStack.delete(f);
    verdict.set(f, why);
    return why;
  };
  for (const f of files) resolve(f);
  return { verdict, direct, edges };
}

/** Prove the walk is not a direct-import grep wearing a longer name. */
function selfCheck() {
  const files = ["tools/__canary-a.mjs", "tools/__canary-hop.mjs", "tools/__canary-b.mjs"];
  const fake = {
    // A reaches the browser only through two hops, and names none of it.
    "tools/__canary-a.mjs": 'const NEXT = "tools/__canary-hop.mjs"; run(NEXT);',
    "tools/__canary-hop.mjs": 'import { findChrome } from "../tests/chrome-cdp.mjs";',
    // B is isolated: it must NOT be smeared web-bound by its neighbours.
    "tools/__canary-b.mjs": "export const x = 1 + 1;",
  };
  const { verdict } = classify(files, (f) => fake[f]);
  const problems = [];
  if (!verdict.get("tools/__canary-a.mjs")) {
    problems.push("canary A (web-bound over 2 hops) came out PORTABLE -- transitive walk is broken");
  }
  if (verdict.get("tools/__canary-b.mjs")) {
    problems.push("canary B (isolated) came out WEB-ONLY -- classifier is smearing");
  }
  return problems;
}

/** Stage two: which tests run on react-native-web because the BUILD says so?
 *
 * Stage one only finds tools that drive a browser. It misses the larger and
 * quieter half. `tools/fixup-esm.mjs` walks all of `dist-test` and rewrites
 * `from "react-native"` to `from "react-native-web"` in every emitted module,
 * so a test that names no browser at all still renders through the web library
 * the moment it imports a screen. Its own docstring is explicit that this
 * "deliberately cannot prove ... anything about iOS or Android".
 *
 * This reads the built artifact instead of the source, so it is a measurement
 * of what actually ran, not a guess about what might. It needs `npm test` to
 * have produced `dist-test` first, and refuses to report a number when that
 * directory is absent -- a missing input must not read as "nothing affected".
 */
function stageTwo(testFiles) {
  const distRoot = path.join(MOBILE_ROOT, "dist-test");
  if (!fs.existsSync(distRoot)) return { ran: false };

  const rewritten = new Set();
  const distEdges = new Map();
  const walkDist = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walkDist(full);
      else if (e.name.endsWith(".js")) {
        const rel = path.relative(distRoot, full);
        // Comments must be stripped first. `api.js` explains a react-native-web
        // quirk in prose, and a bare substring search calls that an import: a
        // loose `grep react-native-web` over this same tree reports 37 modules
        // where 0 actually import it. Match the import forms, not the topic.
        const src = stripComments(fs.readFileSync(full, "utf8"));
        if (/(?:from|import)\s*["']react-native-web["']/.test(src)) rewritten.add(rel);
        const deps = [];
        for (const m of src.matchAll(/from\s*["'](\.[^"']+\.js)["']/g)) {
          deps.push(path.relative(distRoot, path.resolve(path.dirname(full), m[1])));
        }
        distEdges.set(rel, deps);
      }
    }
  };
  walkDist(distRoot);

  const memo = new Map();
  const reachesRnw = (mod, stack = new Set()) => {
    if (memo.has(mod)) return memo.get(mod);
    if (stack.has(mod)) return false;
    stack.add(mod);
    let hit = rewritten.has(mod);
    if (!hit) {
      for (const d of distEdges.get(mod) ?? []) {
        if (reachesRnw(d, stack)) {
          hit = true;
          break;
        }
      }
    }
    stack.delete(mod);
    memo.set(mod, hit);
    return hit;
  };

  const bound = [];
  for (const t of testFiles) {
    const src = fs.readFileSync(path.join(MOBILE_ROOT, t), "utf8");
    const mods = [...stripComments(src).matchAll(/from\s*["'][^"']*dist-test\/([^"']+\.js)["']/g)].map(
      (m) => m[1],
    );
    if (mods.some((m) => reachesRnw(m))) bound.push(t);
  }
  return { ran: true, rewrittenCount: rewritten.size, distCount: distEdges.size, bound };
}

const args = process.argv.slice(2);
const asJson = args.includes("--json");
const directOnly = args.includes("--chi-truc-tiep");

const problems = selfCheck();
if (problems.length) {
  for (const p of problems) console.error(`DOI CHUNG HONG: ${p}`);
  process.exit(1);
}

const files = discover();
if (files.length === 0) {
  console.error("Khong tim thay file .mjs nao trong tools/ va tests/ -- danh sach nguon RONG.");
  console.error("Cong nay tu thao khi chay sai thu muc. Chay tu apps/mobile.");
  process.exit(1);
}

const read = (f) => fs.readFileSync(path.join(MOBILE_ROOT, f), "utf8");
const full = classify(files, read, { directOnly });
const directOnlyRun = directOnly ? full : classify(files, read, { directOnly: true });

const webBound = files.filter((f) => full.verdict.get(f));
const portable = files.filter((f) => !full.verdict.get(f));
const directBound = files.filter((f) => directOnlyRun.verdict.get(f));
const onlyTransitive = webBound.filter((f) => !directOnlyRun.verdict.get(f));

// Stage two only has anything to say about the files stage one called portable.
const s2 = stageTwo(portable.filter((f) => f.endsWith(".test.mjs")));
const rnwBound = s2.ran ? s2.bound : [];
const afterS2 = portable.filter((f) => !rnwBound.includes(f));

/* Stage three: gates that read the exported WEB bundle as text.
 *
 * `npm test` builds with `expo export --platform web`, and 20 cases assert
 * against that output. The android export is Hermes BYTECODE (magic c6 1f bc
 * 03), not text: measured on this tree, `build-check.invalid` appears 8 times
 * in the web bundle and 0 times in the .hbc, `VietQR` 2 times and 0. A
 * string-grep gate does not fail loudly there -- it reports "not found",
 * which is the same answer it gives for a feature that was genuinely deleted.
 */
const bundleReaders = afterS2.filter((f) =>
  /expo-build-check|_expo\/static/.test(fs.readFileSync(path.join(MOBILE_ROOT, f), "utf8")),
);
const trulyLeft = afterS2.filter((f) => !bundleReaders.includes(f));

if (asJson) {
  console.log(
    JSON.stringify(
      {
        do_tai: "apps/mobile/{tools,tests}/**/*.mjs",
        tong: files.length,
        web_bound: webBound.length,
        portable: portable.length,
        bat_duoc_boi_import_truc_tiep: directBound.length,
        chi_bat_duoc_khi_di_theo_do_thi: onlyTransitive.length,
        chi_transitive: onlyTransitive,
        con_lai_sau_tang_1: portable.length,
        tang_2_chay_duoc: s2.ran,
        tang_2_module_bi_viet_lai: s2.ran ? `${s2.rewrittenCount}/${s2.distCount}` : null,
        tang_2_test_chay_tren_rnw: rnwBound.length,
        tang_3_ca_doc_bundle_web: bundleReaders.length,
        con_lai_that_su: trulyLeft.length,
        con_lai: trulyLeft,
      },
      null,
      2,
    ),
  );
} else {
  console.log(`Do tai   : apps/mobile/{tools,tests}/**/*.mjs`);
  console.log(`Tong     : ${files.length} file do dac`);
  console.log(`WEB-ONLY : ${webBound.length}  (mat phep do khi bo DOM)`);
  console.log(`Con lai  : ${portable.length}`);
  console.log("");
  console.log(`Grep import truc tiep chi thay : ${directBound.length}`);
  console.log(`Di theo do thi thay them       : ${onlyTransitive.length}`);
  console.log("");
  console.log("Chi bat duoc khi di theo do thi (grep truc tiep doc nham la PORTABLE):");
  for (const f of onlyTransitive) {
    console.log(`  ${f}  -> web qua ${full.verdict.get(f).via}`);
  }
  console.log("");
  if (!s2.ran) {
    console.log("TANG 2: KHONG CHAY DUOC -- thieu dist-test/. Chay `npm test` truoc.");
    console.log("        Dung doc cho nay thanh 'khong test nao dinh react-native-web'.");
  } else {
    console.log(`TANG 2 -- doc BAN DUNG, khong doc van ban nguon`);
    console.log(`  module dist-test bi viet lai sang react-native-web : ${s2.rewrittenCount}/${s2.distCount}`);
    console.log(`  test tang 1 goi la PORTABLE nhung chay tren rnw    : ${rnwBound.length}`);
  }
  console.log(`TANG 3 -- ca doc BAN DUNG WEB nhu van ban`);
  console.log(`  android xuat ra Hermes bytecode, grep chuoi tra 0    : ${bundleReaders.length}`);
  console.log("");
  console.log(`CON LAI THAT SU: ${trulyLeft.length}/${files.length}`);
  console.log("");
  console.log("Khong cham web surface va khong qua rnw (van CHUA chay tren may that):");
  for (const f of trulyLeft) console.log(`  ${f}`);
}
