import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { demoAssets } from "../fixtures";
import { typography, useRudiTheme } from "../theme";
import {
  Card,
  Chip,
  DemoBadge,
  Field,
  Heading,
  Inline,
  Logo,
  Photo,
  ProgressBar,
  RudiButton,
  RudiScreen,
  Spacer,
  TopBar,
} from "../ui";

export function WelcomeScreen() {
  const router = useRouter();

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
          <Text style={styles.heroTitle}>Hẹn hội bạn. Rủ Đi lo phần còn lại.</Text>
          <Text style={styles.heroSubtitle}>
            Khám phá, lên plan, chia bill và giữ trọn mọi kỷ niệm trong một nơi.
          </Text>
          <RudiButton icon="arrow-forward" label="Rủ Đi thôi!" onPress={() => router.push("/login")} />
        <Pressable
          accessibilityRole="button"
          onPress={() => router.replace("/explore")}
            style={({ pressed }) => [styles.previewLink, pressed && styles.pressed]}
        >
            <Text style={styles.previewText}>Tìm hiểu thêm</Text>
            <Ionicons color="#FFFFFF" name="chevron-forward" size={18} />
        </Pressable>
          <View style={styles.pager}>
            <View style={styles.pagerActive} />
            <View style={styles.pagerDot} />
            <View style={styles.pagerDot} />
            <View style={styles.pagerDot} />
          </View>
        </View>
      </View>
    </RudiScreen>
  );
}

