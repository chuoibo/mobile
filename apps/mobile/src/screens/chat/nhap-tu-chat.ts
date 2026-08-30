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
      tenNguoiTra: string;
      tenNguoiChia: string[];
      canXemLai: boolean;
    }
  | { kind: "khong-thay"; reason: string }
  | { kind: "hong"; loi: string };

export const TRANG_CHUA_GOI: TrangNhapTuChat = { kind: "chua-goi" };

/** The sentence that must sit inside the card, above any button.
 *
 * The route never creates or allocates an expense. Saying so in a footnote
 * under the button would make it a caption about the button rather than the
 * condition for pressing it.
 */
export const CAU_CHUA_GHI_KHOAN_CHI =
  "Chưa ghi khoản chi nào. Đây mới là bản đọc, bạn còn phải chốt.";

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
