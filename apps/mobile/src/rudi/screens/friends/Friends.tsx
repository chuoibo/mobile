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
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, newAttempt, thongDiepNguoiDoc } from "../../../api";
import {
  docDanhSachBan,
  docLoiMoi,
  traLoiLoiMoi,
  type Ban,
  type LoiMoi,
  type TraLoi,
} from "../../../screens/ca-nhan/ban-be";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Divider, Heading, RudiButton, RudiScreen, Segmented, TopBar } from "../../ui";
import { HangNguoi, HangNguoiCho } from "./HangNguoi";

type Du = { ban: Ban[]; daNhan: LoiMoi[]; daGui: LoiMoi[] };
type Trang = { pha: "dang-doc" } | { pha: "xong"; du: Du } | { pha: "hong"; loi: string };

const MUC = ["Đã là bạn", "Đã nhận", "Đã gửi"];

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

function ngayKetBan(iso: string): string {
  return `Bạn từ ${new Date(iso).toLocaleDateString("vi-VN")}`;
}

/** Rows inside one card, a hairline between neighbours, like the profile menu. */
function DanhSach({ hang }: { hang: ReactNode[] }) {
  return (
    <Card style={styles.danhSach}>
      {hang.map((h, i) => (
        <View key={i}>
          {i > 0 ? (
            <View style={styles.vach}>
              <Divider />
            </View>
          ) : null}
          {h}
        </View>
      ))}
    </Card>
  );
}

export function FriendsScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  // The pinned footer must clear the gesture bar: the screen shell only pads
  // top/left/right, so the bottom inset is this screen's to add.
  const { bottom: menDuoi } = useSafeAreaInsets();
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

  return (
    <RudiScreen
      footer={
        <RudiButton
          icon="person-add-outline"
          label="Thêm bạn bằng số điện thoại"
          onPress={() => router.push("/friends/add")}
        />
      }
      footerInset={14 + menDuoi}
      testID="friends-screen"
    >
      <TopBar title="Bạn bè" />
      <Segmented items={MUC} onSelect={setMuc} selected={muc} />
      {trang.pha === "dang-doc" ? (
        <Card style={styles.danhSach}>
          <HangNguoiCho />
        </Card>
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
          <DanhSach
            hang={trang.du.ban.map((b) => (
              <HangNguoi key={b.person_id} phu={ngayKetBan(b.friends_since)} ten={b.display_name} />
            ))}
          />
        )
      ) : null}
      {trang.pha === "xong" && muc === 1 ? (
        trang.du.daNhan.length === 0 ? (
          <Heading title="Không có lời mời nào đang chờ" />
        ) : (
          <DanhSach
            hang={trang.du.daNhan.map((lm) => (
              <HangNguoi
                key={lm.id}
                duoi={
                  <>
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
                  </>
                }
                phu="Muốn kết bạn với bạn"
                ten={lm.other_display_name}
              />
            ))}
          />
        )
      ) : null}
      {trang.pha === "xong" && muc === 2 ? (
        trang.du.daGui.length === 0 ? (
          <Heading title="Bạn chưa gửi lời mời nào" />
        ) : (
          <DanhSach
            hang={trang.du.daGui.map((lm) => (
              <HangNguoi key={lm.id} phu="Đang chờ người ấy trả lời" ten={lm.other_display_name} />
            ))}
          />
        )
      ) : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  danhSach: { paddingVertical: 6 },
  // Hairline starts at the text column, like the Profile menu card (tile 40 + gap 12).
  vach: { marginLeft: 52 },
});
