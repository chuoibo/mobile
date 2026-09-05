import { useFocusEffect, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useCallback, useRef, useState } from "react";
import {
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { CUA_FIXTURE_DEV } from "../cua-fixture";
import { DAU_VAN_CAY } from "../dau-van-cay";
import { displayFace, lopPhu, mauSang, typography, useRudiTheme } from "../theme";
import { DemoBadge } from "../ui";
import { CoverButton } from "../ui/CoverButton";
import { Grain } from "../ui/Grain";
import { RouteLine } from "../ui/RouteLine";
import { StampButton } from "../ui/StampButton";
import { useAdaptiveLayout } from "../ui/useAdaptiveLayout";
import { useMotion } from "../ui/useMotion";
import { Washi } from "../ui/Washi";
import { Wordmark } from "../ui/Wordmark";

/**
 * The closed cover of the group's travel journal (FIRST VIEWPORT of the v2
 * contract): indigo cloth full-bleed, the wordmark pressed large into the
 * upper third, one coral washi strip carrying the positioning line, and the
 * invitation as a coral seal at the foot. Pressing the seal lifts the cover
 * (`shared`, 300ms) and opens onto the bright Login page. No photograph: the
 * cover is the brand, and a stock photo of strangers was never ours to show.
 */

export const WELCOME_PAGES = [
  {
    title: "Hẹn hội bạn. Rủ Đi lo phần còn lại.",
    body: "Khám phá, lên plan, chia bill và giữ trọn mọi kỷ niệm trong một nơi.",
  },
  {
    title: "Tìm nơi hợp cả hội",
    body: "Gợi ý theo gu nhóm, khoảng cách và ngân sách. Bạn luôn được sửa trước khi chốt.",
  },
  {
    title: "Chia bill từng đồng",
    body: "Gán món, xem ai nợ ai. Số trên quyết toán và tài chính phải cùng một nguồn, không bịa sổ cái.",
  },
  {
    title: "Giữ kỷ niệm của hội",
    body: "Tường riêng, album chuyến đi, check-in khi tới nơi. Đây là không gian của nhóm bạn, không phải mạng xã hội mở.",
  },
];

/** One glyph per page above: friends, finding a place, the bill, the memories. */
const CHANG_GLYPHS = ["people", "compass", "receipt", "images"] as const;

export function WelcomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const layout = useAdaptiveLayout();
  const motion = useMotion();
  const { brand, colors } = useRudiTheme();
  const pager = useRef<ScrollView>(null);
  const [page, setPage] = useState(0);
  const [pageWidth, setPageWidth] = useState(0);
  const [routeBox, setRouteBox] = useState({ w: 0, h: 0 });
  const lift = useSharedValue(0);
  // One press opens one Login: a second tap inside the 300ms lift used to queue a
  // second push. Reset when the cover regains focus (back from Login), together
  // with the lift, so the cover is whole again instead of staying faded.
  const dangMo = useRef(false);
  useFocusEffect(
    useCallback(() => {
      dangMo.current = false;
      lift.value = 0;
    }, [lift]),
  );

  const onScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(event.nativeEvent.contentOffset.x / Math.max(pageWidth, 1));
    if (next !== page && next >= 0 && next < WELCOME_PAGES.length) setPage(next);
  };

  const learnMore = () => {
    const next = page < WELCOME_PAGES.length - 1 ? page + 1 : 0;
    pager.current?.scrollTo({ x: next * pageWidth, animated: !motion.reduced });
    if (motion.reduced) setPage(next);
  };

  const openCover = () => {
    if (dangMo.current) return;
    dangMo.current = true;
    // The cover lifts before the page shows; under Reduce Motion the route
    // changes at once. `router.push` waits on the animation, never on data.
    const ms = motion.ms("shared");
    lift.value = withTiming(1, motion.timing("shared", "accelerate"));
    setTimeout(() => router.push("/login"), ms);
  };

  const coverStyle = useAnimatedStyle(() => ({
    opacity: 1 - lift.value * 0.35,
    transform: [{ translateY: -lift.value * 48 }],
  }));

  const short = layout.heightClass === "short";
  const markHeight = short ? 72 : layout.sizeClass === "compact" ? 118 : 150;

  return (
    <View style={[styles.root, { backgroundColor: colors.cover }]} testID="welcome-screen">
      <StatusBar style="light" />
      <Grain material="vaiBia" opacity={0.3} />
      <Animated.View style={[styles.cover, { paddingTop: insets.top + 12, paddingBottom: Math.max(insets.bottom, 16) + 6 }, coverStyle]}>
        <View style={styles.top}>
          {CUA_FIXTURE_DEV ? <DemoBadge label="Bản trải nghiệm" /> : <View />}
        </View>

        <View style={[styles.mark, short && styles.markShort]}>
          <Wordmark height={markHeight} color={colors.coverInk} />
          <Washi tone="accent" tilt={-2} height={40} style={styles.tape}>
            {/* Static dark ink: the tape is coral in both schemes, and the scheme's light ink on coral would read 2.4:1. */}
            <Text style={[styles.tagline, { color: mauSang.ink }]}>AI đi chơi, chia bill thông minh</Text>
          </Washi>
        </View>

        <View
          onLayout={(e) => setRouteBox({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}
          style={styles.route}
          pointerEvents="none"
        >
          {routeBox.h > 40 && !short ? (
            <RouteLine
              width={routeBox.w}
              height={routeBox.h}
              color={colors.coverInk}
              opacity={0.82}
              stops={WELCOME_PAGES.length}
              activeStop={page}
              glyphs={CHANG_GLYPHS}
              activeColor={brand.coral}
              activeInk={mauSang.ink}
              accessibilityLabel={`Chặng ${page + 1} trên ${WELCOME_PAGES.length}`}
            />
          ) : null}
        </View>

        <View style={[styles.bottom, layout.sizeClass !== "compact" && styles.bottomWide]}>
          <ScrollView
            ref={pager}
            horizontal
            onLayout={(e) => setPageWidth(e.nativeEvent.layout.width)}
            onMomentumScrollEnd={onScroll}
            pagingEnabled
            showsHorizontalScrollIndicator={false}
          >
            {WELCOME_PAGES.map((item) => (
              <View key={item.title} style={{ width: pageWidth || undefined, paddingHorizontal: 20 }}>
                <Text style={[styles.pageTitle, { color: colors.coverInk }]}>{item.title}</Text>
                <Text style={[typography.body, styles.pageBody, { color: colors.coverInkSoft }]}>{item.body}</Text>
              </View>
            ))}
          </ScrollView>
          <View style={styles.dots} accessibilityLabel={`Trang ${page + 1} trên ${WELCOME_PAGES.length}`}>
            {WELCOME_PAGES.map((item, index) => (
              <View
                key={item.title}
                style={[styles.dot, { backgroundColor: index === page ? colors.coverInk : lopPhu.trang(0.35) }, index === page && styles.dotActive]}
              />
            ))}
          </View>
          <View style={styles.actions}>
            <StampButton label="Rủ Đi thôi!" onPress={openCover} testID="welcome-cta" tilt={-1.5} />
            <CoverButton
              icon="chevron-forward"
              label={page < WELCOME_PAGES.length - 1 ? "Tìm hiểu thêm" : "Xem lại từ đầu"}
              onPress={learnMore}
            />
            {DAU_VAN_CAY ? (
              // Native gate anchor (NEO 2b): the harness inlines a per-run value and
              // asserts it on screen. Absent outside the harness, so nothing ships.
              <Text accessibilityLabel="dau-van-cay" style={[typography.caption, styles.dauVanCay, { color: colors.coverInkSoft }]}>
                {DAU_VAN_CAY}
              </Text>
            ) : null}
          </View>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  cover: { flex: 1, paddingHorizontal: 20 },
  top: { flexDirection: "row", alignItems: "center", justifyContent: "flex-end", minHeight: 28 },
  mark: { alignItems: "center", gap: 22, marginTop: 36 },
  // Never wider than a page: on a tablet the S-curve across 1600px read as a wire.
  route: { flex: 1, marginVertical: 8, marginHorizontal: 12, alignSelf: "center", width: "100%", maxWidth: 560 },
  markShort: { gap: 12 },
  tape: { alignSelf: "center", paddingHorizontal: 18 },
  tagline: { fontFamily: displayFace.bold, fontSize: 17, lineHeight: 21, letterSpacing: -0.1 },
  bottom: { gap: 12, marginHorizontal: -20 },
  bottomWide: { alignSelf: "center", width: "100%", maxWidth: 640, marginHorizontal: 0 },
  pageTitle: { fontFamily: displayFace.extraBold, fontSize: 28, lineHeight: 33, letterSpacing: -0.7, minHeight: 68 },
  pageBody: { marginTop: 6, minHeight: 60, maxWidth: 520 },
  dots: { flexDirection: "row", justifyContent: "center", gap: 7 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  dotActive: { width: 20 },
  actions: { paddingHorizontal: 20, gap: 10 },
  dauVanCay: { textAlign: "center", paddingTop: 4 },
});
