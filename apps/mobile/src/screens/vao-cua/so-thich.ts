/** F01.03 -- what the personalization step collects, and where it stops.
 *
 * React-free on purpose, like `danh-tinh.ts` beside it. The parts of this
 * screen that can be wrong -- the money in the budget presets, which answers
 * are optional, what a refused permission means -- are checked by
 * `tests/so-thich.test.mjs` rather than by looking at a phone.
 *
 * ## The honest boundary, stated once and not buried
 *
 * There is no route to save these answers. Measured against the running API of
 * this branch: `/people/{person_id}` has no preferences body, and the only
 * preference route the server has at all is
 * `GET /contexts/{context_id}/preference-profile` -- read-only, and about a
 * *group*, which does not exist yet at the moment somebody finishes signing
 * up. So the answers live in this module for the length of the session and are
 * gone on reload.
 *
 * That makes persistence a shell, and naming it here is the point: a screen
 * that collects taste and quietly drops it is indistinguishable, from the
 * outside, from one that saved it. Whoever adds `PUT /people/{id}/preferences`
 * replaces `ghiNhoSoThich` and nothing else on the screen changes.
 *
 * What is *not* a shell: every choice below is real state, reaches the
 * caller, and the budget is real money under this repo's first law.
 *
 * ## Why the budget is a range of integers and not a number
 *
 * Law 1 is integer đồng, including intermediate values, and a "budget" typed
 * as one number invites the average of a range -- which is how `225000.5`
 * enters a product that has no halves of a đồng. A preset is two integer
 * bounds and no arithmetic is done on them here.
 *
 * `null` is a legal answer and is not "unknown means cheap": the mockup's own
 * rule is that a skipped budget leaves recommendation on default rather than
 * guessing hard, so `khoang` stays absent instead of being filled in with the
 * middle preset.
 */

/** One taste chip. `nhan` is the accessible name; `hinh` is decoration beside
 *  it and never carries meaning on its own. */
export type SoThichMuc = { id: string; nhan: string; hinh: string };

/** The eight the mockup draws, in its reading order.
 *
 * A fixed local vocabulary rather than the place catalogue's categories, and
 * that is a decision rather than a shortcut: this question is about the person,
 * is asked before they have a group or a city, and must answer identically on a
 * device that cannot reach the server. Binding it to `GET /places` would make
 * signing up fail when the catalogue is empty.
 */
export const SO_THICH: readonly SoThichMuc[] = [
  { id: "an-uong", nhan: "Ăn uống", hinh: "🍜" },
  { id: "cafe", nhan: "Cafe", hinh: "☕" },
  { id: "nightlife", nhan: "Nightlife", hinh: "🍸" },
  { id: "mon-local", nhan: "Món local", hinh: "🍲" },
  { id: "outdoor", nhan: "Outdoor", hinh: "🥾" },
  { id: "shopping", nhan: "Shopping", hinh: "🛍️" },
  { id: "karaoke", nhan: "Karaoke", hinh: "🎤" },
  { id: "game", nhan: "Game", hinh: "🎮" },
];

/** A budget band, per person, per outing, in đồng.
 *
 * `tu` is inclusive and `den` is exclusive, so the three bands below tile
 * without overlapping and no amount belongs to two of them. `den: null` is the
 * open top end; `tu: 0` is the open bottom.
 */
export type NganSachKhoang = {
  id: string;
  /** Inclusive lower bound, đồng. Integer. */
  tu: number;
  /** Exclusive upper bound, đồng. Integer, or null for no ceiling. */
  den: number | null;
  /** The range as the mockup prints it. */
  nhan: string;
  /** The one word under it. Not decoration: it is what makes the three
   *  comparable to somebody who does not read the numbers. */
  phu: string;
};

export const NGAN_SACH: readonly NganSachKhoang[] = [
  { id: "tiet-kiem", tu: 0, den: 100_000, nhan: "Dưới 100K", phu: "Tiết kiệm" },
  { id: "vua-phai", tu: 100_000, den: 250_000, nhan: "100K–250K", phu: "Vừa phải" },
  { id: "thoai-mai", tu: 250_000, den: 500_000, nhan: "250K–500K", phu: "Thoải mái" },
];

