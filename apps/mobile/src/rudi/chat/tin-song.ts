/**
 * The chat wire for the RuDi shell (M3): messages, reactions, read marks.
 *
 * Thin wrappers over `translatedAsActor` in `src/api.ts` so every call carries
 * the bearer (ADR-0014) and the `Idempotency-Key` for writes. The legacy chat
 * module (`src/screens/chat/tin-nhan.ts`) used its own `fetch` with actor
 * headers only, which a `prod` server ignores -- it cannot be reused here.
 *
 * Pure helpers (`gopTin`, `nhomTheoNgay`, `docTheAi`) are exported so the list
 * logic is testable without a device: an inverted FlatList wants newest-first,
 * a forward poll answers oldest-first, and mixing those up is how a chat shows
 * yesterday under today.
 */
import { type Attempt, newAttempt, translatedAsActor } from "../../api";

export type LoaiPhanUng = "heart" | "haha" | "like" | "wow" | "sad" | "fire";

export const PHAN_UNG: readonly { kind: LoaiPhanUng; glyph: string; nhan: string }[] = [
  { kind: "heart", glyph: "❤️", nhan: "Thích" },
  { kind: "haha", glyph: "😂", nhan: "Haha" },
  { kind: "like", glyph: "👍", nhan: "Đồng ý" },
  { kind: "wow", glyph: "😮", nhan: "Wow" },
  { kind: "sad", glyph: "😢", nhan: "Buồn" },
  { kind: "fire", glyph: "🔥", nhan: "Cháy" },
];

export function glyphPhanUng(kind: string): string {
  return PHAN_UNG.find((p) => p.kind === kind)?.glyph ?? "•";
}

export type PhanUngTomTat = { kind: LoaiPhanUng; count: number; mine: boolean };

export type Tin = {
  id: string;
  context_id: string;
  author_id: string | null;
  kind: "text" | "image" | "ai_card";
  body: string | null;
  image_url: string | null;
  card: unknown | null;
  created_at: string;
  cursor: string;
  reactions?: PhanUngTomTat[];
};

export type TrangTin = {
  context_id: string;
  messages: Tin[];
  next_cursor: string | null;
  has_more: boolean;
};

export type LuotAi = {
  context_id: string;
  spoke: boolean;
  reason: string;
  message: Tin | null;
};

/** `POST /messages` answers the stored message plus what the server did about a command. */
export type TinDaGui = Tin & {
  intent?: "plan" | "chia_bill" | "vote" | "mention" | null;
  companion?: LuotAi | null;
  vote?: { id: string; question: string } | null;
  expense_card?: Tin | null;
  intent_error?:
    | "vote_malformed"
    | "companion_rate_limited"
    | "chia_bill_not_available"
    | "chia_bill_no_expenses"
    | "chia_bill_refused"
    | null;
};

const LOI_CHAT: Record<string, string> = {
  permission_denied: "Bạn không còn ở trong nhóm này.",
  message_not_found: "Tin nhắn này không còn.",
  card_ungrounded: "Thẻ này không hợp lệ.",
  invalid_cursor: "Danh sách tin bị lệch, kéo để tải lại.",
};

const QUYEN = "group_admin,member";

export async function docTrangTin(
  contextId: string,
  personId: string,
  opts: { before?: string; after?: string; limit?: number } = {},
): Promise<TrangTin> {
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 50));
  if (opts.before) params.set("before", opts.before);
  if (opts.after) params.set("after", opts.after);
  return translatedAsActor<TrangTin>(LOI_CHAT, `/contexts/${contextId}/messages?${params}`, {
    method: "GET",
    actorId: personId,
    roles: QUYEN,
    contexts: contextId,
  });
}

export async function guiTin(
  contextId: string,
  personId: string,
  body: string,
  attempt: Attempt,
): Promise<TinDaGui> {
  return translatedAsActor<TinDaGui>(LOI_CHAT, `/contexts/${contextId}/messages`, {
    method: "POST",
    body: { kind: "text", body, image_url: null, card: null },
    actorId: personId,
    roles: QUYEN,
    contexts: contextId,
    attempt,
  });
}

export type DanhSachPhanUng = { message_id: string; reactions: PhanUngTomTat[] };

