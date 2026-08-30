/** Tick the dishes you ate. The list you send is the whole claim, not a delta.
 *
 * `POST /bills/{id}/my-items` takes `item_keys` as the caller's COMPLETE set
 * on this bill. Every key absent from the body is released. That is how a
 * mis-tap is undone without a second endpoint, and it is why this screen
 * sends the tick state as it stands rather than a "just this one" patch.
 * Unticking is not decoration: it is the person handing the dish back.
 *
 * Lead tone is `split` (teal). DESIGN.md gives teal to money being divided
 * or settled, and the number pinned in the footer is exactly that -- the
 * sum of the rows this person is about to put their name on. Orange would
 * say "brand action" on a screen whose subject is a dinner bill.
 *
 * The sum is addition of integer đồng already on the rows. It is not a
 * split, not a preview, and not a second allocator. Quantity is display;
 * `tienVnd` is the line total the parent already resolved.
 *
 * Pure: props in, callbacks out. The parent owns the bill and the write.
 */
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { toggleState } from "../../ui/a11y";
import { Button, Card, Screen } from "../../ui/Kit";

export function MonCuaToi({
  tenNhom,
  mon,
  daChon,
  dangLuu,
  loi,
  onBat,
  onLuu,
  onQuayLai,
}: {
  tenNhom: string;
  mon: { itemKey: string; ten: string; soLuong: number; tienVnd: number }[];
  daChon: readonly string[];
  dangLuu: boolean;
  loi: string | null;
  onBat: (itemKey: string) => void;
  onLuu: () => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const phan = mon
    .filter((m) => daChon.includes(m.itemKey))
    .reduce((tong, m) => tong + m.tienVnd, 0);

  return (
    <Screen
      title="Món của tôi"
      hint={tenNhom}
      gap={space.lg}
      footer={
        <>
          <Text style={{ ...type.amountSmall, color: c.split, fontVariant: ["tabular-nums"] }}>
            Phần của bạn: {tienVnd(phan)}
          </Text>
          <Text style={{ ...type.label, color: c.ink }}>
            Danh sách gửi lên thay hết món bạn nhận trước đó, nên bỏ tích là nhả món ra.
          </Text>
          <Button
            label="Lưu món của tôi"
            tone="split"
            onPress={onLuu}
            disabled={dangLuu}
          />
          <Button label="Quay lại" tone="ghost" onPress={onQuayLai} disabled={dangLuu} />
        </>
      }
    >
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: space.sm, paddingBottom: space.sm }}
        tabIndex={0}
      >
        {loi ? (
          <Card>
            <Text style={{ ...type.body, color: c.ink }} accessibilityRole="alert">
              {loi}
            </Text>
          </Card>
        ) : null}

        {mon.length === 0 ? (
          <Text style={{ ...type.body, color: c.inkSoft }}>
            Bill này chưa có món nào để nhận.
          </Text>
        ) : (
          mon.map((hang) => {
            const chon = daChon.includes(hang.itemKey);
            return (
              <Pressable
                key={hang.itemKey}
                onPress={() => onBat(hang.itemKey)}
                disabled={dangLuu}
                {...toggleState("checkbox", chon)}
                accessibilityLabel={nhanDocMon(hang, chon)}
                style={({ pressed }) => ({
                  minHeight: 44,
                  flexDirection: "row",
                  alignItems: "center",
                  gap: space.sm,
                  paddingHorizontal: space.sm,
                  paddingVertical: space.xs,
                  borderRadius: radius.base,
                  borderWidth: 1,
                  borderColor: chon ? c.split : c.lineStrong,
                  backgroundColor: chon ? c.splitSoft : c.card,
                  opacity: dangLuu ? 0.85 : pressed ? 0.85 : 1,
                })}
              >
                <View
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 4,
                    borderWidth: chon ? 2 : 1,
                    borderColor: chon ? c.split : c.lineStrong,
                    backgroundColor: chon ? c.split : "transparent",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {chon ? (
                    <Text style={{ ...type.micro, color: c.splitInk, fontWeight: "700" }}>
                      ✓
                    </Text>
                  ) : null}
                </View>
                <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
                  <Text numberOfLines={2} style={{ ...type.body, color: c.ink }}>
                    {hang.ten}
                  </Text>
                  {hang.soLuong !== 1 ? (
                    <Text
                      style={{
                        ...type.micro,
                        color: c.inkSoft,
                        fontVariant: ["tabular-nums"],
                      }}
                    >
                      {hang.soLuong} phần
                    </Text>
                  ) : null}
                </View>
                <Text
                  style={{
                    ...type.amountSmall,
                    color: c.ink,
                    textAlign: "right",
                    fontVariant: ["tabular-nums"],
                    flexShrink: 0,
                  }}
                >
                  {tienVnd(hang.tienVnd)}
                </Text>
              </Pressable>
            );
          })
        )}
      </ScrollView>
    </Screen>
  );
}

/** Vietnamese đồng with a dot thousands separator and a "đ" suffix.
 *
 *  Local on purpose. `toLocaleString` falls back to the C locale in the
 *  Hermes-shaped runtimes this app actually ships, and `860,000đ` on a
 *  Vietnamese screen reads as a foreign product. Integer truncation, not
 *  rounding: a đồng is a đồng, and a fractional leftover here would be a
 *  second allocator hiding in a formatter. */
function tienVnd(dong: number): string {
  const am = dong < 0;
  const digits = Math.abs(Math.trunc(dong)).toString();
  let grouped = "";
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) grouped += ".";
    grouped += digits[i];
  }
  return `${am ? "-" : ""}${grouped}đ`;
}

function nhanDocMon(
  hang: { ten: string; soLuong: number; tienVnd: number },
  chon: boolean,
): string {
  const sl = hang.soLuong !== 1 ? `${hang.soLuong} phần, ` : "";
  return `${hang.ten}, ${sl}${tienVnd(hang.tienVnd)}, ${chon ? "đã chọn" : "chưa chọn"}`;
}
