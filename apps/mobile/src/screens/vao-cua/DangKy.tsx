/** F01. The screen that lets a real person start, rather than be picked.
 *
 * The opening screen offers three ways in and two of them are drawn shells:
 * Google and Apple each need a console project, a redirect scheme and a native
 * rebuild, none of which is visible in what is being demonstrated. The third,
 * "Đăng nhập bằng số điện thoại", needs none of that -- so it is the one that
 * is real, and this is it.
 *
 * Real means the same thing here as everywhere else in this repo: pressing the
 * button sends `PUT /people/{id}` to the actual API and a row appears in
 * `people`. There is no local list of accounts to fall back on. If the server
 * is unreachable the screen says so and names the address it tried, the same
 * way `api.ts` does, because a sign-in that silently succeeds against nothing
 * is the failure mode this product keeps having to design against.
 *
 * The number itself never leaves the device -- see `danh-tinh.ts` for what
 * that is worth and what it is not. The screen says so in a line under the
 * field, because a person typing their telephone number into a demo is owed
 * that sentence before they type it, not in a privacy policy afterwards.
 */
import React, { useRef, useState } from "react";
import { Platform, Pressable, ScrollView, Text, View } from "react-native";
import tokens from "../../../../../packages/shared/tokens.json";
import { ApiError, type Attempt, attemptFor, registerPerson } from "../../api";
import { Gradient, HERO_SUNSET, Scrim } from "../../navigation/Gradient";
import { Button, Field } from "../../ui/Kit";
import { radius, space, type, usePalette } from "../../theme";
import type { NguoiDung } from "../../navigation/nhom-demo";
import { chuDau, chuanHoaSo, idTuSo, tenHopLe } from "./danh-tinh";

const ON_SUNSET = tokens.color.light.accentInk;

type Pha =
  | { buoc: "nhap" }
  | { buoc: "dang-gui" }
  | { buoc: "hong"; loi: string };

