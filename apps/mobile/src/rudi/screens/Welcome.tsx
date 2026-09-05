import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useRef, useState } from "react";
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
import { displayFace, lopPhu, mucTrenAnh, typography, useRudiTheme } from "../theme";
import { DemoBadge } from "../ui";
import { CoverButton } from "../ui/CoverButton";
import { StampButton } from "../ui/StampButton";
import { useAdaptiveLayout } from "../ui/useAdaptiveLayout";
import { useMotion } from "../ui/useMotion";
import { Washi } from "../ui/Washi";
import { Wordmark } from "../ui/Wordmark";
import { WordmarkEmbossed } from "../ui/WordmarkEmbossed";

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

export function WelcomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const layout = useAdaptiveLayout();
  const motion = useMotion();
  const { colors, brand } = useRudiTheme();
  const pager = useRef<ScrollView>(null);
  const [page, setPage] = useState(0);
  const [pageWidth, setPageWidth] = useState(0);
  const lift = useSharedValue(0);

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
      <Animated.View style={[styles.cover, { paddingTop: insets.top + 12, paddingBottom: Math.max(insets.bottom, 16) + 6 }, coverStyle]}>
        <View style={styles.top}>
          <View style={styles.logoRow} accessibilityLabel="Rủ Đi">
            <LinearGradient
              colors={[brand.logoGradient.from, brand.logoGradient.to]}
              end={{ x: 1, y: 1 }}
              start={{ x: 0, y: 0 }}
              style={styles.tile}
            >
              <Text style={styles.tileType}>Rủ{"\n"}Đi</Text>
            </LinearGradient>
            <Wordmark height={18} color={colors.coverInk} />
          </View>
          {CUA_FIXTURE_DEV ? <DemoBadge label="Bản trải nghiệm" /> : null}
        </View>

        <View style={[styles.mark, short && styles.markShort]}>
          <WordmarkEmbossed height={markHeight} color={colors.coverInk} />
          <Washi tone="accent" tilt={-2} height={38} style={styles.tape}>
            <Text style={[styles.tagline, { color: colors.ink }]}>AI đi chơi, chia bill thông minh</Text>
          </Washi>
        </View>

        <View style={styles.bottom}>
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
            <StampButton label="Rủ Đi thôi!" onPress={openCover} testID="welcome-cta" />
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
  cover: { flex: 1, justifyContent: "space-between", paddingHorizontal: 20 },
  top: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  logoRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  tile: { width: 34, height: 34, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  tileType: { color: mucTrenAnh, fontFamily: displayFace.extraBold, fontSize: 10, lineHeight: 10, letterSpacing: -0.4, textAlign: "center", transform: [{ skewX: "-9deg" }] },
  mark: { alignItems: "center", gap: 22, marginTop: -10 },
  markShort: { gap: 12 },
  tape: { alignSelf: "center", paddingHorizontal: 18 },
  tagline: { fontFamily: displayFace.bold, fontSize: 17, lineHeight: 21, letterSpacing: -0.1 },
  bottom: { gap: 12, marginHorizontal: -20 },
  pageTitle: { fontFamily: displayFace.extraBold, fontSize: 28, lineHeight: 33, letterSpacing: -0.7, minHeight: 68 },
  pageBody: { marginTop: 6, minHeight: 60, maxWidth: 520 },
  dots: { flexDirection: "row", justifyContent: "center", gap: 7 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  dotActive: { width: 20 },
  actions: { paddingHorizontal: 20, gap: 10 },
  dauVanCay: { textAlign: "center", paddingTop: 4 },
});
