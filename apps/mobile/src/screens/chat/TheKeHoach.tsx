/** Why a card is parsed before a single field of it is drawn.
 *
 * The AI's answer arrives as `card`, a free dict. Rendering `undefined` for a
 * missing time looks like a styling bug and gets chased in the wrong file
 * for an hour. `theTuCard` already drops a broken row and keeps the rest;
 * this file exists to respect that answer, including the `null` one.
 *
 * `null` is not a crash and it is not a canned itinerary. It is the honest
 * sentence that the card could not be read. Inventing a title or a stop to
 * fill the hole would put a plan on screen the server never asserted, which
 * is the thing the acceptance criteria forbid.
 *
 * The itinerary kind stops at two or three stages and a real button. Screen
 * 2 is a different surface; inlining the whole timeline here would make the
 * thread unreadably long and would hide that the rest of the plan is a tap
 * away. There is no day tab and no total, because the wire has neither.
 */
import React from "react";
import { Pressable, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { keHoachTuCard, khoangGia, theTuCard, type DiaDiem, type KeHoach } from "./ke-hoach";

export function TheKeHoach({
  card,
  onXemChiTiet,
}: {
  card: unknown;
  onXemChiTiet: (keHoach: KeHoach) => void;
}) {
  const c = usePalette();
  const the = theTuCard(card);

  if (the === null) {
    return (
      <View
        style={{
          backgroundColor: c.card,
          borderColor: c.ai,
          borderWidth: 1,
          borderRadius: radius.base,
          padding: space.sm,
          gap: space.xs,
        }}
      >
        <Text style={{ ...type.body, color: c.ink }}>Thẻ này không đọc được.</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Máy chủ gửi một thẻ mà app không nhận dạng được, nên không vẽ gì từ nó.
        </Text>
      </View>
    );
  }

  return (
    <View
      style={{
        backgroundColor: c.card,
        borderColor: c.ai,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.sm,
        gap: space.sm,
      }}
    >
      {the.kind === "text" ? (
        <Text style={{ ...type.body, color: c.ink }}>{the.text}</Text>
      ) : null}

      {the.kind === "places" ? (
        <>
          {the.intro ? <Text style={{ ...type.body, color: c.ink }}>{the.intro}</Text> : null}
          {the.diaDiem.map((d) => (
            <DongDiaDiem key={d.id} diaDiem={d} />
          ))}
        </>
      ) : null}

      {the.kind === "itinerary" ? (
        <>
          <Text style={{ ...type.title, color: c.ink }}>{the.tieuDe}</Text>
          {the.chang.slice(0, 3).map((ch, i) => (
            <View key={`${ch.diaDiem.id}-${ch.gio}-${i}`} style={{ gap: 2 }}>
              <Text style={{ ...type.label, color: c.inkSoft, fontVariant: ["tabular-nums"] }}>
                {ch.gio}
              </Text>
              <Text style={{ ...type.body, color: c.ink }}>{ch.diaDiem.ten}</Text>
            </View>
          ))}
          <Pressable
            onPress={() => {
              const dayDu = keHoachTuCard(card);
              if (dayDu) onXemChiTiet(dayDu);
            }}
            accessibilityRole="button"
            accessibilityLabel="Xem chi tiết kế hoạch"
            style={({ pressed }) => ({
              minHeight: 44,
              borderRadius: radius.control,
              borderWidth: 1,
              borderColor: c.lineStrong,
              alignItems: "center",
              justifyContent: "center",
              paddingHorizontal: space.md,
              opacity: pressed ? 0.85 : 1,
            })}
          >
            <Text style={{ ...type.body, fontWeight: "600", color: c.accent }}>
              Xem chi tiết kế hoạch
            </Text>
          </Pressable>
        </>
      ) : null}
    </View>
  );
}

/** One place row. A missing field is a missing line, not the word
 *  "undefined" sitting where an address should be.
 *
 *  Exported because the poll composer picks its options from these same
 *  places. Drawing a second, thinner place row there would let the two
 *  drift, and then the same restaurant reads one way in the AI's suggestion
 *  and another way on the ballot the group votes with. */
export function DongDiaDiem({ diaDiem }: { diaDiem: DiaDiem }) {
  const c = usePalette();
  const gia = khoangGia(diaDiem);
  return (
    <View style={{ gap: 2 }}>
      <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>{diaDiem.ten}</Text>
      {diaDiem.loai ? <Text style={{ ...type.micro, color: c.inkFaint }}>{diaDiem.loai}</Text> : null}
      {diaDiem.diaChi ? <Text style={{ ...type.label, color: c.inkSoft }}>{diaDiem.diaChi}</Text> : null}
      {gia ? <Text style={{ ...type.label, color: c.inkSoft }}>{gia}</Text> : null}
      {diaDiem.danhGia !== undefined ? (
        <Text style={{ ...type.micro, color: c.inkSoft }}>Đánh giá {diaDiem.danhGia}</Text>
      ) : null}
      {diaDiem.cachKm !== undefined ? (
        <Text style={{ ...type.micro, color: c.inkSoft }}>{diaDiem.cachKm} km</Text>
      ) : null}
    </View>
  );
}
