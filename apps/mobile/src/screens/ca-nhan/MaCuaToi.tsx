/** F05, the showing half: the square a friend points a camera at.
 *
 * The encoder is `ui/qr.ts`, and this is now its only caller. It used to be
 * shared with `ui/MaVietQr.tsx`, the card on the money path, and this file
 * deliberately did NOT share that component: it parsed EMVCo and masked an
 * account number, none of which is true of a friend code. That card left with
 * the payment rail (ADR-0015); the encoder stayed, because a friend code is
 * not a payment. When `src/ui/` grows a shared `MaQr` this file should call it
 * instead -- that is the frontend lane's to define, not this one's.
 *
 * The card states two things a demo audience would otherwise have to guess:
 * whether the square opens anything, and what is inside it. Both matter. A
 * code that scans to a dead domain looks identical to one that works until
 * somebody tries it, and "what is in this square" is a privacy question --
 * the answer is an id and a name, never a telephone number.
 */
import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { encodeQr, type QrMatrix } from "../../ui/qr";
import { linkMaBan, maMoDuocApp } from "../vao-cua/ma-ban";

/** Modules of white around the code, as the QR spec requires. Scanners use it
 *  to find the symbol's edge. */
const QUIET = 4;
const TARGET = 200;

/** Whole-pixel modules. A fractional module width lands every edge mid-pixel
 *  and gets anti-aliased into a grey seam, and grey seams are what a camera
 *  reads as ambiguous -- a code that decodes on a screenshot can still fail at
 *  arm's length across a table. Rounding down costs width and buys hard edges. */
function moduleSize(matrixSize: number): number {
  return Math.max(2, Math.floor(TARGET / (matrixSize + QUIET * 2)));
}

export function MaCuaToi({ personId, ten }: { personId: string; ten: string }) {
  const c = usePalette();

  let payload: string;
  try {
    payload = linkMaBan(personId, ten);
  } catch {
    return <KhongDung ly="Tài khoản này chưa có mã cá nhân dùng được." />;
  }

  let matrix: QrMatrix;
  try {
    matrix = encodeQr(payload);
  } catch {
    // Version 15 at EC level M runs out somewhere north of 400 bytes, which a
    // very long display name can reach. Refusing is the honest end of that:
    // a half-drawn square would still scan, into something else.
    return <KhongDung ly="Tên hiển thị dài quá mức vẽ được thành mã." />;
  }

  const px = moduleSize(matrix.size);
  const side = (matrix.size + QUIET * 2) * px;
  const moDuoc = maMoDuocApp();

  return (
    <View style={{ gap: space.sm, alignItems: "center" }}>
      <View
        style={{
          // White regardless of theme. `c.card` is dark in dark mode and a QR
          // drawn dark-on-dark does not scan, so this one surface is a literal.
          backgroundColor: "#ffffff",
          borderColor: c.line,
          borderWidth: 1,
          borderRadius: radius.base,
          padding: space.sm,
        }}
      >
        <O matrix={matrix} px={px} side={side} ten={ten} />
      </View>

      <Text style={{ ...type.micro, color: c.inkSoft, textAlign: "center" }}>
        {moDuoc
          ? "Bạn của bạn quét mã này bằng camera điện thoại là mở thẳng vào app."
          : "Trên điện thoại mã trỏ về ru-di.app. Tên miền đó chưa đăng ký, nên " +
            "quét ở đây chỉ đọc ra mã chứ chưa mở được gì. Trên bản web thì mở được."}
      </Text>

      {/* Said out loud rather than left to trust. A square is opaque by
          construction, and "what did I just hand this person" is exactly the
          question somebody should be able to answer before showing it. */}
      <Text style={{ ...type.micro, color: c.inkFaint, textAlign: "center" }}>
        Trong mã chỉ có mã tài khoản và tên hiển thị. Không có số điện thoại.
      </Text>
    </View>
  );
}

/** The symbol. Drawn as horizontal runs rather than one View per module: a
 *  version 4 code is 33x33, and 1,089 nodes for a decorative square showed as
 *  a hitch on mount. Light modules are not drawn -- the white ground is the
 *  light module, which is why that ground is a literal above. */
function O({ matrix, px, side, ten }: {
  matrix: QrMatrix;
  px: number;
  side: number;
  ten: string;
}) {
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

  return (
    <View
      // An image with a sentence, not the payload read out. A screen reader
      // announcing a URL character by character helps nobody; what a person
      // needs to know is whose code this is.
      accessibilityRole="image"
      accessibilityLabel={`Mã QR kết bạn của ${ten}`}
      style={{ width: side, height: side, backgroundColor: "#ffffff" }}
    >
      {runs}
    </View>
  );
}

function KhongDung({ ly }: { ly: string }) {
  const c = usePalette();
  return (
    <View
      accessibilityRole="alert"
      style={{
        borderColor: c.warn,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.sm,
        gap: 2,
      }}
    >
      <Text style={{ ...type.label, fontWeight: "700", color: c.warn }}>
        Chưa hiện được mã
      </Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>{ly}</Text>
    </View>
  );
}
