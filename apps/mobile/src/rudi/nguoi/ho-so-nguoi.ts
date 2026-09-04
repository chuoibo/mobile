/**
 * Somebody else's profile and wall (M8).
 *
 * Two server reads, no arithmetic: `GET /people/{id}` says who they are and
 * what the reader's relation to them is, `GET /people/{id}/posts` says what of
 * their wall this reader may have. Both narrow at the server; nothing here
 * filters, and nothing here asks for an id the reader did not already hold.
 *
 * The empty wall is the delicate part. `GET /people/{id}/posts` answers 200
 * with an empty list rather than 403, so "no posts" and "nothing addressed to
 * you" arrive identically -- deliberately, so the route cannot be used as an
 * account directory. The screen therefore may not say «Chưa đăng bài nào»,
 * which would be a claim about the other person's wall this app cannot make.
 * `cauTuongRong` says only what is true: nothing here for you to read.
 */
import { ApiError, docTuongNguoi, translatedAsActor, type PostWire } from "../../api";
import { MUC_NGUOI_DOC, type Audience } from "../../screens/ca-nhan/bai-dang";

/** What `GET /people/{id}` returns: no counts, no login methods, no phone. */
export type HoSoNguoi = {
  id: string;
  display_name: string;
  bio: string | null;
  city: string | null;
  created_at: string;
  relation: QuanHe;
};

export type QuanHe = "self" | "friend" | "groupmate";

export type Bai = PostWire;

/**
 * Refusals in words that name the next move.
 *
 * `person_not_visible` is the server's single answer for both "this id is not
 * a person" and "this person is not visible to you" -- keeping the two apart
 * on the screen would rebuild the oracle the server refuses to be, so the
 * sentence covers both without guessing which one happened.
 */
export const LOI_NGUOI: Record<string, string> = {
  person_not_visible:
    "Hồ sơ này chỉ bạn bè hoặc người cùng nhóm mới xem được. Gửi lời mời kết bạn trước nhé.",
  person_not_found: "Máy chủ chưa có hồ sơ cho tài khoản này.",
};

/** One person's public profile, as this reader is allowed to see it. */
export async function docHoSoNguoi(personId: string, actorId: string): Promise<HoSoNguoi> {
  return translatedAsActor<HoSoNguoi>(LOI_NGUOI, `/people/${personId}`, {
    method: "GET",
    actorId,
  });
}

/** Their wall, already narrowed by the server to what this reader may have. */
export async function docTuongCua(personId: string, actorId: string): Promise<Bai[]> {
  return docTuongNguoi(personId, actorId);
}

/** The relation, said in the second person. Drives the header chip. */
export function cauQuanHe(quanHe: QuanHe): string {
  if (quanHe === "self") return "Hồ sơ của bạn";
  if (quanHe === "friend") return "Bạn bè";
  return "Cùng nhóm";
}

/**
 * What an empty wall means, without claiming the wall is empty.
 *
 * For `self` the claim is safe: you are allowed to read everything you wrote,
 * so nothing back means nothing written. For the other two it is not.
 */
export function cauTuongRong(quanHe: QuanHe): string {
  if (quanHe === "self") return "Bạn chưa đăng bài nào. Bài đầu tiên chỉ mình bạn đọc, trừ khi bạn đổi mức người đọc.";
  return "Chưa có bài nào bạn đọc được. Người ấy có thể đã đăng ở mức riêng tư hơn.";
}

/** «Tham gia từ tháng 9/2026», from the server's ISO string. */
export function cauNgayVao(iso: string): string {
  const ngay = new Date(iso);
  if (Number.isNaN(ngay.getTime())) return "";
  return `Tham gia từ tháng ${ngay.getMonth() + 1}/${ngay.getFullYear()}`;
}

/** The audience badge on one post, in the same words the composer offers. */
export function nhanMuc(audience: Audience): string {
  return MUC_NGUOI_DOC[audience]?.nhan ?? audience;
}

/**
 * The line under a post: when, and who could read it.
 *
 * The audience is shown on every post, including on somebody else's wall, so
 * a person can tell a public post from one they were let into.
 */
export function dongPhuBai(bai: Bai, bayGio: Date = new Date()): string {
  return `${cauLucNao(bai.created_at, bayGio)} · ${nhanMuc(bai.audience)}`;
}

/** Relative time, coarse on purpose: an exact clock adds nothing on a wall. */
export function cauLucNao(iso: string, bayGio: Date = new Date()): string {
  const luc = new Date(iso);
  if (Number.isNaN(luc.getTime())) return "";
  const phut = Math.floor((bayGio.getTime() - luc.getTime()) / 60000);
  if (phut < 1) return "Vừa xong";
  if (phut < 60) return `${phut} phút trước`;
  const gio = Math.floor(phut / 60);
  if (gio < 24) return `${gio} giờ trước`;
  const ngay = Math.floor(gio / 24);
  if (ngay < 7) return `${ngay} ngày trước`;
  return luc.toLocaleDateString("vi-VN");
}

/** Server refusals to a sentence, for the two reads this module makes. */
export function loiRaChu(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Không gọi được máy chủ. Kiểm tra mạng rồi thử lại.";
}
