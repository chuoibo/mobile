/** The opening screen. Sunset, wordmark, and a way in.
 *
 * There is no real sign-in behind these buttons and there will not be one
 * before the deadline -- see `navigation/nhom-demo.ts` for why. Pressing
 * Google or Apple opens a picker of the demo group instead. The screen says so
 * in a caption that sits under the buttons at all times rather than in a
 * dismissible notice, because the person who most needs to read it is the one
 * being shown the app by somebody else.
 *
 * Contrast is the reason this screen is built the way it is. `tokens.json`
 * states the brand layer may not carry small text: white on `coral` measures
 * 2.92:1. Measured for this composition, white sits at 4.74:1 on the violet
 * top of the ramp, 3.64:1 on the rose middle, and 2.62:1 on the ember bottom.
 * So the wordmark and tagline live in the violet third where white is legal
 * outright, and the button block sits under a scrim that takes the ember down
 * to roughly 10:1. Nothing here is decoration hoping to pass.
 */
import React, { useState } from "react";
import { Platform, Pressable, ScrollView, Text, View } from "react-native";
import type { DimensionValue } from "react-native";
import tokens from "../../../../../packages/shared/tokens.json";
import { radius, space, type, usePalette } from "../../theme";
import { Gradient, HERO_SUNSET, Scrim, mixHex } from "../../navigation/Gradient";
import { DEMO_GROUP_NAME, DEMO_PEOPLE, type DemoPerson } from "../../navigation/nhom-demo";
import { useInertBackground } from "../../navigation/modal";
import { Anh } from "../../ui/Anh";

const brand = tokens.brand;

/** Ink for anything sitting on the sunset. Not a new colour: it is `accentInk`. */
const ON_SUNSET = tokens.color.light.accentInk;

/** Ground under the sign-in block. A stated blend of two tokens, not a taste
 *  decision: dark enough to carry white body text at AA with room to spare. */
const PANEL = mixHex(brand.violet, tokens.color.light.ink, 0.84);

