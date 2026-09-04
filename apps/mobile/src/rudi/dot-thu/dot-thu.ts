/**
 * Đợt thu in the RuDi shell (M5, slice v-b): the bridge from the shell to the
 * batch client App B already proved end to end, plus the pure helpers the
 * screens draw from.
 *
 * What the server owns, and what this module never does:
 *
 *   - Obligations, their amounts and their status come from `/batches` and the
 *     board. Status is derived on the server from confirmed receipts; nothing
 *     here adds money or decides that a transfer arrived.
 *   - Guest links exist exactly once. The server persists only a SHA-256
 *     digest of a token, so the publish response is the only copy there will
 *     ever be. This module returns it; keeping it is the screen's job (see
 *     `kho-link.ts`), and a phone that never published a round has no link to
 *     show for it -- the screen says so instead of inventing one.
 *   - Who may say "the money arrived" is the recipient of that obligation.
 *     The board is read with ids, not names, so the screen can tell.
 */
import {
  OPEN_BATCH_REFUSALS,
  PUBLISH_REFUSALS,
  confirmReceipt,
  publishBatch,
  translatedAsActor,
  type Attempt,
} from "../../api";
import type { Envelope } from "../../screens/ChiaSe";
import { dinhDangTienVnd } from "../../screens/chat/ke-hoach";
import { tenCua, type ThanhVien } from "../chia-bill/hoa-don";

/** The guest-link envelope App B's publish returns; the type lives with its legacy screen until M6 moves it. */
export type { Envelope };

export type TrangThaiDot =
  | "accruing"
  | "frozen"
  | "published"
  | "collecting"
  | "completed"
  | "closed_with_exceptions"
  | "cancelled";

/** One round as `GET /contexts/{id}/batches` lists it. Counts are the server's. */
export type DotThuTomTat = {
  id: string;
  trangThai: TrangThaiDot;
  taoLuc: string;
  phatLuc: string | null;
  soNghiaVu: number;
  soDaNhan: number;
  soTranhCai: number;
  tongVnd: number;
};

export type TrangThaiNghiaVu =
  | "outstanding"
  | "partially_confirmed"
  | "confirmed"
  | "over_confirmed"
  | "waived"
  | "disputed";

/** One obligation on the board, with ids: names are the screen's to look up. */
export type NghiaVu = {
  id: string;
  senderId: string;
  recipientId: string;
  amountVnd: number;
  trangThai: TrangThaiNghiaVu;
  tranhCai: boolean;
};

type DotThuWire = {
  batch_id: string;
  status: TrangThaiDot;
  created_at: string;
  published_at: string | null;
  obligation_count: number;
  confirmed_count: number;
  disputed_count: number;
  total_vnd: number;
};

/** Sentences for the refusals a round can meet on the way in, on top of App B's table. */
export const LOI_MO_DOT: Record<string, string> = {
  ...OPEN_BATCH_REFUSALS,
  no_unbatched_allocations:
    "Sổ chưa có khoản nào để thu: mọi khoản đã vào một đợt thu rồi, hoặc chưa có khoản nào được ghi.",
  expense_versions_unavailable: "Khoản chi này đã nằm trong một đợt thu khác, hoặc chưa được xác nhận.",
  due_at_not_future: "Hạn thu phải ở tương lai.",
};

export const LOI_PHAT_DOT: Record<string, string> = { ...PUBLISH_REFUSALS };

/** `GET /contexts/{id}/batches`, newest first as the server orders it. */
export async function docDotThuCuaNhom(contextId: string, actorId: string): Promise<DotThuTomTat[]> {
  const result = await translatedAsActor<{ batches: DotThuWire[] }>({}, `/contexts/${contextId}/batches`, {
    method: "GET",
    actorId,
    contexts: contextId,
  });
  return result.batches.map((row) => ({
    id: row.batch_id,
    trangThai: row.status,
    taoLuc: row.created_at,
    phatLuc: row.published_at,
    soNghiaVu: row.obligation_count,
    soDaNhan: row.confirmed_count,
    soTranhCai: row.disputed_count,
    tongVnd: row.total_vnd,
  }));
}

/**
 * `POST /batches`: the same request App B's `openBatch` sends, minus the
 * proposal object it reads the group from -- the shell has the group id in
 * hand. `expenseVersionIds: null` asks the server for every confirmed
 * allocation not yet in a round, which is what "Tạo đợt thu từ sổ" means.
 * Seven days to pay, as App B chose; the server refuses a past date itself.
 */
export async function moDotThu(input: {
  contextId: string;
  actorId: string;
  expenseVersionIds: string[] | null;
  attempt: Attempt;
}): Promise<{ batchId: string; nghiaVu: NghiaVu[] }> {
  const result = await translatedAsActor<{
    batch_id: string;
    obligations: { obligation_id: string; sender_id: string; recipient_id: string; amount_vnd: number }[];
  }>(LOI_MO_DOT, "/batches", {
    body: {
      context_id: input.contextId,
      expense_version_ids: input.expenseVersionIds,
      due_at: new Date(input.attempt.at + 7 * 24 * 60 * 60 * 1000).toISOString(),
    },
    actorId: input.actorId,
    attempt: input.attempt,
    contexts: input.contextId,
  });
  return {
    batchId: result.batch_id,
    nghiaVu: result.obligations.map((row) => ({
      id: row.obligation_id,
      senderId: row.sender_id,
      recipientId: row.recipient_id,
      amountVnd: row.amount_vnd,
      trangThai: "outstanding" as const,
      tranhCai: false,
    })),
  };
}