export function DangKy({ onXong, onQuayLai }: {
  onXong: (nguoi: NguoiDung) => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const [so, setSo] = useState("");
  const [ten, setTen] = useState("");
  const [pha, setPha] = useState<Pha>({ buoc: "nhap" });

  // One book for the life of the screen, so a retry after a dropped response
  // re-sends the key the server already fingerprinted instead of asking it to
  // write a second time. Held in a ref: regenerating it on re-render would
  // defeat the whole point of keying the attempt.
  const soLanThu = useRef<Record<string, Attempt>>({});

  const sanSang = chuanHoaSo(so) !== null && tenHopLe(ten) && pha.buoc !== "dang-gui";

  async function gui() {
    const chuan = chuanHoaSo(so);
    if (chuan === null || !tenHopLe(ten)) return;
    setPha({ buoc: "dang-gui" });
    try {
      const id = idTuSo(chuan);
      const name = ten.trim();
      // The actor is the person themselves. That matters at the server:
      // naming an id that has no row is open to any member, but changing a
      // name that already exists requires `is_self`, so somebody returning
      // with the same number and a corrected spelling is only allowed through
      // because this header says they are who they are editing.
      await registerPerson(
        { id, name },
        id,
        attemptFor(soLanThu.current, `dang-ky:${id}:${name}`),
      );
      onXong({ id, personId: id, name, initials: chuDau(name) });
    } catch (loi) {
      // `ApiError` messages are already Vietnamese and already vetted for what
      // they may contain. Anything else is a programming error, and its
      // message could carry anything at all -- including, if this file ever
      // grows a throw that interpolates the input, the telephone number. So
      // unknown failures get a fixed sentence rather than `loi.message`.
      setPha({
        buoc: "hong",
        loi:
          loi instanceof ApiError
            ? loi.message
            : "Chưa đăng ký được. Thử lại sau một chút.",
      });
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: HERO_SUNSET[0] }}>
      <Gradient colors={HERO_SUNSET} style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }} />
      <Scrim alphas={[0.3, 0.1, 0.3]} />

      <ScrollView
        contentContainerStyle={{
          flexGrow: 1,
          paddingHorizontal: space.md,
          paddingTop: Platform.OS === "ios" ? 52 : 36,
          paddingBottom: space.lg,
          gap: space.md,
        }}
        keyboardShouldPersistTaps="handled"
      >
        <View style={{ flexDirection: "row" }}>
          <Pressable
            onPress={onQuayLai}
            accessibilityRole="button"
            accessibilityLabel="Quay lại màn mở đầu"
            style={({ pressed }) => ({
              minHeight: 44,
              justifyContent: "center",
              paddingRight: space.sm,
              opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: ON_SUNSET }}>← Quay lại</Text>
          </Pressable>
        </View>

        {/* The heading sits on the violet third of the ramp, where white is
            legal outright. Everything smaller lives on the card below, which
            brings its own ground rather than trusting the scrim. */}
        <View style={{ gap: space.xs, marginBottom: space.xs }}>
          <Text style={{ ...type.h1, color: ON_SUNSET }}>Vào Rủ Đi</Text>
          <Text style={{ ...type.body, color: ON_SUNSET }}>
            Nhập số của bạn. Số cũ thì vào lại đúng tài khoản cũ, số mới thì tạo tài khoản mới.
          </Text>
        </View>

        <View
          style={{
            backgroundColor: c.card,
            borderRadius: radius.base,
            padding: space.md,
            gap: space.md,
          }}
        >
          <Field
            label="Số điện thoại"
            value={so}
            onChangeText={(t) => {
              setSo(t);
              if (pha.buoc === "hong") setPha({ buoc: "nhap" });
            }}
            keyboardType="number-pad"
            // A shape, not a specimen. A literal example number here is what
            // `repo_guard.py` refuses on sight -- correctly, since it cannot
            // tell an invented number from somebody's real one -- and the mask
            // says what the field wants without spending that argument.
            placeholder="09xx xxx xxx"
          />
          {/* Shown always, not only on error. Somebody deciding whether to
              type their number needs this before they type it. */}
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Số này chỉ nằm trên máy bạn. App không gửi số lên máy chủ và không
            lưu số ở đâu cả — nó chỉ dùng để nhận ra bạn khi quay lại.
          </Text>

          <Field
            label="Tên hiển thị"
            value={ten}
            onChangeText={(t) => {
              setTen(t);
              if (pha.buoc === "hong") setPha({ buoc: "nhap" });
            }}
            placeholder="Tên bạn muốn cả nhóm thấy"
          />
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Tên này hiện cho cả nhóm, và hiện trên trang đòi tiền mà người ngoài
            nhóm mở được. Đặt tên bạn thấy thoải mái khi người lạ đọc.
          </Text>

          {pha.buoc === "hong" ? (
            // `alert` so a screen reader speaks the refusal without being
            // moved: the person is still in the field they were typing in.
            <View
              role="alert"
              style={{
                backgroundColor: c.accentSoft,
                borderColor: c.warn,
                borderWidth: 1,
                borderRadius: radius.base,
                padding: space.sm,
              }}
            >
              <Text style={{ ...type.body, color: c.warn }}>{pha.loi}</Text>
            </View>
          ) : null}

          <Button
            label={pha.buoc === "dang-gui" ? "Đang gửi…" : "Tiếp tục"}
            onPress={gui}
            disabled={!sanSang}
          />

          {/* The refusal a person can actually act on, and the only one this
              screen can know before asking the server. Kept under the button
              rather than in the error box so it reads as guidance rather than
              as a failure that already happened. */}
          {so.trim() !== "" && chuanHoaSo(so) === null ? (
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Chưa đúng dạng số di động Việt Nam: 10 số bắt đầu bằng 03, 05, 07,
              08 hoặc 09 — hoặc viết theo dạng +84 rồi 9 số còn lại.
            </Text>
          ) : null}
        </View>
      </ScrollView>
    </View>
  );
}
