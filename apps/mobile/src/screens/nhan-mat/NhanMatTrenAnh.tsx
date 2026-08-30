/** Anonymous face rectangles on a group photograph. The machine drew boxes; it named nobody.
 *
 * A box is a fraction of the image, not a person. `box_key` is an ordinal
 * inside one response, is not derived from the pixels, and is NOT stable
 * between requests -- `api.ts` says so on `OKhuonMatWire`. Claiming a box
 * from a previous scan after a re-scan is claiming a different rectangle.
 * This screen therefore never stores a name against a key, and never labels
 * a box with anything but "Bạn" after *this* person taps it.
 *
 * The honesty line under the photo is the requirement, not decoration.
 * Softening it into "AI đã nhận diện mọi người" would be the product saying
 * it knows who is in the picture, which is the one thing the detector
 * refuses to claim. Purple (`ai`) is spent only on the rectangles: that is
 * DESIGN.md's meaning for "a machine made this, a person can still correct
 * it". The lead of the screen stays `accent`, because choosing your own
 * face is a human action.
 *
 * Boxes are laid out as percentages of the frame. Converting the fractions
 * to pixels would lock the overlay to whatever size this phone happened to
 * measure on first layout, and a rotate or a wider window would put every
 * box on the wrong face.
 *
 * WHY THE FRAME TAKES THE PHOTOGRAPH'S OWN ASPECT RATIO. The server gives each
 * box as a fraction OF THE IMAGE. Percentages here are of the FRAME. Those are
 * the same rectangle only while the frame has the image's shape, so the frame
 * is given that shape from `onLoad` and the image is drawn `contain` inside it.
 *
 * This started as `resizeMode="cover"` on a flex-filling frame, which is the
 * ordinary way to fill a card and is wrong here: cover CROPS, so the visible
 * picture is no longer the picture the fractions were measured against, and
 * every box slides off its face by however much was cut. It is invisible in
 * code review and invisible to the detector -- an overlay with confident
 * rectangles on it looks equally correct whatever is underneath. It was caught
 * by looking at a screenshot in which the boxes plainly missed the shapes.
 *
 * Until the first `onLoad` there is no known ratio, so the frame holds 3:4 --
 * a shape, not a guess at this photograph. Nothing is drawn against it: the
 * boxes wait for `tiLe`, because an overlay positioned against a placeholder
 * ratio is exactly the wrong-face bug in a smaller window.
 *
 * Pure: props in, callbacks out. Finding faces and claiming a box are the
 * parent's network. `Anh` is not used: that frame fetches with credentials,
 * and a presentational screen that starts a request is no longer presentational.
 */
import React, { useEffect, useState } from "react";
import { Image, Pressable, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Screen } from "../../ui/Kit";

