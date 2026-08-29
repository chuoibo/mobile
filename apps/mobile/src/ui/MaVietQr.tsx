/** The one square on the money path that a person points a bank app at.
 *
 * Everything here is display. The payload is the EMVCo string the server built
 * in `app/payments/vietqr.py` and sent back from `POST /batches/{id}/publish`;
 * this module draws it and reads it back to label it. It never builds a
 * payload, never touches an account number it was not handed, and never does
 * arithmetic on an amount.
 *
 * It also refuses. Three things make this component draw a refusal instead of
 * a code, and all three are cheap to check and expensive to miss:
 *
 *   1. the payload does not parse as VietQR at all;
 *   2. the amount encoded *inside* the payload disagrees with the amount the
 *      screen is showing beside it;
 *   3. the payload is too long to encode.
 *
 * (2) is the one worth explaining. Both numbers come from the same server, so
 * they should never differ, and that is exactly why a difference must stop the
 * screen: it means one of the two is not what it claims to be, and the person
 * holding the phone cannot tell which. A QR that moves a different sum than the
 * line above it is the worst outcome this screen can produce, worse than
 * showing nothing, because the transfer succeeds and looks correct.
 *
 * A refusal here is not an error state to be tidied away later. It is the
 * feature.
 */
import React from "react";
import { Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { radius, space, type, usePalette } from "../theme";
import { encodeQr, type QrMatrix } from "./qr";
import { readVietQr, type VietQrAccount } from "./vietqr";

/** Modules of white around the code, as the QR spec requires. Scanners use it
 *  to find the symbol's edge; without it a code drawn tight against a coloured
 *  card is measurably harder to acquire. */
const QUIET = 4;

/** Rough width the square should aim for, in points. The real width is rounded
 *  down to a whole number of modules -- see `moduleSize`. */
const TARGET = 232;

/**
 * Whole-pixel modules, deliberately.
 *
 * Dividing a target width by the module count gives a fraction, and a fraction
 * means every module edge lands mid-pixel and gets anti-aliased into a grey
 * seam. Grey seams are what a camera sees as ambiguous, and a code that decodes
 * on a screenshot can still fail in a dim restaurant at arm's length. Rounding
 * down to an integer costs a few points of width and buys hard edges.
 */
function moduleSize(matrixSize: number): number {
  return Math.max(2, Math.floor(TARGET / (matrixSize + QUIET * 2)));
}

type Refusal = { reason: string };

/** Read the payload back and check it says what the screen says it says. */
function inspect(payload: string, expectedAmountVnd: number):
  | { ok: true; account: VietQrAccount; matrix: QrMatrix }
  | { ok: false; refusal: Refusal } {
  let account: VietQrAccount;
  try {
    account = readVietQr(payload);
  } catch {
    // The parse failure code is deliberately not shown. It is a machine's word
    // for a machine's problem, and the person reading this screen can do
    // nothing with "NO_BENEFICIARY" except feel worse.
    return { ok: false, refusal: { reason: "Không đọc được mã chuyển tiền máy chủ gửi về." } };
  }

  if (account.amountVnd !== null && account.amountVnd !== expectedAmountVnd) {
    return {
      ok: false,
      refusal: {
        reason:
          "Số tiền trong mã không khớp số tiền ghi trên màn hình, nên mã này " +
          "chưa dùng được. Báo lại với nhóm trước khi chuyển.",
      },
    };
  }

  let matrix: QrMatrix;
  try {
    matrix = encodeQr(payload);
  } catch {
    return { ok: false, refusal: { reason: "Mã chuyển tiền dài quá mức vẽ được." } };
  }

  return { ok: true, account, matrix };
}

export function MaVietQr({ payload, expectedAmountVnd, recipientName }: {
  payload: string;
  /** What the row above this card says is being transferred. Checked against
   *  the payload rather than trusted. */
  expectedAmountVnd: number;
  recipientName: string;
}): React.JSX.Element {
  const c = usePalette();
  const result = inspect(payload, expectedAmountVnd);

  if (!result.ok) {
    return (
      <View
        accessibilityRole="alert"
        style={{
          backgroundColor: c.card,
          borderColor: c.warn,
          borderWidth: 1,
          borderRadius: radius.base,
          padding: space.md,
          gap: space.xs,
        }}
      >
        <Text style={{ ...type.label, fontWeight: "700", color: c.warn }}>
          Chưa hiện được mã
        </Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>{result.refusal.reason}</Text>
      </View>
    );
  }

  const { account, matrix } = result;
  const px = moduleSize(matrix.size);
  const side = (matrix.size + QUIET * 2) * px;

  return (
    <View
      style={{
        // White, not `c.card`. In dark mode `c.card` is dark, and a QR drawn
        // dark-on-dark does not scan. The symbol needs its own light ground
        // regardless of the theme around it, so this one surface is a literal.
        backgroundColor: "#ffffff",
        borderColor: c.line,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.sm,
        alignItems: "center",
      }}
    >
      <Text style={{ ...type.micro, color: "#4e5563", letterSpacing: 1 }}>
        VIETQR · NAPAS 247
      </Text>

      <QrSquare matrix={matrix} px={px} side={side} account={account} />

      <View style={{ alignItems: "center", gap: 2 }}>
        <Text style={{ ...type.label, fontWeight: "700", color: "#1f2230" }}>
          {recipientName}
        </Text>
        {/* Masked, and masked by `vietqr.ts` rather than here, so the rule
            lives in one place. The full number is inside the QR, where a
            camera reads it and a shoulder does not. */}
        <Text style={{ ...type.label, color: "#4e5563", fontVariant: ["tabular-nums"] }}>
          {account.accountMasked}
        </Text>
        <Text style={{ ...type.micro, color: "#676e7b" }}>{account.bankName}</Text>
      </View>
    </View>
  );
}

/**
 * The symbol itself.
 *
 * Drawn as runs rather than modules. A version 7 code is 45x45, and one View
 * per module is 2,025 nodes for a decorative square -- on web that is 2,025
 * divs, and it showed as a visible hitch when the screen mounted. Consecutive
 * dark modules in a row are one View instead, which for a typical payload is
 * roughly a tenth of the nodes and pixel-identical output.
 *
 * Light modules are not drawn at all; the card's white ground is the light
 * module, which is also why the ground above is a literal white.
 */
function QrSquare({ matrix, px, side, account }: {
  matrix: QrMatrix;
  px: number;
  side: number;
  account: VietQrAccount;
}): React.JSX.Element {
  const runs: React.JSX.Element[] = [];
  for (let row = 0; row < matrix.size; row++) {
    const line = matrix.modules[row];
    if (line === undefined) continue;
    let start = -1;
    for (let col = 0; col <= matrix.size; col++) {
      const dark = col < matrix.size && line[col] === true;
      if (dark && start === -1) start = col;
      if (!dark && start !== -1) {
        runs.push(
          <View
            key={`${row}:${start}`}
            style={{
              position: "absolute",
              left: (QUIET + start) * px,
              top: (QUIET + row) * px,
              width: (col - start) * px,
              height: px,
              backgroundColor: "#000000",
            }}
          />,
        );
        start = -1;
      }
    }
  }

  // A screen reader gets a sentence, because a QR is an image of a string and
  // reading the string aloud would help nobody. The amount and the destination
  // are the two facts a person needs before they point a bank app at this.
  const spoken =
    account.amountVnd === null
      ? `Mã VietQR chuyển tiền tới ${account.bankName}, tài khoản ${account.accountMasked}`
      : `Mã VietQR chuyển ${formatVnd(account.amountVnd)} đồng tới ${account.bankName}, ` +
        `tài khoản ${account.accountMasked}`;

  return (
    <View
      accessibilityRole="image"
      accessibilityLabel={spoken}
      style={{ width: side, height: side, backgroundColor: "#ffffff" }}
    >
      {runs}
    </View>
  );
}
