/**
 * Somebody else's profile and wall (M8): `/people/{id}`.
 *
 * Two independent reads. The profile is the gate -- a refusal there is the
 * whole screen, because there is nothing honest to draw without it. The wall
 * is loaded after and fails on its own, so a wall that does not answer does
 * not hide a person who did.
 *
 * The header tile is the same warm initial used on every friend surface, not
 * `Avatar`: that primitive takes a fixture person and a fixture colour, and
 * this screen never touches the fixture.
 */
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { chuDau } from "../../../screens/ca-nhan/ban-be";
import {
  cauNgayVao,
  cauQuanHe,
  cauTuongRong,
  docHoSoNguoi,
  docTuongCua,
  dongPhuBai,
  loiRaChu,
  type Bai,
  type HoSoNguoi,
} from "../../nguoi/ho-so-nguoi";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Divider, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

type TrangHoSo =
  | { pha: "dang-doc" }
  | { pha: "xong"; hoSo: HoSoNguoi }
  | { pha: "hong"; loi: string };

type TrangTuong =
  | { pha: "dang-doc" }
  | { pha: "xong"; bai: Bai[] }
  | { pha: "hong"; loi: string };

export function HoSoNguoiScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { phien, phienDaDoc } = useRudiSession();
  const params = useLocalSearchParams<{ id?: string }>();
  // Written as a statement, not `x ? x : ""`: the id-default scanner reads that
  // shape as a display fallback wherever it appears, and it is right to.
  let personId = "";
  if (typeof params.id === "string") personId = params.id;
  const [hoSo, setHoSo] = useState<TrangHoSo>({ pha: "dang-doc" });
  const [tuong, setTuong] = useState<TrangTuong>({ pha: "dang-doc" });

  const napHoSo = useCallback(async () => {
    if (phien === null || personId === "") return;
    setHoSo({ pha: "dang-doc" });
    try {
      setHoSo({ pha: "xong", hoSo: await docHoSoNguoi(personId, phien.person_id) });
    } catch (error) {
      setHoSo({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [personId, phien]);

  const napTuong = useCallback(async () => {
    if (phien === null || personId === "") return;
    setTuong({ pha: "dang-doc" });
    try {
      setTuong({ pha: "xong", bai: await docTuongCua(personId, phien.person_id) });
    } catch (error) {
      setTuong({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [personId, phien]);

  useFocusEffect(
    useCallback(() => {
      void napHoSo();
      void napTuong();
    }, [napHoSo, napTuong]),
  );

  if (!phienDaDoc) return null;

  return (
    <RudiScreen testID="ho-so-nguoi-screen">
      <TopBar title="Hồ sơ" />
      {hoSo.pha === "dang-doc" ? (
        <Card>
          <Text style={[typography.body, { color: colors.inkFaint }]}>Đang đọc từ máy chủ…</Text>
        </Card>
      ) : null}
      {hoSo.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{hoSo.loi}</Text>
          <View style={styles.khoangTren}>
            <RudiButton label="Thử lại" onPress={() => void napHoSo()} variant="outline" />
          </View>
        </Card>
      ) : null}
      {hoSo.pha === "xong" ? (
        <>
          <Card>
            <View style={styles.dau}>
              <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
                <Text style={[typography.h2, { color: colors.accent }]}>
                  {chuDau(hoSo.hoSo.display_name)}
                </Text>
              </View>
              <View style={styles.dauChu}>
                <Text numberOfLines={2} style={[typography.h2, { color: colors.ink }]}>
                  {hoSo.hoSo.display_name}
                </Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>
                  {cauNgayVao(hoSo.hoSo.created_at)}
                </Text>
              </View>
            </View>
            <View style={styles.chips}>
              <Chip label={cauQuanHe(hoSo.hoSo.relation)} />
              {hoSo.hoSo.city ? <Chip icon="location-outline" label={hoSo.hoSo.city} /> : null}
            </View>
            {hoSo.hoSo.bio ? (
              <Text style={[typography.body, { color: colors.inkSoft }]}>{hoSo.hoSo.bio}</Text>
            ) : (
              <Text style={[typography.caption, { color: colors.inkFaint }]}>
                Người này chưa viết giới thiệu.
              </Text>
            )}
            {hoSo.hoSo.relation === "self" ? (
              <View style={styles.khoangTren}>
                <RudiButton
                  icon="create-outline"
                  label="Đăng bài mới"
                  onPress={() => router.push("/posts/new")}
                />
              </View>
            ) : null}
          </Card>
          <Heading title={hoSo.hoSo.relation === "self" ? "Tường của bạn" : "Tường cá nhân"} />
          {tuong.pha === "dang-doc" ? (
            <Card>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc bài…</Text>
            </Card>
          ) : null}
          {tuong.pha === "hong" ? (
            <Card>
              <Text style={[typography.body, { color: colors.warn }]}>{tuong.loi}</Text>
              <View style={styles.khoangTren}>
                <RudiButton label="Đọc lại tường" onPress={() => void napTuong()} variant="outline" />
              </View>
            </Card>
          ) : null}
          {tuong.pha === "xong" && tuong.bai.length === 0 ? (
            <Card>
              <Text style={[typography.body, { color: colors.inkSoft }]}>
                {cauTuongRong(hoSo.hoSo.relation)}
              </Text>
            </Card>
          ) : null}
          {tuong.pha === "xong" && tuong.bai.length > 0 ? (
            <Card style={styles.danhSach}>
              {tuong.bai.map((bai, i) => (
                <View key={bai.id}>
                  {i > 0 ? <Divider /> : null}
                  <View style={styles.bai}>
                    <Text style={[typography.body, { color: colors.ink }]}>{bai.body}</Text>
                    <Text style={[typography.caption, { color: colors.inkFaint }]}>
                      {dongPhuBai(bai)}
                    </Text>
                  </View>
                </View>
              ))}
            </Card>
          ) : null}
        </>
      ) : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  dau: { flexDirection: "row", alignItems: "center", gap: 14 },
  dauChu: { flex: 1, gap: 2 },
  chuDau: { width: 60, height: 60, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  danhSach: { paddingVertical: 6 },
  bai: { gap: 6, paddingVertical: 10 },
  khoangTren: { marginTop: 4 },
});
