/**
 * One person, the way every friend surface shows one (M2): a warm initial
 * tile, the name, a caption, and an optional trailing action pair. The friend
 * list and the add-by-phone confirm step share it so a person reads the same
 * on both screens. `HangNguoiCho` is the same silhouette in grey while the
 * server answers.
 */
import { type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { chuDau } from "../../../screens/ca-nhan/ban-be";
import { typography, useRudiTheme } from "../../theme";

/**
 * `onPress` turns the row into the way into that person's profile. It stays
 * optional: a row for somebody the reader may not open (a pending request from
 * a stranger) has no destination, and drawing it as a button would promise one.
 */
export function HangNguoi({
  ten,
  phu,
  duoi,
  onPress,
}: {
  ten: string;
  phu: string;
  duoi?: ReactNode;
  onPress?: () => void;
}) {
  const { colors } = useRudiTheme();
  const than = (
    <>
      <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
        <Text style={[typography.title, { color: colors.accent }]}>{chuDau(ten)}</Text>
      </View>
      <View style={styles.hangChu}>
        <Text numberOfLines={1} style={[typography.body, { color: colors.ink }]}>
          {ten}
        </Text>
        <Text numberOfLines={2} style={[typography.caption, { color: colors.inkFaint }]}>
          {phu}
        </Text>
      </View>
      {duoi ? <View style={styles.duoi}>{duoi}</View> : null}
    </>
  );
  if (onPress === undefined) return <View style={styles.hang}>{than}</View>;
  return (
    <Pressable
      accessibilityLabel={`Xem hồ sơ ${ten}`}
      accessibilityRole="button"
      onPress={onPress}
      style={styles.hang}
    >
      {than}
    </Pressable>
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
