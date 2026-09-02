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
 * ## Why the total can be absent, and why that is not an error
 *
 * `/balances` answers "who owes whom", not "what did this trip cost". The
 * figure the settlement hero shows comes from `GET /contexts/{id}/recap`, whose
 * `split_total_vnd` is recomputed per request over the expenses that fall on an
 * outing's days. `group_recap` selects FINISHED outings, so a trip still under
 * way is simply absent -- and absent is not zero. `tongChuyen: null` is that
 * third state, and the screen has to render it as "chưa có số" rather than as
 * "0đ", which would be a claim nobody made.
 *
 * ## Names
 *
 * `/balances` speaks in person UUIDs. A screen that prints a UUID where a name
 * belongs is the defect `tests/ten-dia-diem-album.test.mjs` was written for, one
 * layer over. Names come from `GET /contexts/{id}/members`, and a member the
 * roster does not know falls back to a neutral label -- never to the fixture
 * roster, which would put a demo person's name on a real person's debt.
 */
import { docSoDu } from "../api";
import { moNhomDaCo, type NhomState } from "../screens/chat/nhom";

/** A person the server named, or admitted it could not name. */
export type NguoiLive = {
  personId: string;
  ten: string;
};

export type QuyetToanLive = {
  /** Đồng, from the recap. `null` when the server has no figure for this group. */
  tongChuyen: number | null;
  /** Everyone the roster reports as part of this group. */
  nguoi: NguoiLive[];
  /** The server's own minimal transfer set. Not recomputed here. */
  chuyenTien: { fromId: string; toId: string; amountVnd: number }[];
  /** True when the server proved this transfer set is minimal. */
  toiThieu: boolean;
};

/** The label for somebody the roster did not name. Never a UUID, never a fixture name. */
export const TEN_CHUA_BIET = "Thành viên chưa đặt tên";

type RecapWire = { split_total_vnd?: unknown };

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
function tongTuRecap(wire: unknown): number | null {
  if (typeof wire !== "object" || wire === null) return null;
  const { split_total_vnd: tong } = wire as RecapWire;
  return Number.isInteger(tong) ? (tong as number) : null;
}

/**
 * `GET /contexts/{id}/recap`, read for its total only.
 *
 * Failures are swallowed into `null` on purpose: a settlement screen whose
 * transfer list loaded fine should not go blank because the recap route was
 * unhappy. The two answer different questions and fail independently.
 */
async function docTongChuyen(contextId: string, actorId: string, base: string): Promise<number | null> {
  try {
    const res = await fetch(`${base}/contexts/${contextId}/recap`, {
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": actorId,
        "X-Actor-Roles": "member",
        "X-Actor-Contexts": contextId,
      },
    });
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
