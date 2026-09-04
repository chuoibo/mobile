/** A settled bill, frozen, so the settlement screen can be measured.
 *
 * The detector and the screenshot tools render a URL and cannot press
 * anything. Reaching the real settlement screen means photographing a bill,
 * naming four people, confirming a split, opening a round and publishing it
 * against a live server. Without a fixture, every scan of this app is a scan
 * of the opening screen, and the settlement screen ships unmeasured while the
 * report says the app was checked.
 *
 * This file used to carry three frozen VietQR payloads as well, built by the
 * server and pasted in, so the QR card could be scanned by the detector. There
 * is no QR card: the product names each person's share and stops there.
 */
import type { SplitPreview } from "../api";
import type { Assignment } from "../assignment";
import type { BillWire } from "../bill";
import type { GroupMember, Roster } from "../participants";
import type { BillReading } from "../receipt";
import type { Envelope } from "../api";
import type { Obligation } from "../api";

export const DEMO_ADVANCER_ID = "d2";

export const DEMO_ROSTER: Roster = {
  participants: [
    { id: "d1", name: "Minh Anh" },
    { id: "d2", name: "Quang Huy" },
    { id: "d3", name: "Thu Hà" },
    { id: "d4", name: "Đức Duy" },
  ],
  advancerId: DEMO_ADVANCER_ID,
};

/** 312.500 + 287.500 + 262.500 + 262.500 = 1.125.000, the mockup's bill. */
export const DEMO_ALLOCATIONS: Record<string, number> = {
  d1: 312500,
  d2: 287500,
  d3: 262500,
  d4: 262500,
};

/** Quang Huy fronted the bill, so the other three owe him and he owes nobody.
 *  Three transfers for four people, which is also the fewest possible when one
 *  person paid. */
export const DEMO_OBLIGATIONS: Obligation[] = [
  { id: "do1", senderId: "d1", senderName: "Minh Anh", recipient: "Quang Huy", amountVnd: 312500, status: "outstanding" },
  { id: "do3", senderId: "d3", senderName: "Thu Hà", recipient: "Quang Huy", amountVnd: 262500, status: "outstanding" },
  { id: "do4", senderId: "d4", senderName: "Đức Duy", recipient: "Quang Huy", amountVnd: 262500, status: "outstanding" },
];

/* Each envelope's amount matches both its obligation above and the amount
 * encoded in its payload. That agreement is the fixture's whole job: it is
 * what lets the screen draw a code on real grounds rather than because a
 * check was skipped. */
export const DEMO_ENVELOPES: Envelope[] = [
  {
    senderId: "d1", senderName: "Minh Anh", amountVnd: 312500,
    url: "https://ru-di.example/g/demo1", opened: false,
    obligations: [{ obligationId: "do1", amountVnd: 312500 }],
  },
  {
    senderId: "d3", senderName: "Thu Hà", amountVnd: 262500,
    url: "https://ru-di.example/g/demo3", opened: false,
    obligations: [{ obligationId: "do3", amountVnd: 262500 }],
  },
  {
    senderId: "d4", senderName: "Đức Duy", amountVnd: 262500,
    url: "https://ru-di.example/g/demo4", opened: false,
    obligations: [{ obligationId: "do4", amountVnd: 262500 }],
  },
];

export const DEMO_ITEM_COUNT = 8;

/* ------------------------------------------------- the two middle screens */

/** The same bill, one step earlier: eight lines as the reader transcribed them.
 *
 * `KetQuaNhanDien` and `GoiYChia` are the two screens between the photograph
 * and the money, and on 2026-08-30 neither had ever been rendered by a
 * detector, a screenshot pass or an accessibility sweep. Not because anybody
 * decided to skip them -- because there was no address. `tests/
 * moi-man-co-duong-do.test.mjs` records the reason in `SO_DO`: both are
 * "chỉ tới được sau khi ảnh bill đã quét xong", which for a headless browser
 * means never. A source scan of the two `.tsx` files is not a substitute and
 * is not a smaller version of the same thing: measured on this repo the same
 * day, a fixture carrying 1.2:1 text and a 12px tap target scores 3 findings
 * written as `.html` and 0 written as `.tsx`.
 *
 * The eight lines are chosen so this fixture and `DEMO_ALLOCATIONS` above are
 * the same bill rather than two bills that happen to share a total:
 *
 *   six lines everyone shares        1.050.000  ->  262.500 each
 *   one line Minh Anh + Quang Huy       50.000  ->   25.000 each
 *   one line only Minh Anh              25.000  ->   25.000
 *   ------------------------------------------
 *   total                            1.125.000
 *
 *   Minh Anh  262.500 + 25.000 + 25.000 = 312.500
 *   Quang Huy 262.500 + 25.000          = 287.500
 *   Thu Hà                                262.500
 *   Đức Duy                               262.500
 *
 * Those four numbers are `DEMO_ALLOCATIONS`, to the dong. That is not
 * decoration: `GoiYChia` paints a preview only when its signature matches the
 * live matrix, so a fixture whose arithmetic disagreed would render "..." in
 * every cell and the scan would measure a screen mid-flight while reporting
 * the settled one. `tests/fixture-hai-man-giua.test.mjs` holds the agreement
 * so it cannot drift silently.
 *
 * Every division here is exact -- 1.050.000/4, 50.000/2, 25.000/1 -- so
 * `roundingGainers` is honestly empty. It is not empty because the field was
 * ignored.
 */
