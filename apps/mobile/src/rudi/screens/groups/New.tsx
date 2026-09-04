/**
 * Open a group from inside RuDi.
 *
 * `taoNhom` is the legacy client module, unchanged: the server makes the
 * creator an active admin inside the same transaction, so there is no
 * invite-yourself step and no window with a group nobody administers.
 *
 * One attempt per intent. The `Idempotency-Key` is minted when the name is
 * first submitted and reused for a retry of the SAME name, so a dropped
 * response replays instead of opening a second «Nhóm OTP». A changed name is a
 * different intent and mints a new key -- the server fingerprints the body.
 *
 * After the write the screen re-reads `GET /people/me/contexts` rather than
 * trusting the response: the session needs the membership id and state the
 * list carries, and it is the list `chonNhomMacDinh` reads.
 */
import { Redirect, useRouter } from "expo-router";
import { useRef, useState } from "react";
import { StyleSheet, Text } from "react-native";

import { ApiError, newAttempt, thongDiepNguoiDoc, type Attempt } from "../../../api";
import { docNhomCuaToi, ganDanhSachNhom } from "../../../phien";
import { taoNhom } from "../../../screens/vao-cua/cong-api";
import { manDau } from "../../duong-vao";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Field, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

type Trang = { pha: "nhap" } | { pha: "dang-mo" } | { pha: "hong"; loi: string };

export function GroupNewScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { phien, phienDaDoc, datPhien } = useRudiSession();
  const [ten, setTen] = useState("");
  const [trang, setTrang] = useState<Trang>({ pha: "nhap" });
  const lanBam = useRef<{ ten: string; attempt: Attempt } | null>(null);

  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;

  const mo = async () => {
    const sach = ten.trim();
    if (sach === "") {
      setTrang({ pha: "hong", loi: "Đặt tên cho nhóm." });
      return;
    }
    if (lanBam.current === null || lanBam.current.ten !== sach) {
      lanBam.current = { ten: sach, attempt: newAttempt() };
    }
    setTrang({ pha: "dang-mo" });
    try {
      await taoNhom(sach, phien.person_id, lanBam.current.attempt);
      const nhom = await docNhomCuaToi(phien.person_id);
      const moi = await ganDanhSachNhom(phien, nhom);
      datPhien(moi);
      router.replace(manDau(moi) as never);
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  };

  const dangMo = trang.pha === "dang-mo";

  return (
    <RudiScreen contentStyle={styles.screen} testID="group-new-screen">
      <TopBar title="Nhóm mới" />
      <Heading
        title="Đặt tên cho hội"
        subtitle="Bạn là quản trị của nhóm này. Mời bạn bè sau, bằng lời mời đích danh hoặc link."
      />
      <Card style={styles.card}>
        <Field
          accessibilityLabel="Ô tên nhóm"
          autoFocus
          editable={!dangMo}
          icon="people-outline"
          label="Tên nhóm"
          maxLength={200}
          onChangeText={setTen}
          onSubmitEditing={() => void mo()}
          placeholder="Ví dụ: Hội cafe cuối tuần"
          returnKeyType="done"
          value={ten}
        />
        <RudiButton disabled={dangMo} label="Mở nhóm" loading={dangMo} onPress={() => void mo()} />
        {trang.pha === "hong" ? (
          <Text style={[typography.caption, { color: colors.warn }]}>{trang.loi}</Text>
        ) : null}
      </Card>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  screen: { gap: 20 },
  card: { gap: 14 },
});
