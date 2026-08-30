/** The purple card after a screenshot has been read.
 *
 * Lead tone is `ai`: the machine produced this and a person can still change
 * it. Teal touches only the amount. There is no line-item list and no person
 * name -- the wire has neither, and drawing empty slots for them would be
 * the defect this screen exists to avoid.
 *
 * The "nothing was written" sentence sits inside the card, above the
 * confirm button, because it is the condition for pressing, not a footnote.
 */
import React from "react";
import { Pressable, Text, View } from "react-native";
import type { ScreenshotScanWire } from "../api";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { radius, space, type, usePalette } from "../theme";
import { CAU_CHUA_GHI_QUET_ANH, tenNguonQuetAnh } from "./quet-anh";

const HIT = 44;

export function KetQuaQuetAnh({
  ketQua,
  onChot,
  onHuy,
}: {
  ketQua: ScreenshotScanWire;
  onChot: () => void;
  onHuy: () => void;
}): React.JSX.Element {
  const c = usePalette();

  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <Pressable
        onPress={onHuy}
        accessibilityRole="button"
        accessibilityLabel="Huỷ"
        style={{ minHeight: HIT, justifyContent: "center", alignSelf: "flex-start" }}
      >
        <Text style={{ ...type.body, fontWeight: "600", color: c.ink }}>Huỷ</Text>
      </Pressable>

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
        <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>
          {tenNguonQuetAnh(ketQua.source)}
        </Text>
        <Text style={{ ...type.title, color: c.ink }}>{ketQua.merchant}</Text>
        <Text
          style={{
            ...type.amountSmall,
            color: c.split,
            fontVariant: ["tabular-nums"],
          }}
        >
          {formatVnd(ketQua.total_vnd)}đ
        </Text>
        {ketQua.occurred_on ? (
          <Text style={{ ...type.body, color: c.ink }}>Ngày {ketQua.occurred_on}</Text>
        ) : null}
        {ketQua.needs_review ? (
          <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>Cần xem lại</Text>
        ) : null}
        <Text style={{ ...type.body, color: c.ink }}>{CAU_CHUA_GHI_QUET_ANH}</Text>
        <Pressable
          onPress={onChot}
          accessibilityRole="button"
          accessibilityLabel="Chốt vào form nhập tay"
          style={({ pressed }) => ({
            minHeight: HIT,
            borderRadius: radius.control,
            backgroundColor: c.ai,
            alignItems: "center",
            justifyContent: "center",
            opacity: pressed ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "700", color: c.aiInk }}>
            Chốt vào form nhập tay
          </Text>
        </Pressable>
      </View>
    </View>
  );
}
