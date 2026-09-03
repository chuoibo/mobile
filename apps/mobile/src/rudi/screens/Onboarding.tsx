import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useRef, useState } from "react";
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

import { chuanHoaSo } from "../../screens/vao-cua/danh-tinh";
import { demoAssets } from "../fixtures";
import { noiLuu } from "../luu-tru";
import { useRudiSession } from "../session";
import { typography, useRudiTheme } from "../theme";
import { DAU_VAN_CAY } from "../dau-van-cay";
import {
  Card,
  Chip,
  DemoBadge,
  Field,
  Heading,
  Inline,
  Logo,
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
        colors={["rgba(38,14,5,0.12)", "rgba(24,8,3,0.23)", "rgba(20,7,3,0.9)"]}
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
          <DemoBadge label="Bản trải nghiệm" />
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
              <Ionicons color="#FFFFFF" name="chevron-forward" size={18} />
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

export function LoginScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerNotice, setProviderNotice] = useState<string | null>(null);

  const normalized = chuanHoaSo(phone);

  const sendOtp = () => {
    setProviderNotice(null);
    if (!normalized) {
      setError("Nhập số điện thoại di động Việt Nam hợp lệ.");
      return;
    }
    setOtpSent(true);
    setError("Chưa có nhà cung cấp OTP nên không gửi được mã. Dùng bản trải nghiệm bên dưới, hoặc đợi Pha D.");
  };

  const verifyOtp = () => {
    setProviderNotice(null);
    if (!otp.trim()) {
      setError("Nhập mã OTP khi nhà cung cấp đã kết nối.");
      return;
    }
    setError("OTP nhà cung cấp chưa kết nối. Không thể xác thực số thật trên bản này.");
  };

  // No state to set: the screens are on the experience build whenever there is
  // no session token, and that is the only thing that decides it now.
  const enterDemo = () => router.push("/personalization");

  return (
    <RudiScreen contentStyle={styles.formScreen} testID="login-screen">
      <TopBar right={<DemoBadge />} />
      <View style={styles.loginBrand}>
        <Logo />
        <Heading
          align="center"
          title="Chào bạn"
          subtitle="Đăng nhập bằng Google, Apple hoặc số điện thoại. Tài khoản nhà cung cấp chưa gắn, đừng nhầm với bản trải nghiệm."
        />
      </View>
      <Card style={styles.loginCard}>
        <RudiButton
          icon="logo-google"
          label="Tiếp tục với Google"
          onPress={() => {
            setError(null);
            setProviderNotice("Google chưa kết nối. Cần tài khoản OAuth (Pha D).");
          }}
          variant="outline"
        />
        <RudiButton
          icon="logo-apple"
          label="Tiếp tục với Apple"
          onPress={() => {
            setError(null);
            setProviderNotice("Apple chưa kết nối. Trên iOS sẽ hiện sau khi có chứng chỉ.");
          }}
          variant="outline"
        />
        <View style={styles.orRow}>
          <View style={[styles.orLine, { backgroundColor: colors.line }]} />
          <Text style={[typography.caption, { color: colors.inkFaint }]}>hoặc số điện thoại</Text>
          <View style={[styles.orLine, { backgroundColor: colors.line }]} />
        </View>
        <Field
          autoCapitalize="none"
          icon="call-outline"
          keyboardType="phone-pad"
          label="Số điện thoại"
          onChangeText={setPhone}
          placeholder="Nhập số di động"
          value={phone}
        />
        {otpSent ? (
          <Field
            icon="keypad-outline"
            keyboardType="number-pad"
            label="Mã OTP"
            onChangeText={setOtp}
            placeholder="6 số từ nhà cung cấp"
            value={otp}
          />
        ) : null}
        <RudiButton
          label={otpSent ? "Xác nhận OTP" : "Gửi OTP"}
          onPress={() => (otpSent ? verifyOtp() : sendOtp())}
        />
        {error ? <Text style={[typography.caption, styles.authError, { color: colors.warn }]}>{error}</Text> : null}
        {providerNotice ? (
          <Text style={[typography.caption, { color: colors.inkSoft }]}>{providerNotice}</Text>
        ) : null}
        <Pressable accessibilityRole="button" onPress={() => setError("Khôi phục mật khẩu cần nhà cung cấp OTP, hiện chưa kết nối.")}>
          <Text style={[typography.caption, { color: colors.accent }]}>Quên mật khẩu?</Text>
        </Pressable>
      </Card>
      <RudiButton
        icon="mail-open-outline"
        label="Tôi có lời mời"
        onPress={() => router.push("/moi")}
      />
      <RudiButton label="Vào bản trải nghiệm Team Đà Lạt" onPress={enterDemo} variant="soft" />
      <Inline style={styles.signupRow}>
        <Text style={[typography.label, { color: colors.inkSoft }]}>Chưa có tài khoản?</Text>
        <Pressable accessibilityRole="button" onPress={enterDemo}>
          <Text style={[typography.label, { color: colors.accent }]}>Tạo ngay (bản trải nghiệm)</Text>
        </Pressable>
      </Inline>
      <Text style={[typography.caption, styles.privacyText, { color: colors.inkFaint }]}>
        Tiếp tục nghĩa là bạn đồng ý Điều khoản và Chính sách bảo mật. Bản trải nghiệm không tạo tài khoản thật.
      </Text>
    </RudiScreen>
  );
}

