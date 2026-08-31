/** State for a chat-expense draft, and the only place ids become names.
 *
 * `POST /contexts/{id}/messages/{id}/expense-draft` returns UUIDs for who
 * paid and who shares. Those ids are roster facts, not display strings. A
 * name that is not on the roster this screen already holds is unknown --
 * `TEN_CHUA_BIET`, never a guessed name, never a sliced id.
 *
 * The five machine states are the only ones the card knows how to draw.
 * `chua-goi` is the rest state: no card. `dang-doc` is the wait. `co-nhap`
 * and `khong-thay` are the two honest answers the server can give.
 * `hong` is a refusal, already translated by `api.ts`.
 */
import { ApiError, thongDiepNguoiDoc, type ChatExpenseDraftWire } from "../../api";
import { TEN_CHUA_BIET } from "./tin-nhan";
import type { ThanhVien } from "./nhom";

export type TrangNhapTuChat =
  | { kind: "chua-goi" }
  | { kind: "dang-doc" }
  | {
      kind: "co-nhap";
      title: string;
      amountVnd: number;
      /** The ids, kept beside the names rather than instead of them.
       *
       *  This state used to hold names only, because names are all the card
       *  draws. That made the card unconfirmable: the ids the server sent were
       *  resolved to display strings and then dropped, so the button that
       *  writes the expense had nothing to send and could not exist. A name is
       *  not an identity -- two people in a group can share one, and
       *  `TEN_CHUA_BIET` is the same string for everybody off the roster -- so
       *  the ids never round-trip through the display text. */
      nguoiTraId: string;
      nguoiChiaIds: string[];
      tenNguoiTra: string;
      tenNguoiChia: string[];
      canXemLai: boolean;
    }
  | { kind: "khong-thay"; reason: string }
  | { kind: "hong"; loi: string };

export const TRANG_CHUA_GOI: TrangNhapTuChat = { kind: "chua-goi" };

/** Whether the person has written this reading into the ledger yet.
 *
 * Kept apart from `TrangNhapTuChat` on purpose. The reading is what the server
 * said about one message; this is what the person did about it. Folding the two
 * into one machine would mean a failed write has to overwrite the draft, and
 * then the numbers somebody was looking at when they pressed are gone -- which
 * is the one thing they need in order to decide whether to press again.
 */
export type TrangGhiKhoanChi =
  | { kind: "chua-ghi" }
  | { kind: "dang-ghi" }
  | { kind: "da-ghi"; dong: DongChia[] }
  | { kind: "ghi-hong"; loi: string };

export const CHUA_GHI: TrangGhiKhoanChi = { kind: "chua-ghi" };

/** One person's share, as the server computed it. Never computed here. */
export type DongChia = { ten: string; soTien: number };

/** The body `proposeSplit` takes, described structurally.
 *
 * Structural rather than imported from `screens/NhapKhoanChi`, because that
 * module pulls React Native in and this one is deliberately importable by a
 * plain `node --test` process. TypeScript checks the shape, which is the part
 * that can drift.
 */
export type BanNhapDeGhi = {
  participants: { id: string; name: string }[];
  totalVnd: number;
  advancerId: string;
  occasion: string;
};

/** The sentence that must sit inside the card, above any button.
 *
 * The route never creates or allocates an expense. Saying so in a footnote
 * under the button would make it a caption about the button rather than the
 * condition for pressing it.
 */
export const CAU_CHUA_GHI_KHOAN_CHI =
  "Chưa ghi khoản chi nào. Đây mới là bản đọc, bạn còn phải chốt.";

/** What replaces it once the ledger actually has the expense.
 *
 * The sentence above is a claim about the state of the world, not a caption, so
 * it cannot stay on the card after the write. Leaving it there would be the
 * mirror of the defect it was written to prevent: the first version said
 * nothing was written when nothing was, this one would say nothing was written
 * when something was.
 */
export const CAU_DA_GHI_KHOAN_CHI = "Đã ghi vào sổ nhóm. Số tiền mỗi người:";

