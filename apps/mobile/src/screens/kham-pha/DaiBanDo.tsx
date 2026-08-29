import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import type { Place } from "./places";

/**
 * The strip along the bottom of the mockup, drawn from the coordinates the
 * server actually sent.
 *
 * There is no basemap and the caption says so. Pins are placed by normalising
 * each place's lat/lng into the box, so the *relative* arrangement is real
 * data -- north is up, two places near each other look near each other -- and
 * nothing here implies a street it cannot draw. A tile layer is an API key, a
 * native module and an attribution requirement; none of that is on the hero
 * path this PoC is proving.
 */
export function DaiBanDo({ places }: { places: Place[] }) {
  const c = usePalette();
  const H = 132;
  const co = places.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));
  if (co.length === 0) return null;

  const lats = co.map((p) => p.lat);
  const lngs = co.map((p) => p.lng);
  const spanLat = Math.max(...lats) - Math.min(...lats) || 1;
  const spanLng = Math.max(...lngs) - Math.min(...lngs) || 1;
  const minLat = Math.min(...lats);
  const minLng = Math.min(...lngs);

  return (
    <View style={{ gap: space.xs }}>
      <View
        style={{
          height: H,
          borderRadius: radius.base,
          borderColor: c.line,
          borderWidth: 1,
          backgroundColor: c.splitSoft,
          overflow: "hidden",
        }}
      >
        {co.map((p) => {
          // 10% inset each side so a pin at the extreme still sits inside.
          const x = 10 + ((p.lng - minLng) / spanLng) * 80;
          const y = 82 - ((p.lat - minLat) / spanLat) * 64;
          const noiBat = p.match?.source === "ai";
          return (
            <View
              key={p.id}
              accessibilityLabel={p.name}
              style={{
                position: "absolute",
                left: `${x}%`,
                top: `${y}%`,
                width: 14,
                height: 14,
                borderRadius: 7,
                backgroundColor: noiBat ? c.ai : c.accent,
                borderColor: c.card,
                borderWidth: 2,
              }}
            />
          );
        })}
      </View>
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        Vị trí tương đối của {co.length} chỗ, từ toạ độ máy chủ gửi. Chưa phải bản đồ thật.
      </Text>
    </View>
  );
}
