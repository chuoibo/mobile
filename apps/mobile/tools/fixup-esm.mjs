/* Make tsc's output loadable by Node, so tests can run the real modules.
 *
 * The app's own tsconfig uses bundler resolution, so source files import
 * `./fixtures/proposals` with no extension -- which is what Metro wants and
 * what the rest of the codebase is written in. Node refuses that. Rather than
 * bend the source to suit the test runner, bend the build output.
 *
 * Three rewrites, and the second and third exist so that screens -- not just
 * plain `.ts` logic -- can be rendered in a test:
 *
 *   1. relative specifiers get their extension back;
 *   2. `react-native` becomes `react-native-web`;
 *   3. JSON imports get the attribute Node demands.
 *
 * (2) is not a stub and not a mock. It is the same substitution Expo's web
 * build performs, so a component rendered this way goes through the library
 * that ships to the browser, and the DOM it produces is the DOM a visitor
 * gets. That is the whole point: the bug this enabled a test for --
 * `accessibilityState` reaching the browser as nothing -- lives *in* that
 * substitution, and no assertion about the source file could have seen it.
 * What it deliberately cannot prove is anything about iOS or Android, where a
 * different library reads the same props.
 */
import { readdirSync, readFileSync, writeFileSync, statSync } from "node:fs";
import { join } from "node:path";

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) walk(path);
    else if (path.endsWith(".js")) {
      const fixed = readFileSync(path, "utf8")
        .replace(
          /from "(\.[^"]*?)"/g,
          // Any specifier that already carries an extension is left alone, not
          // just `.js`. `packages/shared/money.mjs` is imported by its real
          // filename because it is hand-written ESM rather than tsc output, and
          // the old `.endsWith(".js")` test did not match it -- so the rewrite
          // produced `money.mjs.js` and the loader failed on a file that was
          // sitting right there.
          (whole, spec) => (/\.(js|mjs|cjs|json)$/.test(spec) ? whole : `from "${spec}.js"`),
        )
        // Expo aliases this for every web build; the test build says so out
        // loud instead of resolving to the native package, which Node cannot
        // parse at all.
        .replace(/from "react-native"/g, 'from "react-native-web"')
        // `theme.ts` reads `tokens.json`. tsc emits a bare JSON import and
        // Node refuses it without the attribute.
        .replace(/from "([^"]*\.json)"/g, 'from "$1" with { type: "json" }');
      writeFileSync(path, fixed);
    }
  }
}

walk("dist-test");