export function MoDau({ onVao, onBoQua, onSoDienThoai, anhNen }: {
  onVao: (nguoi: DemoPerson) => void;
  /** Skip. Enters the shell with nobody signed in, which is a real state. */
  onBoQua: () => void;
  /** The one way in that is not a shell. Opens F01, which sends a real
   *  `PUT /people/{id}`; the two provider buttons above it still open the
   *  demo picker, and the caption under them now has to say which is which. */
  onSoDienThoai: () => void;
  anhNen?: string | null;
}) {
  const [dangChon, setDangChon] = useState(false);
  // The picker below is the same kind of sheet as the [+] menu and had the
  // same hole: it covers the sign-in block, and Tab used to walk straight onto
  // the buttons underneath it. Not in QA's report -- they measured the [+]
  // sheet -- but it is the same defect on the screen the demo opens on, and
  // finding it and leaving it would be a choice.
  const nenRef = useInertBackground(dangChon);

  return (
    // The solid ground is not decoration and not a duplicate of the gradient.
    // The ramp above it is painted by sibling views, so nothing in the
    // ancestor chain of this white text declares a background -- which means a
    // contrast checker reads white-on-white, and more importantly, if that
    // band layer ever fails to lay out, the text really would be white on
    // white. Naming the ramp's own top stop here makes the DOM state what is
    // actually behind the text and gives the screen a floor to fail onto.
    <View style={{ flex: 1, backgroundColor: HERO_SUNSET[0] }}>
      <Anh
        uri={anhNen}
        // Decorative: the wordmark and caption already say everything this
        // screen means, so an empty alt keeps the frame out of the tree.
        alt=""
        cho={
          <>
            <Gradient colors={HERO_SUNSET} style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }} />
            <CanhHoangHon />
          </>
        }
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
      />
      {/* Enough at the top to seat the wordmark, out of the way through the
          middle so the sunset stays a sunset. The button block does not lean
          on this -- it brings its own ground. */}
      <Scrim alphas={[0.3, 0.06, 0.28]} />

      {/* The decorations above are not focusable and carry `pointerEvents:
          none`, so the only thing the picker has to shut off is this block. */}
      <View ref={nenRef} style={{ flex: 1, paddingHorizontal: space.md, paddingTop: Platform.OS === "ios" ? 52 : 36, paddingBottom: space.lg }}>
        <View style={{ flexDirection: "row", justifyContent: "flex-end" }}>
          <Pressable
            onPress={onBoQua}
            accessibilityRole="button"
            accessibilityLabel="Bỏ qua, vào app mà chưa chọn người"
            style={({ pressed }) => ({
              minHeight: 44,
              justifyContent: "center",
              paddingHorizontal: space.sm,
              opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: ON_SUNSET }}>Bỏ qua</Text>
          </Pressable>
        </View>

        {/* Wordmark, kept in the darkened violet third where white is legal
            outright rather than floated into the rose middle where it is not. */}
        <View style={{ alignItems: "center", marginTop: space.sm, gap: space.xs }}>
          <View style={{ flexDirection: "row", alignItems: "flex-start" }}>
            <Text
              style={{
                fontSize: 64,
                lineHeight: 72,
                fontWeight: "800",
                letterSpacing: -2,
                color: ON_SUNSET,
              }}
            >
              Rủ Đi
            </Text>
            <Text style={{ fontSize: 22, lineHeight: 30, color: ON_SUNSET, marginTop: 6 }}>✦</Text>
          </View>
          <Text style={{ ...type.title, fontWeight: "500", color: ON_SUNSET, textAlign: "center" }}>
            AI đi chơi, chia bill thông minh
          </Text>
        </View>

        <View style={{ flex: 1 }} />

        {/* The sign-in block carries its own ground for the same reason the
            root does: the link and the caption underneath are small white
            text, and small white text on the ember end of the ramp measures
            2.62:1 -- the exact case tokens.json warns about. On this panel
            the colour pair measures 13.51:1 instead, and the number is
            computable by anything that reads the DOM rather than only by me.

            That pair is necessary and was not sufficient. The caption also
            carried opacity 0.92, and the rendered result measured 4.1:1
            median pixel contrast against a 4.5:1 floor -- a colour pair is
            what two hex values do, not what reaches the eye through an
            opacity stack and 13px anti-aliasing. Measure the render. */}
        <View
          style={{
            gap: space.sm,
            backgroundColor: PANEL,
            borderRadius: radius.base,
            padding: space.md,
          }}
        >
          <NutHang
            label="Đăng ký với Google"
            monogram="G"
            background={tokens.color.light.card}
            ink={tokens.color.light.ink}
            onPress={() => setDangChon(true)}
          />
          <NutHang
            label="Đăng ký với Apple"
            monogram=""
            background={tokens.color.light.ink}
            ink={tokens.color.light.card}
            onPress={() => setDangChon(true)}
          />

          <Pressable
            onPress={onSoDienThoai}
            accessibilityRole="button"
            style={({ pressed }) => ({
              minHeight: 44,
              alignItems: "center",
              justifyContent: "center",
              opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: ON_SUNSET, textDecorationLine: "underline" }}>
              Đăng nhập bằng số điện thoại
            </Text>
          </Pressable>

          {/* Permanent, not dismissible.
              No opacity on this one. It carried 0.92 to make it recede, which
              was backwards twice over: this is the sentence that admits the
              sign-in is not real, so it is the last thing on the screen that
              should be dimmed -- and the detector measured the result at 4.1:1
              median pixel contrast against a 4.5:1 floor, because 13px text at
              400 weight renders as mostly anti-aliased edge pixels and the
              nominal 13.51:1 of the colour pair never reaches the eye. Full
              opacity plus 500 weight; it stays subordinate by size, not by
              being hard to read. */}
          {/* This sentence used to say all three buttons opened the picker,
              which was true when it was written and stopped being true when
              F01 landed. A caption that overstates what is a shell is the
              lesser failure; one that calls a working thing a shell teaches
              the person watching to distrust the parts that do work. Both
              halves are named separately now. */}
          <Text style={{ ...type.label, fontWeight: "500", color: ON_SUNSET, textAlign: "center" }}>
            Google và Apple chưa nối thật: bấm vào sẽ mở danh sách{" "}
            {DEMO_GROUP_NAME} để chọn nhanh một người. Đăng nhập bằng số điện
            thoại là thật: nó tạo tài khoản trên máy chủ.
          </Text>
        </View>
      </View>

      {dangChon ? (
        <ChonNguoi onPick={onVao} onClose={() => setDangChon(false)} />
      ) : null}
    </View>
  );
}

/**
 * The sunset itself: sun, three ridges, a string of lights, and the group.
 *
 * Built from Views because there is no image generation in this toolchain and
 * a stock photograph of strangers is not something this repo may carry. Every
 * tone is a stated blend of two brand tokens (see `mixHex`), so the scene
 * moves with the palette instead of drifting away from it.
 */
