/** Reading an opening destination out of the URL.
 *
 * `VoTab` records that its hand-rolled router is the right trade "when a
 * second entry point exists (a link into a group, a push notification)". This
 * is the smallest version of that second entry point, and it exists for a
 * reason worth stating plainly: a tab that can only be reached by tapping
 * cannot be measured. Every automated check of a screen -- the anti-pattern
 * detector, a screenshot diff, an accessibility pass -- loads a URL cold and
 * gets whatever the app opens on. Four of the five tabs were unreachable to
 * all of them.
 *
 * This is not an auth bypass, because there is no auth to bypass. `MoDau`
 * picks a demo person out of a hard-coded list of seven and "Bỏ qua" already
 * enters with nobody selected; naming one of those seven in a fragment is the
 * same act as tapping their button. When real sign-in arrives, this reads
 * whatever the session says and the fragment stops choosing a person.
 *
 * Web only by nature -- `location` does not exist on a phone -- so it degrades
 * to "no destination" rather than branching on platform.
 *
 * Format:  #tab=ca-nhan&nguoi=minh
 *
 * `?man=<tab>` is also accepted, because that is the spelling the Khám phá
 * work shipped with and the detector runs already point at it. It names a tab
 * and nothing else. Keeping it is three lines; dropping it would break those
 * runs silently -- they would still exit 0, still produce a report, and the
 * report would describe the opening screen while claiming to describe a tab.
 */
import { DEMO_PEOPLE, type DemoPerson } from "./nhom-demo";
import { TABS } from "./tabs";

export type DiemDen = {
  /** Which tab to open on, or null to use the default. */
  tab: string | null;
  /** Who to enter as. `null` means the opening screen still asks. */
  nguoi: DemoPerson | null;
  /** Whether the fragment asked to skip the opening screen at all. */
  boQuaMoDau: boolean;
};

export const KHONG_CO_DIEM_DEN: DiemDen = { tab: null, nguoi: null, boQuaMoDau: false };

/**
 * Parse a location fragment into a destination.
 *
 * Unknown tab names and unknown people are dropped rather than guessed at. A
 * fragment naming a tab that does not exist should open the app normally, not
 * open a blank screen -- and a typo'd person must never silently become a
 * different person, because this app then asks the API about their money.
 */
export function docDiemDen(hash: string, search = ""): DiemDen {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const rawSearch = search.startsWith("?") ? search.slice(1) : search;
  if (!raw && !rawSearch) return KHONG_CO_DIEM_DEN;

  const params = new URLSearchParams(raw);
  // Fragment wins over query: it is the richer form, and a page carrying both
  // asked for the specific thing rather than the compatible one.
  const tabAsked = params.get("tab") ?? new URLSearchParams(rawSearch).get("man");
  const tab = TABS.some((t) => t.id === tabAsked) ? tabAsked : null;

  const slug = params.get("nguoi");
  const nguoi = slug ? (DEMO_PEOPLE.find((p) => p.id === slug) ?? null) : null;

  return {
    tab,
    nguoi,
    // A recognised tab is enough to enter: opening the app on a named screen
    // with nobody signed in is a real state, and the screens render it.
    boQuaMoDau: tab !== null || nguoi !== null,
  };
}

/** The destination this page was opened with, if it is a page at all. */
export function diemDenHienTai(): DiemDen {
  const loc = (globalThis as { location?: { hash?: string; search?: string } }).location;
  if (!loc) return KHONG_CO_DIEM_DEN;
  return docDiemDen(loc.hash ?? "", loc.search ?? "");
}
