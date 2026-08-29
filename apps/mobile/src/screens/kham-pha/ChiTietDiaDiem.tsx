/** One place, in full. Mockup screen 3 of
 *  `product/features/02-kham-pha-va-goi-y-dia-diem.png`.
 *
 * The reason this screen exists is the purple card two thirds of the way down.
 * Everything above it -- rating, distance, price band, opening hours -- is
 * available on a dozen other apps. "Phù hợp với nhóm bạn vì budget ~250k/người
 * và thích không gian ngoài trời" is the thing only this product can say, and
 * rd-be-05's brief is explicit that the sentence, not the percentage, is what
 * makes it believable.
 *
 * So the layout puts weight there: the reason card is full width, carries the
 * `ai` tone, and is the only element on the screen allowed to use it.
 */
import React, { useState } from "react";
import { Linking, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card } from "../../ui/Kit";
import { AnhDiaDiem, Ruy } from "./AnhDiaDiem";
import { HuyHieuMatch, TheLyDoAi } from "./NhanAi";
import { DaiBanDo } from "./DaiBanDo";
import { CheckIn } from "./CheckIn";
import type { NguoiDung } from "../../navigation/nhom-demo";
import type { Nhom as NhomWire } from "../vao-cua/cong-api";
import {
  formatDistance,
  formatKinds,
  formatPricePerPerson,
  formatRating,
  type Place,
} from "./places";

