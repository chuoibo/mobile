/** The vote card. It draws numbers it is given; it does not count.
 *
 * Every figure on this surface (`phieu`, `phanTram`, `dangDan`, `dangHoa`,
 * `luaChonCuaToi`, `soNguoiDaBoPhieu`) arrives on `ketQua` from `binh-chon.ts`.
 * Recalculating any of them here would put a second counter on screen, and
 * two counters is how a tie becomes a winner by accident.
 *
 * WHY NO "71%" NEXT TO THE BAR, when the mockup draws one. ADR-0009 decision
 * 4 and the Lead note of 2026-08-29 ban a percentage on any screen,
 * computable or not, and `tests/receipt.test.mjs` holds that line against an
 * exact list. A vote share is computable and is not a model's confidence, so
 * there is an argument it should be exempt -- but that argument is an ADR to
 * open, not a regular expression to slip past on the way to a demo. So
 * `phanTram` reaches this file and is spent entirely on the width of the bar.
 * Nothing is lost by it: the ballot count is the truth, it is printed in
 * words on every row, and it is what the screen reader reads.
 *
 * A tie is a result. The mockup crowns one row. When `dangHoa` is true this
 * card crowns nobody, shows the "Hoà" chip, and lets `cauKetQua` say the
 * names. Picking a winner by list order would be the app casting the last
 * vote, which nobody asked it to.
 */
import React from "react";
import { Pressable, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { toggleState } from "../../ui/a11y";
import { Card } from "../../ui/Kit";
import { cauKetQua, type KetQuaBinhChon, type KetQuaLuaChon } from "./binh-chon";

export function TheBinhChon({
  ketQua,
  soThanhVien,
  dangGui,
  onChon,
}: {
  ketQua: KetQuaBinhChon;
  soThanhVien: number;
  dangGui: boolean;
  onChon: (optionId: string) => void;
}) {
  const c = usePalette();

  return (
    <Card>
      <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>{ketQua.cauHoi}</Text>

      {ketQua.dangHoa ? (
        <View style={{ gap: space.xs }}>
          <View
            style={{
              alignSelf: "flex-start",
              backgroundColor: c.aiSoft,
              borderRadius: radius.pill,
              paddingHorizontal: space.sm,
              paddingVertical: 4,
            }}
          >
            <Text style={{ ...type.micro, fontWeight: "700", color: c.ai }}>Hoà</Text>
          </View>
          <Text style={{ ...type.micro, color: c.inkSoft }}>{cauKetQua(ketQua)}</Text>
        </View>
      ) : null}

      <View accessibilityRole="radiogroup" aria-label={ketQua.cauHoi} style={{ gap: space.xs }}>
        {ketQua.ketQua.map((hang) => (
          <HangLuaChon
            key={hang.optionId}
            hang={hang}
            cuaToi={ketQua.luaChonCuaToi === hang.optionId}
            // A crown on a tied row would name a winner the count did not.
            vuongMien={!ketQua.dangHoa && hang.dangDan}
            dangGui={dangGui}
            onChon={onChon}
          />
        ))}
      </View>

      <Text style={{ ...type.micro, color: c.inkSoft }}>
        {ketQua.soNguoiDaBoPhieu}/{soThanhVien} thành viên đã bỏ phiếu
      </Text>
    </Card>
  );
}

/** One ballot row. The spoken name carries the count, not just the bar. */
function HangLuaChon({
  hang,
  cuaToi,
  vuongMien,
  dangGui,
  onChon,
}: {
  hang: KetQuaLuaChon;
  cuaToi: boolean;
  vuongMien: boolean;
  dangGui: boolean;
  onChon: (optionId: string) => void;
}) {
  const c = usePalette();

  return (
    <Pressable
      onPress={() => onChon(hang.optionId)}
      disabled={dangGui}
      // `disabled` on a Pressable emits `aria-disabled` by itself; the tick
      // needs `toggleState`, because `accessibilityState` reaches no DOM on
      // react-native-web 0.21.2.
      {...toggleState("radio", cuaToi)}
      accessibilityLabel={nhanDocHang(hang)}
      style={({ pressed }) => ({
        minHeight: 44,
        paddingHorizontal: space.sm,
        paddingVertical: space.xs,
        gap: space.xs,
        borderRadius: radius.base,
        borderWidth: 1,
        borderColor: hang.dangDan ? c.ai : c.line,
        backgroundColor: hang.dangDan ? c.aiSoft : "transparent",
        opacity: dangGui ? 0.6 : pressed ? 0.85 : 1,
        flexDirection: "row",
        alignItems: "center",
      })}
    >
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: 11,
          borderWidth: cuaToi ? 2 : 1,
          borderColor: cuaToi ? c.ai : c.line,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {cuaToi ? (
          <View
            style={{
              width: 10,
              height: 10,
              borderRadius: 5,
              backgroundColor: c.ai,
            }}
          />
        ) : null}
      </View>

      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
          {vuongMien ? (
            <Text style={{ ...type.body }} accessibilityElementsHidden>
              👑
            </Text>
          ) : null}
          <Text
            numberOfLines={1}
            style={{ ...type.body, color: c.ink, flex: 1, minWidth: 0 }}
          >
            {hang.nhan}
          </Text>
          <Text
            style={{
              ...type.micro,
              color: c.inkSoft,
              fontVariant: ["tabular-nums"],
              flexShrink: 0,
            }}
          >
            {hang.phieu} phiếu
          </Text>
        </View>

        <View
          accessibilityElementsHidden
          importantForAccessibility="no"
          style={{
            height: 6,
            backgroundColor: c.line,
            borderRadius: 3,
            overflow: "hidden",
          }}
        >
          <View
            style={{
              height: 6,
              width: `${hang.phanTram}%`,
              backgroundColor: hang.dangDan ? c.ai : c.inkFaint,
              borderRadius: 3,
            }}
          />
        </View>
      </View>
    </Pressable>
  );
}

/** Spoken form of a row: name, ballots, and whether it is leading.
 *
 *  The bar is hidden from the reader (`accessibilityElementsHidden`), so this
 *  string is the only place a non-sighted person learns the standings. It
 *  carries the count, which is the same number a sighted person reads; the
 *  bar's share is not restated, because it is a redrawing of that count and
 *  not a second fact. */
function nhanDocHang(hang: KetQuaLuaChon): string {
  const dan = hang.dangDan ? "đang dẫn" : "không đang dẫn";
  return `${hang.nhan}, ${hang.phieu} phiếu, ${dan}`;
}
