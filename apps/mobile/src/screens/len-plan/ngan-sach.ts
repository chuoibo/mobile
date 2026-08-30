/** F34. Spending against the reference budget, for one outing.
 *
 * Pure: no React, no fetch. The tests run this under bare node, so every rule
 * a person can be shown a wrong number by lives here rather than in a screen.
 *
 * TWO NUMBERS, AND ONLY ONE OF THEM IS OURS.
 *
 * The budget is `budget_per_person_vnd * headcount`, computed by `tongDuKien`
 * in `buoi-di.ts` -- two integers whose product stays exact in this range.
 * The spend is `split_total_vnd`, which arrives already summed from
 * `GET /contexts/{id}/recap`, where the server recomputes it from the
 * confirmed allocations on the request that asked. Nothing in this file adds
 * an expense up. Money law 2 is not "get the same answer as the ledger", it is
 * "read the ledger", and a second summation on the phone is exactly the thing
 * that shows two screens two totals for one dinner.
 *
 * NO PERCENTAGE, AND NO BAR. Both would need `spent / budget`, and money law 1
 * bans floats including at intermediate values. A ratio is not money, so the
 * ban is arguably not about it, but "arguably not" is a poor foundation under
 * the one screen whose job is to be trusted about money. The brief asked for
 * two amounts and a warning; two amounts and a warning is what this returns,
 * and every figure below is an integer đồng that came from an integer đồng.
 *
 * WHY A TRIP CAN HAVE NO SPEND FIGURE AT ALL. `group_recap` selects
 * `Outing.ends_on < today`: the ledger figure exists for FINISHED trips only.
 * An outing that has not ended is absent from the recap, and absent is not
 * zero. Rendering `0đ` for a trip the group is still on would be a measured
 * claim about money where no measurement was taken, so that case gets its own
 * state and says so in words.
 */
import { formatVnd } from "../../../../../packages/shared/money.mjs";
import { tongDuKien, type BuoiDi } from "./buoi-di";

/** Where this trip's spend figure stands, before any comparing happens.
 *
 *  Three cases and not two, because "the ledger has no number for this trip"
 *  and "we could not ask the ledger" are different facts and a person acts on
 *  them differently. Collapsing them lets the screen say "chuyến chưa xong"
 *  about a trip that finished last week, on a phone whose only real problem is
 *  that the recap request came back 403. A false reason is worse than no
 *  reason: it sends somebody to look in the wrong place.
 */
export type NguonDaTieu =
  /** The recap carried a figure for this outing. */
  | { kind: "co"; vnd: number }
  /** The recap was read, and this outing was not in it. `group_recap` selects
   *  `ends_on < today`, so this means the trip is not over yet. */
  | { kind: "chua-xong" }
  /** The recap request itself failed. We know nothing about this trip's spend. */
  | { kind: "khong-doc-duoc" };

export type YThucNganSach =
  /** No spend figure. `nganSachVnd` still stands: somebody typed it, so it is
   *  knowable before anyone spends anything. `vi` carries which of the two
   *  reasons applies, so the screen can say the true one. */
  | { kind: "chua-co-so"; nganSachVnd: number; vi: "chua-xong" | "khong-doc-duoc" }
  | { kind: "trong"; nganSachVnd: number; daTieuVnd: number; conLaiVnd: number }
  | { kind: "vuot"; nganSachVnd: number; daTieuVnd: number; vuotVnd: number };

/** Money as Vietnamese writes it: `6.000.000đ`.
 *
 *  `formatVnd` throws on a non-integer and on a negative, which is the guard
 *  we want rather than a guard to route around: a screen that cannot render a
 *  number honestly should not render it at all.
 */
export function tienVnd(vnd: number): string {
  return `${formatVnd(vnd)}đ`;
}

/**
 * Compare what the ledger says was spent against the budget the group set.
 *
 * A `co` figure that is not a non-negative integer is demoted to no figure at
 * all. `split_total_vnd` is an integer on the wire, so this only fires when the
 * wire lied, and this is the boundary where such a value would otherwise reach
 * a money label. Money law 1 is enforced where the data arrives, not assumed.
 */
export function doNganSach(buoi: BuoiDi, nguon: NguonDaTieu): YThucNganSach {
  const nganSachVnd = tongDuKien(buoi.budget_per_person_vnd, buoi.headcount);
  if (nguon.kind !== "co") {
    return { kind: "chua-co-so", nganSachVnd, vi: nguon.kind };
  }
  const daTieuVnd = nguon.vnd;
  if (typeof daTieuVnd !== "number" || !Number.isInteger(daTieuVnd) || daTieuVnd < 0) {
    return { kind: "chua-co-so", nganSachVnd, vi: "khong-doc-duoc" };
  }
  if (daTieuVnd > nganSachVnd) {
    return { kind: "vuot", nganSachVnd, daTieuVnd, vuotVnd: daTieuVnd - nganSachVnd };
  }
  return { kind: "trong", nganSachVnd, daTieuVnd, conLaiVnd: nganSachVnd - daTieuVnd };
}

/** The line a person reads first: what was spent, against what was planned. */
export function nhanDaTieu(y: YThucNganSach): string {
  if (y.kind === "chua-co-so") return `Ngân sách ${tienVnd(y.nganSachVnd)}`;
  return `Đã tiêu ${tienVnd(y.daTieuVnd)} / ngân sách ${tienVnd(y.nganSachVnd)}`;
}

/** The second line: the verdict, in words, never as a colour alone.
 *
 *  A red number is not readable by everyone holding this phone, and it carries
 *  nothing at all into a screenshot pasted back into the group chat. The amount
 *  over is therefore written out, and the colour is the redundant channel.
 */
export function nhanKetLuan(y: YThucNganSach): string {
  if (y.kind === "chua-co-so") {
    return y.vi === "chua-xong"
      ? "Chuyến chưa xong nên sổ chưa có số đã tiêu."
      : "Chưa đọc được số đã tiêu từ sổ.";
  }
  if (y.kind === "vuot") return `Vượt ${tienVnd(y.vuotVnd)}`;
  return `Còn ${tienVnd(y.conLaiVnd)}`;
}

/** Where one outing's spend figure stands, given how the recap read went. */
export function nguonDaTieu(
  soDaTieu: { kind: "xong"; theo: ReadonlyMap<string, number> } | { kind: "loi" },
  outingId: string,
): NguonDaTieu {
  if (soDaTieu.kind === "loi") return { kind: "khong-doc-duoc" };
  const v = soDaTieu.theo.get(outingId);
  return v === undefined ? { kind: "chua-xong" } : { kind: "co", vnd: v };
}