export function ChiTietDiaDiem({ place, nguoi, nhom, onQuayLai }: {
  place: Place;
  /** Who the app is acting as. F46's write is authorised by this. */
  nguoi?: NguoiDung | null;
  /** The group a check-in would belong to. Null until this session has opened
   *  one -- see `VoTab`, which holds the handle. */
  nhom?: NhomWire | null;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const [daLuu, setDaLuu] = useState(false);

  return (
    <View style={{ flex: 1, backgroundColor: c.ground }}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: space.md }}
      >
        <AnhDiaDiem category={place.category} height={248} rounded={0}>
          <View
            style={{
              flex: 1,
              padding: space.md,
              paddingTop: Platform.OS === "ios" ? 44 : space.md,
              justifyContent: "space-between",
            }}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <NutTron label="Quay lại danh sách" glyph="‹" onPress={onQuayLai} />
              {place.flag ? <Ruy flag={place.flag} /> : null}
            </View>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end" }}>
              <HuyHieuMatch match={place.match} big />
              {place.photoCount > 0 ? (
                // Stated, not shown: the count is real data from the server,
                // the photos are not in this build. Saying "18 ảnh" over a
                // gallery that does not open would be a worse lie than the
                // drawn ramp underneath it, so it reads as a fact about the
                // place rather than as a button.
                <View
                  style={{
                    backgroundColor: c.card,
                    borderRadius: radius.small,
                    paddingHorizontal: space.xs,
                    paddingVertical: 3,
                  }}
                >
                  <Text style={{ ...type.micro, color: c.inkSoft }}>{place.photoCount} ảnh · chưa có</Text>
                </View>
              ) : null}
            </View>
          </View>
        </AnhDiaDiem>

        <View style={{ padding: space.md, gap: space.md, marginTop: -space.md }}>
          <Card>
            <Text style={{ ...type.h1, color: c.ink }}>{place.name}</Text>
            <Text style={{ ...type.label, color: c.inkFaint }}>{formatKinds(place.kinds)}</Text>

            <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: space.xs }}>
              <Text style={{ ...type.label, color: c.accent }}>★</Text>
              <Text style={{ ...type.label, color: c.ink }}>
                {formatRating(place.rating, place.ratingCount)} đánh giá
              </Text>
              <Text style={{ ...type.label, color: c.inkFaint }}>·</Text>
              <Text style={{ ...type.label, color: c.inkSoft }}>{formatDistance(place.distanceKm)}</Text>
              <Text style={{ ...type.label, color: c.inkFaint }}>·</Text>
              <Text style={{ ...type.label, color: c.inkSoft }}>{place.travelMinutes} phút</Text>
            </View>

            <DongThongTin nhan="Địa chỉ" giaTri={place.address} />
            <DongThongTin
              nhan="Giờ mở"
              giaTri={`${place.openNow ? "Đang mở cửa" : "Đang đóng"} · ${place.openHours}`}
              tone={place.openNow ? "split" : "warn"}
            />
          </Card>

          <Card>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
              <Text style={{ ...type.title, color: c.ink }}>Khoảng giá</Text>
              <Text style={{ ...type.amountSmall, color: c.split }}>
                {formatPricePerPerson(place.priceMinVnd, place.priceMaxVnd)}
              </Text>
            </View>

            {place.groupFit ? (
              <>
                <Text style={{ ...type.title, color: c.ink, marginTop: space.xs }}>Phù hợp với nhóm</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                  <Text style={{ ...type.label, color: c.inkSoft }}>
                    Nhóm {place.groupFit.minPeople}–{place.groupFit.maxPeople} người
                  </Text>
                  <Text style={{ ...type.label, color: c.inkFaint }}>·</Text>
                  <Text style={{ ...type.label, color: c.inkSoft }}>{place.groupFit.relation}</Text>
                </View>
              </>
            ) : null}

            {place.traits.length > 0 ? <ChipDacDiem traits={place.traits} /> : null}
          </Card>

          {/* The point of the screen. */}
          <TheLyDoAi match={place.match} />

          {/* F46. Below the reason card rather than in the bottom bar: the bar
              holds the two actions the mockup draws, and a check-in is not a
              third peer of "Chỉ đường" -- it is a record the group keeps, and
              it comes with the list of times they have kept it before. */}
          <CheckIn place={place} nguoi={nguoi ?? null} nhom={nhom ?? null} />

          <DaiBanDo places={[place]} />
        </View>
      </ScrollView>

      <View
        style={{
          flexDirection: "row",
          gap: space.sm,
          padding: space.md,
          paddingTop: space.sm,
          borderTopColor: c.line,
          borderTopWidth: 1,
          backgroundColor: c.ground,
        }}
      >
        <View style={{ flex: 1 }}>
          <Button
            label="Chỉ đường"
            onPress={() => {
              // Real behaviour, not a shell: hands the coordinates to whatever
              // map app the phone already has. No API key, no native module,
              // no tile bill -- and it works on web too.
              const q = `${place.lat},${place.lng}`;
              Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${q}`);
            }}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Button
            label={daLuu ? "Đã đánh dấu" : "Lưu địa điểm"}
            tone="quiet"
            onPress={() => setDaLuu((v) => !v)}
          />
        </View>
      </View>

      {daLuu ? (
        <Text
          accessibilityRole="alert"
          style={{ ...type.micro, color: c.inkFaint, paddingHorizontal: space.md, paddingBottom: space.sm }}
        >
          Đánh dấu này chỉ nằm trong phiên đang mở — chưa có chỗ lưu trên máy chủ.
        </Text>
      ) : null}
    </View>
  );
}

/** Label over value, so a long address wraps under its own name instead of
 *  pushing the label off the row. */
function DongThongTin({ nhan, giaTri, tone }: { nhan: string; giaTri: string; tone?: "split" | "warn" }) {
  const c = usePalette();
  const mau = tone === "split" ? c.split : tone === "warn" ? c.warn : c.ink;
  return (
    <View style={{ gap: 2, marginTop: space.xs }}>
      <Text style={{ ...type.micro, color: c.inkFaint }}>{nhan.toUpperCase()}</Text>
      <Text style={{ ...type.body, color: mau }}>{giaTri}</Text>
    </View>
  );
}

/** "BBQ · View đẹp · Ngồi ngoài trời · Chill" as chips.
 *
 *  Not the kit's `Choice`: nothing here is selectable, and giving a static
 *  label the shape of a control is how a demo audience ends up tapping
 *  something that cannot respond. Flat `accentSoft` ground, `ink` label,
 *  measured 14.22:1 in DESIGN.md. */
function ChipDacDiem({ traits }: { traits: string[] }) {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs, marginTop: space.xs }}>
      {traits.map((t) => (
        <View
          key={t}
          style={{
            backgroundColor: c.accentSoft,
            borderRadius: radius.pill,
            paddingHorizontal: space.sm,
            paddingVertical: 6,
          }}
        >
          <Text style={{ ...type.micro, color: c.ink }}>{t}</Text>
        </View>
      ))}
    </View>
  );
}

/** A round control on top of the ramp. Brings its own `card` ground because
 *  the brand layer underneath may not carry an icon at this size -- the same
 *  rule the badge follows. 44pt, which is the tap-target floor. */
function NutTron({ glyph, label, onPress }: { glyph: string; label: string; onPress: () => void }) {
  const c = usePalette();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: 44,
        height: 44,
        borderRadius: 22,
        backgroundColor: c.card,
        alignItems: "center",
        justifyContent: "center",
        opacity: pressed ? 0.8 : 1,
      })}
    >
      <Text style={{ fontSize: 26, lineHeight: 30, fontWeight: "700", color: c.ink }}>{glyph}</Text>
    </Pressable>
  );
}