const INTERESTS = [
  ["restaurant-outline", "Ăn ngon"],
  ["cafe-outline", "Cafe chill"],
  ["trail-sign-outline", "Khám phá"],
  ["camera-outline", "Sống ảo"],
  ["musical-notes-outline", "Âm nhạc"],
  ["game-controller-outline", "Vui chơi"],
] as const;

const VIBES = ["Yên bình", "Náo nhiệt", "Ngoài trời", "Có gu", "Tiết kiệm", "Tự thưởng"];

export function PersonalizationScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();

  const toggle = (value: string, values: string[], setValues: (next: string[]) => void) => {
    void Haptics.selectionAsync();
    setValues(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  return (
    <RudiScreen contentStyle={styles.personalization} testID="personalization-screen">
      <TopBar right={<Text style={[typography.caption, { color: colors.inkFaint }]}>1/1</Text>} />
      <ProgressBar value={100} />
      <Heading
        title="Cho Rủ Đi biết gu của bạn"
        subtitle={`Chọn ít nhất 3 sở thích. Lựa chọn ${noiLuu(session.luuTruSong)}.`}
      />
      <Card style={styles.preferenceCard}>
        <Text style={[typography.title, { color: colors.ink }]}>Bạn thường mê gì?</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Chọn mọi thứ khiến bạn muốn xách balo lên.</Text>
        <View style={styles.interestGrid}>
          {INTERESTS.map(([icon, label]) => {
            const selected = session.interests.includes(label);
            return (
              <Pressable
                key={label}
                accessibilityRole="checkbox"
                aria-checked={selected}
                onPress={() => toggle(label, session.interests, session.setInterests)}
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
                  <Ionicons color={selected ? colors.accentInk : colors.inkSoft} name={icon} size={23} />
                </View>
                <Text style={[typography.label, { color: selected ? colors.accent : colors.ink }]}>{label}</Text>
                {selected ? <Ionicons color={colors.accent} name="checkmark-circle" size={18} /> : null}
              </Pressable>
            );
          })}
        </View>
      </Card>
      <View style={styles.vibeBlock}>
        <Text style={[typography.title, { color: colors.ink }]}>Mood chuyến đi</Text>
        <Inline gap={8} wrap>
          {VIBES.map((vibe) => (
            <Chip
              key={vibe}
              label={vibe}
              onPress={() => toggle(vibe, session.vibes, session.setVibes)}
              selected={session.vibes.includes(vibe)}
            />
          ))}
        </Inline>
      </View>
      <Spacer size={4} />
      <RudiButton
        disabled={session.interests.length < 3}
        icon="sparkles"
        label="Tạo không gian của tôi"
        onPress={() => router.replace("/explore")}
      />
      <Text style={[typography.caption, styles.privacyText, { color: colors.inkFaint }]}>
        Rủ Đi chỉ dùng lựa chọn này để cá nhân hóa gợi ý trên máy. Chưa gửi lên máy chủ.
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
  welcomeLogoMark: { width: 40, height: 40, borderRadius: 14, backgroundColor: "rgba(255,255,255,0.18)", borderWidth: 1, borderColor: "rgba(255,255,255,0.34)", alignItems: "center", justifyContent: "center" },
  welcomeLogoMarkType: { color: "#FFFFFF", fontSize: 12, lineHeight: 11, fontStyle: "italic", fontWeight: "900", letterSpacing: -0.7, textAlign: "center" },
  welcomeLogoType: { color: "#FFFFFF", fontSize: 25, lineHeight: 30, fontStyle: "italic", fontWeight: "900", letterSpacing: -1.2 },
  welcomeCenter: { alignItems: "center", marginTop: -15, paddingHorizontal: 18 },
  welcomeBrand: { color: "#FFFFFF", fontSize: 76, lineHeight: 64, fontStyle: "italic", fontWeight: "900", letterSpacing: -4, textAlign: "center", transform: [{ rotate: "-4deg" }] },
  welcomeTagline: { color: "#FFFFFF", fontSize: 20, lineHeight: 25, fontWeight: "800", textAlign: "center", marginTop: 17 },
  taglineStroke: { width: 120, height: 4, borderRadius: 9, backgroundColor: "#FF9F1C", marginTop: 11, transform: [{ rotate: "-4deg" }] },
  welcomeBottom: { gap: 10 },
  welcomeActions: { paddingHorizontal: 18, gap: 10 },
  heroTitle: { color: "#FFFFFF", fontSize: 28, lineHeight: 33, fontWeight: "900", letterSpacing: -0.8, minHeight: 70 },
  heroSubtitle: { color: "rgba(255,255,255,0.84)", fontSize: 14, lineHeight: 20, fontWeight: "600", maxWidth: 520, marginBottom: 3, minHeight: 60 },
  previewLink: { minHeight: 50, borderWidth: 1, borderColor: "rgba(255,255,255,0.72)", borderRadius: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  previewText: { color: "#FFFFFF", fontSize: 14, fontWeight: "800" },
  pager: { flexDirection: "row", justifyContent: "center", gap: 7, paddingTop: 4 },
  pagerDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.48)" },
  pagerActive: { width: 18, height: 7, borderRadius: 4, backgroundColor: "#FFFFFF" },
  dauVanCay: { color: "rgba(255,255,255,0.55)", fontSize: 12, textAlign: "center", paddingTop: 6 },
  pressed: { opacity: 0.7 },
  formScreen: { gap: 20 },
  loginBrand: { alignItems: "center", gap: 20, marginTop: 3 },
  loginCard: { gap: 14, maxWidth: 560, width: "100%", alignSelf: "center" },
  orRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  orLine: { flex: 1, height: StyleSheet.hairlineWidth },
  signupRow: { justifyContent: "center", gap: 5 },
  authError: { lineHeight: 18 },
  personalization: { maxWidth: 760 },
  preferenceCard: { gap: 8 },
  interestGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 7 },
  interest: { minHeight: 62, minWidth: "47%", flexGrow: 1, flexBasis: 150, borderRadius: 16, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 9, padding: 10 },
  interestIcon: { width: 39, height: 39, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  vibeBlock: { gap: 11 },
  privacyText: { textAlign: "center", paddingHorizontal: 18 },
});
