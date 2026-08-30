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
 * Pure: props in, callbacks out. Finding faces and claiming a box are the
 * parent's network. `Anh` is not used: that frame fetches with credentials,
 * and a presentational screen that starts a request is no longer presentational.
 */
import React from "react";
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
          flex: 1,
          minHeight: 44,
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
          resizeMode="cover"
          style={{ width: "100%", height: "100%" }}
        />
        {o.map((box, i) => {
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
