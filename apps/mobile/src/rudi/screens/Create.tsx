import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { typography, useRudiTheme } from "../theme";
import { DemoBadge, Heading, IconName } from "../ui";

const ACTIONS: { icon: IconName; title: string; detail: string; href: string; tone: string }[] = [
  { icon: "calendar-outline", title: "Tạo cuộc hẹn", detail: "Chốt thời gian, nơi đi và hội bạn", href: "/outings/new", tone: "#C93900" },
  { icon: "receipt-outline", title: "Chia hóa đơn", detail: "Xem lại ảnh bill và gán món", href: "/smart-split/xom-leo/review", tone: "#00756B" },
  { icon: "images-outline", title: "Đăng kỷ niệm", detail: "Chia sẻ ảnh vào tường nhóm", href: "/moments/new", tone: "#7D49EF" },
];

/** Same sheet for the tab FAB (`router.push("/create")`) and the `/create` route. */
export function CreateSheet() {
  const router = useRouter();
  const { colors } = useRudiTheme();

  return (
    <SafeAreaView edges={["top", "bottom"]} style={styles.safe}>
      <Pressable accessibilityLabel="Đóng" onPress={() => router.back()} style={styles.scrim} />
      <View style={[styles.sheet, { backgroundColor: colors.ground, borderColor: colors.line }]}>
        <View style={[styles.handle, { backgroundColor: colors.lineStrong }]} />
        <View style={styles.headingRow}>
          <Heading size="h2" subtitle="Một chạm để bắt đầu với Team Đà Lạt." title="Mình làm gì tiếp?" />
          <DemoBadge />
        </View>
        <View style={styles.actions}>
          {ACTIONS.map((action) => (
            <Pressable
              key={action.title}
              accessibilityRole="button"
              onPress={() => router.replace(action.href as never)}
              style={({ pressed }) => [
                styles.action,
                { backgroundColor: colors.card, borderColor: colors.line },
                pressed && styles.pressed,
              ]}
            >
              <View style={[styles.icon, { backgroundColor: `${action.tone}18` }]}>
                <Ionicons color={action.tone} name={action.icon} size={24} />
              </View>
              <View style={styles.actionText}>
                <Text style={[typography.title, { color: colors.ink }]}>{action.title}</Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>{action.detail}</Text>
              </View>
              <Ionicons color={colors.inkFaint} name="arrow-forward" size={20} />
            </Pressable>
          ))}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, justifyContent: "flex-end" },
  scrim: { position: "absolute", inset: 0, backgroundColor: "rgba(31, 23, 18, 0.48)" },
  sheet: {
    borderTopLeftRadius: 30,
    borderTopRightRadius: 30,
    borderWidth: 1,
    paddingHorizontal: 18,
    paddingTop: 10,
    paddingBottom: 20,
    gap: 20,
  },
  handle: { alignSelf: "center", width: 42, height: 5, borderRadius: 99, opacity: 0.45 },
  headingRow: { gap: 10 },
  actions: { gap: 10 },
  action: {
    minHeight: 78,
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    padding: 13,
    borderRadius: 18,
    borderWidth: 1,
  },
  icon: { width: 48, height: 48, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  actionText: { flex: 1, gap: 2 },
  pressed: { opacity: 0.76, transform: [{ scale: 0.988 }] },
});
