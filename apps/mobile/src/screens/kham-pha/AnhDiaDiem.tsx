/** The place-card frame: a real photograph when the server sends one, and a
 *  drawn mark until then.
 *
 * The mockup fills every card with a photo of the actual place. The frame
 * that will hold that photo is real now -- size, radius, clip -- so the day a
 * URL arrives the layout is filled in rather than redrawn. What is not here
 * yet is the photograph itself: the server does not send `photo_url`, the
 * repo guard refuses binaries, and no real place imagery goes into Git.
 *
 * Until a URL arrives, each category gets a drawn mark on a ramp between two
 * palette tokens. Not a "nice colour" picked by eye: every stop is
 * `mixHex(tokenA, tokenB, t)`, the same rule `Gradient.tsx` follows for the
 * opening illustration, so these move when the palette moves and can be
 * checked by reading the call instead of sampling a pixel.
 *
 * The drawing stays the stand-in, and stays better than a stock photo,
 * because a blurred stock image would imply the app knows what the place
 * looks like. A drawn mark says "category", which is the only thing it
 * actually knows until the server says otherwise.
 */
import React from "react";
import { Text, View } from "react-native";
import tokens from "../../../../../packages/shared/tokens.json";
import { radius, space, type, usePalette } from "../../theme";
import { Gradient, Scrim, mixHex } from "../../navigation/Gradient";
import { Anh } from "../../ui/Anh";

const brand = tokens.brand;
const ink = tokens.color.light.ink;

/** Ink for anything on top of a ramp. Not a new colour -- it is `accentInk`,
 *  and it only ever sits under a scrim (see `Scrim`'s own note on why). */
const ON_RAMP = tokens.color.light.accentInk;

type Mark = "nuong" | "cafe" | "vui-choi" | "dem" | "nui";

/**
 * The ramp and the mark for each category, keyed by the slug the server sends.
 *
 * Unknown slugs fall through to the Đà Lạt hillside rather than to nothing:
 * rd-be-05 owns this vocabulary and may add to it, and a category this file
 * has not heard of must still render a card.
 */
const THEO_DANH_MUC: Record<string, { ramp: string[]; mark: Mark }> = {
  "quan-an-local": { ramp: [brand.glow, brand.rose], mark: "nuong" },
  cafe: { ramp: [mixHex(brand.glow, ink, 0.35), mixHex(brand.rose, ink, 0.55)], mark: "cafe" },
  "vui-choi": { ramp: [brand.rose, brand.violet], mark: "vui-choi" },
  "di-choi-dem": { ramp: [mixHex(brand.violet, ink, 0.4), mixHex(brand.violet, ink, 0.86)], mark: "dem" },
};

const MAC_DINH = { ramp: [brand.violet, mixHex(brand.rose, ink, 0.3)], mark: "nui" as Mark };

export function rampCho(category: string): { ramp: string[]; mark: Mark } {
  return THEO_DANH_MUC[category] ?? MAC_DINH;
}

/**
 * A place "photo": a real frame, a drawn stand-in, and a bottom scrim.
 *
 * The scrim is not mood. `tokens.json` states outright that the brand layer
 * may not carry small text -- white on `coral` measures 2.92:1 -- and every
 * card puts its name over the bottom of this block. The wash takes that third
 * dark enough for white body text to clear AA, which is the same trade the
 * opening screen makes and documents.
 */
export function AnhDiaDiem({ category, height, rounded = radius.small, children, uri, name }: {
  category: string;
  height: number;
  rounded?: number;
  /** Overlaid content -- badges, ribbons, the name block. */
  children?: React.ReactNode;
  uri?: string | null;
  name?: string;
}) {
  const { ramp, mark } = rampCho(category);
  return (
    <Anh
      uri={uri}
      alt={name ? `Ảnh ${name}` : "Ảnh địa điểm"}
      cho={
        <>
          <Gradient
            colors={ramp}
            style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
          />
          <DauHieu mark={mark} height={height} />
        </>
      }
      style={{ height, borderRadius: rounded }}
    >
      {/* The scrim sits above the photograph, not inside `cho`. The place
          name sits on the bottom of this frame and the scrim is what keeps
          that white type above the AA floor; if the scrim lived in `cho` it
          would vanish the moment a real photo arrived and the text would
          drop below the contrast threshold. */}
      <Scrim alphas={[0, 0.18, 0.72]} />
      {children}
    </Anh>
  );
}

/**
 * The mark itself, proportioned off the block height so one number scales it.
 *
 * Rectangles and circles only, for the reason `icons.tsx` gives: a vector or
 * icon-font dependency is a native module and a loading state on the first
 * screen of the app, bought for a handful of shapes.
 */
