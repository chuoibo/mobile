import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";

import { demoAssets } from "../fixtures";
import { manDau } from "../duong-vao";
import {
  LOI_SO_THICH,
  cauLuuTru,
  docSoThich,
  docTuVung,
  luuSoThich,
  maLoi,
} from "../nguoi/so-thich-song";
import { NGAN_SACH, SO_THICH, doiMuc } from "../../screens/vao-cua/so-thich";
import { noiLuu } from "../luu-tru";
import { useRudiSession } from "../session";
import { lopPhu, mauLogo, mucTrenAnh, typography, useRudiTheme } from "../theme";
import { CUA_FIXTURE_DEV } from "../cua-fixture";
import { DAU_VAN_CAY } from "../dau-van-cay";
import {
  Card,
  Chip,
  DemoBadge,
  Heading,
  Inline,
  ProgressBar,
  RudiButton,
  RudiScreen,
  Spacer,
  TopBar,
} from "../ui";

const WELCOME_PAGES = [
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
] as const;

export function WelcomeScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const pager = useRef<ScrollView>(null);
  const [page, setPage] = useState(0);
  const copy = WELCOME_PAGES[page];

  const onScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(event.nativeEvent.contentOffset.x / Math.max(width, 1));
    if (next !== page && next >= 0 && next < WELCOME_PAGES.length) setPage(next);
  };

  const learnMore = () => {
    if (page < WELCOME_PAGES.length - 1) {
      pager.current?.scrollTo({ x: (page + 1) * width, animated: true });
      return;
    }
    pager.current?.scrollTo({ x: 0, animated: true });
  };

  return (
    <RudiScreen bottomInset={0} contentStyle={styles.welcome} padded={false} scroll={false} testID="welcome-screen">
      <Image contentFit="cover" source={demoAssets.friends} style={StyleSheet.absoluteFill} />
      <LinearGradient
        colors={[lopPhu.toi(0.12), lopPhu.toi(0.23), lopPhu.toi(0.9)]}
        locations={[0, 0.48, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View style={styles.welcomeContent}>
        <View style={styles.welcomeTop}>
          <View style={styles.welcomeLogo}>
            <View style={styles.welcomeLogoMark}>
              <Text style={styles.welcomeLogoMarkType}>Rủ{"\n"}Đi</Text>
            </View>
            <View style={styles.welcomeWordmark}>
              <Text style={styles.welcomeLogoType}>Rủ</Text>
              <Text style={styles.welcomeLogoType}>Đi</Text>
            </View>
          </View>
          {/* Only a dev build with the fixture door is an «experience build»;
              a shipped build must not call itself one. */}
          {CUA_FIXTURE_DEV ? <DemoBadge label="Bản trải nghiệm" /> : null}
        </View>
        <View style={styles.welcomeCenter}>
          <Text style={styles.welcomeBrand}>Rủ{"\n"}Đi</Text>
          <Text style={styles.welcomeTagline}>AI đi chơi,{"\n"}chia bill thông minh</Text>
          <View style={styles.taglineStroke} />
        </View>
        <View style={styles.welcomeBottom}>
          <ScrollView
            ref={pager}
            horizontal
            onMomentumScrollEnd={onScroll}
            pagingEnabled
            showsHorizontalScrollIndicator={false}
          >
            {WELCOME_PAGES.map((item) => (
              <View key={item.title} style={{ width, paddingHorizontal: 18 }}>
                <Text style={styles.heroTitle}>{item.title}</Text>
                <Text style={styles.heroSubtitle}>{item.body}</Text>
              </View>
            ))}
          </ScrollView>
          <View style={styles.welcomeActions}>
            <RudiButton icon="arrow-forward" label="Rủ Đi thôi!" onPress={() => router.push("/login")} />
            <Pressable
              accessibilityRole="button"
              onPress={learnMore}
              style={({ pressed }) => [styles.previewLink, pressed && styles.pressed]}
            >
              <Text style={styles.previewText}>{page < WELCOME_PAGES.length - 1 ? "Tìm hiểu thêm" : "Xem lại từ đầu"}</Text>
              <Ionicons color={mucTrenAnh} name="chevron-forward" size={18} />
            </Pressable>
            <View style={styles.pager}>
              {WELCOME_PAGES.map((item, index) => (
                <View key={item.title} style={index === page ? styles.pagerActive : styles.pagerDot} />
              ))}
            </View>
            {DAU_VAN_CAY ? (
              // Native gate anchor (NEO 2b): the harness inlines a per-run value and
              // asserts it on screen. Absent outside the harness, so nothing ships.
              <Text accessibilityLabel="dau-van-cay" style={styles.dauVanCay}>
                {DAU_VAN_CAY}
              </Text>
            ) : null}
          </View>
        </View>
      </View>
    </RudiScreen>
  );
}


/** One icon per taste word the SERVER knows. The words themselves come from
 *  `so-thich.ts`, which `tests/test_interest_vocabulary_matches_client.py`
 *  keeps equal to the server's list; the icon is decoration and lives here. */
const BIEU_TUONG: Record<string, keyof typeof Ionicons.glyphMap> = {
  "an-uong": "restaurant-outline",
  cafe: "cafe-outline",
  nightlife: "wine-outline",
  "mon-local": "fast-food-outline",
  outdoor: "trail-sign-outline",
  shopping: "bag-handle-outline",
  karaoke: "mic-outline",
  game: "game-controller-outline",
};

export function PersonalizationScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const personId = session.phien?.person_id ?? null;

  const [muc, setMuc] = useState<string[]>([]);
  // Which words the server will accept. Null until it answers, and null forever
  // if it cannot be reached -- the screen renders the local list either way.
  const [tuVung, setTuVung] = useState<string[] | null>(null);
  const [khoang, setKhoang] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  // What this person already told the server, so re-opening the step shows
  // their answers rather than an empty screen that looks like a reset.
  useEffect(() => {
    let con = true;
    void docTuVung().then((ds) => con && setTuVung(ds));
    return () => {
      con = false;
    };
  }, []);

  const danhSach = tuVung === null ? SO_THICH : SO_THICH.filter((m) => tuVung.includes(m.id));

  useEffect(() => {
    if (personId === null) return;
    let con = true;
    void docSoThich(personId)
      .then((da) => {
        if (!con) return;
        setMuc(da.muc);
        setKhoang(da.khoang);
      })
      .catch(() => undefined);
    return () => {
      con = false;
    };
  }, [personId]);

  /** Tapping the chosen band again clears it: «bỏ qua» has to stay reachable
   *  after somebody has answered, or the first answer is permanent. */
  const doiKhoang = (id: string) => {
    void Haptics.selectionAsync();
    if (khoang === id) {
      setKhoang(null);
      return;
    }
    setKhoang(id);
  };

  const doiMucChon = (id: string) => {
    void Haptics.selectionAsync();
    setMuc(doiMuc(muc, id));
  };

  const xong = async () => {
    setLoi(null);
    if (personId === null) {
      // The dev fixture door reaches this screen with no session. Nothing to
      // attach the answers to, and writing them to a file a later sign-in
      // adopts would make one phone's guesses look like somebody's taste.
      router.replace("/explore");
      return;
    }
    setDangLuu(true);
    try {
      await luuSoThich(personId, { muc, khoang });
      router.replace(manDau(session.phien));
    } catch (error) {
      const ma = maLoi(error);
      setLoi((ma !== null ? LOI_SO_THICH[ma] : null) ?? "Chưa lưu được. Thử lại giúp mình nhé.");
    } finally {
      setDangLuu(false);
    }
  };

  return (
    <RudiScreen contentStyle={styles.personalization} testID="personalization-screen">
      <TopBar
        right={
          <Pressable accessibilityRole="button" onPress={() => router.replace(manDau(session.phien))}>
            {/* Not a gate. The step is editable forever from Cá nhân, and a
                required question on the first screen of a new account is a
                toll booth, not a personalization. */}
            <Text style={[typography.label, { color: colors.inkFaint }]}>Bỏ qua</Text>
          </Pressable>
        }
      />
      <ProgressBar value={100} />
      <Heading
        title="Cho Rủ Đi biết gu của bạn"
        subtitle="Chọn ít nhất 3 sở thích. Rủ Đi xếp gợi ý theo đúng những gì bạn chọn."
      />
      <Card style={styles.preferenceCard}>
        <Text style={[typography.title, { color: colors.ink }]}>Bạn thường mê gì?</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Chọn mọi thứ khiến bạn muốn xách balo lên.</Text>
        <View style={styles.interestGrid}>
          {danhSach.map((m) => {
            const selected = muc.includes(m.id);
            return (
              <Pressable
                key={m.id}
                accessibilityRole="checkbox"
                aria-checked={selected}
                onPress={() => doiMucChon(m.id)}
                style={({ pressed }) => [
                  styles.interest,
                  {
                    backgroundColor: selected ? colors.accentSoft : colors.card,
                    borderColor: selected ? colors.accent : colors.line,
                  },
                  pressed && styles.pressed,
                ]}
              >
                <View style={[styles.interestIcon, { backgroundColor: selected ? colors.accent : colors.ground }]}>
                  <Ionicons color={selected ? colors.accentInk : colors.inkSoft} name={BIEU_TUONG[m.id] ?? "sparkles-outline"} size={23} />
                </View>
                <Text style={[typography.label, { color: selected ? colors.accent : colors.ink }]}>{m.nhan}</Text>
                {selected ? <Ionicons color={colors.accent} name="checkmark-circle" size={18} /> : null}
              </Pressable>
            );
          })}
        </View>
      </Card>
      <View style={styles.vibeBlock}>
        <Text style={[typography.title, { color: colors.ink }]}>Mỗi lần đi chơi bạn tiêu khoảng</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Bỏ qua cũng được. Rủ Đi để trống chỗ này chứ không đoán thay bạn.
        </Text>
        <Inline gap={8} wrap>
          {NGAN_SACH.map((k) => (
            <Chip
              key={k.id}
              label={k.nhan}
              onPress={() => doiKhoang(k.id)}
              selected={khoang === k.id}
            />
          ))}
        </Inline>
      </View>
      <Spacer size={4} />
      {loi !== null ? (
        <Text style={[typography.body, { color: colors.warn }]}>{loi}</Text>
      ) : null}
      <RudiButton
        disabled={muc.length < 3 || dangLuu}
        icon="sparkles"
        label={dangLuu ? "Đang lưu…" : "Tạo không gian của tôi"}
        onPress={() => void xong()}
      />
      <Text style={[typography.caption, styles.privacyText, { color: colors.inkFaint }]}>
        {cauLuuTru(personId !== null)}
      </Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  welcome: { flex: 1, paddingTop: 0 },
  welcomeContent: { flex: 1, justifyContent: "space-between", paddingTop: 14, paddingBottom: 18 },
  welcomeTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 18 },
  welcomeLogo: { flexDirection: "row", alignItems: "center", gap: 8 },
  welcomeWordmark: { flexDirection: "row", alignItems: "center", gap: 4 },
  welcomeLogoMark: { width: 40, height: 40, borderRadius: 14, backgroundColor: lopPhu.trang(0.18), borderWidth: 1, borderColor: lopPhu.trang(0.34), alignItems: "center", justifyContent: "center" },
  welcomeLogoMarkType: { color: mucTrenAnh, fontSize: 12, lineHeight: 11, fontStyle: "italic", fontWeight: "900", letterSpacing: -0.7, textAlign: "center" },
  welcomeLogoType: { color: mucTrenAnh, fontSize: 25, lineHeight: 30, fontStyle: "italic", fontWeight: "900", letterSpacing: -1.2 },
  welcomeCenter: { alignItems: "center", marginTop: -15, paddingHorizontal: 18 },
  welcomeBrand: { color: mucTrenAnh, fontSize: 76, lineHeight: 64, fontStyle: "italic", fontWeight: "900", letterSpacing: -4, textAlign: "center", transform: [{ rotate: "-4deg" }] },
  welcomeTagline: { color: mucTrenAnh, fontSize: 20, lineHeight: 25, fontWeight: "800", textAlign: "center", marginTop: 17 },
  taglineStroke: { width: 120, height: 4, borderRadius: 9, backgroundColor: mauLogo.diem, marginTop: 11, transform: [{ rotate: "-4deg" }] },
  welcomeBottom: { gap: 10 },
  welcomeActions: { paddingHorizontal: 18, gap: 10 },
  heroTitle: { color: mucTrenAnh, fontSize: 28, lineHeight: 33, fontWeight: "900", letterSpacing: -0.8, minHeight: 70 },
  heroSubtitle: { color: lopPhu.trang(0.84), fontSize: 14, lineHeight: 20, fontWeight: "600", maxWidth: 520, marginBottom: 3, minHeight: 60 },
  previewLink: { minHeight: 50, borderWidth: 1, borderColor: lopPhu.trang(0.72), borderRadius: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  previewText: { color: mucTrenAnh, fontSize: 14, fontWeight: "800" },
  pager: { flexDirection: "row", justifyContent: "center", gap: 7, paddingTop: 4 },
  pagerDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: lopPhu.trang(0.48) },
  pagerActive: { width: 18, height: 7, borderRadius: 4, backgroundColor: mucTrenAnh },
  dauVanCay: { color: lopPhu.trang(0.55), fontSize: 12, textAlign: "center", paddingTop: 6 },
  pressed: { opacity: 0.7 },
  personalization: { maxWidth: 760 },
  privacyText: { textAlign: "center", paddingHorizontal: 18 },
  preferenceCard: { gap: 8 },
  interestGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 7 },
  interest: { minHeight: 62, minWidth: "47%", flexGrow: 1, flexBasis: 150, borderRadius: 16, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 9, padding: 10 },
  interestIcon: { width: 39, height: 39, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  vibeBlock: { gap: 11 },
});
