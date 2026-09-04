/**
 * Kỷ niệm in the RuDi shell (M6, slice vi-a): the bridge from the shell to
 * the memory-wall, album and achievement clients App B already proved, plus
 * the pure helpers the screens draw from.
 *
 * What the server owns: the wall (`/contexts/{id}/memories`, photo and
 * check-in alike, paged by cursor), hearts and comments on it, the album per
 * outing and its reel (`reeled:false` is a normal answer, not an error), and
 * the bytes of every photo -- read with the caller's headers, never a public
 * URL. What the server does not have: achievements. Those are App B's pure
 * `thanh-tich.ts` over `GET /people/{id}/finance`, so every badge here is
 * explainable from the ledger and nothing is awarded on the phone's say-so.
 *
 * App B read the wall once (limit 24) and ignored `next_cursor`; the shell
 * pages, because a group that has been out twenty times has more than a
 * screenful.
 */
import type { ImageSource } from "expo-image";

import {
  ANH_REFUSALS,
  BASE_URL,
  XA_HOI_REFUSALS,
  attemptFor,
  boTim,
  docBinhLuan,
  guiBinhLuan,
  taiAnhNhom,
  thaTim,
  themKyNiemAnh,
  translatedAsActor,
  type Attempt,
  type BinhLuanWire,
  type KyNiemWire,
} from "../../api";
import { headerNguoiGoi } from "../../danh-tinh";
import {
  TEN_DIA_DIEM_CHUA_BIET,
  layAlbum,
  layDanhSachAlbum,
  layThuocPhim,
  lyDoPhim,
  tenDiaDiem,
  type Album,
  type CanhPhim,
  type DanhSachAlbum,
  type ThuocPhim,
  type TomTatAlbum,
} from "../../screens/album/album-api";
import { layTaiChinh, type Finance } from "../../screens/ca-nhan/tai-chinh";
import { dinhDangTienVnd } from "../../screens/chat/ke-hoach";
import {
  huyHieuCuaNguoi,
  thuThachTuan,
  tienDoCapDo,
  type HuyHieu,
  type ThuThach,
  type TienDoCap,
} from "../../screens/thanh-tich/thanh-tich";

export type { Album, CanhPhim, DanhSachAlbum, HuyHieu, ThuThach, ThuocPhim, TienDoCap, TomTatAlbum };
export { TEN_DIA_DIEM_CHUA_BIET, layAlbum, layDanhSachAlbum, layThuocPhim, lyDoPhim, tenDiaDiem };

/** One memory on the wall, as the screen draws it. Counts are the server's. */
export type KyNiem = {
  id: string;
  authorId: string;
  kind: "photo" | "checkin";
  imageUrl: string | null;
  caption: string | null;
  placeName: string | null;
  createdAt: string;
  reactionCount: number;
  commentCount: number;
  toiDaTim: boolean;
};

export type TrangTuong = { kyNiem: KyNiem[]; conNua: boolean; conTro: string | null };

export type BinhLuan = { id: string; tacGiaId: string; tenTacGia: string; noiDung: string; luc: string };

function soHoacKhong(x: unknown): number {
  return typeof x === "number" && Number.isInteger(x) ? x : 0;
}

function docKyNiemWire(w: KyNiemWire): KyNiem {
  return {
    id: w.id,
    authorId: w.author_id,
    kind: w.kind,
    imageUrl: w.image_url,
    caption: w.caption,
    placeName: w.place_name,
    createdAt: w.created_at,
    reactionCount: soHoacKhong(w.reaction_count),
    commentCount: soHoacKhong(w.comment_count),
    toiDaTim: w.viewer_has_reacted === true,
  };
}

/** `GET /contexts/{id}/memories`, newest first, one page; `before` continues from the last cursor. */
export async function docTuongNhom(
  contextId: string,
  actorId: string,
  opts: { before?: string | null; limit?: number } = {},
): Promise<TrangTuong> {
  const limit = opts.limit === undefined ? 24 : opts.limit;
  const duoi = typeof opts.before === "string" && opts.before !== "" ? `&before=${encodeURIComponent(opts.before)}` : "";
  const r = await translatedAsActor<{ memories?: KyNiemWire[]; next_cursor?: unknown; has_more?: unknown }>(
    ANH_REFUSALS,
    `/contexts/${contextId}/memories?limit=${limit}${duoi}`,
    { method: "GET", actorId, roles: "member", contexts: contextId },
  );
  const danhSach = Array.isArray(r.memories) ? r.memories : [];
  return {
    kyNiem: danhSach.map(docKyNiemWire),
    conNua: r.has_more === true,
    conTro: typeof r.next_cursor === "string" ? r.next_cursor : null,
  };
}

/** Upload, then the memory: App B's two steps, the second under its own Attempt keyed by the stored url. */
export async function dangAnhLenTuong(
  contextId: string,
  anh: { uri: string },
  caption: string | null,
  actorId: string,
  attempts: Record<string, Attempt>,
): Promise<KyNiem> {
  const daTai = await taiAnhNhom(contextId, anh, actorId);
  const w = await themKyNiemAnh(contextId, daTai.url, caption, actorId, attemptFor(attempts, `ky-niem:${daTai.url}`));
  return docKyNiemWire(w);
}

