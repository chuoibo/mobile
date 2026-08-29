/** The three states a screen is in when it has nothing to show yet.
 *
 * Mockups draw the full case. Every screen also has an empty one, a waiting
 * one, and a broken one, and those are where an app stops looking finished --
 * they get written last, by whoever is closest to the deadline, one per screen,
 * each with its own wording and its own idea of what to do next. That is how
 * one product ends up apologising four different ways.
 *
 * So they are primitives here rather than a paragraph on each screen. The shape
 * is copied from `screens/kham-pha/KhamPha.tsx`, which had already worked it
 * out and is still the reference: say what happened, say what to do next, and
 * when there is an address involved, print it.
 *
 * Three rules these components exist to enforce, all three learned the hard way
 * in this repo:
 *
 *  1. **An error names the next move.** "Đã xảy ra lỗi" is not an error
 *     message, it is an apology. `CoLoi` takes `viecTiepTheo` and a retry
 *     handler, and neither is optional-by-accident: a dead end has to be
 *     written as one on purpose.
 *  2. **Waiting is announced, not just drawn.** A spinner is invisible to a
 *     screen reader. Every state here carries `accessibilityLiveRegion` and
 *     `role="status"` so the change is spoken -- react-native-web maps the
 *     first to `aria-live` and native reads the second.
 *  3. **No percentages.** Nothing here accepts one. The app does not know how
 *     far along a server is, and `tests/receipt.test.mjs` gates the source
 *     against printing a number no machine computed.
 *
 * Lead tone is inherited, never set: these render inside whatever screen owns
 * them, so they use `accent` for waiting, `warn` for broken, and `inkSoft` for
 * empty, which are the palette's stated meanings rather than a fourth voice.
 */
import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../theme";
import { Card } from "./Kit";

/** Spoken as well as drawn. See rule 2 in this file's header. */
const SONG: {
  accessibilityLiveRegion: "polite";
  role: "status";
} = { accessibilityLiveRegion: "polite", role: "status" };

/**
 * Something is happening and it is not finished.
 *
 * `phu` is for the line under the headline that says which part is running.
 * It changes while the wait continues, which is the difference between a
 * screen that is working and a screen that has frozen -- and on the bill path
 * that difference is several seconds long.
 */
export function DangTai({ noiDung, phu }: { noiDung: string; phu?: string }) {
  const c = usePalette();
  return (
    <Card>
      <View {...SONG} style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <ActivityIndicator color={c.accent} />
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={{ ...type.body, color: c.ink }}>{noiDung}</Text>
          {phu ? <Text style={{ ...type.label, color: c.inkSoft }}>{phu}</Text> : null}
        </View>
      </View>
    </Card>
  );
}

/**
 * There is nothing here, and that is the correct answer rather than a failure.
 *
 * Separate from `CoLoi` on purpose. An empty list and a broken list send a
 * person to two completely different places, and collapsing them into one
 * "không có dữ liệu" is how somebody spends an afternoon restarting a server
 * that was fine the whole time.
 */
export function TrongRong({
  tieuDe,
  than,
  hanhDong,
}: {
  tieuDe: string;
  than: string;
  hanhDong?: { nhan: string; onPress: () => void };
}) {
  const c = usePalette();
  return (
    <Card>
      <View {...SONG} style={{ gap: space.xs }}>
        <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
        <Text style={{ ...type.body, color: c.inkSoft }}>{than}</Text>
      </View>
      {hanhDong ? <NutNhe nhan={hanhDong.nhan} onPress={hanhDong.onPress} mau={c.accent} /> : null}
    </Card>
  );
}

/**
 * It broke, and here is what to do about it.
 *
 * `than` is the sentence a person reads. It must already be Vietnamese written
 * for a person: `thongDiepNguoiDoc` in `api.ts` is what guarantees that for
 * anything coming off the wire, and `tests/trang-thai.test.mjs` gates it. This
 * component deliberately does not sanitise, because a component that quietly
 * cleaned up its input would hide the leak instead of the gate catching it.
 *
 * `diaChi` prints the server the app is talking to. Copied from Khám phá,
 * where it stopped an afternoon of debugging the wrong machine.
 */
export function CoLoi({
  tieuDe,
  than,
  viecTiepTheo,
  diaChi,
  onThuLai,
  nhanThuLai = "Thử lại",
}: {
  tieuDe: string;
  than: string;
  /** What the person should do now. Required: a dead end has to be deliberate. */
  viecTiepTheo: string;
  diaChi?: string;
  onThuLai?: () => void;
  nhanThuLai?: string;
}) {
  const c = usePalette();
  return (
    <Card style={{ borderColor: c.warn }}>
      <View {...SONG} style={{ gap: space.xs }}>
        <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
        <Text style={{ ...type.body, color: c.inkSoft }}>{than}</Text>
        <Text style={{ ...type.label, color: c.ink }}>{viecTiepTheo}</Text>
        {diaChi ? (
          <Text style={{ ...type.micro, color: c.inkFaint }}>Đã thử: {diaChi}</Text>
        ) : null}
      </View>
      {onThuLai ? <NutNhe nhan={nhanThuLai} onPress={onThuLai} mau={c.warn} /> : null}
    </Card>
  );
}

/**
 * The one control these three share.
 *
 * Outline rather than filled: these cards appear *inside* a screen that already
 * has a primary action, and a second filled button would compete with it. The
 * border carries the whole affordance, so it uses a measured token rather than
 * the hairline `line`, which WCAG 1.4.11 would not accept on a control.
 */
function NutNhe({ nhan, onPress, mau }: { nhan: string; onPress: () => void; mau: string }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={nhan}
      style={({ pressed }) => ({
        alignSelf: "flex-start",
        minHeight: 44,
        justifyContent: "center",
        paddingHorizontal: space.md,
        borderWidth: 1,
        borderColor: mau,
        borderRadius: radius.control,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <Text style={{ ...type.body, fontWeight: "600", color: mau }}>{nhan}</Text>
    </Pressable>
  );
}