export async function themPhanUng(
  contextId: string,
  messageId: string,
  personId: string,
  kind: LoaiPhanUng,
): Promise<DanhSachPhanUng> {
  return translatedAsActor<DanhSachPhanUng>(
    LOI_CHAT,
    `/contexts/${contextId}/messages/${messageId}/reactions`,
    {
      method: "POST",
      body: { kind },
      actorId: personId,
      roles: QUYEN,
      contexts: contextId,
      attempt: newAttempt(),
    },
  );
}

export async function boPhanUng(
  contextId: string,
  messageId: string,
  personId: string,
  kind: LoaiPhanUng,
): Promise<DanhSachPhanUng> {
  return translatedAsActor<DanhSachPhanUng>(
    LOI_CHAT,
    `/contexts/${contextId}/messages/${messageId}/reactions/${kind}`,
    { method: "DELETE", actorId: personId, roles: QUYEN, contexts: contextId },
  );
}

export async function danhDauDaDoc(contextId: string, personId: string, messageId: string): Promise<void> {
  await translatedAsActor<unknown>(LOI_CHAT, `/contexts/${contextId}/read-mark`, {
    method: "PUT",
    body: { message_id: messageId },
    actorId: personId,
    roles: QUYEN,
    contexts: contextId,
    attempt: newAttempt(),
  });
}

// ---- pure helpers ----------------------------------------------------------

/** Newest first, no duplicates. Both inputs may be in either order. */
export function gopTin(dangGiu: Tin[], them: Tin[]): Tin[] {
  const theoId = new Map<string, Tin>();
  for (const t of [...dangGiu, ...them]) theoId.set(t.id, t);
  return [...theoId.values()].sort((a, b) => {
    if (a.created_at === b.created_at) return a.id < b.id ? 1 : -1;
    return a.created_at < b.created_at ? 1 : -1;
  });
}

/** The cursor of the newest message held, for `?after=` polling. */
export function cursorMoiNhat(tin: Tin[]): string | null {
  return tin.length === 0 ? null : tin[0].cursor;
}

/** The cursor of the oldest message held, for `?before=` paging. */
export function cursorCuNhat(tin: Tin[]): string | null {
  return tin.length === 0 ? null : tin[tin.length - 1].cursor;
}

/** Replace one message's reactions after the server answered. */
export function thayPhanUng(tin: Tin[], messageId: string, reactions: PhanUngTomTat[]): Tin[] {
  return tin.map((t) => (t.id === messageId ? { ...t, reactions } : t));
}

export type HangHienThi =
  | { loai: "tin"; tin: Tin }
  | { loai: "ngay"; nhan: string; key: string };

/**
 * Day dividers for an inverted list: the divider for a day sits AFTER (below,
 * in list order) the newest-first messages of that day, i.e. visually above
 * them. Labels are «Hôm nay», «Hôm qua», or dd/MM.
 */
export function nhomTheoNgay(tin: Tin[], homNay: Date = new Date()): HangHienThi[] {
  const ra: HangHienThi[] = [];
  let ngayHienTai: string | null = null;
  for (const t of tin) {
    const ngay = t.created_at.slice(0, 10);
    if (ngayHienTai !== null && ngay !== ngayHienTai) {
      ra.push({ loai: "ngay", nhan: nhanNgay(ngayHienTai, homNay), key: `ngay-${ngayHienTai}` });
    }
    ra.push({ loai: "tin", tin: t });
    ngayHienTai = ngay;
  }
  if (ngayHienTai !== null) {
    ra.push({ loai: "ngay", nhan: nhanNgay(ngayHienTai, homNay), key: `ngay-${ngayHienTai}` });
  }
  return ra;
}

export function nhanNgay(yyyyMmDd: string, homNay: Date): string {
  const nay = homNay.toISOString().slice(0, 10);
  const qua = new Date(homNay.getTime() - 86_400_000).toISOString().slice(0, 10);
  if (yyyyMmDd === nay) return "Hôm nay";
  if (yyyyMmDd === qua) return "Hôm qua";
  const [, mm, dd] = yyyyMmDd.split("-");
  return `${dd}/${mm}`;
}

