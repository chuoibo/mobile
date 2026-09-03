/**
 * What a cold-start URL means, decided before anything navigates.
 *
 * ## The defect this replaces
 *
 * `LegacyFragmentAdapter` used to read
 *
 *     if (pathname !== "/") return;
 *     void Linking.getInitialURL().then((url) => { ... router.replace(...) });
 *
 * The guard is synchronous and the redirect is not. On a cold start expo-router
 * renders `/` for a frame before it resolves the deep link, so the guard passed,
 * the promise then resolved, and `router.replace("/welcome")` fired on top of
 * the route the link had just opened. Measured on Expo Go 57 / SDK 57:
 * `exp://localhost:8095/--/settlements/team-da-lat` landed on the welcome
 * screen 4 times out of 4, and deleting the one `<LegacyFragmentAdapter />`
 * line made the same link open the settlement screen. With the `rudi://` scheme
 * that is every invite, share and push-notification link in the product.
 *
 * ## The rule now
 *
 * Exactly one thing changes: a URL that ALREADY NAMES A ROUTE is left alone,
 * because the router has already honoured it. Everything else the old code did
 * is kept, and the reason is a measurement rather than a preference.
 *
 * The first version of this file also dropped the `?? "/welcome"` fallback, on
 * the reasoning that `app/index.tsx` redirects a pathless entry to `/welcome`
 * anyway. On the emulator that turned out to be false: a `console.log` in
 * `IndexRoute` never fired, and a pathless cold start landed on the Khám phá
 * tab. expo-router does not route `exp://localhost:8095` through `/` at all, so
 * the unconditional redirect was the ONLY thing putting anybody on the welcome
 * screen. Twelve Maestro flows went red at once and said so.
 *
 * That is the shape of finding a web-target gate cannot produce, and it is the
 * reason the fallback is spelled out here instead of being inferred from the
 * route tree.
 *
 * Kept as a pure function of the URL string so it can be tested without a
 * device, a router, or a frame of render. The version that lived inside the
 * component could only be measured by driving an emulator.
 */

/** Fragment (from the legacy web app) to route. */
const LEGACY_FRAGMENT_ROUTES: Record<string, string> = {
  explore: "/explore",
  "lap-ke-hoach": "/plan",
  plan: "/plan",
  "tin-nhan": "/messages",
  messages: "/messages",
  "ca-nhan": "/profile",
  profile: "/profile",
};

export type DiemVao =
  /** expo-router already knows where to go, or there is nowhere to go. */
  | { kieu: "giu-nguyen" }
  /** A legacy fragment names a screen expo-router did not open. */
  | { kieu: "doi-huong"; toi: string }
  /**
   * The link carries an invitation, which is how a real person gets in.
   *
   * Kept apart from `doi-huong` because the token must not become part of a
   * route string. A secret in a path is a secret in the navigation history, in
   * a crash report, and in whatever the router logs.
   */
  | { kieu: "loi-moi"; ma: string };

const GIU_NGUYEN: DiemVao = { kieu: "giu-nguyen" };

/**
 * The route part of a deep link, or "" when the URL names no route.
 *
 * Expo Go wraps the app's own path after `/--/`; everything before it is the
 * dev server's host and port, which is not a route. A custom scheme has no
 * wrapper, and its first segment IS part of the path -- `rudi://settlements/x`
 * opens `/settlements/x`, so the host must not be stripped there.
 */
function duongDan(url: string): string {
  const truoc = url.split("#")[0].split("?")[0];
  const moc = truoc.indexOf("/--/");
  if (moc >= 0) return truoc.slice(moc + 4).replace(/^\/+|\/+$/g, "");
  if (/^exps?:/i.test(truoc)) return "";
  return truoc.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "").replace(/^\/+|\/+$/g, "");
}

const WELCOME: DiemVao = { kieu: "doi-huong", toi: "/welcome" };

/**
 * The invitation a link is carrying, or "".
 *
 * `rudi://moi/<token>` is the shape a real invitation ships as; the Expo Go
 * form `exp://host:port/--/moi/<token>` is the same path behind the dev
 * wrapper, and both fall out of `duongDan` above. Only the FIRST segment after
 * `moi/` is taken: a token is one opaque string, and treating anything after a
 * second slash as part of it would quietly accept a malformed link.
 */
function maLoiMoi(duong: string): string {
  if (!duong.startsWith("moi/")) return "";
  const ma = duong.slice(4).split("/")[0];
  return decodeURIComponent(ma);
}

export function diemVaoTuUrl(url: string | null | undefined): DiemVao {
  // Launched from the icon with no URL at all. expo-router picks its own
  // initial route, and on this app that is not the welcome screen.
  if (!url) return WELCOME;
  // The web QA harness addresses screens with `?man=` and with `#key=value`
  // fragments. Neither is a route name, and neither is this function's job.
  if (url.includes("?man=")) return GIU_NGUYEN;
  const manh = url.split("#")[1]?.replace(/^\/+/, "") ?? "";
  if (manh.includes("=")) return GIU_NGUYEN;
  const duong = duongDan(url);
  // An invitation, before the route check: `moi/<token>` looks like a path to
  // expo-router, and letting the router "honour" it would land on a screen
  // that does not exist while the token went nowhere.
  const ma = maLoiMoi(duong);
  if (ma !== "") return { kieu: "loi-moi", ma };
  // A URL that already names a route has already been honoured by the router.
  // This is the branch whose absence sent every deep link to /welcome.
  if (duong !== "") return GIU_NGUYEN;
  const toi = LEGACY_FRAGMENT_ROUTES[manh];
  return toi === undefined ? WELCOME : { kieu: "doi-huong", toi };
}
