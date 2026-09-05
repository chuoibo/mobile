/**
 * Six boxes, one decision: does the server accept this code for this number.
 *
 * The challenge comes from `otp-dang-cho.ts` (memory), never from a route
 * param. A cold start therefore lands here with nothing to verify and goes
 * back to the login screen -- which is right, because a code requested by a
 * previous launch is a code the person should request again.
 *
 * ## What the screen says, and why it is the server's sentence
 *
 * A wrong code answers 422 `otp_code_invalid` with «Mã chưa đúng. Còn N lần
 * thử.» The count is the server's; a fixed sentence here would hide it, and
 * the fifth wrong try turning into a burned challenge (429, then 404 for the
 * right code) is exactly the moment a person needs the number.
 *
 * ## After the code
 *
 * `xacMinhOtp` stores the session and `chonNhomMacDinh` picks a group when the
 * server listed an active one. `manDau` then decides between the Khám phá tab
 * and «Chưa có nhóm nào». `datPhien` puts the session into force for the
 * screens already mounted; without it they would read fixtures until restart.
 *
 * UI v2: the cover band continues from the login page (title and the masked
 * number in cover ink), the six boxes sit on the paper without a card.
 */
import { Redirect, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { guiOtp, xacMinhOtp } from "../../../phien";
import { manDau } from "../../duong-vao";
import { cheSo, datOtpDangCho, layOtpDangCho, xoaOtpDangCho, type OtpDangCho } from "../../otp-dang-cho";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { OtpBoxes, RudiButton, RudiScreen } from "../../ui";
import { CoverBand } from "../../ui/CoverBand";
import { useAdaptiveLayout } from "../../ui/useAdaptiveLayout";

type Trang =
  | { pha: "nhap" }
  | { pha: "dang-xac-minh" }
  | { pha: "dang-gui-lai" }
  | { pha: "hong"; loi: string };

const DO_DAI_MA = 6;

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function OtpScreen() {
  const router = useRouter();
  const { colors, space } = useRudiTheme();
  const layout = useAdaptiveLayout();
  const { datPhien } = useRudiSession();
  const [cho, setCho] = useState<OtpDangCho | null>(() => layOtpDangCho());
  const [ma, setMa] = useState("");
  const [trang, setTrang] = useState<Trang>({ pha: "nhap" });
  const [bayGio, setBayGio] = useState(() => Date.now());

  // One tick a second for the resend countdown. Cleared on unmount so a screen
  // that was left does not keep a timer alive behind the tabs.
  useEffect(() => {
    const nhip = setInterval(() => setBayGio(Date.now()), 1000);
    return () => clearInterval(nhip);
  }, []);

  if (cho === null) return <Redirect href="/login" />;

  const conLai = Math.max(0, Math.ceil((cho.guiLaiLuc - bayGio) / 1000));
  const ban = trang.pha === "dang-xac-minh" || trang.pha === "dang-gui-lai";

  const xacMinh = async (code: string) => {
    setTrang({ pha: "dang-xac-minh" });
    try {
      const phien = await xacMinhOtp(cho.challengeId, cho.phone, code);
      xoaOtpDangCho();
      datPhien(phien);
      router.replace(manDau(phien) as never);
    } catch (error) {
      // The boxes clear so the next attempt starts from the first one; the
      // sentence stays until the person types again.
      setMa("");
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  };

  const guiLai = async () => {
    setTrang({ pha: "dang-gui-lai" });
    try {
      const daGui = await guiOtp(cho.phone);
      const moi: OtpDangCho = {
        challengeId: daGui.challenge_id,
        phone: cho.phone,
        guiLaiLuc: Date.now() + daGui.resend_after_seconds * 1000,
      };
      datOtpDangCho(moi);
      setCho(moi);
      setMa("");
      setTrang({ pha: "nhap" });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  };

  const doiMa = (tiep: string) => {
    setMa(tiep);
    if (trang.pha === "hong") setTrang({ pha: "nhap" });
    if (tiep.length === DO_DAI_MA && !ban) void xacMinh(tiep);
  };

  const doiSo = () => {
    xoaOtpDangCho();
    router.replace("/login");
  };
  const bleed = layout.sizeClass === "compact" ? space.md : space.lg;

  return (
    <RudiScreen contentStyle={styles.screen} surface="cover" testID="otp-screen">
      <StatusBar style="light" />
      <CoverBand bleed={bleed} onBack={doiSo} style={styles.band} underStatusBar>
        <Text style={[typography.hero, { color: colors.coverInk }]}>Nhập mã 6 số</Text>
        <Text style={[typography.body, styles.dan, { color: colors.coverInkSoft }]}>
          Mã đã gửi tới {cheSo(cho.phone)}. Có hiệu lực 5 phút; nhập đủ 6 số là tự kiểm.
        </Text>
      </CoverBand>
      <View style={styles.form}>
        <OtpBoxes disabled={ban} length={DO_DAI_MA} onChange={doiMa} value={ma} />
        {trang.pha === "dang-xac-minh" ? (
          <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang kiểm mã...</Text>
        ) : null}
        {trang.pha === "hong" ? (
          // Body size, not caption: this is the one line that carries the
          // retry count, and it must not sit at the 12sp floor under a control.
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
        ) : null}
        <RudiButton
          disabled={ban || conLai > 0}
          label="Gửi lại mã"
          loading={trang.pha === "dang-gui-lai"}
          onPress={() => void guiLai()}
          variant="outline"
        />
        {conLai > 0 ? (
          // Live information stays readable: a disabled button's label is pale
          // by design, so the countdown lives in ink beneath it instead.
          <Text style={[typography.caption, styles.demNguoc, { color: colors.inkSoft }]}>
            Gửi lại được sau {conLai} giây.
          </Text>
        ) : null}
      </View>
      <RudiButton disabled={ban} label="Đổi số điện thoại" onPress={doiSo} variant="ghost" />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  screen: { gap: 20 },
  band: { gap: 10 },
  dan: { maxWidth: 520 },
  form: { gap: 16, maxWidth: 560, width: "100%", alignSelf: "center" },
  demNguoc: { textAlign: "center" },
});
