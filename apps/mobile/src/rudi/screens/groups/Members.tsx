/**
 * One group's roster, and the door to invite somebody (M2).
 *
 * Reuses the legacy client module (`danhSachThanhVien`): the route is the
 * same one App B called, with the bearer now doing the identifying. Names
 * come with the roster (`display_name`), initials are drawn in one tone -- the
 * design system does not colour people.
 */
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { chuDau } from "../../../screens/ca-nhan/ban-be";
import { danhSachThanhVien, type ThanhVien } from "../../../screens/vao-cua/cong-api";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Heading, ListRow, RudiButton, RudiScreen, TopBar } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; thanhVien: ThanhVien[] }
  | { pha: "hong"; loi: string };

export function GroupMembersScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });

  const nap = useCallback(async () => {
    if (phien === null || typeof id !== "string") return;
    try {
      setTrang({ pha: "xong", thanhVien: await danhSachThanhVien(id, phien.person_id) });
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  }, [id, phien]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;
  if (typeof id !== "string") return <Redirect href="/messages" />;

  const tenNhom = phien.contexts?.find((nhom) => nhom.id === id)?.display_name ?? "Nhóm";
  const conSong = trang.pha === "xong" ? trang.thanhVien.filter((tv) => tv.state !== "left") : [];

  return (
    <RudiScreen testID="group-members-screen">
      <TopBar title={tenNhom} />
      <Heading
        title="Thành viên"
        subtitle={
          trang.pha === "xong"
            ? `${conSong.filter((tv) => tv.state === "active").length} đang ở trong nhóm, ${conSong.filter((tv) => tv.state === "invited").length} đang được mời.`
            : "Đang đọc danh sách từ máy chủ..."
        }
      />
      <Card style={styles.loiVao}>
        <ListRow icon="images-outline" onPress={() => router.push(`/groups/${id}/wall` as never)} subtitle="Ảnh, check-in, tim và bình luận. Chỉ thành viên thấy." title="Tường kỷ niệm" />
        <ListRow icon="albums-outline" onPress={() => router.push(`/groups/${id}/album` as never)} subtitle="Mỗi kèo một album, có thước phim." title="Album chuyến đi" />
      </Card>
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" ? (
        <Card style={styles.danhSach}>
          {conSong.map((tv) => {
            const ten = tv.display_name ?? "Thành viên";
            const laToi = tv.person_id === phien.person_id;
            return (
              <View key={tv.id} style={styles.hang}>
                <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
                  <Text style={[typography.title, { color: colors.accent }]}>{chuDau(ten)}</Text>
                </View>
                <View style={styles.hangChu}>
                  <Text style={[typography.body, { color: colors.ink }]}>
                    {ten}
                    {laToi ? " (bạn)" : ""}
                  </Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>
                    {tv.state === "invited" ? "Đã mời, chưa đồng ý" : tv.role === "admin" ? "Quản trị" : "Thành viên"}
                  </Text>
                </View>
                {tv.role === "admin" && tv.state === "active" ? <Chip label="Quản trị" /> : null}
              </View>
            );
          })}
        </Card>
      ) : null}
      <RudiButton
        icon="person-add-outline"
        label="Mời bằng số điện thoại"
        onPress={() => router.push(`/groups/${id}/invite` as never)}
      />
      <Text style={[typography.caption, { color: colors.inkFaint }]}>
        Người được mời thấy lời mời ở tab Tin nhắn ngay khi đăng nhập bằng số đó, và chính họ bấm «Đồng
        ý». Không ai bị đưa vào nhóm mà chưa gật đầu.
      </Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  loiVao: { gap: 0, paddingVertical: 4 },
  danhSach: { gap: 12 },
  hang: { flexDirection: "row", alignItems: "center", gap: 12 },
  hangChu: { flex: 1, gap: 2 },
  chuDau: { width: 40, height: 40, borderRadius: 14, alignItems: "center", justifyContent: "center" },
});
