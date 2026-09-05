import { Image, type ImageSource } from "expo-image";
import type { ReactNode } from "react";
import { StyleSheet, Text, View, type DimensionValue, type StyleProp, type ViewStyle } from "react-native";

import { MOTION_MS } from "../motion";
import { nenAnhTrong, typography, useRudiTheme } from "../theme";

export interface Attribution {
  /** Photographer or uploader, as the licence requires it to be named. */
  author: string;
  /** Licence short name, e.g. «CC BY-SA 4.0», or «Ảnh của nhóm». */
  license: string;
  /** Where the file came from; shown as text, opened by the screen if it wants. */
  source?: string;
}

export interface MediaSlotProps {
  /** An authenticated source from `nguonAnh`, or null when there is no photo. */
  source: ImageSource | null;
  /** Width / height. 16/10 for a place, 1 for a tile, 4/5 for a polaroid. */
  ratio?: number;
  /** Fixed height instead of a ratio, when the parent sets the width. */
  height?: number;
  width?: DimensionValue;
  radius?: number;
  /** What a viewer with a screen reader hears; required, never decorative. */
  alt: string;
  /** Provenance line under a licensed photo. Required whenever `source` is not the group's own. */
  attribution?: Attribution;
  /** Authored artwork for the empty slot (an SVG per category). */
  fallback?: ReactNode;
  /** Content laid over the picture: a tag, a counter, a title on a scrim. */
  overlay?: ReactNode;
  contentFit?: "cover" | "contain";
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * The one place a photograph may appear in the shell.
 *
 * The rule in DESIGN.md is blunt: a stock photo standing in for a real place is
 * a fabrication. This slot exists so that rule can be kept *and* the layout can
 * be image-led: the frame is the same whether or not there is a picture, the
 * fallback is authored artwork from the visual world, and a licensed photograph
 * drops into that frame with its author and licence printed beneath it --
 * never a photo without its provenance. Since M12 the catalogue actually sends
 * them: `docAnhDiaDiem` for a place's gallery, `anhBiaThe` for a card's cover,
 * and both refuse a URL that arrived without a credit. Group photos
 * (`nguonAnh`) come with request headers; a URL from anywhere else is refused
 * by that helper before it reaches here.
 */
export function MediaSlot({
  source,
  ratio = 16 / 10,
  height,
  width = "100%",
  radius,
  alt,
  attribution,
  fallback,
  overlay,
  contentFit = "cover",
  style,
  testID,
}: MediaSlotProps) {
  const { colors, radius: r, space } = useRudiTheme();
  const frame: ViewStyle = height !== undefined ? { width, height } : { width, aspectRatio: ratio };
  return (
    <View testID={testID} style={style}>
      <View style={[frame, { borderRadius: radius ?? r.small, backgroundColor: nenAnhTrong, overflow: "hidden" }]}>
        {source ? (
          <Image
            accessibilityLabel={alt}
            source={source}
            contentFit={contentFit}
            transition={MOTION_MS.standard}
            style={StyleSheet.absoluteFill}
          />
        ) : (
          <View accessibilityLabel={alt} style={[StyleSheet.absoluteFill, styles.center]}>
            {fallback}
          </View>
        )}
        {overlay ? <View style={StyleSheet.absoluteFill} pointerEvents="box-none">{overlay}</View> : null}
      </View>
      {source && attribution ? (
        // Two lines, not one: this credit is the condition on which the picture
        // above it is allowed to be here, so a long author name has to wrap
        // rather than end in an ellipsis.
        <Text
          numberOfLines={2}
          style={[typography.caption, { color: colors.inkFaint, marginTop: space.xs }]}
        >
          {attribution.author} · {attribution.license}
          {attribution.source ? ` · ${attribution.source}` : ""}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
});
