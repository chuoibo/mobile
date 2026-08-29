/** Five tab glyphs and a plus, drawn out of Views.
 *
 * Same reasoning as `Gradient.tsx`: an icon set is a dependency, and this
 * shell needs six shapes. `@expo/vector-icons` ships a font per family and
 * pulls a loading state into the one bar that must never be empty -- a tab bar
 * that renders its labels before its glyphs looks broken for the frame it
 * takes, on the first screen anyone sees.
 *
 * Six shapes of rectangles, circles and two CSS triangles cost nothing, render
 * the same on both platforms, and take their colour from the caller so the
 * selected tab can be `accent` while the rest are `inkSoft`.
 *
 * They are solid rather than outlined. At 24pt an outline is a 1.5pt stroke,
 * and a 1.5pt stroke of `inkSoft` on `card` is the kind of edge the contrast
 * floor in DESIGN.md exists to catch. Solid shapes carry their measured text
 * contrast straight into the glyph.
 */
import React from "react";
import { View } from "react-native";

export type IconProps = { color: string; size?: number };

/** Everything is proportioned off a 24pt box, so one number scales a glyph. */
const BOX = 24;
const u = (size: number, n: number) => (size / BOX) * n;

function Box({ size, children }: { size: number; children: React.ReactNode }) {
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      {children}
    </View>
  );
}

/** Khám phá. A house: roof triangle over a body. */
export function IconKhamPha({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View
        style={{
          width: 0,
          height: 0,
          borderLeftWidth: u(size, 11),
          borderRightWidth: u(size, 11),
          borderBottomWidth: u(size, 9),
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderBottomColor: color,
        }}
      />
      <View
        style={{
          width: u(size, 15),
          height: u(size, 9),
          backgroundColor: color,
          borderBottomLeftRadius: u(size, 2.5),
          borderBottomRightRadius: u(size, 2.5),
        }}
      />
    </Box>
  );
}

/** Lên plan. A board with two ruled lines -- a plan, not a date. */
export function IconLenPlan({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View
        style={{
          width: u(size, 18),
          height: u(size, 19),
          borderRadius: u(size, 4),
          borderWidth: u(size, 2),
          borderColor: color,
          paddingTop: u(size, 6),
          alignItems: "center",
          gap: u(size, 3),
        }}
      >
        <View style={{ width: u(size, 9), height: u(size, 2), borderRadius: 999, backgroundColor: color }} />
        <View style={{ width: u(size, 9), height: u(size, 2), borderRadius: 999, backgroundColor: color }} />
      </View>
      {/* The binding, sat on top of the board's own border. */}
      <View
        style={{
          position: "absolute",
          top: u(size, 2.5),
          width: u(size, 12),
          height: u(size, 3),
          borderRadius: 999,
          backgroundColor: color,
        }}
      />
    </Box>
  );
}

/** Tin nhắn. A bubble with a tail at the bottom left. */
export function IconTinNhan({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View
        style={{
          width: u(size, 19),
          height: u(size, 15),
          borderRadius: u(size, 5),
          backgroundColor: color,
          marginBottom: u(size, 3),
        }}
      />
      <View
        style={{
          position: "absolute",
          left: u(size, 6),
          bottom: u(size, 2),
          width: 0,
          height: 0,
          borderLeftWidth: u(size, 3),
          borderRightWidth: u(size, 3),
          borderTopWidth: u(size, 5),
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: color,
        }}
      />
    </Box>
  );
}

/** Cá nhân. Head over shoulders. */
export function IconCaNhan({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View
        style={{
          width: u(size, 9),
          height: u(size, 9),
          borderRadius: 999,
          backgroundColor: color,
          marginBottom: u(size, 2),
        }}
      />
      <View
        style={{
          width: u(size, 17),
          height: u(size, 8),
          borderTopLeftRadius: u(size, 9),
          borderTopRightRadius: u(size, 9),
          backgroundColor: color,
        }}
      />
    </Box>
  );
}

