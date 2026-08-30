/* Every module specifier in this app resolves on a machine that is not the
 * one it was written on.
 *
 * Thirteen tools under `tools/` imported puppeteer by absolute path:
 *
 *     import puppeteer from "file:///home/lakiet/.claude/node_modules/..."
 *
 * On the author's laptop that path exists, so every one of them ran and every
 * measurement they produced looked trustworthy. Nowhere else does it exist. CI
 * died at module load with ERR_MODULE_NOT_FOUND before a single assertion ran,
 * and it died on the *whole file*: `luoi-kham-pha` and `tim-binh-luan` import
 * `tab-snapshots.mjs`, so the image-regression cases went down with it. The
 * repo went public with the browser half of its evidence runnable on exactly
 * one computer.
 *
 * An absolute specifier is a worse defect than an absolute data path, and the
 * difference is why this gate draws its line where it does. A data path with an
 * env override degrades: `findChrome()` in `tests/chrome-cdp.mjs` tries
 * CHROME_BIN, then /usr/bin/google-chrome, and a test that cannot find a
 * browser says so. An import has no override and no fallback. It fails
 * unconditionally, at load, before any code can explain itself.
 *
 * So: specifiers must be bare or relative. Declare the dependency in
 * package.json and let the resolver do its job.
 *
 * What this proves: no import in apps/mobile names a path outside the package.
 * What it does not prove: that the dependency is pinned, that it installs, or
 * that the browser those tools drive can be found at runtime. Those are
 * package-lock.json, `npm ci`, and findChrome() respectively.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * Source files this package owns, read from git rather than the filesystem.
 *
 * `git ls-files` and not a recursive walk: a walk finds `node_modules/`, build
 * output under `dist-test/` and `.expo-build-check/`, and whatever scratch file
 * happens to be lying in the tree, and every one of those would turn this gate
 * red for something nobody committed. The question is about the repository, so
 * ask the repository.
 */
function sourceFiles() {
  const out = execFileSync(
    "git",
    ["ls-files", "-z", "--", "*.mjs", "*.js", "*.ts", "*.tsx"],
    { cwd: MOBILE_ROOT, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  );
  return out.split("\0").filter(Boolean);
}

/**
 * Module specifiers that name a location outside this package.
 *
 * Anchored on import/export/require syntax, so a bare string that merely looks
 * like a path -- "/usr/bin/google-chrome" handed to `executablePath` -- is not
 * mistaken for one. Only the specifier position counts.
 */
const FORMS = [
  // import x from "..."  ·  import "..."  ·  export … from "..."
  /(?:^|[\s;}])(?:import|export)\s[^;]*?from\s*["']([^"']+)["']/g,
  /(?:^|[\s;}])import\s*["']([^"']+)["']/g,
  // await import("...")  ·  require("...")
  /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g,
  /\brequire\s*\(\s*["']([^"']+)["']\s*\)/g,
];

/**
 * Source with comments removed, because a comment is not an import.
 *
 * The banner at the top of this very file quotes the broken import as
 * documentation, and the first version of this gate flagged it -- prose that
 * describes a defect read as the defect. Left alone, a gate like that teaches
 * people to reword their comments, which is the opposite of what it is for.
 *
 * Block comments go whole (that is where JSDoc banners and their `*`
 * continuation lines live); line comments only when the line is nothing else.
 * A trailing `// ...` after real code survives, so an import commented out at
 * the end of a line still counts -- over-strict in a direction that reports
 * too much rather than too little, which is the safe direction for a gate.
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n");
}

function offendingSpecifiers(raw) {
  const src = stripComments(raw);
  const bad = [];
  for (const re of FORMS) {
    for (const [, spec] of src.matchAll(re)) {
      // Absolute POSIX path, a file:// URL, or a Windows drive letter. Bare
      // ("puppeteer-core") and relative ("../tools/x.mjs") are the two shapes
      // that survive being cloned somewhere else.
      if (/^(?:file:\/\/|\/|[A-Za-z]:[\\/])/.test(spec)) bad.push(spec);
    }
  }
  return bad;
}

test("không import nào trỏ ra ngoài package bằng đường dẫn tuyệt đối", () => {
  const found = [];
  for (const rel of sourceFiles()) {
    const src = readFileSync(join(MOBILE_ROOT, rel), "utf8");
    for (const spec of offendingSpecifiers(src)) found.push(`${rel}: ${spec}`);
  }

  assert.deepEqual(
    found,
    [],
    `import theo đường dẫn tuyệt đối chỉ chạy được trên một máy:\n  ${found.join("\n  ")}`,
  );
});

/* Absolute *data* paths are the softer half of the same defect, and fixing only
 * the imports proved that in one CI run: the module-not-found errors cleared and
 * the very next thing the job printed was
 *
 *     Chromium not found at /home/lakiet/.cache/ms-playwright/...
 *
 * Same cause, one layer down. This is a separate case rather than part of the
 * import gate because the two are not equally severe -- an import cannot be
 * overridden and kills the file at load, while a browser path has env overrides
 * in front of it -- but a literal home directory is somebody else's machine
 * either way, and CI cannot use it.
 *
 * Scoped to /home/<user> and /Users/<user>. Rooted system paths like
 * /usr/bin/google-chrome are exactly what the fallbacks are supposed to name.
 */
