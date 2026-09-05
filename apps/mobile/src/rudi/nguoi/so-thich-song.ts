/**
 * The personalization step, wired to the server (M11, ADR-0019).
 *
 * Until now this screen collected eight taste chips and a budget band and said
 * so on itself: «Rủ Đi chỉ dùng lựa chọn này để cá nhân hóa gợi ý trên máy.
 * Chưa gửi lên máy chủ.» That was true, and being true is what made it a
 * boundary rather than a shell. This module is what makes it false in the
 * direction the product wanted.
 *
 * ## The vocabulary is the server's, and the copy of it here is deliberate
 *
 * `GET /interests` is the list. This screen is drawn before there is a session
 * -- on a phone that may not reach the server at all -- so it renders the local
 * copy in `screens/vao-cua/so-thich.ts` and never blocks on the network.
 * `tests/test_interest_vocabulary_matches_client.py` (repo root) fails the day
 * the two lists disagree, which is the failure neither side can see alone.
 *
 * ## What this module refuses to do
 *
 * It does not save anything for a reader with no session. The answers are the
 * person's own row; there is nobody to attach them to before sign-in, and
 * writing them to a device file that a later sign-in silently adopts would
 * make one phone's guesses look like somebody's stated taste.
 */
import { ApiError, translatedAnonymous, translatedAsActor } from "../../api";
import { NGAN_SACH, SO_THICH } from "../../screens/vao-cua/so-thich";

/** What `PUT /people/me/interests` answers, and what `GET /people/me` carries. */
export type SoThichSong = {
  /** Tag ids, in the vocabulary's order. */
  muc: string[];
  /** Band id, or null for «bỏ qua» -- which is not the cheapest band. */
  khoang: string | null;
};

export const LOI_SO_THICH: Record<string, string> = {
  interest_unknown: "Máy chủ chưa biết một trong những lựa chọn này. Thử cập nhật app.",
  budget_band_unknown: "Mức chi này máy chủ không còn dùng. Chọn lại giúp mình nhé.",
  person_not_found: "Máy chủ chưa có hồ sơ cho tài khoản này.",
};

type HoSoWire = { interests?: unknown; budget_band?: unknown };

/**
 * The vocabulary the server will actually accept, or null when it cannot be
 * reached.
 *
 * The screen renders `SO_THICH` and does not wait for this: it is drawn before
 * there is a session, on a phone that may have no network. What the answer buys
 * is a filter -- a chip this build knows but the server has dropped would
 * otherwise be tappable and then 422 on save, which reads as «the app is
 * broken» rather than «that word is gone». Anonymous on purpose: the list is a
 * product vocabulary and says nothing about anybody.
 */
export async function docTuVung(): Promise<string[] | null> {
  try {
    const body = await translatedAnonymous<{ interests?: unknown }>(
      LOI_SO_THICH,
      "/interests",
      { method: "GET" },
    );
    const ds = Array.isArray(body.interests) ? body.interests : [];
    const ids = ds
      .map((row) => (row as { id?: unknown })?.id)
      .filter((id): id is string => typeof id === "string");
    // An empty list is «the server answered nothing useful», which is the same
    // state as not reaching it: the screen keeps its own copy either way.
    if (ids.length === 0) return null;
    return ids;
  } catch {
    // Offline is the normal case for this screen. Falling back to the local
    // copy is right; showing an error for a list nobody asked to see is not.
    return null;
  }
}

/** Read one person's own answers off their profile. Nobody else's are readable. */
export async function docSoThich(personId: string): Promise<SoThichSong> {
  const body = await translatedAsActor<HoSoWire>(LOI_SO_THICH, "/people/me", {
    method: "GET",
    actorId: personId,
  });
  return doc(body);
}

/**
 * Replace the whole answer.
 *
 * A PUT because the screen holds all of it: a partial update would need the
 * client to say what it removed, and a client that gets that wrong leaves a
 * taste nobody can see to take back.
 */
export async function luuSoThich(personId: string, chon: SoThichSong): Promise<SoThichSong> {
  const body = await translatedAsActor<HoSoWire>(LOI_SO_THICH, "/people/me/interests", {
    method: "PUT",
    actorId: personId,
    body: { interests: chon.muc, budget_band: chon.khoang },
  });
  return doc(body);
}

/** The wire shape, read defensively: absent is «nothing», never a guess. */
export function doc(body: HoSoWire): SoThichSong {
  const muc = Array.isArray(body.interests)
    ? body.interests.filter((tag): tag is string => typeof tag === "string")
    : [];
  const bietMuc = new Set(SO_THICH.map((m) => m.id));
  const khoang = typeof body.budget_band === "string" ? body.budget_band : null;
  const bietKhoang = NGAN_SACH.some((k) => k.id === khoang);
  return {
    // A word this build does not know is dropped rather than rendered as an
    // id: the server's vocabulary may grow before this app does, and a chip
    // spelled «du-thuyen» on screen is worse than one chip fewer.
    muc: SO_THICH.filter((m) => muc.includes(m.id) && bietMuc.has(m.id)).map((m) => m.id),
    khoang: bietKhoang ? khoang : null,
  };
}

/** Has this person said anything at all? Empty is an answer; both empty is not. */
export function daNoiGi(chon: SoThichSong): boolean {
  return chon.muc.length > 0 || chon.khoang !== null;
}

/**
 * The sentence under the save button, which has to be true in three states.
 *
 * The old caption said «Chưa gửi lên máy chủ» and was correct. Keeping it after
 * wiring the route would be the exact lie the shell rule exists to forbid, and
 * printing «đã lưu» for a reader with no session would be the mirror of it.
 */
export function cauLuuTru(coPhien: boolean): string {
  return coPhien
    ? "Lựa chọn được lưu vào tài khoản của bạn và dùng để xếp gợi ý. Sửa lại bất cứ lúc nào ở Cá nhân."
    : "Đăng nhập rồi mới lưu được. Bây giờ lựa chọn chỉ nằm trên máy này.";
}

/** What the Cá nhân row shows beside «Sở thích». */
export function tomTat(chon: SoThichSong): string {
  if (!daNoiGi(chon)) return "Chưa chọn";
  const ten = SO_THICH.filter((m) => chon.muc.includes(m.id)).map((m) => m.nhan);
  const muc = ten.length === 0 ? "Chưa chọn sở thích" : ten.slice(0, 3).join(", ");
  const them = ten.length > 3 ? ` +${ten.length - 3}` : "";
  const khoang = NGAN_SACH.find((k) => k.id === chon.khoang);
  return khoang ? `${muc}${them} · ${khoang.nhan}` : `${muc}${them}`;
}

/** `ApiError` code, or null. Lets a screen keep its own copy for the rest. */
export function maLoi(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null;
}