function DauHieu({ mark, height }: { mark: Mark; height: number }) {
  const u = (n: number) => (height / 120) * n;
  const wash = "rgba(255,255,255,0.24)";
  const washSoft = "rgba(255,255,255,0.13)";

  const common = {
    position: "absolute" as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center" as const,
    justifyContent: "center" as const,
  };

  if (mark === "nuong") {
    // Three skewers over a glow: a grill, at the scale a thumbnail can hold.
    return (
      <View style={common} pointerEvents="none">
        <View
          style={{
            width: u(64), height: u(64), borderRadius: u(32),
            backgroundColor: washSoft, alignItems: "center", justifyContent: "center",
            flexDirection: "row", gap: u(7),
          }}
        >
          {[0, 1, 2].map((i) => (
            <View
              key={i}
              style={{ width: u(5), height: u(38 - i * 6), borderRadius: u(3), backgroundColor: wash }}
            />
          ))}
        </View>
      </View>
    );
  }

  if (mark === "cafe") {
    return (
      <View style={common} pointerEvents="none">
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <View
            style={{
              width: u(46), height: u(38),
              borderBottomLeftRadius: u(16), borderBottomRightRadius: u(16),
              borderTopLeftRadius: u(4), borderTopRightRadius: u(4),
              backgroundColor: wash,
            }}
          />
          <View
            style={{
              width: u(18), height: u(18), borderRadius: u(9),
              borderWidth: u(4), borderColor: wash, marginLeft: -u(3), marginTop: u(2),
            }}
          />
        </View>
      </View>
    );
  }

  if (mark === "vui-choi") {
    // A wheel: hub, rim, four spokes.
    return (
      <View style={common} pointerEvents="none">
        <View
          style={{
            width: u(62), height: u(62), borderRadius: u(31),
            borderWidth: u(5), borderColor: wash,
            alignItems: "center", justifyContent: "center",
          }}
        >
          <View style={{ position: "absolute", width: u(52), height: u(4), backgroundColor: washSoft }} />
          <View style={{ position: "absolute", width: u(4), height: u(52), backgroundColor: washSoft }} />
          <View style={{ width: u(12), height: u(12), borderRadius: u(6), backgroundColor: wash }} />
        </View>
      </View>
    );
  }

  if (mark === "dem") {
    // A crescent, made by a disc with a second disc bitten out of it. The
    // bite is the ramp's own dark end rather than a new colour, so it stays
    // a silhouette instead of a grey blob.
    return (
      <View style={common} pointerEvents="none">
        <View style={{ width: u(64), height: u(64) }}>
          <View
            style={{
              position: "absolute", width: u(56), height: u(56), borderRadius: u(28),
              backgroundColor: wash, top: u(4), left: u(4),
            }}
          />
          <View
            style={{
              position: "absolute", width: u(46), height: u(46), borderRadius: u(23),
              backgroundColor: mixHex(brand.violet, ink, 0.75), top: 0, left: u(18),
            }}
          />
        </View>
      </View>
    );
  }

  // Đà Lạt: two hills and a sun. The fallback, so it has to read at any size.
  return (
    <View style={[common, { justifyContent: "flex-end" }]} pointerEvents="none">
      <View style={{ width: "100%", height: u(58), justifyContent: "flex-end" }}>
        <View
          style={{
            position: "absolute", right: u(22), bottom: u(30),
            width: u(20), height: u(20), borderRadius: u(10), backgroundColor: wash,
          }}
        />
        <View style={{ flexDirection: "row", alignItems: "flex-end" }}>
          <View style={{ flex: 1, height: u(30), borderTopRightRadius: u(40), backgroundColor: washSoft }} />
          <View style={{ flex: 1.3, height: u(44), borderTopLeftRadius: u(52), borderTopRightRadius: u(30), backgroundColor: wash }} />
          <View style={{ flex: 1, height: u(26), borderTopLeftRadius: u(36), backgroundColor: washSoft }} />
        </View>
      </View>
    </View>
  );
}

/** "NEW" / "HOT", the mockup's top-left ribbon.
 *
 *  White on `accent` is 5.16:1 and on `ai` is 5.16:1 -- both measured in
 *  DESIGN.md. The brand-layer colours underneath are off limits for text of
 *  this size, so the chip brings its own legal ground rather than sitting
 *  transparent on the ramp. */
export function Ruy({ flag }: { flag: "new" | "hot" }) {
  const c = usePalette();
  const bg = flag === "new" ? c.split : c.accent;
  const fg = flag === "new" ? c.splitInk : c.accentInk;
  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: bg,
        paddingHorizontal: space.xs,
        paddingVertical: 3,
        borderRadius: radius.small,
      }}
    >
      <Text style={{ ...type.micro, color: fg }}>{flag === "new" ? "NEW" : "HOT"}</Text>
    </View>
  );
}

/** "ĐANG ĐÓNG", the same ribbon slot as NEW/HOT.
 *
 *  A closed place still appears in the list -- it is a real answer to "where
 *  could we go", just not tonight -- so it sorts to the bottom rather than
 *  disappearing. Sorting alone is invisible though: a card at the bottom looks
 *  identical to a card that merely scored badly. This is the part a reader can
 *  see.
 *
 *  Foreground is `splitInk`, not a literal white. White on `warn` measures
 *  5.18:1 in light but 3.68:1 in dark, which fails AA at this size. `splitInk`
 *  is the palette's mode-aware ink for a saturated fill (#ffffff light,
 *  #04201d dark) and lands at 5.18:1 and 4.64:1 -- both legal, and it stays
 *  legal if the brand ramp moves, which a hardcoded white would not. */
export function RuyDongCua() {
  const c = usePalette();
  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: c.warn,
        paddingHorizontal: space.xs,
        paddingVertical: 3,
        borderRadius: radius.small,
      }}
    >
      <Text style={{ ...type.micro, color: c.splitInk }}>ĐANG ĐÓNG</Text>
    </View>
  );
}

export { ON_RAMP };
