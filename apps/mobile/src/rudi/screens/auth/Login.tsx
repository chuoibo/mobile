/**
 * The front door, on the real API.
 *
 * Until this screen existed the only button here that did anything was «Vào
 * bản trải nghiệm»; Google, Apple and the phone field set an error string and
 * stopped. ADR-0016 opens two doors that need no invitation, and this is the
 * first: a phone number, a six-digit code, a session (`POST /auth/otp/*`).
 *
 * ## What is deliberately not here
 *
 * - A password. There is none anywhere in the product, so there is nothing to
 *   forget and no «Quên mật khẩu?» to offer.
 * - The number in a route param or a log. It goes into ONE request body and
 *   into `otp-dang-cho.ts` (memory only) for the code screen to echo masked.
 * - The fixture door on a shipped build. The «Vào bản trải nghiệm…» button is
 *   rendered only when `CUA_FIXTURE_DEV` is true -- a development build with
 *   `EXPO_PUBLIC_RUDI_FIXTURE=1` -- because the Maestro table and the design
 *   measurements need it and nobody with a real account should ever land on it.
 *
 * Google is a button that says, truthfully, that it opens once the team has
 * configured OAuth; PR-BE4 and the client ids turn it into a chooser. Apple
 * renders on iOS only: on Android it would be a promise with nothing behind it.
 */
import { useRouter } from "expo-router";
import { useState } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { guiOtp } from "../../../phien";
import { chuanHoaSo } from "../../../screens/vao-cua/danh-tinh";
import { CUA_FIXTURE_DEV } from "../../cua-fixture";
import { datOtpDangCho } from "../../otp-dang-cho";
import { typography, useRudiTheme } from "../../theme";
import { Card, DemoBadge, Field, Heading, Logo, RudiButton, RudiScreen, TopBar } from "../../ui";

type Trang = { pha: "nhap" } | { pha: "dang-gui" } | { pha: "hong"; loi: string };

export const CAU_GOOGLE_CHO_CAU_HINH =
  "Đăng nhập Google mở sau khi đội cấu hình OAuth. Số điện thoại dùng được ngay.";

export function LoginScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [phone, setPhone] = useState("");
  const [trang, setTrang] = useState<Trang>({ pha: "nhap" });
  const [thongBao, setThongBao] = useState<string | null>(null);

  const gui = async () => {
    setThongBao(null);
    const sach = phone.trim();
    if (chuanHoaSo(sach) === null) {
      setTrang({ pha: "hong", loi: "Chưa đúng dạng số di động Việt Nam." });
      return;
    }
    setTrang({ pha: "dang-gui" });
    try {
      const daGui = await guiOtp(sach);
      datOtpDangCho({
        challengeId: daGui.challenge_id,
        phone: sach,
        guiLaiLuc: Date.now() + daGui.resend_after_seconds * 1000,
      });
      setTrang({ pha: "nhap" });
      router.push("/otp");
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  };

  const dangGui = trang.pha === "dang-gui";

  return (
    <RudiScreen contentStyle={styles.screen} testID="login-screen">
      <TopBar />
      <View style={styles.brand}>
        <Logo />
        <Heading
          align="center"
          title="Chào bạn"
          subtitle="Nhập số điện thoại để nhận mã. Chưa có tài khoản thì Rủ Đi tạo luôn, không cần mật khẩu."
        />
      </View>
      <Card style={styles.card}>
        <Field
          accessibilityLabel="Ô số điện thoại"
          autoCapitalize="none"
          autoComplete="tel"
          editable={!dangGui}
          icon="call-outline"
          keyboardType="phone-pad"
          label="Số điện thoại"
          onChangeText={setPhone}
          onSubmitEditing={() => void gui()}
          placeholder="Nhập số di động"
          returnKeyType="send"
          textContentType="telephoneNumber"
          value={phone}
        />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Số di động Việt Nam. Mã 6 số đến bằng tin nhắn, có hiệu lực 5 phút.
        </Text>
        <RudiButton disabled={dangGui} label="Gửi mã" loading={dangGui} onPress={() => void gui()} />
        {trang.pha === "hong" ? (
          <Text style={[typography.caption, styles.loi, { color: colors.warn }]}>{trang.loi}</Text>
        ) : null}
      </Card>
      <View style={styles.orRow}>
        <View style={[styles.orLine, { backgroundColor: colors.line }]} />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>hoặc</Text>
        <View style={[styles.orLine, { backgroundColor: colors.line }]} />
      </View>
      <View style={styles.khac}>
        <RudiButton
          icon="logo-google"
          label="Tiếp tục với Google"
          onPress={() => setThongBao(CAU_GOOGLE_CHO_CAU_HINH)}
          variant="outline"
        />
        {Platform.OS === "ios" ? (
          <RudiButton
            icon="logo-apple"
            label="Tiếp tục với Apple"
            onPress={() => setThongBao("Apple hiện sau khi có chứng chỉ của đội.")}
            variant="outline"
          />
        ) : null}
        <RudiButton
          icon="mail-open-outline"
          label="Tôi có lời mời"
          onPress={() => router.push("/moi")}
          variant="outline"
        />
        {thongBao ? (
          <Text style={[typography.caption, styles.loi, { color: colors.inkSoft }]}>{thongBao}</Text>
        ) : null}
      </View>
      {CUA_FIXTURE_DEV ? (
        // Development builds only, and only when the operator asked. A store
        // build has neither switch and never renders this block.
        <View style={styles.cuaDev}>
          <DemoBadge label="Cửa dev: dữ liệu demo" />
          <RudiButton
            label="Vào bản trải nghiệm Team Đà Lạt"
            onPress={() => router.push("/personalization")}
            variant="soft"
          />
        </View>
      ) : null}
      <Text style={[typography.caption, styles.phapLy, { color: colors.inkFaint }]}>
        Tiếp tục nghĩa là bạn đồng ý Điều khoản và Chính sách bảo mật. Số điện thoại chỉ dùng để
        gửi mã và không hiển thị cho người khác.
      </Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  screen: { gap: 20 },
  brand: { alignItems: "center", gap: 20, marginTop: 3 },
  card: { gap: 14, maxWidth: 560, width: "100%", alignSelf: "center" },
  orRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  orLine: { flex: 1, height: StyleSheet.hairlineWidth },
  khac: { gap: 10 },
  cuaDev: { gap: 8, alignItems: "center" },
  loi: { lineHeight: 18 },
  phapLy: { textAlign: "center", paddingHorizontal: 18 },
});