test("không đường dẫn nào trỏ vào thư mục nhà của một người cụ thể", () => {
  const HOME = /["'](\/home\/[^/"']+|\/Users\/[^/"']+)\//g;
  const found = [];
  for (const rel of sourceFiles()) {
    const src = stripComments(readFileSync(join(MOBILE_ROOT, rel), "utf8"));
    for (const [, prefix] of src.matchAll(HOME)) found.push(`${rel}: ${prefix}/...`);
  }
  assert.deepEqual(
    found,
    [],
    `đường dẫn cứng vào thư mục nhà, chỉ tồn tại trên một máy:\n  ${found.join("\n  ")}`,
  );
});

/* The gate above is a regex over source, so it is worth one case proving the
 * regex can actually see the shape it was written to catch. Without this, a
 * botched pattern reports zero findings on a tree full of them and reads
 * exactly like a clean run -- which is the failure mode that let the original
 * thirteen sit unnoticed. */
test("phép kiểm bắt được đúng hình dạng đã làm CI đỏ", () => {
  /* Every specifier below is interpolated, never written out as a literal.
   *
   * The first draft of this case spelled the bad import out in full, and the
   * gate above -- correctly -- flagged this very file the moment it was
   * committed and `git ls-files` began returning it. The tempting repair is to
   * exempt this file from the scan, which would leave the one file nobody is
   * watching free to carry the exact defect it exists to forbid. Building the
   * fixtures at runtime keeps this file inside the scan and still hands the
   * matcher the byte-for-byte shape that broke CI. */
  // Assembled from parts so the literal never appears in this file: the second
  // gate forbids a hardcoded home directory, and it scans this file too.
  const NHA = ["", "home", "lakiet", ".claude"].join("/");
  const CU = `file://${NHA}/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js`;
  assert.deepEqual(offendingSpecifiers(`import puppeteer from "${CU}";`), [CU]);

  // Other shapes of the same defect, so the gate is not pinned to one literal.
  const ABS = "/abs/x.mjs";
  const ABS_URL = "file://" + "/abs/x.mjs";
  assert.equal(offendingSpecifiers(`import a from "${ABS}";`).length, 1);
  assert.equal(offendingSpecifiers(`await import("${ABS_URL}");`).length, 1);
  assert.equal(offendingSpecifiers(`const a = require("${ABS}");`).length, 1);

  // And the shapes that must stay legal, including the data path this gate is
  // deliberately not policing.
  const BARE = "puppeteer-core";
  const REL = "../tools/x.mjs";
  const BIN = "/usr/bin/google-chrome";
  assert.deepEqual(offendingSpecifiers(`import puppeteer from "${BARE}";`), []);
  assert.deepEqual(offendingSpecifiers(`import { STEPS } from "${REL}";`), []);
  assert.deepEqual(offendingSpecifiers(`const CHROME = "${BIN}";`), []);

  // Comments describing the defect are not the defect. Both shapes appear in
  // this file's own banner, which is how the false positive was found.
  assert.deepEqual(offendingSpecifiers(`/* import a from "${CU}"; */`), []);
  assert.deepEqual(offendingSpecifiers(`// import a from "${CU}";`), []);
  // The banner shape: a `*` continuation line inside a block comment. Only the
  // enclosing /* */ makes it a comment, which is why it is written out in full
  // here rather than as a lone `* ...` line.
  assert.deepEqual(
    offendingSpecifiers(`/**\n * Was:\n *     import a from "${CU}";\n */`),
    [],
  );

  // But stripping comments must not blind the scan to real code around them.
  assert.deepEqual(
    offendingSpecifiers(`/* banner */\nimport a from "${ABS}";`),
    [ABS],
  );
});
