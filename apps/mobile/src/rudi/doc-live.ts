/**
 * The settlement screen's numbers, read from the server instead of the fixture.
 *
 * ## What this deliberately does NOT do
 *
 * No arithmetic. `GET /contexts/{id}/balances` recomputes net-per-person and a
 * minimal transfer set from the ledger on every request, and `src/rudi/money.ts`
 * is a DRAFT over a fixture that exists only so two screens cannot print two
 * different constants. Running both and picking one would be the second
 * allocator the repo has already thrown out once (PR13-02), and the two
 * disagree about who absorbs the rounding đồng. In live mode the draft is not
 * consulted at all.
 *
 * ## What the recap total is, and what it is not
 *
 * `/balances` answers "who owes whom", not "what did this trip cost". The
 * figure the settlement hero shows comes from `GET /contexts/{id}/recap`, whose
 * per-trip `split_total_vnd` is recomputed per request over the expenses that
 * fall on that trip's days. The top-level `split_total_vnd` sums FINISHED trips
 * only, so on a group whose only trip is still under way the server answers
 * `0` -- an honest sum over an empty list, and the wrong number to print under
 * "tổng chi tiêu" on the day a bill was just written. So this reads the trips
 * themselves: a trip under way shows its running figure (`in_progress`),
 * finished trips show their sum, and a group with no trip says so instead of
 * printing 0đ. `null` is reserved for "the recap could not be read".
 *
 * ## Names
 *
 * `/balances` speaks in person UUIDs. A screen that prints a UUID where a name
 * belongs is the defect `tests/ten-dia-diem-album.test.mjs` was written for, one
 * layer over. Names come from `GET /contexts/{id}/members`, and a member the
 * roster does not know falls back to a neutral label -- never to the fixture
 * roster, which would put a demo person's name on a real person's debt.
 */
import { ApiError, docSoDu, thongDiepNguoiDoc } from "../api";
import { headerNguoiGoi } from "../danh-tinh";
import { dinhDangTienVnd } from "../screens/chat/ke-hoach";
import { moNhomDaCo, type NhomState } from "../screens/chat/nhom";

/** A person the server named, or admitted it could not name. */
export type NguoiLive = {
  personId: string;
  ten: string;
};

/**
 * The recap's answer about spending, by trip. A group with no trip is its own
 * state: the server's `0` there is a sum over nothing, not a spend.
 */
export type TongChuyen =
  | { kieu: "dang-di"; ten: string; tong: number; soChuyenDangDi: number }
  | { kieu: "da-ket-thuc"; soChuyen: number; tong: number }
  | { kieu: "chua-co-chuyen" };

export type QuyetToanLive = {
  /** The recap's spending, by trip. `null` when the recap could not be read. */
  tongChuyen: TongChuyen | null;
  /** Everyone the roster reports as part of this group. */
  nguoi: NguoiLive[];
  /** The server's own minimal transfer set. Not recomputed here. */
  chuyenTien: { fromId: string; toId: string; amountVnd: number }[];
  /** True when the server proved this transfer set is minimal. */
  toiThieu: boolean;
};

/** The label for somebody the roster did not name. Never a UUID, never a fixture name. */
export const TEN_CHUA_BIET = "Thành viên chưa đặt tên";

type RecapOutingWire = { title?: unknown; split_total_vnd?: unknown };
type RecapWire = { outings?: unknown; in_progress?: unknown; split_total_vnd?: unknown };

/**
 * Read the total the SERVER computed. Do not add anything up here.
 *
 * `GroupRecapResponse` carries a top-level `split_total_vnd` beside the
 * per-outing figures. An earlier draft of this function summed the per-outing
 * ones, which is a second summation of money on the phone -- the exact thing
 * `src/screens/len-plan/ngan-sach.ts` says money law 2 forbids: *"Money law 2 is
 * not 'get the same answer as the ledger', it is 'read the ledger'"*. Both
 * happened to give 6.785.000đ on the seeded group, which is how that kind of
 * mistake survives review.
 *
 * A non-integer is refused rather than rounded: that would be a server contract
 * change worth failing on.
 */
function chuyenTuWire(wire: unknown): { ten: string; tong: number } | null {
  if (typeof wire !== "object" || wire === null) return null;
  const { title, split_total_vnd: tong } = wire as RecapOutingWire;
  if (typeof title !== "string" || !Number.isInteger(tong)) return null;
  return { ten: title, tong: tong as number };
}

/**
 * Exported for the node test: the screen's three spending states come from
 * here and nowhere else. A malformed trip (no title, non-integer figure) makes
 * the whole answer `null` -- a contract change worth failing on, not rounding.
 */
