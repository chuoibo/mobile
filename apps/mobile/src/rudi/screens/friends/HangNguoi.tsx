/**
 * One person, the way every friend surface shows one (M2): a warm initial
 * tile, the name, a caption, and an optional trailing action pair. The friend
 * list and the add-by-phone confirm step share it so a person reads the same
 * on both screens. `HangNguoiCho` is the same silhouette in grey while the
 * server answers.
 */
import { type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { chuDau } from "../../../screens/ca-nhan/ban-be";
import { typography, useRudiTheme } from "../../theme";

export function HangNguoi({ ten, phu, duoi }: { ten: string; phu: string; duoi?: ReactNode }) {
  const { colors } = useRudiTheme();
  return (
    <View style={styles.hang}>
      <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
        <Text style={[typography.title, { color: colors.accent }]}>{chuDau(ten)}</Text>
      </View>
      <View style={styles.hangChu}>
        <Text numberOfLines={1} style={[typography.body, { color: colors.ink }]}>
          {ten}
        </Text>
        <Text numberOfLines={1} style={[typography.caption, { color: colors.inkFaint }]}>
          {phu}
        </Text>
      </View>
      {duoi ? <View style={styles.duoi}>{duoi}</View> : null}
    </View>
  );
}

export function HangNguoiCho({ soHang = 3 }: { soHang?: number }) {
  const { colors } = useRudiTheme();
  return (
    <View accessibilityLabel="Đang đọc từ máy chủ">
      {Array.from({ length: soHang }, (_, i) => (
        <View key={i} style={styles.hang}>
          <View style={[styles.chuDau, { backgroundColor: colors.line }]} />
          <View style={styles.hangChu}>
            <View style={[styles.xuongTen, { backgroundColor: colors.line }]} />
            <View style={[styles.xuongPhu, { backgroundColor: colors.line }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  hang: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8 },
  hangChu: { flex: 1, gap: 2 },
  chuDau: { width: 40, height: 40, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  duoi: { flexShrink: 0, flexDirection: "row", alignItems: "center", gap: 8 },
  xuongTen: { height: 14, width: "55%", borderRadius: 7 },
  xuongPhu: { height: 10, width: "35%", borderRadius: 5 },
});