export function gioPhut(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

export type TheAi =
  | { loai: "text"; text: string }
  | { loai: "places"; title: string; items: { place_id: string; name?: string; reason?: string }[] }
  | { loai: "itinerary"; title: string; days: { label?: string; stops: { time?: string; name?: string; place_id?: string }[] }[] }
  | { loai: "poll"; vote_id: string; question: string; options: { id: string; label: string }[] }
  | {
      loai: "expense_draft";
      drafts: { title: string; amount_vnd: number; paid_by_id: string; shared_by: string[]; needs_review: boolean }[];
    }
  | { loai: "khac" };

function laBanGhi(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** Read a server card without trusting its shape. Anything odd is `khac`. */
export function docTheAi(card: unknown): TheAi {
  if (!laBanGhi(card) || !laBanGhi(card.payload)) return { loai: "khac" };
  const p = card.payload;
  switch (card.kind) {
    case "text":
      return typeof p.text === "string" ? { loai: "text", text: p.text } : { loai: "khac" };
    case "places": {
      const items = Array.isArray(p.items)
        ? p.items.filter(laBanGhi).map((i) => ({
            place_id: String(i.place_id ?? ""),
            name: typeof i.name === "string" ? i.name : undefined,
            reason: typeof i.reason === "string" ? i.reason : undefined,
          }))
        : [];
      return { loai: "places", title: typeof p.title === "string" ? p.title : "Gợi ý", items };
    }
    case "itinerary": {
      const days = Array.isArray(p.days)
        ? p.days.filter(laBanGhi).map((d) => ({
            label: typeof d.label === "string" ? d.label : undefined,
            stops: Array.isArray(d.stops)
              ? d.stops.filter(laBanGhi).map((s) => ({
                  time: typeof s.time === "string" ? s.time : undefined,
                  name: typeof s.name === "string" ? s.name : undefined,
                  place_id: typeof s.place_id === "string" ? s.place_id : undefined,
                }))
              : [],
          }))
        : [];
      return { loai: "itinerary", title: typeof p.title === "string" ? p.title : "Lịch trình", days };
    }
    case "poll": {
      const options = Array.isArray(p.options)
        ? p.options
            .filter(laBanGhi)
            .map((o) => ({ id: String(o.id ?? ""), label: String(o.label ?? "") }))
            .filter((o) => o.id !== "" && o.label !== "")
        : [];
      if (typeof p.vote_id !== "string" || typeof p.question !== "string" || options.length < 2) {
        return { loai: "khac" };
      }
      return { loai: "poll", vote_id: p.vote_id, question: p.question, options };
    }
    case "expense_draft": {
      const drafts = Array.isArray(p.drafts)
        ? p.drafts.filter(laBanGhi).map((d) => ({
            title: String(d.title ?? ""),
            amount_vnd: typeof d.amount_vnd === "number" ? d.amount_vnd : 0,
            paid_by_id: String(d.paid_by_id ?? ""),
            shared_by: Array.isArray(d.shared_by) ? d.shared_by.map(String) : [],
            needs_review: d.needs_review !== false,
          }))
        : [];
      return { loai: "expense_draft", drafts };
    }
    default:
      return { loai: "khac" };
  }
}

/** Copy for what the server said about a command, or null when nothing to say. */
export function cauYDinh(gui: TinDaGui): string | null {
  switch (gui.intent_error) {
    case "companion_rate_limited":
      return "Hết lượt hỏi Rủ Đi AI trong phút này. Tin của bạn vẫn được gửi.";
    case "vote_malformed":
      return "Bình chọn cần dạng: /vote Câu hỏi? Lựa chọn A | Lựa chọn B";
    case "chia_bill_not_available":
      return "Chia bill từ chat chưa sẵn sàng trên máy chủ này.";
    case "chia_bill_no_expenses":
      return "Không thấy khoản chi nào trong các tin gần đây.";
    case "chia_bill_refused":
      return "Máy chủ từ chối bản đọc lần này. Thử lại sau.";
    default:
      break;
  }
  if (gui.companion && !gui.companion.spoke) {
    switch (gui.companion.reason) {
      case "unavailable":
        return "Rủ Đi AI chưa nối được mô hình trên máy chủ này.";
      case "ungrounded":
        return "Rủ Đi AI có ý nhưng không nêu được địa điểm trong danh mục, nên im lặng.";
      default:
        return "Rủ Đi AI đang im lặng (" + gui.companion.reason + ").";
    }
  }
  return null;
}