export function tongTuRecap(wire: unknown): TongChuyen | null {
  if (typeof wire !== "object" || wire === null) return null;
  const { outings, in_progress: dangDiWire, split_total_vnd: tong } = wire as RecapWire;
  const dangDi = Array.isArray(dangDiWire) ? dangDiWire.map(chuyenTuWire) : [];
  if (dangDi.some((chuyen) => chuyen === null)) return null;
  const dauTien = dangDi[0];
  if (dauTien !== undefined && dauTien !== null) {
    return { kieu: "dang-di", ten: dauTien.ten, tong: dauTien.tong, soChuyenDangDi: dangDi.length };
  }
  const daXong = Array.isArray(outings) ? outings.length : 0;
  if (daXong > 0) {
    if (!Number.isInteger(tong)) return null;
    return { kieu: "da-ket-thuc", soChuyen: daXong, tong: tong as number };
  }
  return { kieu: "chua-co-chuyen" };
}

/**
 * The three lines of the settlement hero, as strings. Pure so the copy for each
 * state is pinned by a test rather than by whichever state the emulator
 * happened to be in when somebody looked.
 */
export function dongHeroQuyetToan(
  tong: TongChuyen | null,
  soNguoi: number,
): { nhan: string; so: string; cau: string } {
  const nguoi = `${soNguoi} người`;
  if (tong === null) {
    return {
      nhan: `Chi tiêu theo chuyến (${nguoi})`,
      so: "Chưa có số",
      cau: "Máy chủ chưa trả tổng cho nhóm này. Các khoản chuyển bên dưới vẫn tính từ sổ.",
    };
  }
  if (tong.kieu === "chua-co-chuyen") {
    return {
      nhan: `Chi tiêu theo chuyến (${nguoi})`,
      so: "Chưa có chuyến",
      cau: "Nhóm chưa có kèo nào để gom chi tiêu theo ngày. Các khoản chuyển bên dưới vẫn tính từ sổ, kể cả khoản vừa ghi.",
    };
  }
  if (tong.kieu === "dang-di") {
    const them = tong.soChuyenDangDi > 1 ? ` và ${tong.soChuyenDangDi - 1} chuyến khác` : "";
    return {
      nhan: `Đang đi: ${tong.ten}${them} (${nguoi})`,
      so: dinhDangTienVnd(tong.tong),
      cau: "Tính từ sổ theo ngày của chuyến, tới giờ này. Sửa một bill là số đổi theo.",
    };
  }
  return {
    nhan: `${tong.soChuyen} chuyến đã kết thúc (${nguoi})`,
    so: dinhDangTienVnd(tong.tong),
    cau: "Số này máy chủ tính lại từ sổ mỗi lần hỏi.",
  };
}

/**
 * `GET /contexts/{id}/recap`, read for its total only.
 *
 * Failures are swallowed into `null` on purpose: a settlement screen whose
 * transfer list loaded fine should not go blank because the recap route was
 * unhappy. The two answer different questions and fail independently.
 */
async function docTongChuyen(contextId: string, actorId: string, base: string): Promise<TongChuyen | null> {
  try {
    const res = await fetch(`${base}/contexts/${contextId}/recap`, {
      headers: headerNguoiGoi(actorId, { roles: "member", contexts: contextId }),
    });
    // 401 is not "the server has no total for this group". It is "this request
    // was not signed in", and printing the first sentence for the second fact
    // is the exact lie this branch exists to remove -- it is how the missing
    // bearer stayed invisible in the first place. Let it travel.
    if (res.status === 401) {
      throw new ApiError(401, "unauthorized", thongDiepNguoiDoc(401, null));
    }
    if (!res.ok) return null;
    return tongTuRecap(await res.json());
  } catch {
    return null;
  }
}

export async function docQuyetToanLive(
  actorId: string,
  contextId: string,
  base: string,
): Promise<QuyetToanLive> {
  // Roster and balances in parallel: neither needs the other, and a settlement
  // screen that waits for two serial round trips on a phone reads as broken.
  const [soDu, nhom, tongChuyen] = await Promise.all([
    docSoDu(contextId, actorId),
    moNhomDaCo({ id: contextId, display_name: "" }, { id: actorId, personId: actorId, name: "", initials: "" }, { base }),
    docTongChuyen(contextId, actorId, base),
  ]);
  return {
    tongChuyen,
    nguoi: nguoiTuNhom(nhom),
    chuyenTien: soDu.transfers.map((row) => ({
      fromId: row.fromId,
      toId: row.toId,
      amountVnd: row.amountVnd,
    })),
    toiThieu: soDu.provenMinimal,
  };
}

function nguoiTuNhom(nhom: NhomState): NguoiLive[] {
  if (nhom.kind !== "xong") return [];
  return nhom.members
    .filter((m) => m.state !== "left")
    .map((m) => ({ personId: m.personId, ten: m.displayName ?? TEN_CHUA_BIET }));
}

/** Name for a person id, without ever falling back to the demo roster. */
export function tenCua(nguoi: readonly NguoiLive[], personId: string): string {
  return nguoi.find((n) => n.personId === personId)?.ten ?? TEN_CHUA_BIET;
}