export function NhanMatTrenAnh({
  anhUri,
  o,
  dangTim,
  oCuaToi,
  loi,
  onTim,
  onChonO,
  onXong,
  onQuayLai,
}: {
  anhUri: string;
  o: { boxKey: string; x: number; y: number; width: number; height: number }[];
  dangTim: boolean;
  oCuaToi: string | null;
  loi: string | null;
  onTim: () => void;
  onChonO: (boxKey: string) => void;
  onXong: () => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  // Null until the photograph reports its own dimensions. The overlay waits on
  // it rather than guessing, because a box drawn against the wrong ratio is a
  // box on somebody else's face.
  const [tiLe, setTiLe] = useState<number | null>(null);

  // `Image.getSize` rather than the `onLoad` event. The event's payload is not
  // the same shape on react-native-web as on native -- reading
  // `nativeEvent.source` there leaves the ratio null forever, and a null ratio
  // draws no boxes at all, which is a blank overlay that looks like "no faces
  // found". `getSize` is one call with one contract on both platforms.
  useEffect(() => {
    let song = true;
    setTiLe(null);
    Image.getSize(
      anhUri,
      (rong, cao) => {
        if (song && rong > 0 && cao > 0) setTiLe(rong / cao);
      },
      () => {
        /* Unreadable photograph. The frame keeps its placeholder shape and no
           box is drawn, which is the honest outcome: without the image there
           is nothing for a rectangle to be a fraction of. */
      },
    );
    return () => {
      song = false;
    };
  }, [anhUri]);

  return (
    <Screen
      title="Nhận mặt trên ảnh"
      gap={space.md}
      footer={
        <>
          {dangTim ? (
            <Text
              style={{ ...type.body, color: c.inkSoft }}
              accessibilityLiveRegion="polite"
              accessibilityRole="text"
            >
              Đang tìm...
            </Text>
          ) : o.length === 0 ? (
            <Button label="Tìm khuôn mặt" onPress={onTim} />
          ) : null}
          <Button
            label="Xong"
            onPress={onXong}
            disabled={oCuaToi === null}
          />
          <Button label="Quay lại" tone="ghost" onPress={onQuayLai} />
        </>
      }
    >
      <View
        style={{
          width: "100%",
          // Bounded, because `width: 100%` plus an aspect ratio is a frame that
          // grows without limit: on a desktop-width window the picture became
          // tall enough to slide under the footer, and the detector caught the
          // consequence rather than the cause -- "Quay lại" measured 3.3:1
          // against the photograph instead of against the page. A phone never
          // reaches this cap; it exists so the web build cannot outgrow itself.
          maxWidth: 420,
          // The photograph's own shape once it is known. 3:4 only until then,
          // and no box is drawn against that placeholder.
          aspectRatio: tiLe ?? 3 / 4,
          flexShrink: 1,
          alignSelf: "center",
          borderRadius: radius.base,
          overflow: "hidden",
          backgroundColor: c.card,
          borderWidth: 1,
          borderColor: c.line,
        }}
      >
        <Image
          source={{ uri: anhUri }}
          accessibilityLabel="Ảnh nhóm"
          // `contain`, never `cover`. See the header: cover crops, and a
          // cropped picture is not the picture the box fractions describe.
          resizeMode="contain"
          style={{ width: "100%", height: "100%" }}
        />
        {(tiLe === null ? [] : o).map((box, i) => {
          const chon = oCuaToi === box.boxKey;
          const so = i + 1;
          return (
            <Pressable
              key={box.boxKey}
              onPress={() => onChonO(box.boxKey)}
              accessibilityRole="button"
              accessibilityLabel={`Ô vuông số ${so}, bấm để nhận đây là bạn`}
              style={({ pressed }) => ({
                position: "absolute",
                left: `${box.x * 100}%`,
                top: `${box.y * 100}%`,
                width: `${box.width * 100}%`,
                height: `${box.height * 100}%`,
                minWidth: 44,
                minHeight: 44,
                borderWidth: chon ? 4 : 2,
                borderColor: c.ai,
                borderRadius: radius.small,
                backgroundColor: chon ? c.aiSoft : "transparent",
                opacity: pressed ? 0.85 : 1,
              })}
            >
              {chon ? (
                <View
                  style={{
                    alignSelf: "flex-start",
                    margin: 2,
                    backgroundColor: c.card,
                    borderColor: c.lineStrong,
                    borderWidth: 1,
                    borderRadius: radius.pill,
                    paddingHorizontal: space.xs,
                    paddingVertical: 2,
                  }}
                >
                  <Text style={{ ...type.micro, fontWeight: "700", color: c.ink }}>
                    Bạn
                  </Text>
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </View>

      <Text style={{ ...type.label, color: c.ink }}>
        Máy chỉ khoanh các hình chữ nhật. Máy không biết ô nào là ai.
      </Text>

      {loi ? (
        <Card>
          <Text style={{ ...type.body, color: c.ink }} accessibilityRole="alert">
            {loi}
          </Text>
        </Card>
      ) : null}
    </Screen>
  );
}
