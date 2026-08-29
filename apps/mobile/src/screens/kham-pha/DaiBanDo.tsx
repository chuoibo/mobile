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
 *
 * ## Why the strip is named once and the dots are not named at all
 *
 * Each dot used to carry `accessibilityLabel={p.name}`, which reaches the
 * browser as `<div aria-label="…">` with no role. ARIA prohibits a name there
 * and screen readers drop it, so all twelve names were unreadable rather than
 * merely terse -- axe called it `aria-prohibited-attr`, serious, twelve times.
 *
 * The repair is not twelve buttons. The seed catalogue is two cities 200 km
 * apart -- eight places in Đà Lạt, four in TP.HCM -- so a linear projection
 * puts eight dots within 1-2 px of each other (`Tiệm Nướng Xóm Lào` and
 * `Chill Đêm Đà Lạt` land on the same pixel at 390 px wide). Twelve tab stops
 * on marks a pointer can never separately hit is a worse defect than the one
 * it replaces, and it would fail WCAG 2.5.8 for the sighted half of the same
 * audience.
 *
 * So the strip is treated as what it is -- one diagram -- and named as one,
 * carrying every place name in the order drawn. That is the pattern WAI gives
 * for a simple image with a text alternative, and it is the only reading of
 * this picture that is true: at this scale the information really is "these
 * twelve, in two clusters", not "this dot is that restaurant". Every place is
 * separately reachable, named and pressable in the card grid directly above.
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
        accessibilityRole="image"
        // Every name the picture contains, in the order it draws them, said
        // once. `image` is what react-native-web turns into `role="img"` and
        // what native reads as a graphic, so the one prop serves both.
        accessibilityLabel={
          `Sơ đồ vị trí tương đối của ${co.length} chỗ: ` +
          co.map((p) => p.name).join(", ")
        }
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
              // No name here on purpose: see the header. The mark is a stroke
              // inside a named diagram, not a control and not a separate
              // object in the accessibility tree.
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
