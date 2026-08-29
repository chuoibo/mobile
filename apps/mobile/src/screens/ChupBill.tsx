/** The viewfinder. The bill has to be the brightest thing on the screen.
 *
 * Black is the leading tone on purpose: the live paper sits in a dark well so
 * the four white corners read as a frame, not as decoration. Palette colours
 * from the light-ground system (`inkSoft` especially) are not used on this
 * surface; they were measured on cream, not on #000.
 */
import { CameraView } from "expo-camera";
import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import type { CameraAccess } from "../camera";
import { radius, space, type } from "../theme";

const BLACK = "#000";
const WHITE = "#fff";
const WHITE_SOFT = "rgba(255, 255, 255, 0.62)";
// 0.55, not 0.45. Measured: white at 0.45 alpha composites to #737373, which
// is 4.43:1 on #000 -- under the 4.5:1 that WCAG asks of 12px text, and the
// "Powered by Rủ Đi AI" line is 12px. 0.55 composites to #8c8c8c at 6.25:1.
// The detector cannot compute this pair for us (rgba over a parent fill), so
// it was worked out by hand rather than assumed to be fine because it is only
// a footer.
const WHITE_FAINT = "rgba(255, 255, 255, 0.55)";
const WHITE_WELL = "rgba(255, 255, 255, 0.12)";

const SHUTTER = 76;
const RING_GAP = 6;
const RING = SHUTTER + RING_GAP * 2;
const CORNER = 28;
const CORNER_STROKE = 3;
const HIT = 44;

