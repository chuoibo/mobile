/**
 * Bạn bè (M2): the person's own friend graph, three views of one table.
 *
 * `friend_requests` rows are the truth for all three segments -- accepted
 * edges are friends, pending edges I received are «Đã nhận», pending edges I
 * sent are «Đã gửi». The server resolves «the other person» per reader, so no
 * screen branches on direction (and none can get it backwards).
 *
 * Reuses the legacy client module (`ban-be.ts`) as-is: the routes are the ones
 * App B called, with the bearer now doing the identifying.
 */
import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, newAttempt, thongDiepNguoiDoc } from "../../../api";
import {
  chuDau,
  docDanhSachBan,
  docLoiMoi,
  traLoiLoiMoi,
  type Ban,
  type LoiMoi,
  type TraLoi,
} from "../../../screens/ca-nhan/ban-be";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, RudiButton, RudiScreen, Segmented, TopBar } from "../../ui";

type Du = { ban: Ban[]; daNhan: LoiMoi[]; daGui: LoiMoi[] };
type Trang = { pha: "dang-doc" } | { pha: "xong"; du: Du } | { pha: "hong"; loi: string };

const MUC = ["Bạn bè", "Đã nhận", "Đã gửi"];

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function FriendsScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { phien, phienDaDoc } = useRudiSession();
  const [muc, setMuc] = useState(0);
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [dangTraLoi, setDangTraLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    if (phien === null) return;
    try {
      const toi = phien.person_id;
      const [ban, daNhan, daGui] = await Promise.all([
        docDanhSachBan(toi, toi),
        docLoiMoi(toi, toi, "incoming"),
        docLoiMoi(toi, toi, "outgoing"),
      ]);
      setTrang({
        pha: "xong",
        du: {
          ban,
          daNhan: daNhan.filter((lm) => lm.state === "pending"),
          daGui: daGui.filter((lm) => lm.state === "pending"),
        },
      });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [phien]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;

  const traLoi = async (lm: LoiMoi, quyetDinh: TraLoi) => {
    setDangTraLoi(lm.id);
    try {
      await traLoiLoiMoi(lm.id, quyetDinh, phien.person_id, newAttempt());
      await nap();
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    } finally {
      setDangTraLoi(null);
    }
  };

  const hangNguoi = (id: string, ten: string, phu: string, duoi?: ReactNode) => (
    <View key={id} style={styles.hang}>
      <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
        <Text style={[typography.title, { color: colors.accent }]}>{chuDau(ten)}</Text>
      </View>
      <View style={styles.hangChu}>
        <Text style={[typography.body, { color: colors.ink }]}>{ten}</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>{phu}</Text>
      </View>
      {duoi}
    </View>
  );

  return (
    <RudiScreen testID="friends-screen">
      <TopBar title="Bạn bè" />
      <Segmented items={MUC} onSelect={setMuc} selected={muc} />
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc từ máy chủ...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" && muc === 0 ? (
        trang.du.ban.length === 0 ? (
          <Heading title="Chưa có bạn nào" subtitle="Thêm bạn bằng số điện thoại. Người ấy đồng ý thì hai bên là bạn." />
        ) : (
          <Card style={styles.danhSach}>
            {trang.du.ban.map((b) =>
              hangNguoi(
                b.person_id,
                b.display_name,
                `Bạn từ ${new Date(b.friends_since).toLocaleDateString("vi-VN")}`,
                <RudiButton
                  compact
                  full={false}
                  label="Xem"
                  onPress={() => router.push(`/people/${b.person_id}` as never)}
                  variant="ghost"
                />,
              ),
            )}
          </Card>
        )
      ) : null}
      {trang.pha === "xong" && muc === 1 ? (
        trang.du.daNhan.length === 0 ? (
          <Heading title="Không có lời mời nào đang chờ" />
        ) : (
          <Card style={styles.danhSach}>
            {trang.du.daNhan.map((lm) =>
              hangNguoi(
                lm.id,
                lm.other_display_name,
                "Muốn kết bạn với bạn",
                <View style={styles.cap}>
                  <RudiButton
                    compact
                    disabled={dangTraLoi !== null}
                    full={false}
                    label="Đồng ý"
                    loading={dangTraLoi === lm.id}
                    onPress={() => void traLoi(lm, "accept")}
                  />
                  <RudiButton
                    compact
                    disabled={dangTraLoi !== null}
                    full={false}
                    label="Từ chối"
                    onPress={() => void traLoi(lm, "decline")}
                    variant="ghost"
                  />
                </View>,
              ),
            )}
          </Card>
        )
      ) : null}
      {trang.pha === "xong" && muc === 2 ? (
        trang.du.daGui.length === 0 ? (
          <Heading title="Bạn chưa gửi lời mời nào" />
        ) : (
          <Card style={styles.danhSach}>
            {trang.du.daGui.map((lm) => hangNguoi(lm.id, lm.other_display_name, "Đang chờ người ấy trả lời"))}
          </Card>
        )
      ) : null}
      <RudiButton icon="person-add-outline" label="Thêm bạn bằng số điện thoại" onPress={() => router.push("/friends/add")} />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  danhSach: { gap: 12 },
  hang: { flexDirection: "row", alignItems: "center", gap: 12 },
  hangChu: { flex: 1, gap: 2 },
  chuDau: { width: 40, height: 40, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  cap: { flexDirection: "row", gap: 6 },
});
