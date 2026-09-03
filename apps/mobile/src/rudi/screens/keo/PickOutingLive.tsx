/**
 * «Thêm vào kèo» from a place (M4): pick one of the group's outings and the
 * place becomes a stop on it (next full hour, labelled with its name). The
 * server refuses a place it does not know before writing anything.
 */
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, newAttempt, thongDiepNguoiDoc } from "../../../api";
import type { Phien } from "../../../phien";
import { nhanKhoangNgay, type BuoiDi } from "../../../screens/len-plan/buoi-di";
import { docChiTiet } from "../../kham-pha/dia-diem";
import { cauSoChang, docKeoCuaNhom, gioTiepTheo, luuLichTrinh, themChang } from "../../keo/keo";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; keo: BuoiDi[]; ten: string }
  | { pha: "hong"; loi: string };

function thamSoChuoi(v: unknown): string {
  if (typeof v === "string") return v;
  return "";
}

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function PickOutingLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const params = useLocalSearchParams<{ place?: string }>();
  const { colors } = useRudiTheme();
  const placeId = thamSoChuoi(params.place);
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [dangGhi, setDangGhi] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const contextId = phien.context_id;

  const nap = useCallback(async () => {
    if (contextId === null || !placeId) return;
    try {
      const [keo, place] = await Promise.all([docKeoCuaNhom(contextId, phien.person_id), docChiTiet(placeId)]);
      setTrang({ pha: "xong", keo, ten: place.name });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [contextId, placeId, phien.person_id]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  if (contextId === null) return <Redirect href="/(tabs)/plan" />;

  const them = async (keo: BuoiDi, ten: string) => {
    setDangGhi(keo.id);
    setLoi(null);
    try {
      await luuLichTrinh(
        keo,
        themChang(keo.stops, { at: gioTiepTheo(), label: ten, place_name: ten, place_id: placeId }),
        phien.person_id,
        newAttempt(),
      );
      router.replace(`/outings/${keo.id}` as never);
    } catch (error) {
      setLoi(loiRaChu(error));
    } finally {
      setDangGhi(null);
    }
  };

  return (
    <RudiScreen testID="pick-outing-screen">
      <TopBar title="Thêm vào kèo" />
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc kèo từ máy chủ...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Quay về" onPress={() => router.back()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" ? (
        <>
          <Heading title={trang.ten} subtitle="Chọn kèo để thêm làm một chặng. Giờ đặt tạm là giờ tròn kế tiếp, sửa được trong kèo." />
          {loi !== null ? <Text style={[typography.body, { color: colors.warn }]}>{loi}</Text> : null}
          {trang.keo.length === 0 ? (
            <Card style={styles.rong}>
              <Heading align="center" size="h2" title="Nhóm chưa có kèo nào" subtitle="Tạo kèo trước ở Lên plan, rồi quay lại thêm địa điểm này." />
              <RudiButton label="Tạo kèo" onPress={() => router.push("/outings/new")} />
            </Card>
          ) : null}
          {trang.keo.map((k) => (
            <Card key={k.id} style={styles.the}>
              <View style={[styles.theIcon, { backgroundColor: colors.accentSoft }]}>
                <Ionicons color={colors.accent} name="calendar-outline" size={22} />
              </View>
              <View style={styles.theChu}>
                <Text numberOfLines={1} style={[typography.title, { color: colors.ink }]}>
                  {k.title}
                </Text>
                <Text style={[typography.caption, { color: colors.inkSoft }]}>
                  {nhanKhoangNgay(k.starts_on, k.ends_on)} · {cauSoChang(k.stops.length)}
                </Text>
              </View>
              <RudiButton
                compact
                disabled={dangGhi !== null}
                full={false}
                label="Thêm vào"
                loading={dangGhi === k.id}
                onPress={() => void them(k, trang.ten)}
              />
            </Card>
          ))}
        </>
      ) : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  rong: { alignItems: "center", gap: 12, paddingVertical: 20 },
  the: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12 },
  theIcon: { width: 44, height: 44, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  theChu: { flex: 1, gap: 3 },
});