export function ChupBill(props: {
  access: CameraAccess;
  cameraRef: React.RefObject<any>;
  busy: boolean;
  error: string | null;
  onShutter: () => void;
  onPickImage: () => void;
  onRequestPermission: () => void;
  onOpenSettings: () => void;
  onCancel: () => void;
}): React.JSX.Element {
  const { access, busy, error } = props;
  const live = access.nextAction === "mo-camera";
  const canShoot = live && !busy;

  return (
    <View style={{ flex: 1, backgroundColor: BLACK }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          paddingHorizontal: space.md,
          paddingTop: space.sm,
          minHeight: HIT,
        }}
      >
        <Pressable
          onPress={props.onCancel}
          accessibilityRole="button"
          accessibilityLabel="Huỷ"
          style={{ minWidth: HIT, minHeight: HIT, justifyContent: "center" }}
        >
          <Text style={{ ...type.body, color: WHITE, fontWeight: "600" }}>Huỷ</Text>
        </Pressable>
        <Text
          style={{
            ...type.title,
            color: WHITE,
            flex: 1,
            textAlign: "center",
          }}
        >
          Chụp bill
        </Text>
        {/* Same width as Huỷ so the title sits on the true centre. */}
        <View style={{ minWidth: HIT }} />
      </View>

      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          paddingHorizontal: space.lg,
          gap: space.md,
        }}
      >
        {/* The second line is the mockup's, verbatim, and half of it is not
            true of this build: nothing auto-captures. A person presses the
            shutter. The reading afterwards is real -- `POST /receipts/scan`
            against Gemini -- so "nhận diện" holds and "tự động chụp" does not.
            Kept verbatim because the copy is a specified deliverable and
            rewriting a spec line is not this lane's call, but flagged here and
            to the lead rather than left to be discovered in a demo. Auto-capture
            is a real feature (frame-stability detection); if it is not going to
            be built, this line should become "AI sẽ nhận diện từng món ngay sau
            khi chụp". */}
        <View style={{ alignItems: "center", gap: 4, paddingHorizontal: space.md }}>
          <Text style={{ ...type.body, color: WHITE, fontWeight: "600", textAlign: "center" }}>
            Đưa bill vào khung hình
          </Text>
          <Text style={{ ...type.label, color: WHITE_SOFT, textAlign: "center" }}>
            AI sẽ tự động chụp và nhận diện
          </Text>
        </View>

        <View
          style={{
            width: "100%",
            maxWidth: 360,
            aspectRatio: 3 / 4,
            backgroundColor: BLACK,
          }}
        >
          {live ? (
            <CameraView
              ref={props.cameraRef}
              facing="back"
              style={{ flex: 1 }}
            />
          ) : (
            <AccessWell
              access={access}
              busy={busy}
              onRequestPermission={props.onRequestPermission}
              onOpenSettings={props.onOpenSettings}
              onPickImage={props.onPickImage}
            />
          )}
          <CornerMarks />
        </View>


        {error !== null ? (
          <View
            style={{
              alignSelf: "stretch",
              backgroundColor: WHITE_WELL,
              borderRadius: radius.small,
              paddingVertical: space.sm,
              paddingHorizontal: space.md,
            }}
          >
            <Text style={{ ...type.label, color: WHITE, textAlign: "center" }}>{error}</Text>
          </View>
        ) : null}

        {busy ? (
          <Text style={{ ...type.label, color: WHITE_SOFT, textAlign: "center" }}>
            Đang đọc bill...
          </Text>
        ) : null}
      </View>

      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          paddingHorizontal: space.xl,
          paddingBottom: space.sm,
        }}
      >
        <Pressable
          onPress={props.onPickImage}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Chọn ảnh bill"
          // No `accessibilityState={{ disabled: busy }}`: react-native-web
          // drops that prop entirely, and `disabled` above already emits
          // `aria-disabled` on web and wins over it on native
          // (`Pressable.js:236`). It was two ways to say one thing, one of
          // which never arrived.
          style={({ pressed }) => ({
            minWidth: HIT,
            minHeight: HIT,
            alignItems: "center",
            justifyContent: "center",
            opacity: busy ? 0.4 : pressed ? 0.7 : 1,
          })}
        >
          <GalleryGlyph />
        </Pressable>

        <Pressable
          onPress={props.onShutter}
          disabled={!canShoot}
          accessibilityRole="button"
          accessibilityLabel="Chụp bill"
          // `disabled` carries the first half. The second half was the part
          // that mattered and the part that vanished: while a photo is being
          // read the shutter looked identical to a shutter that was merely
          // not ready. `aria-busy` is the spelling both platforms read.
          aria-busy={busy}
          style={({ pressed }) => ({
            width: RING,
            height: RING,
            borderRadius: RING / 2,
            borderWidth: 2,
            borderColor: WHITE,
            alignItems: "center",
            justifyContent: "center",
            opacity: !canShoot ? 0.45 : pressed ? 0.8 : 1,
          })}
        >
          <View
            style={{
              width: SHUTTER,
              height: SHUTTER,
              borderRadius: SHUTTER / 2,
              backgroundColor: WHITE,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {busy ? <ActivityIndicator color={BLACK} /> : null}
          </View>
        </Pressable>

        {/* Visual balance for the gallery control. No facing handler exists
            on this screen, so this is empty space, not a dead button. */}
        <View style={{ minWidth: HIT, minHeight: HIT }} />
      </View>

      {/* `type.label`, not `type.micro`.
          Measured, not preferred: with a 12pt step on this screen the rendered
          scale was 12 / 13 / 13.3 / 16 / 20, and 12 to 13 is a 1.08 step that
          does no work. It really does none -- what separates this line from
          the instruction above it is weight and a dimmer white, not one point
          of size -- so dropping it leaves 13 / 16 / 20.
          What that did and did not buy, because the difference matters: the
          rendered scan reports `flat-type-hierarchy` before and after, one
          finding either way. The scale underneath it went from five sizes to
          three. The finding survives because this screen's largest text is
          20px, and it is not fixable from here without contradicting the
          mockup, which gives the screen a compact nav title and puts the
          hierarchy in the viewfinder and the shutter rather than in type. */}
      <Text
        style={{
          ...type.label,
          color: WHITE_FAINT,
          textAlign: "center",
          paddingBottom: space.md,
        }}
      >
        Powered by Rủ Đi AI
      </Text>
    </View>
  );
}

