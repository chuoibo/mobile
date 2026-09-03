/**
 * The door a real person comes through.
 *
 * Until this screen existed, RuDi -- the 21 screens somebody actually sees --
 * had no way in at all. The only button on the login screen that did anything
 * was «Vào bản trải nghiệm». The working door lived in `src/screens/len-plan/
 * NhanLoiMoi.tsx`, rendered only by `VoTab.tsx`, reachable only through
 * `/legacy`. Two apps in one binary, and the pretty one had no lock.
 *
 * ## What it reuses rather than rebuilds
 *
 * - `doiLoiMoiLayPhien` from `src/phien.ts` -- the exchange, the SecureStore
 *   write, and the `Idempotency-Key` that turns a dropped response into a
 *   replay instead of a spent secret and a locked-out person.
 * - `cauSauKhiNhan` from `NhanLoiMoi.tsx` -- the sentences. Signing in and
 *   joining are two different things, and there is exactly one place in this
 *   repo that knows how to say which one happened. A second copy would drift,
 *   and the drift would show up as two screens telling one person two stories.
 *
 * ## Two ways in, one screen
 *
 * A link (`rudi://moi/<token>`) hands the code through `loi-moi-den.ts`; a
 * person who was sent the code some other way pastes it. Both end at the same
 * request, so there is one place where redemption can be wrong.
 *
 * ## What it must not do
 *
 * Say "thành công". `membership_state` is the difference between somebody who
 * is in and somebody a member still has to accept, and merging those is how a
 * person ends up staring at an empty group wondering what they did wrong.
 */
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../api";
import { doiLoiMoiLayPhien } from "../../phien";
import { cauSauKhiNhan } from "../../screens/len-plan/NhanLoiMoi";
import { layLoiMoiDen } from "../loi-moi-den";
import { typography, useRudiTheme } from "../theme";
import { Card, Field, Heading, RudiButton, RudiScreen, TopBar } from "../ui";

type Trang =
  | { pha: "cho-ma" }
  | { pha: "dang-doi" }
  | { pha: "xong"; state: "invited" | "active" | "left" }
  | { pha: "hong"; loi: string };

export function LoiMoiScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [ma, setMa] = useState("");
  const [trang, setTrang] = useState<Trang>({ pha: "cho-ma" });

  // A link fills the field; it does not redeem on its own. Spending a
  // single-use secret is irreversible, so it stays a thing somebody pressed.
  useEffect(() => {
    const den = layLoiMoiDen();
    if (den !== null) setMa(den);
  }, []);

  const nhan = async () => {
    const sach = ma.trim();
    if (sach === "") {
      setTrang({ pha: "hong", loi: "Dán mã lời mời bạn được gửi." });
      return;
    }
    setTrang({ pha: "dang-doi" });
    try {
      const phien = await doiLoiMoiLayPhien(sach);
      setTrang({ pha: "xong", state: phien.membership_state });
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  };

  if (trang.pha === "xong") {
    // `active` is in; anything else is signed in and still waiting. The
    // session is real either way, so the app reloads itself through the entry
    // screen rather than dropping somebody into a group they cannot read.
    const daVao = trang.state === "active";
    return (
      <RudiScreen testID="loi-moi-screen">
        <TopBar title="Lời mời" />
        <Heading
          title={daVao ? "Xong, bạn đã ở trong nhóm" : "Đã đăng nhập"}
          subtitle={cauSauKhiNhan(trang.state === "active" ? "active" : "invited", "phien")}
        />
        <RudiButton
          label={daVao ? "Vào nhóm" : "Về trang đầu"}
          onPress={() => router.replace(daVao ? "/explore" : "/welcome")}
        />
      </RudiScreen>
    );
  }

  return (
    <RudiScreen testID="loi-moi-screen">
      <TopBar title="Lời mời" />
      <Heading
        title="Bạn được rủ đi"
        subtitle="Dán mã trong lời mời. Rủ Đi chỉ vào được bằng lời mời của một người đã ở trong nhóm."
      />
      <Card>
        <Field
          autoCapitalize="none"
          autoCorrect={false}
          icon="mail-open-outline"
          label="Mã lời mời"
          onChangeText={setMa}
          placeholder="Dán mã ở đây"
          value={ma}
        />
        <RudiButton
          disabled={trang.pha === "dang-doi"}
          label="Nhận lời mời"
          loading={trang.pha === "dang-doi"}
          onPress={() => void nhan()}
        />
        {trang.pha === "hong" ? (
          <Text style={[typography.caption, { color: colors.warn }]}>{trang.loi}</Text>
        ) : null}
      </Card>
      <View>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Chưa có lời mời? Nhờ một người trong nhóm gửi cho bạn. Đây là chủ ý, không phải thiếu sót:
          không ai tự tạo tài khoản trước khi có bạn rủ đi.
        </Text>
      </View>
      <RudiButton
        label="Xem bản trải nghiệm"
        onPress={() => router.replace("/welcome")}
        variant="ghost"
      />
    </RudiScreen>
  );
}