export function LoginScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  return (
    <RudiScreen contentStyle={styles.formScreen} testID="login-screen">
      <TopBar right={<DemoBadge />} />
      <View style={styles.loginBrand}>
        <Logo />
        <Heading
          align="center"
          title="Chào mừng bạn quay lại"
          subtitle="Đăng nhập để tiếp tục những cuộc vui còn dang dở."
        />
      </View>
      <Card style={styles.loginCard}>
        <Field
          autoCapitalize="none"
          autoComplete="email"
          icon="mail-outline"
          keyboardType="email-address"
          label="Email"
          onChangeText={setEmail}
          placeholder="Địa chỉ email"
          value={email}
        />
        <Field
          autoCapitalize="none"
          icon="lock-closed-outline"
          label="Mật khẩu"
          onChangeText={setPassword}
          placeholder="Ít nhất 8 ký tự"
          secureTextEntry={!showPassword}
          trailing={
            <Pressable
              accessibilityLabel={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              hitSlop={10}
              onPress={() => setShowPassword((value) => !value)}
            >
              <Ionicons color={colors.inkFaint} name={showPassword ? "eye-off-outline" : "eye-outline"} size={21} />
            </Pressable>
          }
          value={password}
        />
        <Pressable accessibilityRole="button" style={styles.forgotLink}>
          <Text style={[typography.caption, { color: colors.accent }]}>Quên mật khẩu?</Text>
        </Pressable>
        <RudiButton
          disabled={!email || password.length < 3}
          label="Đăng nhập"
          onPress={() => router.push("/personalization")}
        />
        <View style={styles.orRow}>
          <View style={[styles.orLine, { backgroundColor: colors.line }]} />
          <Text style={[typography.caption, { color: colors.inkFaint }]}>hoặc tiếp tục với</Text>
          <View style={[styles.orLine, { backgroundColor: colors.line }]} />
        </View>
        <Inline gap={10}>
          <RudiButton
            full={false}
            icon="logo-google"
            label="Google"
            style={styles.buttonRowItem}
            variant="outline"
          />
          <RudiButton
            full={false}
            icon="logo-apple"
            label="Apple"
            style={styles.buttonRowItem}
            variant="outline"
          />
        </Inline>
      </Card>
      <Inline style={styles.signupRow}>
        <Text style={[typography.label, { color: colors.inkSoft }]}>Chưa có tài khoản?</Text>
        <Pressable accessibilityRole="button">
          <Text style={[typography.label, { color: colors.accent }]}>Đăng ký ngay</Text>
        </Pressable>
      </Inline>
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
  const [interests, setInterests] = useState<string[]>(["Ăn ngon", "Cafe chill", "Khám phá"]);
  const [vibes, setVibes] = useState<string[]>(["Ngoài trời", "Có gu"]);

  const toggle = (value: string, values: string[], setValues: (next: string[]) => void) => {
    void Haptics.selectionAsync();
    setValues(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  return (
    <RudiScreen contentStyle={styles.personalization} testID="personalization-screen">
      <TopBar right={<Text style={[typography.caption, { color: colors.inkFaint }]}>1/1</Text>} />
      <ProgressBar value={100} />
      <Heading
        title="Cho RuDi biết gu của bạn"
        subtitle="Chọn ít nhất 3 sở thích. Bạn luôn có thể thay đổi sau."
      />
      <Card style={styles.preferenceCard}>
        <Text style={[typography.title, { color: colors.ink }]}>Bạn thường mê gì?</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Chọn mọi thứ khiến bạn muốn xách balo lên.</Text>
        <View style={styles.interestGrid}>
          {INTERESTS.map(([icon, label]) => {
            const selected = interests.includes(label);
            return (
              <Pressable
                key={label}
                accessibilityRole="checkbox"
                aria-checked={selected}
                onPress={() => toggle(label, interests, setInterests)}
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
              onPress={() => toggle(vibe, vibes, setVibes)}
              selected={vibes.includes(vibe)}
            />
          ))}
        </Inline>
      </View>
      <Spacer size={4} />
      <RudiButton
        disabled={interests.length < 3}
        icon="sparkles"
        label="Tạo không gian của tôi"
        onPress={() => router.replace("/explore")}
      />
      <Text style={[typography.caption, styles.privacyText, { color: colors.inkFaint }]}>
        RuDi chỉ dùng lựa chọn này để cá nhân hóa gợi ý. Bạn kiểm soát dữ liệu của mình.
      </Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  buttonRowItem: { flex: 1 },
  welcome: { flex: 1, paddingTop: 0 },
  welcomeContent: { flex: 1, justifyContent: "space-between", paddingHorizontal: 18, paddingTop: 14, paddingBottom: 18 },
  welcomeTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  welcomeLogo: { flexDirection: "row", alignItems: "center", gap: 8 },
  welcomeWordmark: { flexDirection: "row", alignItems: "center", gap: 4 },
  welcomeLogoMark: { width: 40, height: 40, borderRadius: 14, backgroundColor: "rgba(255,255,255,0.18)", borderWidth: 1, borderColor: "rgba(255,255,255,0.34)", alignItems: "center", justifyContent: "center" },
  welcomeLogoMarkType: { color: "#FFFFFF", fontSize: 12, lineHeight: 11, fontStyle: "italic", fontWeight: "900", letterSpacing: -0.7, textAlign: "center" },
  welcomeLogoType: { color: "#FFFFFF", fontSize: 25, lineHeight: 30, fontStyle: "italic", fontWeight: "900", letterSpacing: -1.2 },
  welcomeCenter: { alignItems: "center", marginTop: -15 },
  welcomeBrand: { color: "#FFFFFF", fontSize: 76, lineHeight: 64, fontStyle: "italic", fontWeight: "900", letterSpacing: -4, textAlign: "center", transform: [{ rotate: "-4deg" }] },
  welcomeTagline: { color: "#FFFFFF", fontSize: 20, lineHeight: 25, fontWeight: "800", textAlign: "center", marginTop: 17 },
  taglineStroke: { width: 120, height: 4, borderRadius: 9, backgroundColor: "#FF9F1C", marginTop: 11, transform: [{ rotate: "-4deg" }] },
  welcomeBottom: { gap: 10 },
  heroTitle: { color: "#FFFFFF", fontSize: 28, lineHeight: 33, fontWeight: "900", letterSpacing: -0.8 },
  heroSubtitle: { color: "rgba(255,255,255,0.84)", fontSize: 14, lineHeight: 20, fontWeight: "600", maxWidth: 520, marginBottom: 3 },
  previewLink: { minHeight: 50, borderWidth: 1, borderColor: "rgba(255,255,255,0.72)", borderRadius: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  previewText: { color: "#FFFFFF", fontSize: 14, fontWeight: "800" },
  pager: { flexDirection: "row", justifyContent: "center", gap: 7, paddingTop: 4 },
  pagerDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.48)" },
  pagerActive: { width: 18, height: 7, borderRadius: 4, backgroundColor: "#FFFFFF" },
  pressed: { opacity: 0.7 },
  formScreen: { gap: 20 },
  loginBrand: { alignItems: "center", gap: 20, marginTop: 3 },
  loginCard: { gap: 14, maxWidth: 560, width: "100%", alignSelf: "center" },
  forgotLink: { alignSelf: "flex-end", minHeight: 30, justifyContent: "center" },
  orRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  orLine: { flex: 1, height: StyleSheet.hairlineWidth },
  signupRow: { justifyContent: "center", gap: 5 },
  personalization: { maxWidth: 760 },
  preferenceCard: { gap: 8 },
  interestGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 7 },
  interest: { minHeight: 62, minWidth: "47%", flexGrow: 1, flexBasis: 150, borderRadius: 16, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 9, padding: 10 },
  interestIcon: { width: 39, height: 39, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  vibeBlock: { gap: 11 },
  privacyText: { textAlign: "center", paddingHorizontal: 18 },
});
