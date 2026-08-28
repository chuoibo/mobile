/* Add the extensions Node's ESM loader requires to tsc's output.
 *
 * The app's own tsconfig uses bundler resolution, so source files import
 * `./fixtures/proposals` with no extension -- which is what Metro wants and
 * what the rest of the codebase is written in. Node refuses that. Rather than
 * bend the source to suit the test runner, bend the build output.
 */
import { readdirSync, readFileSync, writeFileSync, statSync } from "node:fs";
import { join } from "node:path";

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) walk(path);
    else if (path.endsWith(".js")) {
      const fixed = readFileSync(path, "utf8").replace(
        /from "(\.[^"]*?)"/g,
        // Any specifier that already carries an extension is left alone, not
        // just `.js`. `packages/shared/money.mjs` is imported by its real
        // filename because it is hand-written ESM rather than tsc output, and
        // the old `.endsWith(".js")` test did not match it -- so the rewrite
        // produced `money.mjs.js` and the loader failed on a file that was
        // sitting right there.
        (whole, spec) => (/\.(js|mjs|cjs|json)$/.test(spec) ? whole : `from "${spec}.js"`),
      );
      writeFileSync(path, fixed);
    }
  }
}

walk("dist-test");
