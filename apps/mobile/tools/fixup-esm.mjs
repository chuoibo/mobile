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
        (whole, spec) => (spec.endsWith(".js") ? whole : `from "${spec}.js"`),
      );
      writeFileSync(path, fixed);
    }
  }
}

walk("dist-test");