function CanhHoangHon() {
  // Ridges recede by getting lighter and bluer, the way haze actually works.
  // Nearest is darkest, so the group silhouetted on it stays readable.
  const xa = mixHex(brand.violet, tokens.color.light.ink, 0.5);
  const giua = mixHex(brand.rose, tokens.color.light.ink, 0.66);
  const gan = mixHex(brand.rose, tokens.color.light.ink, 0.85);

  return (
    // `overflow: hidden` is load-bearing, not tidiness. The ridges below are
    // deliberately wider than the screen and start left of it -- that is how
    // three arcs read as a range instead of three domes centred in the
    // viewport. A react-native `View` does not clip its children on web, so
    // those overhangs became document width: 445px inside a 390px viewport,
    // and the opening screen -- the first thing anyone touches -- could be
    // swiped 55px sideways into a white band with the sign-in buttons cut off
    // the left edge. Clipping here keeps the shape and drops the overhang.
    // Stated rather than left to the platform default, because that default is
    // exactly what differs between web, iOS and Android.
    <View
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, overflow: "hidden" }}
      pointerEvents="none"
    >
      {/* String lights, strung across the sky above the horizon. */}
      <View
        style={{
          position: "absolute",
          top: "15%",
          left: 0,
          right: 0,
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "flex-start",
          paddingHorizontal: space.sm,
        }}
      >
        {SAG.map((drop, i) => (
          <View key={i} style={{ alignItems: "center", marginTop: drop }}>
            <View style={{ width: 1, height: 10, backgroundColor: ON_SUNSET, opacity: 0.3 }} />
            <View
              style={{
                width: 7,
                height: 7,
                borderRadius: 999,
                backgroundColor: mixHex(brand.glow, tokens.color.light.card, 0.6),
              }}
            />
          </View>
        ))}
      </View>

      {/* Everything is anchored to the bottom of the screen, in that order, so
          the stack reads back-to-front: sun, far ridge, middle ridge, near
          ridge, then the group standing on it. Two things the first attempt
          got wrong and this fixes -- the group was drawn before the near ridge
          and so was painted out entirely, and the near ridge stopped short of
          the screen bottom, leaving a bright strip of the ramp's ember end
          showing underneath the hills like a seam. */}
      <View
        style={{
          position: "absolute",
          bottom: "42%",
          alignSelf: "center",
          width: 130,
          height: 130,
          borderRadius: 999,
          backgroundColor: mixHex(brand.glow, tokens.color.light.card, 0.45),
        }}
      />

      <Ridge color={xa} bottom={"40%"} height={95} width={"128%"} left={"-14%"} radius={[250, 300]} />
      <Ridge color={giua} bottom={"38%"} height={88} width={"118%"} left={"-9%"} radius={[300, 240]} />
      {/* Height reaches past the bottom of the screen on purpose: this is the
          ground the viewer is standing on, not a band floating above the edge. */}
      <Ridge color={gan} bottom={0} height={"36%"} width={"116%"} left={"-8%"} radius={[260, 320]} />

      <View
        style={{
          position: "absolute",
          bottom: "35%",
          left: 0,
          right: 0,
          flexDirection: "row",
          justifyContent: "center",
          alignItems: "flex-end",
          gap: space.xs,
        }}
      >
        {NHOM.map((p, i) => (
          <Nguoi key={i} scale={p} color={gan} />
        ))}
      </View>
    </View>
  );
}

/** Vertical offsets that make a row of dots read as a hanging wire. */
const SAG = [0, 10, 18, 23, 25, 23, 18, 10, 0];

/** Relative heights, so the group looks like people rather than a fence. */
const NHOM = [0.86, 1, 0.92, 1.04, 0.88, 0.96];

/**
 * One hill of the skyline.
 *
 * `DimensionValue` rather than `number | string`: it is the type React Native
 * already uses for these style fields, so percentages typecheck instead of
 * being cast past the compiler. The casts that used to sit here were not
 * cosmetic -- they were what let `height` stay `number` while a call site
 * passed `"36%"`, which is exactly the mismatch this signature now states.
 *
 * `radius` is a pair, [left, right]. Each ridge gets its own asymmetric
 * curve so three hills read as a range rather than as three copies of one
 * arc; a single hardcoded pair made the far and near ridges identical in
 * silhouette and only their colour told them apart.
 */