/** `POST /contexts/{id}/checkins`: a memory without a photo, pinned to a catalogue place. */
export async function checkInKyNiem(
  contextId: string,
  placeId: string,
  caption: string | null,
  actorId: string,
  attempt: Attempt,
): Promise<KyNiem> {
  const w = await translatedAsActor<KyNiemWire>(ANH_REFUSALS, `/contexts/${contextId}/checkins`, {
    method: "POST",
    body: { place_id: placeId, caption: caption !== null && caption.trim() !== "" ? caption.trim() : null },
    actorId,
    attempt,
    roles: "member",
    contexts: contextId,
  });
  return docKyNiemWire(w);
}

/** Heart or un-heart; returns the row as it will read after the server agreed. */
export async function doiTim(k: KyNiem, contextId: string, actorId: string): Promise<KyNiem> {
  if (k.toiDaTim) {
    await boTim(contextId, k.id, actorId);
    return { ...k, toiDaTim: false, reactionCount: Math.max(0, k.reactionCount - 1) };
  }
  await thaTim(contextId, k.id, actorId);
  return { ...k, toiDaTim: true, reactionCount: k.reactionCount + 1 };
}

function docBinhLuanWire(w: BinhLuanWire): BinhLuan {
  return { id: w.id, tacGiaId: w.author_id, tenTacGia: w.display_name, noiDung: w.body, luc: w.created_at };
}

export async function docBinhLuanCua(contextId: string, memoryId: string, actorId: string): Promise<BinhLuan[]> {
  return (await docBinhLuan(contextId, memoryId, actorId)).map(docBinhLuanWire);
}

export async function guiBinhLuanCho(
  contextId: string,
  memoryId: string,
  noiDung: string,
  actorId: string,
  attempts: Record<string, Attempt>,
): Promise<BinhLuan> {
  const body = noiDung.trim();
  const w = await guiBinhLuan(contextId, memoryId, body, actorId, attemptFor(attempts, `binh-luan:${memoryId}:${body}`));
  return docBinhLuanWire(w);
}

/**
 * How the screen loads a photo: the read route wants the caller's headers, so
 * the image source carries them (expo-image sends `source.headers`). A server
 * url that is not ours is refused rather than fetched with our credentials.
 */
export function nguonAnh(imageUrl: string | null, actorId: string, contextId: string): ImageSource | null {
  if (imageUrl === null || imageUrl === "") return null;
  if (!imageUrl.startsWith("/")) return null;
  return { uri: BASE_URL + imageUrl, headers: headerNguoiGoi(actorId, { roles: "member", contexts: contextId }) };
}

/* ------------------------------------------------------------ pure copy */

export function cauKyNiem(k: KyNiem): string {
  if (k.kind === "checkin") return k.placeName === null ? "Check-in" : `Check-in tại ${k.placeName}`;
  if (k.caption !== null && k.caption.trim() !== "") return k.caption.trim();
  return "Ảnh của nhóm";
}

export function cauTuongTac(k: KyNiem): string {
  return `${k.reactionCount} tim · ${k.commentCount} bình luận`;
}

export const CAPTION_DAI_NHAT = 300;

export function cauThongKeAlbum(a: Pick<TomTatAlbum, "photo_count" | "place_count" | "checkin_count" | "expense_count" | "split_total_vnd">): string {
  // Non-breaking spaces: a count must not be orphaned from its noun when the line wraps.
  const phan = [`${a.photo_count}\u00a0ảnh`, `${a.place_count}\u00a0chỗ đã tới`, `${a.checkin_count}\u00a0check-in`];
  if (a.expense_count > 0) phan.push(`đã chia\u00a0${dinhDangTienVnd(a.split_total_vnd)}`);
  return phan.join(" · ");
}

/** Who made the reel, said out loud: model output is labelled, and a reel that was not made says why. */
export function cauThuocPhim(t: ThuocPhim): string {
  if (t.reeled && t.source === "ai") return `Rủ Đi AI dựng thước phim này, ${t.picks.length} cảnh.`;
  if (t.reeled) return "Thước phim dựng từ kỷ niệm của nhóm, không phải AI dựng.";
  return lyDoPhim(t.reason);
}

/* ------------------------------------------------------------ achievements */

export type ThanhTich = { so: Finance; tienDo: TienDoCap; huyHieu: HuyHieu[]; thuThach: ThuThach[] };

/** Everything the achievements screen shows, derived from the ledger by App B's rules. */
export async function docThanhTich(personId: string, bayGio: number = Date.now()): Promise<ThanhTich> {
  const so = await layTaiChinh(personId);
  return { so, tienDo: tienDoCapDo(so), huyHieu: huyHieuCuaNguoi(so), thuThach: thuThachTuan(so, bayGio) };
}

export function cauCapDo(t: TienDoCap): string {
  return `Cấp ${t.cap} · ${t.diemTrongCap}/${t.diemMoiCap} điểm tới cấp ${t.cap + 1}`;
}

export function demHuyHieuMo(huyHieu: HuyHieu[]): string {
  const mo = huyHieu.filter((h) => h.trangThai === "mo").length;
  return `${mo}/${huyHieu.length} đã mở`;
}
