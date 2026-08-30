/** Reading a stored bill as "which of these did I eat", and writing the answer back.
 *
 * Pure on purpose, and separate from `BuocMonCuaToi.tsx` for one reason: the
 * screen is a `Pressable` tree and this repo has no interactive renderer, so
 * anything left inside the component cannot be pressed by a test. Everything
 * here is a function over plain values, which is the part a unit test can hold
 * a knife to. What remains in the component is state plumbing and one `await`.
 *
 * `POST /bills/{id}/my-items` charges the CALLER and takes the caller's
 * COMPLETE set on the bill -- there is no field in the body that could name
 * somebody else, and every key left out is released. So all three functions
 * below are about exactly one person, `toiId`, and none of them may touch
 * anybody else's shares. `apDungMonCuaToi` is where that would be easiest to
 * get wrong and is written to make it hard.
 */
import type { Assignment } from "../../assignment";
import type { BillWire } from "../../bill";

/** One tickable row, in the shape `MonCuaToi` renders.
 *
 * `position` rather than array order, same reason `assignmentFromBill` keys on
 * `item_key`: the server sends an explicit position and leaning on the order it
 * happened to serialise them in is how one person's food ends up on another
 * person's row. */
export function monTuBill(bill: BillWire): {
  itemKey: string;
  ten: string;
  soLuong: number;
  tienVnd: number;
}[] {
  return [...bill.items]
    .sort((left, right) => left.position - right.position)
    .map((item) => ({
      itemKey: item.item_key,
      ten: item.name,
      soLuong: item.quantity,
      tienVnd: item.line_total_vnd,
    }));
}

/** The ticks this screen opens with: what the server already holds against me.
 *
 * Seeded from the bill rather than from an empty set, because the body sent on
 * save REPLACES the whole claim. Opening on nothing ticked and saving would
 * read to a person as "I changed my mind about none of it" and land on the
 * server as "I ate none of it" -- silently releasing dishes they had claimed
 * on a previous visit. */
export function monToiDaNhan(bill: BillWire, toiId: string): string[] {
  return bill.items
    .filter((item) => item.shares.some((share) => share.participant_id === toiId))
    .map((item) => item.item_key);
}

/**
 * Fold the server's answer about ME into the matrix the group screen is holding.
 *
 * Not `assignmentFromBill`, and the difference is the whole function. That one
 * replaces the matrix with the server's entire picture, which is right when
 * reopening a bill and wrong here: `goi-y` holds unsaved edits about OTHER
 * people -- ticks made since `POST /bills` and not yet written by "Xem kết
 * quả" -- and adopting the server's copy wholesale would throw them away
 * without saying so.
 *
 * So: every line gets `toiId` added or removed to match what came back, and no
 * other id on any line is read or written. A line the bill does not mention is
 * left exactly as it was.
 *
 * Doing nothing at all is the other tempting shape, and it is the worse bug.
 * `onSeeResults` writes the local matrix over the whole bill with
 * `PUT /bills/{id}/assignments`; a claim that never reached the local matrix is
 * a claim that gets erased by the next press, after the screen told the person
 * it was saved.
 */
export function apDungMonCuaToi(
  a: Assignment,
  bill: BillWire,
  toiId: string,
): Assignment {
  const out: Assignment = { ...a };
  for (const item of bill.items) {
    const cuaToi = item.shares.some((share) => share.participant_id === toiId);
    const hienCo = out[item.item_key] ?? [];
    const dangCo = hienCo.includes(toiId);
    if (cuaToi === dangCo) continue;
    out[item.item_key] = cuaToi
      ? [...hienCo, toiId]
      : hienCo.filter((id) => id !== toiId);
  }
  return out;
}

/**
 * Why "Món của tôi" cannot be opened from `goi-y`, or `null` when it can.
 *
 * A sentence rather than a boolean, and it is rendered next to the disabled
 * button. A control that is grey for a reason the screen does not say is a
 * control a person presses twice and then gives up on.
 *
 * Two locks, and they are different failures:
 *
 *   - No bill. The write needs a bill id, and `POST /bills` is fired without
 *     holding the screen, so this state is real for the first moment after
 *     "Tiếp tục" and permanent if that write failed.
 *   - I am not on this bill. The route would accept the claim -- it only asks
 *     that the caller is an active member of the group -- and the matrix I come
 *     back to draws its columns from the roster, so the claim would land on the
 *     server and be invisible on the screen that sent it. Refusing to open is
 *     honest; opening and showing nothing is not.
 */
export function khoaMonCuaToi(
  bill: BillWire | null,
  toiId: string | null,
  idTrenBill: readonly string[],
): string | null {
  if (toiId === null) return "Chưa biết bạn là ai trong nhóm này.";
  if (bill === null) return "Chưa lưu được bill, nên chưa nhận món riêng được.";
  if (!idTrenBill.includes(toiId)) return "Thêm bạn vào bill trước, rồi mới nhận món.";
  return null;
}
