/** The vote itself, as a screen. It draws the tally it is given; it does not count.
 *
 * `TheBinhChon` is the same idea living inside a chat thread: a card among
 * messages, options the companion proposed, purple lead because a machine
 * asked the question. This file is the dedicated surface behind the vote
 * *route*. The person opened it, the person is voting, so the lead is
 * `accent` -- DESIGN.md's tone for a human action -- and teal never enters,
 * because teal means money is being divided and nobody here owes a đồng.
 *
 * A TIE IS A RESULT. When `bang.laHoa` the result card is headed "Hoà",
 * lists every name in `tenCacBenHoa`, and names no winner. Crowning
 * `leading_option_ids[0]` would be this app casting the deciding vote, which
 * is the failure `ket-qua.ts` exists to make unrepresentable. The rows stay
 * even: the bar is a redrawing of the count, not a ribbon.
 *
 * WHY THE BAR IS THE ROW, not a strip under it. A number sitting next to a
 * thing you press is one object; a number sitting under a thing you press is
 * two, and the second one is what a thumb misses. `phanTram` is spent only
 * on the width of that fill, and is never printed. That is a choice made
 * here, not a rule inherited from anywhere: with the group sizes this app is
 * built for, "67%" is four people, and a rounded share reads as more
 * precision than three ballots have. The count is the truth, so the count is
 * what every row says in words.
 *
 * Pure: props in, callbacks out. The parent owns the wire, the in-flight
 * option id, and the close. A fetch in here would be a second copy of that
 * ownership, and the two would disagree the moment a ballot landed.
 */
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { toggleState } from "../../ui/a11y";
import { Button, Card, Screen } from "../../ui/Kit";
import type { BangKetQua, HangLuaChon } from "./ket-qua";

export function BinhChon({
  bang,
  dangGui,
  loi,
  laNguoiMo,
  onChonPhieu,
  onDong,
  onQuayLai,
}: {
  bang: BangKetQua;
  /** The option id currently on the wire, or null. Non-null disables every
   *  row so a second tap cannot race the first; the sending row says so. */
  dangGui: string | null;
  loi: string | null;
  laNguoiMo: boolean;
  onChonPhieu: (optionId: string) => void;
  onDong: () => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const dangBay = dangGui !== null;
  const khoaHang = bang.daDong || dangBay;
  const hint =
    bang.tongPhieu === 0 ? "Chưa ai bỏ phiếu" : `${bang.tongPhieu} phiếu`;

  return (
    <Screen
      title={bang.cauHoi}
      hint={hint}
      gap={space.lg}
      footer={
        <>
          {laNguoiMo && !bang.daDong ? (
            <Button
              label="Đóng bình chọn"
              tone="quiet"
              onPress={onDong}
              disabled={dangBay}
            />
          ) : null}
          <Button label="Quay lại" tone="ghost" onPress={onQuayLai} disabled={dangBay} />
        </>
      }
    >
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: space.md, paddingBottom: space.sm }}
        // Keyboard tab-stop on the scroller itself: a column of radios is
        // focusable, but the region that holds them still needs its own stop
        // or a keyboard cannot scroll past the first few. See KyNiem.
        tabIndex={0}
      >
        {loi ? (
          <Card>
            <Text style={{ ...type.body, color: c.ink }} accessibilityRole="alert">
              {loi}
            </Text>
          </Card>
        ) : null}

        <View
          accessibilityRole="radiogroup"
          aria-label={bang.cauHoi}
          style={{ gap: space.xs }}
        >
          {bang.hang.map((hang) => (
            <HangPhieu
              key={hang.optionId}
              hang={hang}
              daDong={bang.daDong}
              dangGuiHang={dangGui === hang.optionId}
              khoa={khoaHang}
              onChon={() => onChonPhieu(hang.optionId)}
            />
          ))}
        </View>

        {bang.daDong ? <TheKetQua bang={bang} /> : (
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Đang mở, đổi phiếu được
          </Text>
        )}
      </ScrollView>
    </Screen>
  );
}

