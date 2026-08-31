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
import type { CameraAccess, GiaiDoanDocBill } from "../camera";
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

const WELL_SCRIM = "rgba(0, 0, 0, 0.82)";

/* Opacity for the two side controls while a photo is being read.
 *
 * Measured, not chosen. At 0.40 the label "Ảnh chụp màn hình" -- white on this
 * screen's black ground -- composites to #666, which is 3.66:1 against the
 * ground it sits on. That is below the 4.5:1 step for body text. WCAG 2.2
 * SC 1.4.3 does exempt it, because the control really is inactive here
 * (`disabled`, and react-native-web emits `aria-disabled` + `pointer-events:
 * none` from it), so nothing was strictly broken. But "exempt from the floor"
 * is not the same as "legible", and a disabled control still has to say which
 * control it is.
 *
 * 0.46 is the smallest value that clears the step: white at alpha a over black
 * composites to a*255, and 4.5:1 needs relative luminance >= 0.175, i.e. a
 * channel of about 116/255 = 0.455. Rounded up so rounding cannot land under.
 * The dimming still reads as unavailable -- this is a 6% opacity move, not a
 * change of state -- and the scrim above stops at y=612 while these controls
 * sit at y=737, so they are on plain ground and this is the only thing
 * deciding whether their labels can be read.
 */
const MO_KHI_BAN = 0.46;