/**
 * `POST /batches/{id}/publish`. The advancer-acknowledged gate is the
 * server's: a round reached from the list carries no client-side flag, so
 * the client gate is passed and the server's 409 comes back as a sentence.
 */
export function phatDotThu(batchId: string, actorId: string, attempt: Attempt, roster: ThanhVien[]): Promise<Envelope[]> {
  return publishBatch(batchId, { payerAcknowledged: true }, actorId, attempt, roster, roster);
}

/** The board, with ids. Same folding rule as App B's `loadBoard`: a disputed, untouched obligation reads as disputed. */
export async function docBangThu(contextId: string, batchId: string, actorId: string): Promise<{ nghiaVu: NghiaVu[]; soTranhCai: number }> {
  const result = await translatedAsActor<{
    disputed_count: number;
    obligations: {
      obligation_id: string;
      sender_id: string;
      recipient_id: string;
      amount_vnd: number;
      obligation_status: TrangThaiNghiaVu;
      disputed: boolean;
    }[];
  }>({}, `/batches/${batchId}/obligations`, { method: "GET", actorId, contexts: contextId });
  return {
    soTranhCai: result.disputed_count,
    nghiaVu: result.obligations.map((row) => ({
      id: row.obligation_id,
      senderId: row.sender_id,
      recipientId: row.recipient_id,
      amountVnd: row.amount_vnd,
      trangThai: row.disputed && row.obligation_status === "outstanding" ? "disputed" : row.obligation_status,
      tranhCai: row.disputed,
    })),
  };
}

export async function xacNhanDaNhan(obligationId: string, amountVnd: number, actorId: string, attempt: Attempt): Promise<TrangThaiNghiaVu> {
  const result = await confirmReceipt(obligationId, amountVnd, actorId, attempt);
  return result.status;
}

/* ------------------------------------------------------------ pure helpers */

/**
 * Wording for an obligation: what the SENDER's money did. Deliberately not
 * App B's «chưa gửi»/«đã nhận»: on this screen the organiser also "sends" a
 * link, and two facts about two different people must not share a verb.
 * «đã về» is the hero's own word (lượt chuyển đã về), so the row and the
 * count read as one thing.
 */
export const TU_NGHIA_VU: Record<TrangThaiNghiaVu, string> = {
  outstanding: "chưa chuyển",
  partially_confirmed: "chuyển một phần",
  confirmed: "đã về",
  over_confirmed: "về dư",
  waived: "được bỏ qua",
  disputed: "đang thắc mắc",
};

export function cauTrangThaiDot(trangThai: TrangThaiDot): string {
  switch (trangThai) {
    case "accruing":
      return "Đang gom";
    case "frozen":
      return "Chưa phát";
    case "published":
      return "Đã phát";
    case "collecting":
      return "Đang thu";
    case "completed":
      return "Đã thu xong";
    case "closed_with_exceptions":
      return "Đã đóng, còn ngoại lệ";
    case "cancelled":
      return "Đã huỷ";
  }
}

/** True once the round has been published: links exist, obligations are real. */
export function daPhat(trangThai: TrangThaiDot): boolean {
  return trangThai === "published" || trangThai === "collecting" || trangThai === "completed" || trangThai === "closed_with_exceptions";
}

const DA_VE = new Set<TrangThaiNghiaVu>(["confirmed", "over_confirmed"]);
const KHONG_CON_GI = new Set<TrangThaiNghiaVu>(["confirmed", "over_confirmed", "waived"]);

/** App B's hero figures: transfers done, and senders with nothing left. */
export function tomTatBang(nghiaVu: NghiaVu[]): { daVe: number; tong: number; nguoiXong: number; nguoiGui: number } {
  const nguoiGui = new Set(nghiaVu.map((n) => n.senderId));
  const nguoiXong = [...nguoiGui].filter((id) => nghiaVu.filter((n) => n.senderId === id).every((n) => KHONG_CON_GI.has(n.trangThai))).length;
  return { daVe: nghiaVu.filter((n) => DA_VE.has(n.trangThai)).length, tong: nghiaVu.length, nguoiXong, nguoiGui: nguoiGui.size };
}

/** One line for the round list: «3 lượt chuyển · 1 đã về · 500.000đ». */
export function cauTomTatDot(dot: DotThuTomTat): string {
  const phan = [`${dot.soNghiaVu} lượt chuyển`, `${dot.soDaNhan} đã về`];
  if (dot.soTranhCai > 0) phan.push(`${dot.soTranhCai} đang thắc mắc`);
  phan.push(dinhDangTienVnd(dot.tongVnd));
  return phan.join(" · ");
}

/** App B's share message, verbatim in shape; the money in the shell's format. */
export function loiNhanChiaSe(envelope: Envelope): string {
  return (
    `Phần của ${envelope.senderName}: ${dinhDangTienVnd(envelope.amountVnd)}\n${envelope.url}\n\n` +
    `Link này dành cho ${envelope.senderName}; ai có link đều xem được phần của ${envelope.senderName}.`
  );
}

/**
 * The obligations this person may confirm: the ones owed to them that have
 * not fully arrived. A disputed one is left out on purpose -- spec 8.2 stops
 * collection there until the objection is dealt with.
 */
export function nghiaVuToiNhan(nghiaVu: NghiaVu[], personId: string): NghiaVu[] {
  return nghiaVu.filter((n) => n.recipientId === personId && (n.trangThai === "outstanding" || n.trangThai === "partially_confirmed"));
}

/** «An QA → Ban QA», names from the roster, never an id. */
export function cauHangNghiaVu(n: NghiaVu, roster: ThanhVien[]): string {
  return `${tenCua(roster, n.senderId)} → ${tenCua(roster, n.recipientId)}`;
}
