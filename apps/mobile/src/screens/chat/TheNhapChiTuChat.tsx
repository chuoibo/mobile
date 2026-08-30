/** The purple draft card that grows under one chat bubble.
 *
 * Lead tone is `ai`: the machine produced this and a person can still change
 * it. Teal touches only the amount. The card never says an expense was
 * written -- `CAU_CHUA_GHI_KHOAN_CHI` sits inside the card, above the
 * dismiss control, because that sentence is the condition for acting, not a
 * footnote about the control.
 */
import React from "react";
import { Pressable, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { dinhDangTienVnd } from "./ke-hoach";
import {
  CAU_CHUA_GHI_KHOAN_CHI,
  type TrangNhapTuChat,
} from "./nhap-tu-chat";

const HIT = 44;

export function TheNhapChiTuChat({
  trang,
  onDong,
}: {
  trang: TrangNhapTuChat;
  onDong: () => void;
}) {
  const c = usePalette();

  if (trang.kind === "chua-goi") return null;

  return (
    <View
      style={{
        backgroundColor: c.aiSoft,
        borderColor: c.ai,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.sm,
      }}
    >
      {trang.kind === "dang-doc" ? (
        <Text style={{ ...type.body, color: c.inkSoft }}>Đang đọc tin nhắn…</Text>
      ) : null}

      {trang.kind === "hong" ? (
        <Text style={{ ...type.body, color: c.ink }}>{trang.loi}</Text>
      ) : null}

      {trang.kind === "khong-thay" ? (
        <Text style={{ ...type.body, color: c.ink }}>{trang.reason}</Text>
      ) : null}

      {trang.kind === "co-nhap" ? (
        <>
          <Text style={{ ...type.title, color: c.ink }}>{trang.title}</Text>
          <Text
            style={{
              ...type.amountSmall,
              color: c.split,
              fontVariant: ["tabular-nums"],
            }}
          >
            {dinhDangTienVnd(trang.amountVnd)}
          </Text>
          <Text style={{ ...type.body, color: c.ink }}>
            Người trả: {trang.tenNguoiTra}
          </Text>
          <Text style={{ ...type.body, color: c.ink }}>
            Người chia: {trang.tenNguoiChia.join(", ")}
          </Text>
          {trang.canXemLai ? (
            <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>
              Cần xem lại
            </Text>
          ) : null}
          <Text style={{ ...type.body, color: c.ink }}>{CAU_CHUA_GHI_KHOAN_CHI}</Text>
        </>
      ) : null}

      {trang.kind !== "dang-doc" ? (
        <Pressable
          onPress={onDong}
          accessibilityRole="button"
          accessibilityLabel="Đóng"
          style={({ pressed }) => ({
            minHeight: HIT,
            borderRadius: radius.control,
            borderWidth: 1,
            borderColor: c.lineStrong,
            alignItems: "center",
            justifyContent: "center",
            opacity: pressed ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "600", color: c.ink }}>Đóng</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