/**
 * Resolve one person id against the roster this screen already has.
 *
 * Missing from the roster, or present without a name: `TEN_CHUA_BIET`.
 * Nothing here invents a display name from the id.
 */
export function tenTuRoster(personId: string, members: ThanhVien[]): string {
  const tv = members.find((m) => m.personId === personId);
  const ten = tv?.displayName?.trim();
  return ten ? ten : TEN_CHUA_BIET;
}

/** Turn a successful wire reply into the card's machine state. */
export function trangTuWire(
  wire: ChatExpenseDraftWire,
  members: ThanhVien[],
): TrangNhapTuChat {
  if (!wire.detected || wire.draft === null) {
    // The server always sends a non-empty reason when detected is false.
    // Passing it through is the whole point: the card must not invent one.
    return { kind: "khong-thay", reason: wire.reason ?? "" };
  }
  const d = wire.draft;
  return {
    kind: "co-nhap",
    title: d.title,
    amountVnd: d.amount_vnd,
    nguoiTraId: d.paid_by_id,
    nguoiChiaIds: [...d.shared_by],
    tenNguoiTra: tenTuRoster(d.paid_by_id, members),
    tenNguoiChia: d.shared_by.map((id) => tenTuRoster(id, members)),
    canXemLai: d.needs_review,
  };
}

/** A thrown refusal becomes the card's `hong` state, never a made-up draft. */
export function trangTuLoi(err: unknown): TrangNhapTuChat {
  if (err instanceof ApiError) return { kind: "hong", loi: err.message };
  return { kind: "hong", loi: thongDiepNguoiDoc(0, null) };
}

/**
 * The proposal to send, built from exactly what the card is showing.
 *
 * Nobody is added and nobody is dropped. The temptation is to fold the payer
 * into the sharers when the reader left them out, on the theory that the person
 * who paid obviously ate too -- but that is the app deciding a money question
 * from a hunch. The allocator divides the total across `participants` and
 * nothing else, so quietly appending one id there moves real money off every
 * other person's row, and the card would still be showing the list from before
 * the edit. What is on screen is what is sent; if the reading is wrong the
 * person can see that it is wrong before pressing.
 */
export function banNhapDeGhi(trang: {
  title: string;
  amountVnd: number;
  nguoiTraId: string;
  nguoiChiaIds: string[];
}, members: ThanhVien[]): BanNhapDeGhi {
  return {
    participants: trang.nguoiChiaIds.map((id) => ({
      id,
      name: tenTuRoster(id, members),
    })),
    totalVnd: trang.amountVnd,
    advancerId: trang.nguoiTraId,
    occasion: trang.title,
  };
}

/**
 * The server's allocation, turned into lines the card can draw.
 *
 * Reading order follows the sharers as the card listed them, so the rows on the
 * confirmation sit under the same names in the same order the person just read.
 * Anything the server allocated to somebody outside that list is appended
 * rather than dropped: a share nobody is shown is a share nobody can question.
 */
export function dongChiaTuAllocation(
  allocations: Record<string, number>,
  nguoiChiaIds: string[],
  members: ThanhVien[],
): DongChia[] {
  const daVe = new Set<string>();
  const dong: DongChia[] = [];
  for (const id of nguoiChiaIds) {
    if (daVe.has(id) || !(id in allocations)) continue;
    daVe.add(id);
    dong.push({ ten: tenTuRoster(id, members), soTien: allocations[id]! });
  }
  for (const [id, soTien] of Object.entries(allocations)) {
    if (daVe.has(id)) continue;
    daVe.add(id);
    dong.push({ ten: tenTuRoster(id, members), soTien });
  }
  return dong;
}

/** A refusal from the write path, in the words `api.ts` already translated. */
export function ghiHongTuLoi(err: unknown): TrangGhiKhoanChi {
  if (err instanceof ApiError) return { kind: "ghi-hong", loi: err.message };
  return { kind: "ghi-hong", loi: thongDiepNguoiDoc(0, null) };
}
