import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { noiLuu } from "../luu-tru";
import { useRudiSession } from "../session";
import { typography, useRudiTheme } from "../theme";
import {
  Card,
  Chip,
  Heading,
  Inline,
  ProgressBar,
  RudiButton,
  RudiScreen,
  Spacer,
  TopBar,
} from "../ui";

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
  pressed: { opacity: 0.7 },
  personalization: { maxWidth: 760 },
  privacyText: { textAlign: "center", paddingHorizontal: 18 },
  preferenceCard: { gap: 8 },
  interestGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 7 },
  interest: { minHeight: 62, minWidth: "47%", flexGrow: 1, flexBasis: 150, borderRadius: 16, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 9, padding: 10 },
  interestIcon: { width: 39, height: 39, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  vibeBlock: { gap: 11 },
});