export function ChupBill(props: {
  access: CameraAccess;
  cameraRef: React.RefObject<any>;
  busy: boolean;
  error: string | null;
  /** Which half of the read is running, or `null` when nothing is. */
  giaiDoan?: GiaiDoanDocBill | null;
  onShutter: () => void;
  onPickImage: () => void;
  /** A screenshot, not a paper bill. Same picker, different reader. */
  onPickScreenshot: () => void;
  onRequestPermission: () => void;
  onOpenSettings: () => void;
  onCancel: () => void;
}): React.JSX.Element {
  const { access, busy, error, giaiDoan = null } = props;
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
        {/* The second line no longer promises auto-capture, because this build
            does not have it: a person presses the shutter. The previous pass
            kept the mockup's wording verbatim on the grounds that rewriting a
            spec line is not this lane's call, and flagged it. Resolving it now,
            because the spec contradicts itself rather than being overridden:
            the same mockup sheet's own feature card says "Chụp bill hoặc chọn
            ảnh · Rủ Đi AI tự động căn chỉnh, loại bỏ nhiễu và trích xuất thông
            tin", i.e. the person takes the photo and what is automatic is the
            reading. That half matches the build. The phone-screen line was the
            half that did not, and shipping it means a demo where someone holds
            the camera steady waiting for a shutter that never fires.
            The reading itself is real (`POST /receipts/scan` against Gemini),
            so "nhận diện" is kept and only "tự động chụp" goes. If frame
            stability detection is built later, this line comes back. */}
        {/* Hidden during the read. It is an instruction for framing a shot, and
            leaving it up while the photo is already being read told a person to
            line up a bill that had been taken several seconds ago. */}
        {busy ? null : (
          // No `paddingHorizontal` of its own: the parent already insets this
          // column by `space.lg`, and the extra `space.md` on each side was
          // costing 32px that the instruction needs. Measured at 28px: the
          // sentence is 305.2px wide, so with the double inset it wrapped to two
          // lines at 360px viewport and fitted only from 390px up. Without it,
          // one line from 360px up.
          // Still two lines at 320px, breaking as "Đưa bill vào khung" / "hình".
          // Left as is rather than hidden: it does not overflow at that width
          // (measured), and the alternative is a hand-placed break that would be
          // wrong at every other size. Worth revisiting only if a 320px device
          // is actually a target.
          <View style={{ alignItems: "center", gap: 4 }}>
            {/* `type.h1`, not `type.body`. This is the screen's own voice -- the
                one sentence telling a person what to do -- and at the card step
                it rendered SMALLER than the nav chrome above it (20px title vs
                16px body), so the frame outranked the instruction. `DangDocBill`
                already gives this same slot `h1` once the read starts, on the
                stated grounds that whatever covers this screen is its title; the
                resting state now agrees with the busy state instead of
                contradicting it. */}
            <Text style={{ ...type.h1, color: WHITE, textAlign: "center" }}>
              Đưa bill vào khung hình
            </Text>
            <Text style={{ ...type.label, color: WHITE_SOFT, textAlign: "center" }}>
              AI sẽ nhận diện từng món ngay sau khi chụp
            </Text>
          </View>
        )}

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
          {/* Over the well rather than under it. The wait used to be one dim
              line below the frame while the viewfinder kept showing a live
              picture, so the screen looked ready to take another photo during
              the one moment it was busiest. */}
          {busy ? <DangDocBill giaiDoan={giaiDoan} /> : null}
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
            opacity: busy ? MO_KHI_BAN : pressed ? 0.7 : 1,
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

        <Pressable
          onPress={props.onPickScreenshot}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="Ảnh chụp màn hình"
          style={({ pressed }) => ({
            minWidth: HIT,
            minHeight: HIT,
            maxWidth: 88,
            alignItems: "center",
            justifyContent: "center",
            opacity: busy ? MO_KHI_BAN : pressed ? 0.7 : 1,
          })}
        >
          <Text style={{ ...type.label, color: WHITE, fontWeight: "600", textAlign: "center" }}>
            Ảnh chụp màn hình
          </Text>
        </Pressable>
      </View>

      {/* `type.label`, not `type.micro`.
          Measured, not preferred: with a 12pt step on this screen the rendered
          scale was 12 / 13 / 13.3 / 16 / 20, and 12 to 13 is a 1.08 step that
          does no work. It really does none -- what separates this line from
          the instruction above it is weight and a dimmer white, not one point
          of size -- so dropping it leaves 13 / 16 / 20.
          That left `flat-type-hierarchy` standing at 20/13 = 1.5:1, and the
          note here used to say it was unfixable without contradicting the
          mockup. That was the wrong end of the scale to look at. The nav title
          is NOT movable -- `KetQuaNhanDien`, `GoiYChia` and `KetQuaThanhToan`
          all title their nav bar at `type.title`, so shrinking this one alone
          would buy the rule at the cost of the convention. What was movable was
          the top: this screen simply had no screen-level heading, so its
          largest text was chrome. Promoting the instruction to `h1` gives the
          scale a real top step at 28px (28/13 = 2.2:1) instead of flattening
          the bottom, which is also what the rule's own advice asks for --
          "fewer sizes with more contrast", not "more sizes". */}
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

/** Seconds since this component mounted, ticking once a second.
 *
 * Mounted with the wait and unmounted with it, so "since mount" is "since the
 * shutter" without a start time having to be threaded down from the flow.
 * The interval is cleared on unmount; a timer left running behind a screen
 * that has gone is the leak that shows up as a warning in a demo.
 */
function useGiay(): number {
  const [giay, setGiay] = React.useState(0);
  React.useEffect(() => {
    const timer = setInterval(() => setGiay((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return giay;
}

/**
 * The wait between pressing the shutter and seeing the items.
 *
 * This is the longest unavoidable pause in the product: a photo is compressed,
 * uploaded, and read by a model, and on a phone that is several seconds. The
 * screen it replaced showed one static line, which is indistinguishable from a
 * screen that has hung -- and the reflex when an app looks hung is to press the
 * thing again, which here means taking a second photo.
 *
 * So three things move, and all three are real rather than decorative:
 *
 *  - the spinner, which says the UI thread is alive;
 *  - the stage line, which changes when `withBillPhoto` actually crosses from
 *    compressing to uploading, not on a timer;
 *  - the seconds, which are counted, not estimated.
 *
 * There is no progress bar and no percentage. Nothing in this app knows how far
 * through a bill the model is, and a bar that fills on a guess is a lie that
 * gets believed -- `tests/receipt.test.mjs` gates the source against exactly
 * that. The counter is the honest version of the same reassurance.
 *
 * `LAU` is where the copy stops promising it is nearly done and says what a
 * long wait means instead. Ten seconds because that is roughly where the
 * measured reads sit; past it, silence starts to read as failure.
 */
const LAU = 10;

function DangDocBill({ giaiDoan }: { giaiDoan: GiaiDoanDocBill | null }) {
  const giay = useGiay();
  const chuanBi = giaiDoan === "chuan-bi-anh";
  const tieuDe = chuanBi ? "Đang chuẩn bị ảnh bill" : "AI đang đọc từng món";
  const than = chuanBi
    ? "Thu nhỏ ảnh và xoá vị trí chụp trước khi gửi đi."
    : "Ảnh đã gửi. Đang chờ máy chủ đọc xong tên món và số tiền.";

  return (
    <View
      // `role="status"` and a polite live region: the spinner is invisible to a
      // screen reader, so without this the app goes silent for several seconds
      // at the one moment a person most needs to know it is working.
      accessibilityLiveRegion="polite"
      role="status"
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: WELL_SCRIM,
        alignItems: "center",
        justifyContent: "center",
        padding: space.md,
        gap: space.sm,
      }}
    >
      <ActivityIndicator size="large" color={WHITE} />
      {/* `type.h1`, not `type.title`. This overlay covers the whole screen, so
          this line is the screen title while it shows, and DESIGN.md gives the
          `h1` step to "tiêu đề màn" -- `title` is the card step. Rendering it at
          the card step left the screen running 13/16/20, a 1.5:1 spread that
          reads as one size in three weights. Same mistake `theme.ts` documents
          having found elsewhere; this screen was still making it. */}
      <Text style={{ ...type.h1, color: WHITE, textAlign: "center" }}>{tieuDe}</Text>
      <Text style={{ ...type.label, color: WHITE_SOFT, textAlign: "center" }}>{than}</Text>
      <Text style={{ ...type.label, color: WHITE_SOFT, textAlign: "center" }}>
        Đã chờ {giay} giây
      </Text>
      {giay >= LAU ? (
        <Text style={{ ...type.label, color: WHITE_FAINT, textAlign: "center" }}>
          Bill nhiều món thì đọc lâu hơn. Giữ màn hình mở, đừng chụp lại vội.
        </Text>
      ) : null}
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
            opacity: busy ? MO_KHI_BAN : pressed ? 0.75 : 1,
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