/** What the address book toggle actually resolved to.
 *
 * Three outcomes, not two. `chua-co` is the honest one for this build and is
 * why it exists: there is no contacts module in this app, so a screen that
 * offered only granted and denied would have to report one of them falsely.
 * The screen prints a different sentence for each, and none of the three
 * leaves the person with a switch that did nothing.
 */
export type KetQuaQuyen = "cho-phep" | "tu-choi" | "chua-co";

/** The seam the OS permission dialog will be plugged into.
 *
 * Injected rather than imported so the four states the mockup asks for are
 * reachable in a test without an emulator, and so that the day contacts are
 * wired the change is one function and not a screen rewrite.
 */
export type XinQuyenDanhBa = () => Promise<KetQuaQuyen>;

/** The default seam: this build does not read the address book.
 *
 * It resolves rather than throwing, and it resolves to the truth. Returning
 * `cho-phep` here to make the happy path look complete would be the exact lie
 * the shell rule exists to forbid.
 */
export const KHONG_CO_DANH_BA: XinQuyenDanhBa = async () => "chua-co";

/** Everything the step collected. Every field is optional by design: the
 *  mockup puts a "Bỏ qua" in the header, so finishing with nothing chosen is a
 *  supported answer and not a validation failure. */
export type SoThich = {
  /** Chip ids, in `SO_THICH` order rather than the order they were tapped, so
   *  two people who picked the same set produce the same value. */
  muc: string[];
  /** `null` when skipped. Never defaulted to a band. */
  khoang: NganSachKhoang | null;
  /** `null` until the toggle has been resolved one way or another. */
  danhBa: KetQuaQuyen | null;
};

export const SO_THICH_RONG: SoThich = { muc: [], khoang: null, danhBa: null };

/** Add or remove one chip, keeping the canonical order.
 *
 * Sorting by the catalogue rather than appending is what makes the result
 * comparable: an "Ăn uống then Cafe" tap order and a "Cafe then Ăn uống" one
 * are the same taste, and a caller diffing two sets should not see a change
 * because of the order somebody's thumb moved in.
 */
export function doiMuc(dangChon: string[], id: string): string[] {
  const co = dangChon.includes(id);
  const sau = co ? dangChon.filter((x) => x !== id) : [...dangChon, id];
  return SO_THICH.filter((m) => sau.includes(m.id)).map((m) => m.id);
}

/** Is this a band the catalogue actually holds?
 *
 * Used by the screen so a stale id from a previous session cannot select a
 * band that no longer exists and leave the group of three with nothing lit.
 */
export function khoangTheoId(id: string | null): NganSachKhoang | null {
  return NGAN_SACH.find((k) => k.id === id) ?? null;
}

/** One sentence per permission outcome, for the screen to print.
 *
 * Kept here beside the type rather than inline in the JSX so that adding a
 * fourth outcome cannot compile while leaving a state with no sentence, and so
 * the wording is readable in a test.
 *
 * `chua-co` names the limit without naming an error: nothing failed, the
 * feature is not in this build, and the person is told the thing they can
 * actually do instead.
 */
export function cauVeDanhBa(ket: KetQuaQuyen): string {
  switch (ket) {
    case "cho-phep":
      return "Đã bật. Rủ Đi sẽ cho bạn biết những người trong danh bạ đang dùng app.";
    case "tu-choi":
      return "Chưa bật đồng bộ. Bạn vẫn tìm được bạn bè bằng số điện thoại ở mục Cá nhân.";
    case "chua-co":
      return "Bản demo này chưa đọc danh bạ, nên chưa có gì được gửi đi. Tìm bạn bằng số điện thoại ở mục Cá nhân.";
  }
}

/** The answers this session gave, for whoever asks after the step is over.
 *
 * A module-level value and not a React context: the reader is not necessarily
 * inside the tree that collected it, and the whole thing is going away the
 * moment a server route exists. See this file's header for why nothing here
 * survives a reload.
 */
let daChon: SoThich | null = null;

export function ghiNhoSoThich(s: SoThich): void {
  daChon = s;
}

/** `null` means the step was never reached, which is different from reaching
 *  it and choosing nothing -- that answers `SO_THICH_RONG`. A caller deciding
 *  whether to ask again needs to tell those apart. */
export function soThichDaChon(): SoThich | null {
  return daChon;
}

/** Only tests call this. Session state that no test can clear makes the second
 *  test in a file read the first one's answers. */
export function quenSoThich(): void {
  daChon = null;
}
