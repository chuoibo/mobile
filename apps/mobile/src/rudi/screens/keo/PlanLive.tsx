/**
 * Lên plan on a real session (M4): the current group's outings from the
 * server, newest first, and the door to make one. The fixture build keeps
 * the fixture trip, which is what the default Maestro table drives.
 */
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import type { Phien } from "../../../phien";
import { nhanKhoangNgay, nhanNganSach, type BuoiDi } from "../../../screens/len-plan/buoi-di";
import { cauSoChang, docKeoCuaNhom } from "../../keo/keo";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, RudiButton, RudiScreen } from "../../ui";

type Trang = { pha: "dang-doc" } | { pha: "xong"; keo: BuoiDi[] } | { pha: "hong"; loi: string };

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

function tenNhom(phien: Phien): string {
  const nhom = phien.contexts?.find((n) => n.id === phien.context_id);
  if (nhom === undefined) return "nhóm của bạn";
  return nhom.display_name;
}

export function PlanLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const contextId = phien.context_id;

  const nap = useCallback(async () => {
    if (contextId === null) return;
    try {
      const keo = await docKeoCuaNhom(contextId, phien.person_id);
      setTrang({ pha: "xong", keo: [...keo].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)) });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [contextId, phien.person_id]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  if (contextId === null) {
    return (
      <RudiScreen bottomInset={112} testID="plan-screen">
        <Heading title="Lên plan" subtitle="Vào một nhóm trước; kèo là của nhóm." />
        <RudiButton label="Tới Tin nhắn" onPress={() => router.push("/(tabs)/messages" as never)} variant="outline" />
      </RudiScreen>
    );
  }

  return (
    <RudiScreen
      bottomInset={112}
      footer={<RudiButton icon="add" label="Tạo kèo" onPress={() => router.push("/outings/new")} />}
      footerInset={92}
      testID="plan-screen"
    >
      <Heading title="Lên plan" subtitle={`Kèo của ${tenNhom(phien)}, trên máy chủ`} />
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc kèo từ máy chủ...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" && trang.keo.length === 0 ? (
        <Card style={styles.rong}>
          <View style={[styles.rongIcon, { backgroundColor: colors.accentSoft }]}>
            <Ionicons color={colors.accent} name="calendar-outline" size={24} />
          </View>
          <Heading align="center" size="h2" title="Chưa có kèo nào" subtitle="Tạo kèo đầu tiên: ngày, số người, ngân sách. Chặng và địa điểm thêm sau." />
        </Card>
      ) : null}
      {trang.pha === "xong"
        ? trang.keo.map((k) => (
            <Card accessibilityLabel={`Mở kèo ${k.title}`} key={k.id} onPress={() => router.push(`/outings/${k.id}` as never)} style={styles.the}>
              <View style={[styles.theIcon, { backgroundColor: colors.accentSoft }]}>
                <Ionicons color={colors.accent} name="calendar-outline" size={22} />
              </View>
              <View style={styles.theChu}>
                <Text numberOfLines={1} style={[typography.title, { color: colors.ink }]}>
                  {k.title}
                </Text>
                <Text numberOfLines={1} style={[typography.caption, { color: colors.inkSoft }]}>
                  {nhanKhoangNgay(k.starts_on, k.ends_on)} · {k.headcount} người · {nhanNganSach(k.budget_per_person_vnd)} một người
                </Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>{cauSoChang(k.stops.length)}</Text>
              </View>
              <Ionicons color={colors.inkFaint} name="chevron-forward" size={18} />
            </Card>
          ))
        : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  rong: { alignItems: "center", gap: 12, paddingVertical: 24 },
  rongIcon: { width: 52, height: 52, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  the: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
  theIcon: { width: 44, height: 44, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  theChu: { flex: 1, gap: 3 },
});