export const DEMO_READING: BillReading = {
  lines: [
    { id: "l1", name: "Lẩu thái hải sản", quantity: 1, lineTotalVnd: 450000, read: { name: "Lẩu thái hải sản", quantity: 1, lineTotalVnd: 450000 } },
    { id: "l2", name: "Bò nhúng dấm", quantity: 2, lineTotalVnd: 240000, read: { name: "Bò nhúng dấm", quantity: 2, lineTotalVnd: 240000 } },
    { id: "l3", name: "Rau tổng hợp", quantity: 2, lineTotalVnd: 90000, read: { name: "Rau tổng hợp", quantity: 2, lineTotalVnd: 90000 } },
    { id: "l4", name: "Nem hải sản", quantity: 3, lineTotalVnd: 120000, read: { name: "Nem hải sản", quantity: 3, lineTotalVnd: 120000 } },
    { id: "l5", name: "Cơm trắng", quantity: 4, lineTotalVnd: 60000, read: { name: "Cơm trắng", quantity: 4, lineTotalVnd: 60000 } },
    { id: "l6", name: "Bia Sài Gòn", quantity: 6, lineTotalVnd: 90000, read: { name: "Bia Sài Gòn", quantity: 6, lineTotalVnd: 90000 } },
    { id: "l7", name: "Nước ép cam", quantity: 2, lineTotalVnd: 50000, read: { name: "Nước ép cam", quantity: 2, lineTotalVnd: 50000 } },
    { id: "l8", name: "Kem dừa", quantity: 1, lineTotalVnd: 25000, read: { name: "Kem dừa", quantity: 1, lineTotalVnd: 25000 } },
  ],
  printedTotalVnd: 1125000,
  needsReview: false,
  warnings: [],
};

/** Who is on which line. The matrix `DEMO_SPLIT_PREVIEW` is the answer to. */
export const DEMO_ASSIGNMENT: Assignment = {
  l1: ["d1", "d2", "d3", "d4"],
  l2: ["d1", "d2", "d3", "d4"],
  l3: ["d1", "d2", "d3", "d4"],
  l4: ["d1", "d2", "d3", "d4"],
  l5: ["d1", "d2", "d3", "d4"],
  l6: ["d1", "d2", "d3", "d4"],
  l7: ["d1", "d2"],
  l8: ["d1"],
};

/** What the server answered for that matrix.
 *
 * Frozen rather than computed here, for the same reason the VietQR payload
 * above is frozen: the split belongs to the allocator, and a second one in the
 * app is how two screens come to show two numbers for one dinner. */
export const DEMO_SPLIT_PREVIEW: SplitPreview = {
  allocations: DEMO_ALLOCATIONS,
  roundingGainers: [],
  warnings: [],
};

/** The stored bill, derived from the two constants above rather than retyped.
 *
 * `GoiYChia` reads this for one sentence -- `moTaTrangThaiGan` -- and the
 * sentence is the difference between the screen a scan should measure and one
 * it should not. With `bill: null` it prints "Chưa lưu được. Ô đã tích chỉ ở
 * máy này." in the warning colour, which is a real state but not the state the
 * demo reaches; a detector pointed at it would be measuring a failure notice
 * and the report would carry it as the settled screen.
 *
 * Derived, because a hand-written copy of eight lines beside the eight lines
 * above is two sources for one bill, and the copy is the one that goes stale.
 * `suggested_item_keys` is empty and `assignment_state` is `confirmed`: the
 * group has agreed, which is what "AI chia" hands to the settlement screen.
 */
export const DEMO_BILL_WIRE: BillWire = {
  id: "b0e1d2c3-4a5b-4c6d-8e9f-0a1b2c3d4e5f",
  context_id: "c1d2e3f4-5a6b-4c7d-8e9f-1a2b3c4d5e6f",
  printed_total_vnd: DEMO_READING.printedTotalVnd,
  items_total_vnd: DEMO_READING.lines.reduce((sum, line) => sum + line.lineTotalVnd, 0),
  needs_review: DEMO_READING.needsReview,
  created_by_id: DEMO_ADVANCER_ID,
  created_at: "2026-08-29T12:40:00Z",
  assignment_state: "confirmed",
  suggested_item_keys: [],
  items: DEMO_READING.lines.map((line, i) => ({
    item_key: line.id,
    name: line.name,
    quantity: line.quantity,
    unit_price_vnd: null,
    line_total_vnd: line.lineTotalVnd,
    position: i,
    shares: (DEMO_ASSIGNMENT[line.id] ?? []).map((participantId) => ({
      participant_id: participantId,
      source: "confirmed" as const,
      decided_by_id: DEMO_ADVANCER_ID,
      decided_at: "2026-08-29T12:41:00Z",
    })),
  })),
  surcharges: [],
  discounts: [],
};

/** The group the bill was split inside. Bảo Ngọc came along and ate nothing,
 *  which is what gives the "Thêm người" picker a row to show. */
export const DEMO_NHOM: GroupMember[] = [
  { id: "d1", name: "Minh Anh" },
  { id: "d2", name: "Quang Huy" },
  { id: "d3", name: "Thu Hà" },
  { id: "d4", name: "Đức Duy" },
  { id: "d5", name: "Bảo Ngọc" },
];
