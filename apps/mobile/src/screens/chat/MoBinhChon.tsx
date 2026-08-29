/** Compose a poll from places the companion already proposed.
 *
 * The options are existing `DiaDiem` rows, not free text. A typed option
 * would be a place the server never asserted, which is the same class of lie
 * as a canned itinerary. `optionId` is the place id so a later ballot names
 * the same row the card opened with.
 *
 * Each option is drawn by `DongDiaDiem`, the row `TheKeHoach` already uses
 * for the AI's suggestions -- imported, not reimplemented. The place a
 * person is voting for has to look like the place they were shown, or the
 * ballot is quietly about something else.
 *
 * Two options is the floor because one forced answer is not a vote; the
 * counter in `binh-chon.ts` drops a card with fewer than two for the same
 * reason. The button says why it is blocked rather than sitting still.
 */
import React, { useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { toggleState } from "../../ui/a11y";
import { Button, Card, Screen } from "../../ui/Kit";
import type { DiaDiem } from "./ke-hoach";
import { DongDiaDiem } from "./TheKeHoach";

export function MoBinhChon({
  diaDiem,
  dangGui,
  onMo,
  onHuy,
}: {
  diaDiem: DiaDiem[];
  dangGui: boolean;
  onMo: (
    cauHoi: string,
    chon: { optionId: string; nhan: string; diaDiem: DiaDiem }[],
  ) => void;
  onHuy: () => void;
}) {
  const c = usePalette();
  const [cauHoi, setCauHoi] = useState("");
  const [chonId, setChonId] = useState<string[]>([]);

  const cauHoiHopLe = cauHoi.trim() !== "";
  const duChon = chonId.length >= 2;
  const duDieuKien = cauHoiHopLe && duChon;
  const khoaMo = dangGui || !duDieuKien;

  function daoChon(id: string) {
    setChonId((hien) =>
      hien.includes(id) ? hien.filter((x) => x !== id) : [...hien, id],
    );
  }

  function mo() {
    if (khoaMo) return;
    const chon = diaDiem
      .filter((d) => chonId.includes(d.id))
      .map((d) => ({ optionId: d.id, nhan: d.ten, diaDiem: d }));
    onMo(cauHoi.trim(), chon);
  }

  return (
    <Screen
      title="Mở bình chọn"
      hint="Chọn chỗ từ gợi ý của nhóm, rồi đặt câu hỏi."
      footer={
        <>
          {!cauHoiHopLe ? (
            <Text style={{ ...type.micro, color: c.inkSoft }}>Nhập câu hỏi trước</Text>
          ) : null}
          {!duChon ? (
            <Text style={{ ...type.micro, color: c.inkSoft }}>
              Chọn ít nhất 2 chỗ để bình chọn
            </Text>
          ) : null}
          <Button label="Mở bình chọn" onPress={mo} disabled={khoaMo} />
          <Button label="Huỷ" tone="quiet" onPress={onHuy} disabled={dangGui} />
        </>
      }
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ gap: space.md, paddingBottom: space.sm }}
      >
        <Card>
          <View style={{ gap: space.xs }}>
            <Text style={{ ...type.label, color: c.inkSoft }}>Câu hỏi</Text>
            <TextInput
              value={cauHoi}
              onChangeText={setCauHoi}
              editable={!dangGui}
              placeholder="Ăn tối ngày 1 ở đâu nhỉ?"
              placeholderTextColor={c.inkFaint}
              aria-label="Câu hỏi"
              accessibilityLabel="Câu hỏi"
              style={{
                ...type.body,
                color: c.ink,
                backgroundColor: c.card,
                borderColor: c.lineStrong,
                borderWidth: 1,
                borderRadius: radius.base,
                paddingHorizontal: space.md,
                paddingVertical: 12,
              }}
            />
          </View>
        </Card>

        <Card>
          {diaDiem.length === 0 ? (
            <Text style={{ ...type.body, color: c.inkSoft }}>
              Chưa có địa điểm nào để đưa vào bình chọn.
            </Text>
          ) : (
            <View style={{ gap: space.xs }}>
              <Text style={{ ...type.label, color: c.inkSoft }}>Lựa chọn</Text>
              {diaDiem.map((d) => {
                const daChon = chonId.includes(d.id);
                return (
                  <Pressable
                    key={d.id}
                    onPress={() => daoChon(d.id)}
                    disabled={dangGui}
                    {...toggleState("checkbox", daChon)}
                    accessibilityLabel={`${d.ten}${daChon ? ", đã chọn" : ", chưa chọn"}`}
                    style={({ pressed }) => ({
                      minHeight: 44,
                      flexDirection: "row",
                      // Top-aligned: a place row is two to five lines tall, so
                      // centring puts the tick beside the price instead of
                      // beside the name it is ticking.
                      alignItems: "flex-start",
                      gap: space.sm,
                      paddingHorizontal: space.sm,
                      paddingVertical: space.sm,
                      borderRadius: radius.base,
                      borderWidth: 1,
                      borderColor: daChon ? c.ai : c.lineStrong,
                      backgroundColor: daChon ? c.aiSoft : "transparent",
                      opacity: dangGui ? 0.6 : pressed ? 0.85 : 1,
                    })}
                  >
                    <View
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: 4,
                        borderWidth: daChon ? 2 : 1,
                        borderColor: daChon ? c.ai : c.lineStrong,
                        backgroundColor: daChon ? c.ai : "transparent",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {daChon ? (
                        <Text style={{ ...type.micro, color: c.aiInk, fontWeight: "700" }}>
                          ✓
                        </Text>
                      ) : null}
                    </View>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <DongDiaDiem diaDiem={d} />
                    </View>
                  </Pressable>
                );
              })}
            </View>
          )}
        </Card>
      </ScrollView>
    </Screen>
  );
}
