/* Two modules in one directory whose names differ only in casing.
 *
 * `src/screens/ca-nhan/Tuong.tsx` and `src/screens/ca-nhan/tuong.ts` both
 * shipped, and the pair took the mobile stage of the gate down:
 *
 *     dist-test/screens/ca-nhan/Tuong.js(20,104): error TS1149: File name
 *     '.../dist-test/screens/ca-nhan/tuong.js' differs from already included
 *     file name '.../dist-test/screens/ca-nhan/Tuong.js' only in casing.
 *
 * Two independent faults had to line up, so this file gates both of them.
 *
 * The first is the pair itself. On this machine the filesystem is
 * case-sensitive, so the two files coexist and `./tuong` resolves the way the
 * author meant; on any macOS or Windows checkout they are ONE path, and the
 * clone is broken before a compiler ever runs. TypeScript refuses the pair for
 * exactly that reason. So the rule is a property of `src/`, checked here by
 * walking it -- not by reading a tsconfig, and not by reading the compiler's
 * mind.
 *
 * The second is that `tsc --noEmit` was reading `dist-test/`, the output of
 * `tsc -p tsconfig.test.json`, through the default include pattern `**\/*`.
 * That is what made the failure look intermittent: a fresh clone has no
 * `dist-test/`, so the first run of the gate is green and only the second one
 * is red. It also means a renamed or deleted module leaves its stale `.js`
 * behind to be type-checked forever. `exclude` in `tsconfig.json` fixes it,
 * and the second test here proves the exclusion has teeth by planting a
 * collision that WOULD have been fatal and requiring the compiler to stay
 * silent about it.
 *
 * Why the walk is over the filesystem rather than `git ls-files`: a file that
 * has been written but not yet `git add`ed is exactly when this needs to fire,
 * and `git ls-files` is blind until then. `src/` holds no build output and no
 * scratch files, so walking it costs nothing in false reds.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/** Extensions TypeScript will resolve a bare `./name` import to. */
const MODULE_EXT = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];

function laModule(ten) {
  return MODULE_EXT.some((ext) => ten.endsWith(ext));
}

/** `Tuong.tsx` -> `Tuong`. What an import writes, without the extension. */
function than(ten) {
  return ten.replace(/\.[^.]+$/, "");
}

/** Every module file under `dir`, as paths relative to the package root. */
function moiModule(dir) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...moiModule(full));
    else if (laModule(entry.name)) found.push(relative(ROOT, full));
  }
  return found.sort();
}

test("không thư mục nào dưới src/ có hai module trùng tên khi bỏ qua chữ hoa thường", () => {
  const theoKhoa = new Map();
  for (const duong of moiModule(join(ROOT, "src"))) {
    const khoa = `${dirname(duong)}/${than(duong.split("/").pop()).toLowerCase()}`;
    if (!theoKhoa.has(khoa)) theoKhoa.set(khoa, []);
    theoKhoa.get(khoa).push(duong);
  }

  const dungDo = [...theoKhoa.values()].filter((nhom) => nhom.length > 1);
  assert.deepEqual(
    dungDo,
    [],
    "Hai module cùng thư mục chỉ khác nhau chữ hoa thường. Trên macOS và " +
      "Windows chúng là MỘT file, và tsc từ chối cặp này với TS1149. Đổi tên " +
      "một trong hai cho khác nhau nhiều hơn một chữ cái hoa:\n" +
      dungDo.map((nhom) => `  ${nhom.join("  <->  ")}`).join("\n"),
  );
});

test("tsc --noEmit không đọc thư mục dựng, nên hiện vật cũ không làm cổng đỏ", () => {
  // A collision of the same shape as the one that broke the gate, planted
  // where `tsc -p tsconfig.test.json` writes. Before `exclude` landed this
  // made `tsc --noEmit` exit 2; the point of the test is that it no longer
  // can, because build output is not source and is not type-checked.
  const moi = join(ROOT, "dist-test", "__canary-chu-hoa");
  try {
    mkdirSync(moi, { recursive: true });
    writeFileSync(join(moi, "Mau.js"), 'import "./mau";\nexport const mau = 1;\n');
    writeFileSync(join(moi, "mau.js"), "export const mau = 2;\n");
    // A plain type error too, so the test also covers the everyday version of
    // the same fault: a stale `.js` left behind by a module that was renamed.
    writeFileSync(join(moi, "hong.ts"), "export const so: number = 'khong phai so';\n");

    let ma = 0;
    let ra = "";
    try {
      ra = execFileSync("npx", ["--no-install", "tsc", "--noEmit"], {
        cwd: ROOT,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (loi) {
      ma = loi.status ?? 1;
      ra = `${loi.stdout ?? ""}${loi.stderr ?? ""}`;
    }

    assert.equal(
      ma,
      0,
      `tsc --noEmit phải bỏ qua dist-test/ nhưng đã báo lỗi:\n${ra}`,
    );
    assert.ok(
      !ra.includes("__canary-chu-hoa"),
      `tsc --noEmit vẫn đọc dist-test/:\n${ra}`,
    );
  } finally {
    rmSync(moi, { recursive: true, force: true });
  }
});
