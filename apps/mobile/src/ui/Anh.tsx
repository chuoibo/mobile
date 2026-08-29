/** A photograph, and what stands in its place until one arrives.
 *
 * Until this file existed the app rendered zero images: `import { Image }` from
 * react-native appeared in no screen, and every place in the mockup that holds
 * a photo -- the opening illustration, the place cards, the avatar -- was a
 * painted `View`. That was a defensible answer to "we have no photos", and a
 * bad answer to "we will have photos": a coloured block is not a frame, so the
 * day a URL arrives the layout has to be redrawn rather than filled in.
 *
 * So the split this file makes is between the FRAME and the CONTENT. The frame
 * is real now: it has the size and the corner radius the photo will have, it
 * reserves that space whether or not a URL exists, and it clips. The content is
 * whichever of two things the frame can currently show:
 *
 *   - `uri` present and loaded  -> a real `<Image>`, `cover`, filling the frame.
 *   - no `uri`, still loading, or the load failed -> `cho`, the stand-in.
 *
 * Nothing here decides what the stand-in looks like. That stays with the caller,
 * because each surface knows what it can honestly draw when it has no picture:
 * `AnhDiaDiem` draws a category mark, `MoDau` draws the sunset, `CaNhan` draws
 * initials. A generic grey rectangle would be the one option that is both ugly
 * and less honest than all three.
 *
 * Three behaviours worth stating because they are the ones that go wrong:
 *
 * 1. The stand-in stays mounted underneath the image for the whole life of the
 *    frame, not just until `onLoad`. A remote image that decodes and then fails
 *    to repaint, or that is evicted, leaves a hole; something is always behind
 *    it. This costs one static subtree and buys the guarantee that this frame
 *    is never empty.
 * 2. A failed load goes back to the stand-in and stays there. It does not show
 *    a broken-image glyph, and it does not show the server's reason -- the
 *    person looking at a restaurant card cannot act on `ECONNREFUSED`.
 * 3. Overlays (`children`) are drawn above both, so a badge or a name block
 *    reads the same whichever state the frame is in. That matters for contrast:
 *    the scrims those callers put under their text were measured against the
 *    painted stand-in, and a real photograph can be brighter than any of them.
 *    Callers that put text on the frame must bring their own ground.
 */
import React, { useState } from "react";
import { Image, View } from "react-native";
import type { StyleProp, ViewStyle } from "react-native";

/** What the frame is currently able to show. Exported because the tests assert
 *  on it directly, and because a caller may want to dim an overlay while the
 *  photo is still arriving. */
export type TrangThaiAnh = "khong-co" | "dang-tai" | "hien" | "hong";

export function Anh({
  uri,
  alt,
  cho,
  style,
  children,
  onTrangThai,
}: {
  /** Where the photograph lives. `null` is the normal case today: the server
   *  does not send place or profile photos yet, and a screen must render
   *  identically the day before and the day after it starts to. */
  uri?: string | null;
  /** What a screen reader says instead of the picture. Required when a `uri`
   *  can appear, because an image that carries meaning and announces nothing is
   *  worse than no image. Pass `""` only for a frame that is genuinely
   *  decorative; that hides it from the accessibility tree entirely. */
  alt: string;
  /** Drawn when there is no photograph to draw. Sized by this frame, so it
   *  should fill its parent rather than declare its own dimensions. */
  cho: React.ReactNode;
  /** The frame: width, height or aspectRatio, and borderRadius. Sizing lives
   *  with the caller because the mockup gives each surface a different shape. */
  style?: StyleProp<ViewStyle>;
  /** Badges, ribbons, name blocks. Drawn above the photograph. */
  children?: React.ReactNode;
  onTrangThai?: (t: TrangThaiAnh) => void;
}) {
  // `hong` is sticky per URI: once a load has failed, re-rendering must not put
  // the <Image> back and start the same failing request again on every parent
  // update. Keyed by the URI so a *new* URL does get a fresh attempt.
  const [hong, setHong] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);

  const coAnh = typeof uri === "string" && uri.length > 0;
  const veAnh = coAnh && hong !== uri;

  const trangThai: TrangThaiAnh = !coAnh
    ? "khong-co"
    : hong === uri
      ? "hong"
      : xong === uri
        ? "hien"
        : "dang-tai";

  return (
    <View
      style={[{ overflow: "hidden" }, style]}
      // The frame is one thing to a screen reader, not a photograph plus a
      // drawing plus whatever the stand-in is made of. An empty `alt` means the
      // caller says this frame carries no information, so it leaves the tree
      // rather than announcing itself as an unlabelled image.
      accessibilityRole={alt ? "image" : undefined}
      accessibilityLabel={alt || undefined}
      accessibilityElementsHidden={!alt}
      importantForAccessibility={alt ? "yes" : "no-hide-descendants"}
      aria-hidden={alt ? undefined : true}
    >
      {/* Always mounted. See note 1 above: this is the floor, not a splash. */}
      <View
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
        pointerEvents="none"
        // The frame above already carries the label. Without this the stand-in
        // announces its own decorative shapes a second time.
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        aria-hidden
      >
        {cho}
      </View>

      {veAnh ? (
        <Image
          source={{ uri: uri as string }}
          // Never `contain`: a photograph letterboxed inside a card reads as a
          // broken card, and the frame's whole job is to be filled.
          resizeMode="cover"
          style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
          // Labelled on the frame, not here, so the two do not both announce.
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
          aria-hidden
          onLoad={() => {
            setXong(uri as string);
            onTrangThai?.("hien");
          }}
          onError={() => {
            // No message, no code, no retry. The stand-in reappears and the
            // screen keeps working; see note 2.
            setHong(uri as string);
            onTrangThai?.("hong");
          }}
        />
      ) : null}

      {children}
    </View>
  );
}

/**
 * The shapes the mockup actually uses, so three screens cannot drift apart.
 *
 * These are frame geometry, not a new design token: `aspectRatio` is how much
 * of the screen the photograph is allowed to take, measured off `mockup.png`.
 * Kept here rather than inline so that when the photo API lands, the answer to
 * "what size will it be" is already written down and identical everywhere.
 */
export const KHUNG = {
  /** Place card in the Khám phá grid: a wide band above the name block. */
  the: { aspectRatio: 4 / 3 },
  /** The banner behind the profile header. */
  bia: { aspectRatio: 16 / 9 },
} as const;

/** A round frame, for avatars. `borderRadius: 999` on a square, stated once. */
export function khungTron(size: number): ViewStyle {
  return { width: size, height: size, borderRadius: 999 };
}
