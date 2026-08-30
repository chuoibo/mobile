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
import { docMaBan, type TheBan } from "../screens/vao-cua/ma-ban";
import { DEMO_PEOPLE, type DemoPerson } from "./nhom-demo";
import { TABS } from "./tabs";

/** The entry-door screens, which are not tabs and so cannot be named by `tab`.
 *
 * `dang-ky` is F01's form; `nhom` is the F03/F04 group screen and `ky-niem` is
 * the F30/F35 memory wall, both of which live behind the [+] menu inside the
 * shell. All three are unreachable to anything that loads a URL cold -- the
 * same hole this file was written to close for the four tabs, reappearing the
 * moment a screen was put behind a button.
 *
 * `ban-be` is the F03/F04 friend screen, which sits behind a button on the Cá
 * nhân tab. It is here for the same reason and one more: the gate that
 * measures it drives a real DOM, and a screen a URL cannot name is a screen no
 * detector, screenshot pass or accessibility sweep can reach at all.
 *
 * `widget` is F38, and it was added at the same moment the screen was, not
 * afterwards. rd-fe-33 shipped two map screens whose commit said they were
 * "URL-reachable" without adding them to any probe, and for one merge that
 * claim was read as "measured" -- ~780 lines nothing had scanned, under a table
 * printing a clean row for every screen it did visit. Reachable and measured
 * are two claims; this one carries both or neither.
 *
 * `album` is F36/F37, and it is here for one reason the others do not have:
 * the screen it opens is three deep (shelf -> one album -> the AI reel), and
 * only the shelf is reachable without walking. An address that lands on the
 * shelf is still the whole difference between "one tool can start the walk"
 * and "nothing can open this at all". */
export type ManVaoCua = "dang-ky" | "nhom" | "ky-niem" | "ban-be" | "widget" | "album";

const MAN_VAO_CUA: ManVaoCua[] = [
  "dang-ky",
  "nhom",
  "ky-niem",
  "ban-be",
  "widget",
  "album",
];

export type DiemDen = {
  /** Which tab to open on, or null to use the default. */
  tab: string | null;
  /** Who to enter as. `null` means the opening screen still asks. */
  nguoi: DemoPerson | null;
  /** Which entry-door screen to open, or null for none. Spelled `vao` rather
   *  than `man` because `?man=` already means a *tab* in the query form, and
   *  two keys with one name is how a detector run ends up describing the wrong
   *  screen while exiting 0. */
  vao: ManVaoCua | null;
  /** A specific group to open, from `nhom=<uuid>`.
   *
   * Only a well-formed UUID is accepted, and a malformed one becomes null
   * rather than being passed through: this value goes straight into a request
   * path, and a screen that asks the server about `../../etc` is a screen
   * writing somebody else's URL. Null means "find the demo group", which is
   * what every link that does not care should get. */
  nhomId: string | null;
  /** F05. A friend read off a scanned code, or null.
   *
   *  This is the second entry point `VoTab`'s header predicted -- "a link into
   *  a group" -- arriving for real. A person points their phone's own camera
   *  at somebody's square, the phone opens this app at this fragment, and the
   *  group screen comes up with that friend already identified. There is no
   *  in-app scanner and this is why one is not needed on the web build.
   *
   *  It grants nothing. The card it opens is a name and a button that sends
   *  the same `PUT /people/{id}` + `POST /contexts/{id}/members` pair the
   *  typed form sends, authorised by the same `X-Actor-ID` as everything else.
   *  A fragment cannot make somebody a member; only the group's admin can. */
  ban: TheBan | null;
  /** F46. A place id to open the detail card on, or null for the list.
   *
   *  The check-in card lives on a place's detail, which until now was reachable
   *  only by pressing a tile. That made it a screen no URL could name -- not
   *  reachable by a link somebody shares, and not reachable by a detector run
   *  either, which is the same hole `vao` was added to close for the entry
   *  door. An unknown id falls back to the list rather than an empty card. */
  diaDiem: string | null;
  /** rd-fe-33. Open the group map (F43/F44) straight away, from `#ban-do=1`.
   *
   *  Same hole as `dia-diem`, reappearing on the same tab: the map sits behind
   *  a button on Khám phá, so nothing that loads a URL cold could reach it --
   *  not a shared link, and not the anti-pattern detector either. Measured
   *  rather than assumed: `imp detect` on the two `.tsx` files scores them
   *  identically to a file built to be terrible, because a source scan cannot
   *  compute contrast or geometry. A rendered scan can, and a rendered scan
   *  needs an address. */
  banDo: boolean;
  /** rd-fe-33. Open Điểm hẹn (F45) directly, from `#ban-do=hen`. */
  diemHen: boolean;
  /** F36. Which trip's album to open on, from `#chuyen=<uuid>`, or null for
   *  the shelf.
   *
   *  The album screen is three deep and only its first level has an address
   *  without this. Naming the trip is what lets anything that loads a URL cold
   *  -- a shared link, the snapshot probe, an accessibility sweep -- reach the
   *  photo grid and the AI reel underneath instead of stopping at the shelf and
   *  reporting a clean number for two screens it never rendered.
   *
   *  UUID-checked for the same reason `nhomId` is: it goes straight into a
   *  request path, and a screen that asks the server about `../../etc` is a
   *  screen writing somebody else's URL. */
  albumChuyen: string | null;
  /** F14. An outing-invite token from `#moi=<token>`, or null.
   *
   *  The token is a free server string, not a UUID. Empty becomes null.
   *  A value carrying `/` or `..` is refused: it is interpolated into a
   *  request path, the same reason a malformed `nhomId` is dropped. */
  moiBuoiDi: string | null;
  /** Whether the fragment asked to skip the opening screen at all. */
  boQuaMoDau: boolean;
};