function Ridge({ color, bottom, height, width, left, radius }: {
  color: string;
  bottom: DimensionValue;
  height: DimensionValue;
  width: DimensionValue;
  left: DimensionValue;
  radius: [number, number];
}) {
  return (
    <View
      style={{
        position: "absolute",
        bottom,
        left,
        width,
        height,
        backgroundColor: color,
        borderTopLeftRadius: radius[0],
        borderTopRightRadius: radius[1],
      }}
    />
  );
}

function Nguoi({ scale, color }: { scale: number; color: string }) {
  return (
    <View style={{ alignItems: "center" }}>
      <View
        style={{
          width: 13 * scale,
          height: 13 * scale,
          borderRadius: 999,
          backgroundColor: color,
          marginBottom: 2,
        }}
      />
      <View
        style={{
          width: 21 * scale,
          height: 40 * scale,
          borderTopLeftRadius: 11 * scale,
          borderTopRightRadius: 11 * scale,
          backgroundColor: color,
        }}
      />
    </View>
  );
}

/** A sign-in button. Both provider buttons carry their own ground, so neither
 *  depends on the scrim underneath them to be readable. */
function NutHang({ label, monogram, background, ink, onPress }: {
  label: string;
  monogram: string;
  background: string;
  ink: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: space.sm,
        minHeight: 52,
        borderRadius: radius.pill,
        backgroundColor: background,
        opacity: pressed ? 0.88 : 1,
      })}
    >
      {monogram ? (
        <Text style={{ ...type.body, fontWeight: "700", color: ink }}>{monogram}</Text>
      ) : (
        // Apple's mark, near enough at 16pt: a round body with a leaf.
        <View style={{ alignItems: "center", justifyContent: "center", width: 16, height: 18 }}>
          <View style={{ width: 13, height: 13, borderRadius: 999, backgroundColor: ink, marginTop: 3 }} />
          <View
            style={{
              position: "absolute",
              top: 0,
              right: 2,
              width: 5,
              height: 6,
              borderTopRightRadius: 5,
              borderBottomLeftRadius: 5,
              backgroundColor: ink,
            }}
          />
        </View>
      )}
      <Text style={{ ...type.body, fontWeight: "600", color: ink }}>{label}</Text>
    </Pressable>
  );
}

/** The picker that stands in for a consent screen. */
function ChonNguoi({ onPick, onClose }: {
  onPick: (p: DemoPerson) => void;
  onClose: () => void;
}) {
  const c = usePalette();
  return (
    // Declared a modal, now that the screen behind it is genuinely inert. The
    // two go together: `aria-hidden` on the background says what is *not* in
    // the tree, `role="dialog"` + `aria-modal` says what is.
    <View
      role="dialog"
      aria-modal
      accessibilityLabel="Chọn người để vào app"
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, justifyContent: "flex-end" }}
    >
      <Pressable
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Đóng danh sách chọn người"
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(15,8,20,0.55)" }}
      />
      <View
        style={{
          backgroundColor: c.card,
          borderTopLeftRadius: radius.base,
          borderTopRightRadius: radius.base,
          paddingTop: space.md,
          paddingBottom: space.lg,
          paddingHorizontal: space.md,
          gap: space.sm,
          maxHeight: "76%",
        }}
      >
        <Text style={{ ...type.title, color: c.ink }}>Vào app với tư cách ai?</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Đây là chỗ đứng của màn đăng nhập Google/Apple. Bản demo chưa nối OAuth,
          nên chọn thẳng một người trong {DEMO_GROUP_NAME}.
        </Text>

        <ScrollView contentContainerStyle={{ gap: space.xs }} showsVerticalScrollIndicator={false}>
          {DEMO_PEOPLE.map((p) => (
            <Pressable
              key={p.id}
              onPress={() => onPick(p)}
              accessibilityRole="button"
              accessibilityLabel={`Vào app với tư cách ${p.name}`}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                gap: space.md,
                minHeight: 56,
                paddingHorizontal: space.sm,
                borderRadius: radius.control,
                backgroundColor: pressed ? c.accentSoft : "transparent",
              })}
            >
              <View
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 999,
                  backgroundColor: c.accentSoft,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Text style={{ ...type.body, fontWeight: "700", color: c.accent }}>{p.initials}</Text>
              </View>
              <Text style={{ ...type.body, color: c.ink }}>{p.name}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>
    </View>
  );
}