function AccessWell({
  access,
  busy,
  onRequestPermission,
  onOpenSettings,
  onPickImage,
}: {
  access: CameraAccess;
  busy: boolean;
  onRequestPermission: () => void;
  onOpenSettings: () => void;
  onPickImage: () => void;
}) {
  const action = access.nextAction;
  const label =
    action === "xin-quyen" ? "Cho phép dùng camera"
    : action === "mo-cai-dat" ? "Mở Cài đặt"
    : action === "chon-anh" ? "Chọn ảnh bill"
    : null;
  const onPress =
    action === "xin-quyen" ? onRequestPermission
    : action === "mo-cai-dat" ? onOpenSettings
    : action === "chon-anh" ? onPickImage
    : null;

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: BLACK,
        alignItems: "center",
        justifyContent: "center",
        padding: space.md,
        gap: space.md,
      }}
    >
      <Text style={{ ...type.label, color: WHITE_SOFT, textAlign: "center" }}>
        {access.message}
      </Text>
      {label !== null && onPress !== null ? (
        <Pressable
          onPress={onPress}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel={label}
          // Same as the two above: `disabled` is what reaches the element.
          style={({ pressed }) => ({
            minHeight: HIT,
            paddingHorizontal: space.md,
            borderWidth: 1,
            borderColor: WHITE,
            borderRadius: radius.control,
            alignItems: "center",
            justifyContent: "center",
            opacity: busy ? 0.4 : pressed ? 0.75 : 1,
          })}
        >
          <Text style={{ ...type.body, color: WHITE, fontWeight: "600" }}>{label}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/** Four L-shaped marks. A closed rectangle would compete with the paper. */
function CornerMarks() {
  const arm = {
    position: "absolute" as const,
    width: CORNER,
    height: CORNER,
    borderColor: WHITE,
  };
  return (
    <View pointerEvents="none" style={{ position: "absolute", inset: 0 }}>
      <View
        style={{
          ...arm,
          top: 0,
          left: 0,
          borderTopWidth: CORNER_STROKE,
          borderLeftWidth: CORNER_STROKE,
          borderTopLeftRadius: radius.small,
        }}
      />
      <View
        style={{
          ...arm,
          top: 0,
          right: 0,
          borderTopWidth: CORNER_STROKE,
          borderRightWidth: CORNER_STROKE,
          borderTopRightRadius: radius.small,
        }}
      />
      <View
        style={{
          ...arm,
          bottom: 0,
          left: 0,
          borderBottomWidth: CORNER_STROKE,
          borderLeftWidth: CORNER_STROKE,
          borderBottomLeftRadius: radius.small,
        }}
      />
      <View
        style={{
          ...arm,
          bottom: 0,
          right: 0,
          borderBottomWidth: CORNER_STROKE,
          borderRightWidth: CORNER_STROKE,
          borderBottomRightRadius: radius.small,
        }}
      />
    </View>
  );
}

/** A picture frame with a sun. No icon library ships with this app. */
function GalleryGlyph() {
  return (
    <View
      style={{
        width: 26,
        height: 22,
        borderWidth: 2,
        borderColor: WHITE,
        borderRadius: 3,
      }}
    >
      <View
        style={{
          position: "absolute",
          top: 3,
          right: 3,
          width: 5,
          height: 5,
          borderRadius: 3,
          backgroundColor: WHITE,
        }}
      />
      <View
        style={{
          position: "absolute",
          left: 2,
          bottom: 2,
          width: 12,
          height: 8,
          borderTopWidth: 2,
          borderRightWidth: 2,
          borderColor: WHITE,
          transform: [{ rotate: "-30deg" }],
        }}
      />
    </View>
  );
}