/** One ballot row. The bar is the row's ground, not a second control under it. */
function HangPhieu({
  hang,
  daDong,
  dangGuiHang,
  khoa,
  onChon,
}: {
  hang: HangLuaChon;
  daDong: boolean;
  dangGuiHang: boolean;
  khoa: boolean;
  onChon: () => void;
}) {
  const c = usePalette();

  return (
    <Pressable
      onPress={onChon}
      disabled={khoa}
      // `accessibilityState` is dead on react-native-web 0.21.2 -- it reaches
      // the DOM as nothing, so a radio that only declared `checked` there
      // announced identically ticked and unticked. `toggleState` is the
      // spelling that survives (`aria-checked`), and native reads it too.
      {...toggleState("radio", hang.laPhieuCuaToi)}
      accessibilityLabel={nhanDocHang(hang, daDong, dangGuiHang)}
      style={({ pressed }) => ({
        minHeight: 44,
        overflow: "hidden",
        borderRadius: radius.base,
        borderWidth: 1,
        borderColor: hang.laPhieuCuaToi ? c.accent : c.lineStrong,
        backgroundColor: c.card,
        opacity: khoa && !dangGuiHang ? 1 : pressed ? 0.85 : 1,
        justifyContent: "center",
      })}
    >
      {/* Width is the only thing `phanTram` is for. Hidden from the reader
          because the spoken name already carries the count; restating the
          share would print a percentage, which this product refuses. */}
      <View
        accessibilityElementsHidden
        importantForAccessibility="no"
        pointerEvents="none"
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: `${hang.phanTram}%`,
          backgroundColor: c.accentSoft,
        }}
      />
      <View
        style={{
          minHeight: 44,
          paddingHorizontal: space.sm,
          paddingVertical: space.xs,
          flexDirection: "row",
          alignItems: "center",
          gap: space.sm,
        }}
      >
        <View
          style={{
            width: 22,
            height: 22,
            borderRadius: 11,
            borderWidth: hang.laPhieuCuaToi ? 2 : 1,
            borderColor: hang.laPhieuCuaToi ? c.accent : c.lineStrong,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: hang.laPhieuCuaToi ? c.accent : "transparent",
          }}
        >
          {hang.laPhieuCuaToi ? (
            <Text style={{ ...type.micro, color: c.accentInk, fontWeight: "700" }}>✓</Text>
          ) : null}
        </View>
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <Text numberOfLines={1} style={{ ...type.body, color: c.ink }}>
            {hang.nhan}
          </Text>
          {hang.tenDiaDiem ? (
            <Text numberOfLines={1} style={{ ...type.micro, color: c.inkSoft }}>
              {hang.tenDiaDiem}
            </Text>
          ) : null}
          {hang.laPhieuCuaToi ? (
            <Text style={{ ...type.micro, fontWeight: "700", color: c.ink }}>
              Phiếu của bạn
            </Text>
          ) : null}
          {dangGuiHang ? (
            <Text style={{ ...type.micro, color: c.inkSoft }}>Đang gửi...</Text>
          ) : null}
        </View>
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
    </Pressable>
  );
}

/** Spoken form of a row: name, count, mine, and whether the tap still works.
 *
 *  The bar is hidden from the reader, so this string is the only place a
 *  non-sighted person learns the standings. It carries the count a sighted
 *  person reads; the bar's share is not restated. When the vote is closed
 *  the row says so -- `disabled` emits `aria-disabled`, but a name that
 *  only says "radio, checked" does not tell someone why the tap died. */
function nhanDocHang(hang: HangLuaChon, daDong: boolean, dangGuiHang: boolean): string {
  const cuaToi = hang.laPhieuCuaToi ? "phiếu của bạn" : "không phải phiếu của bạn";
  const dong = daDong ? "đã đóng, không chọn được" : dangGuiHang ? "đang gửi" : "";
  return [hang.nhan, `${hang.phieu} phiếu`, cuaToi, dong].filter(Boolean).join(", ");
}

/** Closed-vote card. Exists only after close; while open the line above is enough.
 *
 *  `laHoa` is read as a boolean, not inferred from how many names arrived.
 *  The names listed are `tenCacBenHoa` in the order `ket-qua.ts` already
 *  put them -- the ballot's own order -- and every one of them is drawn.
 *  Dropping a name to "keep the card short" would hide a side the group
 *  actually tied with. */
function TheKetQua({ bang }: { bang: BangKetQua }) {
  const c = usePalette();

  if (bang.laHoa) {
    return (
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Hoà</Text>
        {bang.tenCacBenHoa.map((ten) => (
          <Text key={ten} style={{ ...type.body, color: c.ink }}>
            {ten}
          </Text>
        ))}
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {bang.tenCacBenHoa.length === 2
            ? "Hai bên bằng phiếu. Nhóm chọn tiếp giúp mình."
            : "Các bên bằng phiếu. Nhóm chọn tiếp giúp mình."}
        </Text>
      </Card>
    );
  }

  const tenThang =
    bang.optionIdThang === null
      ? null
      : bang.hang.find((h) => h.optionId === bang.optionIdThang)?.nhan ?? null;

  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Kết quả</Text>
      <Text style={{ ...type.body, color: c.ink }}>
        {tenThang === null
          ? "Cuộc bình chọn đã đóng. Chưa có bên nào được chọn."
          : `${tenThang} được nhóm chọn.`}
      </Text>
    </Card>
  );
}
