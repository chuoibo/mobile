/** A settled bill, frozen, so the settlement screen can be measured.
 *
 * The detector and the screenshot tools render a URL and cannot press
 * anything. Reaching the real settlement screen means photographing a bill,
 * naming four people, confirming a split, opening a round and publishing it,
 * against a live server with a bank account on file. Without a fixture, every
 * scan of this app is a scan of the opening screen, and the QR card -- the one
 * piece of UI on the money path that nobody has ever looked at with a
 * detector -- ships unmeasured while the report says the app was checked.
 *
 * Two things this fixture is careful about:
 *
 * The payload below was built by the server's own `build_payload()` in
 * `app/payments/vietqr.py` and pasted here as a finished string. It is not
 * assembled at runtime, and nothing in `apps/mobile` can assemble one: the app
 * has no EMVCo builder and must never grow one, because then there would be
 * two of them and they could disagree about where money goes.
 *
 * The account number inside it is invented and belongs to nobody. The repo
 * guard flagging it is the guard working correctly: it cannot tell a
 * fabricated account from a real one, which is the right way round. The
 * exemptions below are per line and named rather than the file being
 * allowlisted, so the next long digit run in here still has to be argued for.
 *
 * The numbers are internally consistent on purpose: the four allocations sum
 * to the printed total, and each obligation matches the amount encoded in its
 * payload. A fixture that failed its own screen's cross-checks would make the
 * detector scan a refusal card and report the layout as fine.
 */
import type { Envelope } from "../screens/ChiaSe";
import type { Obligation } from "../screens/DotThu";
import type { Roster } from "../participants";

/* Built by app/payments/vietqr.py, then frozen: one per debt, each encoding
 * its own amount to a made-up MB Bank account. Three strings rather than one
 * reused three times, because the amount is *inside* the payload and
 * `MaVietQr` compares it against the row beside it. A single shared payload
 * would fail that check on two of the three cards, and the detector would
 * spend the scan looking at refusal cards. */
// repo-guard: allow=long-number reason=synthetic-demo-account-in-vietqr-payload
const PAYLOAD_312500 =
  "00020101021238540010A00000072701240006970422011000710008990208QRIBFTTA530370" +
  "454063125005802VN62100806TT do16304530C";
// repo-guard: allow=long-number reason=synthetic-demo-account-in-vietqr-payload
const PAYLOAD_262500_A =
  "00020101021238540010A00000072701240006970422011000710008990208QRIBFTTA530370" +
  "454062625005802VN62100806TT do36304EC60";
// repo-guard: allow=long-number reason=synthetic-demo-account-in-vietqr-payload
const PAYLOAD_262500_B =
  "00020101021238540010A00000072701240006970422011000710008990208QRIBFTTA530370" +
  "454062625005802VN62100806TT do463048BB4";

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
    obligations: [{ obligationId: "do1", amountVnd: 312500, vietqrPayload: PAYLOAD_312500 }],
  },
  {
    senderId: "d3", senderName: "Thu Hà", amountVnd: 262500,
    url: "https://ru-di.example/g/demo3", opened: false,
    obligations: [{ obligationId: "do3", amountVnd: 262500, vietqrPayload: PAYLOAD_262500_A }],
  },
  {
    senderId: "d4", senderName: "Đức Duy", amountVnd: 262500,
    url: "https://ru-di.example/g/demo4", opened: false,
    obligations: [{ obligationId: "do4", amountVnd: 262500, vietqrPayload: PAYLOAD_262500_B }],
  },
];

export const DEMO_ITEM_COUNT = 8;