export const KHONG_CO_DIEM_DEN: DiemDen = {
  tab: null,
  nguoi: null,
  vao: null,
  nhomId: null,
  ban: null,
  diaDiem: null,
  banDo: false,
  diemHen: false,
  albumChuyen: null,
  moiBuoiDi: null,
  boQuaMoDau: false,
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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

  const vaoAsked = params.get("vao");
  // A scanned friend code implies the group screen without having to say so.
  // The square is produced by `linkMaBan`, which writes `ban=` and nothing
  // else; requiring `vao=nhom` beside it would mean a code that scans into the
  // Khám phá tab with the friend silently dropped.
  const ban = raw ? docMaBan("#" + raw) : null;
  const vao = MAN_VAO_CUA.find((m) => m === vaoAsked) ?? (ban ? "nhom" : null);

  const nhomAsked = params.get("nhom");
  const nhomId = nhomAsked && UUID_RE.test(nhomAsked) ? nhomAsked : null;

  // Trimmed, and empty means absent. `#dia-diem=` with nothing after it is what
  // a half-built link looks like, and it must open the list rather than a card
  // for a place with no id.
  const diaDiemAsked = (params.get("dia-diem") ?? "").trim();
  const diaDiem = diaDiemAsked === "" ? null : diaDiemAsked;

  // Presence is the signal, but an explicit "0" turns it off. A link written
  // by hand as `ban-do=0` means "not the map", and reading that as "yes"
  // because the key was there would be the sort of thing nobody notices until
  // a detector report describes the wrong screen while exiting 0.
  const banDoAsked = params.get("ban-do");
  const banDo = banDoAsked !== null && banDoAsked !== "0" && banDoAsked !== "false";
  // `ban-do=hen` goes one screen further, to Điểm hẹn. It is the heavier of the
  // two and the one carrying the inversion warning, so leaving it unnamed would
  // mean every rendered check measured the lighter screen and let the whole
  // feature inherit that result.
  const diemHen = banDoAsked === "hen";

  const chuyenAsked = params.get("chuyen");
  const albumChuyen = chuyenAsked && UUID_RE.test(chuyenAsked) ? chuyenAsked : null;

  const moiAsked = (params.get("moi") ?? "").trim();
  const moiBuoiDi =
    moiAsked === "" || moiAsked.includes("/") || moiAsked.includes("..")
      ? null
      : moiAsked;

  return {
    tab: tab ?? (diaDiem || banDo ? "kham-pha" : null),
    nguoi,
    vao,
    nhomId,
    ban,
    diaDiem,
    banDo,
    diemHen,
    albumChuyen,
    moiBuoiDi,
    // A recognised tab is enough to enter: opening the app on a named screen
    // with nobody signed in is a real state, and the screens render it.
    //
    // `vao=dang-ky` is deliberately NOT enough. That screen sits before the
    // shell and registers somebody; skipping the opening screen to reach it
    // would mean a link could put a person straight into a form that writes to
    // `people`. `vao=nhom` and `vao=ky-niem` do enter, because both live inside
    // the shell and have nothing to show outside it.
    //
    // `dia-diem` enters for the same reason `vao=nhom` does: the card it names
    // is inside the shell, so stopping at the opening screen would mean the
    // link silently does nothing. `ban-be` is the same shape again.
    boQuaMoDau:
      tab !== null ||
      nguoi !== null ||
      vao === "nhom" ||
      vao === "ky-niem" ||
      vao === "ban-be" ||
      // F38. Inside the shell like the three above, and with nothing to show
      // outside it: the widget reads one group's newest photograph, and the
      // opening screen has no group.
      vao === "widget" ||
      // F36/F37. Inside the shell like the rest, and with nothing to show
      // outside it: an album belongs to one group, and the opening screen has
      // no group.
      vao === "album" ||
      diaDiem !== null ||
      banDo ||
      moiBuoiDi !== null,
  };
}

/** The destination this page was opened with, if it is a page at all. */
export function diemDenHienTai(): DiemDen {
  const loc = (globalThis as { location?: { hash?: string; search?: string } }).location;
  if (!loc) return KHONG_CO_DIEM_DEN;
  return docDiemDen(loc.hash ?? "", loc.search ?? "");
}