/** The centre action. Rotates to an x when the menu it opened is showing. */
export function IconPlus({ color, size = BOX, open = false }: IconProps & { open?: boolean }) {
  const arm = { position: "absolute" as const, borderRadius: 999, backgroundColor: color };
  return (
    <Box size={size}>
      <View style={{ transform: [{ rotate: open ? "45deg" : "0deg" }] }}>
        <Box size={size}>
          <View style={[arm, { width: u(size, 17), height: u(size, 2.6) }]} />
          <View style={[arm, { width: u(size, 2.6), height: u(size, 17) }]} />
        </Box>
      </View>
    </Box>
  );
}

/** Small marks the create menu uses to tell its four rows apart. */
export function IconChuyen({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      {/* A pin: circle over a point. */}
      <View
        style={{
          width: u(size, 13),
          height: u(size, 13),
          borderRadius: 999,
          borderWidth: u(size, 3),
          borderColor: color,
        }}
      />
      <View
        style={{
          width: 0,
          height: 0,
          marginTop: -u(size, 1),
          borderLeftWidth: u(size, 4),
          borderRightWidth: u(size, 4),
          borderTopWidth: u(size, 7),
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: color,
        }}
      />
    </Box>
  );
}

/** A receipt, for the one create action that is wired to something real. */
export function IconKhoanChi({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View
        style={{
          width: u(size, 15),
          height: u(size, 19),
          borderRadius: u(size, 2),
          borderWidth: u(size, 2),
          borderColor: color,
          paddingTop: u(size, 4),
          alignItems: "center",
          gap: u(size, 2.5),
        }}
      >
        <View style={{ width: u(size, 8), height: u(size, 1.8), borderRadius: 999, backgroundColor: color }} />
        <View style={{ width: u(size, 8), height: u(size, 1.8), borderRadius: 999, backgroundColor: color }} />
        <View style={{ width: u(size, 5), height: u(size, 1.8), borderRadius: 999, backgroundColor: color }} />
      </View>
    </Box>
  );
}

/** A framed photo, for kỷ niệm. */
export function IconKyNiem({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View
        style={{
          width: u(size, 19),
          height: u(size, 16),
          borderRadius: u(size, 3),
          borderWidth: u(size, 2),
          borderColor: color,
          overflow: "hidden",
          justifyContent: "flex-end",
        }}
      >
        {/* A hill and a sun, the two marks that make a rectangle a picture. */}
        <View
          style={{
            position: "absolute",
            top: u(size, 2),
            right: u(size, 2.5),
            width: u(size, 3.5),
            height: u(size, 3.5),
            borderRadius: 999,
            backgroundColor: color,
          }}
        />
        <View
          style={{
            width: "100%",
            height: u(size, 5),
            backgroundColor: color,
            borderTopLeftRadius: u(size, 6),
            borderTopRightRadius: u(size, 3),
          }}
        />
      </View>
    </Box>
  );
}

/** Two people, for a group. */
export function IconNhom({ color, size = BOX }: IconProps) {
  return (
    <Box size={size}>
      <View style={{ flexDirection: "row", alignItems: "flex-end", gap: -u(size, 2) }}>
        <View style={{ alignItems: "center", opacity: 0.55 }}>
          <View style={{ width: u(size, 7), height: u(size, 7), borderRadius: 999, backgroundColor: color }} />
          <View
            style={{
              width: u(size, 12),
              height: u(size, 6),
              marginTop: u(size, 1),
              borderTopLeftRadius: u(size, 7),
              borderTopRightRadius: u(size, 7),
              backgroundColor: color,
            }}
          />
        </View>
        <View style={{ alignItems: "center" }}>
          <View style={{ width: u(size, 8), height: u(size, 8), borderRadius: 999, backgroundColor: color }} />
          <View
            style={{
              width: u(size, 14),
              height: u(size, 7),
              marginTop: u(size, 1),
              borderTopLeftRadius: u(size, 8),
              borderTopRightRadius: u(size, 8),
              backgroundColor: color,
            }}
          />
        </View>
      </View>
    </Box>
  );
}
