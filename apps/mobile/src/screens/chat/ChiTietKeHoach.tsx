/** Why this screen is one flat column, and why it has no total.
 *
 * The mockup draws "Ngày 1 / Ngày 2" tabs and a "tổng dự kiến" line. The
 * first version of the parser was written against that drawing, while
 * rd-be-04 was still unmerged, and every field name in the guess was wrong.
 * The wire that actually landed is `{kind, payload}` with a flat `stops`
 * list and no amount, no total, no per_person. Splitting the list on a
 * guess (by count, or by parsing `time_text` for a wrap-around) would put a
 * day boundary on screen the server never asserted. Adding the prices up
 * would invent a share, and this product has one splitter, on the server,
 * behind 41 hand-computed golden vectors.
 *
 * The photo slot is a token block with the first letter of the place name.
 * There is no place imagery in Git (the repo guard refuses binaries, and
 * the standing rule is that no real place goes in), and loading a URL of
 * grey rectangles is worse. `AnhDiaDiem` does the same honest substitution
 * on Khám phá; here the category mark is not available on every stop, so
 * the letter is what the stop actually gives us.
 */
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { khoangGia, type Chang, type KeHoach } from "./ke-hoach";

export function ChiTietKeHoach({
  keHoach,
  onBack,
}: {
  keHoach: KeHoach;
  onBack: () => void;
}) {
  const c = usePalette();
  return (
    <View style={{ flex: 1, backgroundColor: c.ground }}>
      <View
        style={{
          paddingHorizontal: space.md,
          paddingTop: space.md,
          paddingBottom: space.sm,
          gap: space.sm,
        }}
      >
        <Pressable
          onPress={onBack}
          accessibilityRole="button"
          accessibilityLabel="Quay lại đoạn chat"
          style={({ pressed }) => ({
            alignSelf: "flex-start",
            minHeight: 44,
            minWidth: 44,
            paddingHorizontal: space.sm,
            borderRadius: radius.control,
            borderWidth: 1,
            borderColor: c.lineStrong,
            alignItems: "center",
            justifyContent: "center",
            opacity: pressed ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "600", color: c.accent }}>Quay lại</Text>
        </Pressable>
        <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>
          Đề xuất bởi Rủ Đi AI ✦
        </Text>
        <Text style={{ ...type.h1, color: c.ink }}>{keHoach.tieuDe}</Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{
          paddingHorizontal: space.md,
          paddingBottom: space.xl,
          gap: space.md,
        }}
      >
        {keHoach.chang.map((ch, i) => (
          <HangChang
            key={`${ch.diaDiem.id}-${ch.gio}-${i}`}
            chang={ch}
            cuoi={i === keHoach.chang.length - 1}
          />
        ))}
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Khoảng giá là của từng chỗ, do máy chủ gửi. App không cộng.
        </Text>
      </ScrollView>
    </View>
  );
}

function HangChang({ chang, cuoi }: { chang: Chang; cuoi: boolean }) {
  const c = usePalette();
  const gia = khoangGia(chang.diaDiem);
  const chu = chang.diaDiem.ten.trim().charAt(0) || "?";
  return (
    <View style={{ flexDirection: "row", gap: space.sm }}>
      <View style={{ width: 16, alignItems: "center" }}>
        <View
          style={{
            width: 10,
            height: 10,
            borderRadius: radius.pill,
            backgroundColor: c.ai,
            marginTop: 4,
          }}
        />
        {cuoi ? null : (
          <View style={{ flex: 1, width: 2, backgroundColor: c.line, marginTop: 2 }} />
        )}
      </View>

      <View style={{ flex: 1, gap: 2, paddingBottom: cuoi ? 0 : space.md }}>
        <Text style={{ ...type.amountSmall, color: c.ink }}>{chang.gio}</Text>
        <Text style={{ ...type.title, color: c.ink }}>{chang.diaDiem.ten}</Text>
        {chang.ghiChu ? <Text style={{ ...type.body, color: c.inkSoft }}>{chang.ghiChu}</Text> : null}
        {chang.diaDiem.diaChi ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>{chang.diaDiem.diaChi}</Text>
        ) : null}
        {gia ? <Text style={{ ...type.label, color: c.inkSoft }}>{gia}</Text> : null}
      </View>

      <View
        style={{
          width: 56,
          height: 56,
          borderRadius: radius.small,
          backgroundColor: c.accentSoft,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ ...type.title, color: c.accent }}>{chu}</Text>
      </View>
    </View>
  );
}
