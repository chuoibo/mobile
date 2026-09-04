/**
 * Invite somebody into a group by their telephone number (M2).
 *
 * Three server calls, in the order the server needs them: the number becomes a
 * person id (`POST /identity/person-id`, a keyed digest -- the number is never
 * stored), the id gets the name the inviter knows them by (`PUT /people/{id}`,
 * 200 when they already had one -- an existing name is never overwritten
 * silently: the server keeps theirs), and then the membership is created as
 * `invited` (`POST /contexts/{id}/members`).
 *
 * When that person later signs in with the same number, the OTP door derives
 * the same id (ADR-0016), so the invitation is waiting for them on the «Tin
 * nhắn» tab with a «Đồng ý» button. Nobody is put into a group without a press.
 *
 * One `Attempt` per call, kept across retries of the same press, so a dropped
 * response replays instead of inviting twice (the server would answer 409 to a
 * second membership, and that would read like a bug in a working invite).
 */
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useRef, useState } from "react";
import { StyleSheet, Text } from "react-native";

import { ApiError, newAttempt, registerPerson, thongDiepNguoiDoc, type Attempt } from "../../../api";
import { chuanHoaSo } from "../../../screens/vao-cua/danh-tinh";
import { layIdTuSo, moiVaoNhom } from "../../../screens/vao-cua/cong-api";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Field, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

type Trang =
  | { pha: "nhap" }
  | { pha: "dang-moi" }
  | { pha: "xong"; ten: string }
  | { pha: "hong"; loi: string };

export function GroupInviteScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  const [phone, setPhone] = useState("");
  const [ten, setTen] = useState("");
  const [trang, setTrang] = useState<Trang>({ pha: "nhap" });
  const lanBam = useRef<{ khoa: string; dat: Attempt; moi: Attempt } | null>(null);

  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;
  if (typeof id !== "string") return <Redirect href="/messages" />;

  const moi = async () => {
    const soSach = phone.trim();
    const tenSach = ten.trim();
    if (chuanHoaSo(soSach) === null) {
      setTrang({ pha: "hong", loi: "Chưa đúng dạng số di động Việt Nam." });
      return;
    }
    if (tenSach === "") {
      setTrang({ pha: "hong", loi: "Đặt tên cho người bạn đang mời, để cả nhóm biết đó là ai." });
      return;
    }
    const khoa = `${soSach}|${tenSach}`;
    if (lanBam.current === null || lanBam.current.khoa !== khoa) {
      lanBam.current = { khoa, dat: newAttempt(), moi: newAttempt() };
    }
    setTrang({ pha: "dang-moi" });
    try {
      const personId = await layIdTuSo(soSach);
      await registerPerson({ id: personId, name: tenSach }, phien.person_id, lanBam.current.dat);
      await moiVaoNhom(id, personId, phien.person_id, lanBam.current.moi);
      setTrang({ pha: "xong", ten: tenSach });
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  };

  if (trang.pha === "xong") {
    return (
      <RudiScreen testID="group-invite-screen">
        <TopBar title="Mời vào nhóm" />
        <Heading
          title={`Đã mời ${trang.ten}`}
          subtitle="Khi người này đăng nhập bằng số đó, lời mời hiện ở tab Tin nhắn và chính họ bấm «Đồng ý»."
        />
        <RudiButton label="Xem thành viên" onPress={() => router.back()} />
        <RudiButton
          label="Mời thêm người"
          onPress={() => {
            setPhone("");
            setTen("");
            setTrang({ pha: "nhap" });
          }}
          variant="outline"
        />
      </RudiScreen>
    );
  }

  const dangMoi = trang.pha === "dang-moi";
  return (
    <RudiScreen contentStyle={styles.screen} testID="group-invite-screen">
      <TopBar title="Mời vào nhóm" />
      <Heading
        title="Mời bằng số điện thoại"
        subtitle="Số điện thoại chỉ dùng để nhận ra đúng người khi họ đăng nhập; máy chủ không lưu số."
      />
      <Card style={styles.card}>
        <Field
          accessibilityLabel="Ô số điện thoại người được mời"
          autoComplete="tel"
          editable={!dangMoi}
          icon="call-outline"
          keyboardType="phone-pad"
          label="Số điện thoại"
          onChangeText={setPhone}
          placeholder="Số di động của bạn ấy"
          textContentType="telephoneNumber"
          value={phone}
        />
        <Field
          accessibilityLabel="Ô tên người được mời"
          editable={!dangMoi}
          icon="person-outline"
          label="Tên"
          maxLength={200}
          onChangeText={setTen}
          placeholder="Bạn gọi người này là gì"
          value={ten}
        />
        <RudiButton disabled={dangMoi} label="Gửi lời mời" loading={dangMoi} onPress={() => void moi()} />
        {trang.pha === "hong" ? (
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
        ) : null}
      </Card>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  screen: { gap: 20 },
  card: { gap: 14 },
});
