/** Translate a server vote into the one shape the screen is allowed to draw.
 *
 * The wire already decided the outcome. This file copies those decisions into
 * names the screen can print; it does not re-count, break a tie, or invent a
 * winner. Two live vote counters in one product is the same class of failure
 * as two splitters -- `api.ts` says so above `CuocBinhChonWire`, and the
 * chat-side fold in `screens/chat/binh-chon.ts` exists for the same reason.
 * When the server starts returning tallies, this is the only function that
 * has to keep agreeing with it.
 *
 * Free of React and of `fetch` on purpose, so a test can feed a wire object
 * and read the view model without a renderer and without a server.
 */
import type { CuocBinhChonWire } from "../../api";

export type HangLuaChon = {
  optionId: string;
  nhan: string;
  tenDiaDiem: string | null;
  phieu: number;
  phanTram: number;
  laPhieuCuaToi: boolean;
  dangDan: boolean;
};

export type BangKetQua = {
  cauHoi: string;
  tongPhieu: number;
  daDong: boolean;
  laHoa: boolean;
  hang: HangLuaChon[];
  optionIdThang: string | null;
  tenCacBenHoa: string[];
};

/**
 * The screen's entire picture of one vote, derived and nothing more.
 *
 * Every rule below is a refusal of a fallback that looks helpful and is
 * the app casting the last vote:
 *
 *  - optionIdThang comes ONLY from wire.decided_option_id. NEVER fall back to
 *    leading_option_ids[0]. Picking the first of a tie is choosing a side
 *    the group did not.
 *  - laHoa comes from wire.is_tie directly, never inferred from list length.
 *    An empty vote has a leading list of length 0; inferring a tie from
 *    that length is how "nobody voted" becomes "it is a draw".
 *  - tenCacBenHoa = labels of every id in leading_option_ids, in the
 *    options' own position order, used only when laHoa. Position order is
 *    the ballot the group saw, not alphabetical and not the leading-list
 *    order the server happened to emit.
 *  - dangDan = leading_option_ids.includes(id) AND total_ballots > 0.
 *    A leader with zero ballots is a standings fiction: nothing is ahead
 *    of nothing.
 *  - phanTram = Math.round(ballot_count / total_ballots * 100), and 0 when
 *    total_ballots is 0. Never divide by zero. The number is spent on the
 *    width of a bar and is never printed -- see `BinhChon.tsx` for why a
 *    rounded share overstates what three ballots know.
 *  - laPhieuCuaToi = wire.my_option_id === option.id. The server resolved
 *    the caller from the actor header; this file does not take a person id.
 *  - hang is sorted by option.position. The ballot's order is the order
 *    the group discussed the options in; re-sorting would quietly promote
 *    whichever label starts with an early letter.
 */
export function bangKetQuaTuWire(wire: CuocBinhChonWire): BangKetQua {
  const tongPhieu = wire.total_ballots;
  const theoViTri = wire.options.slice().sort((a, b) => a.position - b.position);

  const hang: HangLuaChon[] = theoViTri.map((option) => ({
    optionId: option.id,
    nhan: option.label,
    tenDiaDiem: option.place_name,
    phieu: option.ballot_count,
    phanTram:
      tongPhieu === 0
        ? 0
        : Math.round((option.ballot_count / tongPhieu) * 100),
    laPhieuCuaToi: wire.my_option_id === option.id,
    dangDan: wire.leading_option_ids.includes(option.id) && tongPhieu > 0,
  }));

  // is_tie is a fact the domain already computed. Length of the leading
  // list is not a substitute: zero ballots and a two-way tie are different
  // answers that happen to share "more than one name at the top" or not.
  const laHoa = wire.is_tie;

  return {
    cauHoi: wire.question,
    tongPhieu,
    daDong: wire.is_closed,
    laHoa,
    hang,
    // Null while open and null while tied. Accept null. Do not look next door.
    optionIdThang: wire.decided_option_id,
    tenCacBenHoa: laHoa
      ? theoViTri
          .filter((option) => wire.leading_option_ids.includes(option.id))
          .map((option) => option.label)
      : [],
  };
}
