/**
 * Signed in, in no group yet.
 *
 * The OTP and Google doors mint a session for a person the server may know
 * nothing else about. Before this screen that person was sent to the Khám phá
 * tab, where `nguon.ts` said «trai-nghiem» and every number was Team Đà Lạt's
 * -- a signed-in stranger reading a fixture. Now the empty state is a screen
 * with the two ways forward: open a group, or take an invitation.
 *
 * Invitations the server already knows about are listed here with their own
 * «Đồng ý». That is the case of somebody added to a group by phone number
 * before they ever installed the app: `derive_person_id` puts their code login
 * on the same row, `GET /people/me/contexts` lists the `invited` membership,
 * and this is where they accept it. Accepting is a press, never automatic --
 * a member chose them by name; what is left is them saying yes.
 */
import { Redirect, useRouter } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { vaoNhom, type NhomTomTat } from "../../../phien";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

type Trang = { pha: "yen" } | { pha: "dang-vao"; id: string } | { pha: "hong"; loi: string };

export function GroupsEmptyScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { phien, phienDaDoc, datPhien, resetSession } = useRudiSession();
  const [trang, setTrang] = useState<Trang>({ pha: "yen" });

  // Nothing is decided before the disk has answered: a frame of "signed out"
  // here would redirect a signed-in person to the welcome screen.
  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;
  if (phien.context_id !== null && phien.membership_state === "active") {
    return <Redirect href="/explore" />;
  }

  const loiMoi = (phien.contexts ?? []).filter((nhom) => nhom.my_state === "invited");
  const ten = phien.profile?.display_name ?? "bạn";

  const dongY = async (nhom: NhomTomTat) => {
    setTrang({ pha: "dang-vao", id: nhom.id });
    try {
      const daVao = await vaoNhom({
        ...phien,
        context_id: nhom.id,
        membership_state: "invited",
        membership_id: nhom.membership_id,
      });
      datPhien(daVao);
      router.replace("/explore");
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  };

  return (
    <RudiScreen contentStyle={styles.screen} testID="groups-empty-screen">
      <TopBar back={false} title="Nhóm của bạn" />
      <Heading
        title="Chưa có nhóm nào"
        subtitle={`Xin chào ${ten}. Rủ Đi sống trong nhóm bạn bè: mở một nhóm mới, hoặc nhận lời mời của người đã ở trong nhóm.`}
      />
      {phien.is_new_person ? (
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Tài khoản vừa được tạo bằng số điện thoại của bạn. Tên hiển thị sửa được ở mục Cá nhân.
        </Text>
      ) : null}
      {loiMoi.length > 0 ? (
        <Card style={styles.card}>
          <Text style={[typography.title, { color: colors.ink }]}>Lời mời đang chờ</Text>
          {loiMoi.map((nhom) => (
            <View key={nhom.id} style={styles.hang}>
              <View style={styles.hangChu}>
                <Text style={[typography.body, { color: colors.ink }]}>{nhom.display_name}</Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>
                  {nhom.member_count} thành viên
                </Text>
              </View>
              <RudiButton
                compact
                disabled={trang.pha === "dang-vao"}
                full={false}
                label="Đồng ý"
                loading={trang.pha === "dang-vao" && trang.id === nhom.id}
                onPress={() => void dongY(nhom)}
              />
            </View>
          ))}
          {trang.pha === "hong" ? (
            <Text style={[typography.caption, { color: colors.warn }]}>{trang.loi}</Text>
          ) : null}
        </Card>
      ) : null}
      <View style={styles.nut}>
        <RudiButton icon="people-outline" label="Tạo nhóm" onPress={() => router.push("/groups/new")} />
        <RudiButton
          icon="mail-open-outline"
          label="Tôi có lời mời"
          onPress={() => router.push("/moi")}
          variant="outline"
        />
        <RudiButton
          label="Đăng xuất"
          onPress={() => {
            resetSession();
            router.replace("/welcome");
          }}
          variant="ghost"
        />
      </View>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  screen: { gap: 20 },
  card: { gap: 12 },
  hang: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  hangChu: { flex: 1, gap: 2 },
  nut: { gap: 10 },
});
