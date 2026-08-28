/** Metro has to be told the repo is bigger than this folder.
 *
 * `src/screens/ChiaSe.tsx` imports `../../../../packages/shared/money.mjs`,
 * which exists and is tracked. TypeScript resolves it; Metro did not, because
 * by default it will not look above the project directory. The app therefore
 * failed to bundle at all -- while 34 tests passed, `tsc --noEmit` was clean,
 * and nobody noticed, because `tsconfig.test.json` compiles three logic files
 * and none of the screens.
 *
 * Every test being green is not the same as the app starting. That gap is what
 * this file closes, and it took launching the thing to find it.
 */
const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

// Watch the repo root so `packages/shared` is inside the bundler's world.
config.watchFolders = [workspaceRoot];

// Look for modules here first, then at the root. Order matters: the app's own
// copy of a package must win, or two Reacts end up in one bundle.
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];

module.exports = config;
