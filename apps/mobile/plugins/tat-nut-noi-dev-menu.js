/**
 * Config plugin: turn the dev menu's floating "Tools" button off by default.
 *
 * Every native capture of the RuDi shell since the dev client shipped carries a
 * grey gear floating over the top-right corner -- on the Welcome hero, on the
 * bill, on the settlement. It is `expo-dev-menu`'s floating action button, a
 * debug-build affordance, and the audit of 2026-09-05 filed it as P0: it is
 * not product UI, but it is the first thing a viewer sees, and it costs trust
 * exactly where the demo reaches money.
 *
 * `DevMenuDefaultPreferences` (expo-dev-menu 57, debug source set) reads the
 * button's default from the manifest:
 *   metaDataBool("EXDevMenuShowFloatingActionButton", true)
 * so one `<meta-data>` on the application flips the default to hidden. The
 * menu itself stays reachable: `adb shell input keyevent 82`, a shake, or the
 * dev-client launcher. The setting is still toggleable in the menu's Tools
 * section; a person who wants the gear back gets it back.
 *
 * Release builds have no dev menu, so the meta-data is inert there.
 */
const { withAndroidManifest, AndroidConfig } = require("expo/config-plugins");

const META_KEY = "EXDevMenuShowFloatingActionButton";

/**
 * Pure transform on the parsed AndroidManifest.xml. Exported so a node test
 * can prove the meta-data lands, once, without running prebuild.
 */
function tatNutNoiDevMenu(manifest) {
  const app = AndroidConfig.Manifest.getMainApplicationOrThrow(manifest);
  // addMetaDataItemToMainApplication replaces an existing item with the same
  // name, so running the plugin twice leaves exactly one entry.
  AndroidConfig.Manifest.addMetaDataItemToMainApplication(app, META_KEY, "false");
  return manifest;
}

function withTatNutNoiDevMenu(config) {
  return withAndroidManifest(config, (c) => {
    c.modResults = tatNutNoiDevMenu(c.modResults);
    return c;
  });
}

module.exports = withTatNutNoiDevMenu;
module.exports.tatNutNoiDevMenu = tatNutNoiDevMenu;
module.exports.META_KEY = META_KEY;
