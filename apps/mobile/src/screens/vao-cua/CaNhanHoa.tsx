/** F01.03 -- "Giúp Rủ Đi hiểu bạn hơn", the third and last onboarding step.
 *
 * ---------------------------------------------------------------------------
 * DIRECTION CONTRACT (Impeccable, extension flow)
 *
 * Impeccable asks for this as an HTML comment first-child of <body>. There is
 * no <body> here: react-native-web composes the document and no source file
 * owns its first child, so the contract lives at the head of the screen it
 * governs, which is the nearest thing this stack has to markup a reader can
 * audit against the rendered result.
 *
 * THESIS        An extension, not a new world. Steps 01 and 02 already own the
 *               sunset ramp and the white card that lands on it; a third step
 *               that introduced a look would read as a different app two taps
 *               from the first one.
 * OWN-WORLD     Inherited whole from `MoDau` and `DangKy`: HERO_SUNSET behind,
 *               Scrim over it, headings in accentInk on the violet third, and
 *               every smaller thing on a card that brings its own ground
 *               instead of trusting the scrim.
 * STORY         Three questions of falling weight -- taste, then money, then a
 *               favour -- and a header that says out loud you may answer none
 *               of them. The last screen before the product should not be the
 *               first wall.
 * FIRST VIEWPORT  Title, subtitle, and the taste grid already showing two rows,
 *               so the first thing on screen is something to tap rather than
 *               something to read. Budget and the toggle sit below the fold by
 *               design; they are refinements of an answer, not entry tolls.
 * FORM          Tiles, not a list. Eight tastes in a three-column grid read as
 *               a menu to graze; eight rows read as a form to complete, and
 *               this step is optional.
 *
 * FINISH: run the detector on the changed target and hand the build to a
 * fresh-context reviewer before calling this done.
 * ---------------------------------------------------------------------------
 *
 * What is real and what is not, so the next reader does not have to measure:
 *
 * * Real: every selection, the group semantics a screen reader hears, the
 *   permission pre-prompt and all three of its outcomes, and the handoff to
 *   `ghiNhoSoThich`.
 * * A shell: persistence. No route accepts these answers -- `so-thich.ts` has
 *   the measurement -- so they live for the session and no further. The screen
 *   never says "đã lưu", because it has not.
 *
 * The address book is not read by this build and the screen says so in the
 * outcome line rather than in a disclaimer nobody reaches. `KHONG_CO_DANH_BA`
 * is the seam; wiring a real permission means replacing that one function.
 */
import React, { useState } from "react";
import { Platform, Pressable, ScrollView, Text, View } from "react-native";
import tokens from "../../../../../packages/shared/tokens.json";
import { Gradient, HERO_SUNSET, Scrim } from "../../navigation/Gradient";
import { Button } from "../../ui/Kit";
import { toggleState } from "../../ui/a11y";
import { radius, space, type, usePalette } from "../../theme";
import {
  cauVeDanhBa,
  doiMuc,
  KHONG_CO_DANH_BA,
  khoangTheoId,
  NGAN_SACH,
  SO_THICH,
  type KetQuaQuyen,
  type SoThich,
  type XinQuyenDanhBa,
} from "./so-thich";

const ON_SUNSET = tokens.color.light.accentInk;

/** Where the address book question currently stands.
 *
 * `moi` is the pre-prompt the mockup asks for: the benefit is explained on
 * this screen, and only the button inside it opens the OS dialog. Flipping the
 * switch straight into a system prompt is the pattern that earns a permanent
 * "no" from somebody who had not yet been told why.
 */
type PhaQuyen =
  | { buoc: "tat" }
  | { buoc: "moi" }
  | { buoc: "dang-hoi" }
  | { buoc: "xong"; ket: KetQuaQuyen };

export function CaNhanHoa({ ten, onXong, onQuayLai, xinQuyen = KHONG_CO_DANH_BA }: {
  /** The name typed one step earlier. Greeting somebody by the name they just
   *  chose is the cheapest proof that the previous step was recorded. */
  ten: string;
  /** Called with the answers on both "Hoàn tất" and "Bỏ qua". Skipping is an
   *  answer -- an empty one -- not an abort, so the caller gets the same shape
   *  either way and never has to branch on how the step ended. */
  onXong: (chon: SoThich) => void;
  onQuayLai: () => void;
  /** Injected so the granted and denied branches are reachable in a test.
   *  Defaults to the truth about this build. */
  xinQuyen?: XinQuyenDanhBa;
}) {
  const c = usePalette();
  const [muc, setMuc] = useState<string[]>([]);
  const [khoangId, setKhoangId] = useState<string | null>(null);
  const [quyen, setQuyen] = useState<PhaQuyen>({ buoc: "tat" });

  const dangHoi = quyen.buoc === "dang-hoi";
  const danhBa = quyen.buoc === "xong" ? quyen.ket : null;

  function ketQua(): SoThich {
    return { muc, khoang: khoangTheoId(khoangId), danhBa };
  }

  async function hoiQuyen() {
    setQuyen({ buoc: "dang-hoi" });
    // No try/catch that swallows: the seam returns an outcome rather than
    // throwing, and a seam that started throwing should surface here loudly
    // instead of leaving the switch mid-flight forever.
    const ket = await xinQuyen();
    setQuyen({ buoc: "xong", ket });
  }

  return (
    <View style={{ flex: 1, backgroundColor: HERO_SUNSET[0] }}>
      <Gradient colors={HERO_SUNSET} style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }} />
      <Scrim alphas={[0.3, 0.1, 0.3]} />

      <ScrollView
        contentContainerStyle={{
          flexGrow: 1,
          paddingHorizontal: space.md,
          paddingTop: Platform.OS === "ios" ? 52 : 36,
          paddingBottom: space.lg,
          gap: space.md,
        }}
        keyboardShouldPersistTaps="handled"
      >
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <Pressable
            onPress={onQuayLai}
            accessibilityRole="button"
            accessibilityLabel="Quay lại bước nhập tên"
            style={({ pressed }) => ({
              minHeight: 44, justifyContent: "center",
              paddingRight: space.sm, opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: ON_SUNSET }}>← Quay lại</Text>
          </Pressable>

          {/* "Bỏ qua" carries the same payload as "Hoàn tất", just an empty
              one. Two exits that produce different shapes is how a caller ends
              up with `undefined` preferences on one path only. */}
          <Pressable
            onPress={() => onXong(ketQua())}
            accessibilityRole="button"
            accessibilityLabel="Bỏ qua bước cá nhân hóa"
            style={({ pressed }) => ({
              minHeight: 44, justifyContent: "center",
              paddingLeft: space.sm, opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: ON_SUNSET }}>Bỏ qua</Text>
          </Pressable>
        </View>

        <View style={{ gap: space.xs, marginBottom: space.xs }}>
          <Text style={{ ...type.h1, color: ON_SUNSET }}>Giúp Rủ Đi hiểu bạn hơn</Text>
          <Text style={{ ...type.body, color: ON_SUNSET }}>
            Chào {ten}. Chọn sở thích và ngân sách để nhận gợi ý hợp gu hơn. Bỏ
            trống cũng được, đổi lại lúc nào cũng được.
          </Text>
        </View>

        <View style={{ backgroundColor: c.card, borderRadius: radius.base, padding: space.md, gap: space.md }}>
          <View style={{ flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: space.sm }}>
            <Text style={{ ...type.title, color: c.ink }}>Sở thích đi chơi</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>Chọn nhiều tùy thích</Text>
          </View>

          {/* `group`, not `radiogroup`: these are independent checkboxes and a
              radio group would tell a screen reader that picking one drops the
              others, which is the opposite of what happens. */}
          <View
            role="group"
            aria-label="Sở thích đi chơi"
            style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}
          >
            {SO_THICH.map((m) => {
              const on = muc.includes(m.id);
              return (
                <Pressable
                  key={m.id}
                  onPress={() => setMuc((truoc) => doiMuc(truoc, m.id))}
                  {...toggleState("checkbox", on)}
                  // The emoji is inside the tile but outside the name. Without
                  // this the accessible name is whatever the platform makes of
                  // a pictograph next to a word, which differs per screen
                  // reader and is never the label a person would say out loud.
                  aria-label={m.nhan}
                  style={({ pressed }) => ({
                    // Three to a row on a phone, and they still fit two-up on a
                    // narrow one because flexGrow lets the last row spread.
                    flexBasis: "30%",
                    flexGrow: 1,
                    minHeight: 88,
                    alignItems: "center",
                    justifyContent: "center",
                    gap: space.xs,
                    paddingVertical: space.sm,
                    paddingHorizontal: space.xs,
                    borderWidth: on ? 2 : 1,
                    borderRadius: radius.base,
                    // Unselected tiles have no fill, so their edge is the whole
                    // affordance and owes 3:1 -- `lineStrong`, never `line`.
                    borderColor: on ? c.accent : c.lineStrong,
                    backgroundColor: on ? c.accentSoft : "transparent",
                    opacity: pressed ? 0.85 : 1,
                  })}
                >
                  {/* Selection is carried by fill, by border weight AND by this
                      mark, so it is never colour alone. */}
                  <Text style={{ ...type.title, color: c.ink }}>{on ? `${m.hinh} ✓` : m.hinh}</Text>
                  <Text
                    style={{
                      ...type.label,
                      fontWeight: on ? "600" : "400",
                      color: c.ink,
                      textAlign: "center",
                    }}
                  >
                    {m.nhan}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={{ backgroundColor: c.card, borderRadius: radius.base, padding: space.md, gap: space.md }}>
          <View style={{ gap: space.xs }}>
            <Text style={{ ...type.title, color: c.ink }}>Ngân sách mỗi người</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Chọn khoảng bạn thấy thoải mái nhất. Bỏ trống thì Rủ Đi không đoán
              thay bạn.
            </Text>
          </View>

          <View
            accessibilityRole="radiogroup"
            aria-label="Ngân sách mỗi người"
            style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}
          >
            {NGAN_SACH.map((k) => {
              const on = k.id === khoangId;
              return (
                <Pressable
                  key={k.id}
                  // Tapping the lit band clears it. Without this there is no way
                  // back to "chưa chọn" once anything has been touched, and the
                  // screen's own copy promises that blank is allowed.
                  onPress={() => setKhoangId(on ? null : k.id)}
                  {...toggleState("radio", on)}
                  aria-label={`${k.nhan}, ${k.phu}`}
                  style={({ pressed }) => ({
                    flexBasis: "30%",
                    flexGrow: 1,
                    minHeight: 60,
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 2,
                    paddingVertical: space.sm,
                    paddingHorizontal: space.xs,
                    borderWidth: on ? 2 : 1,
                    borderRadius: radius.base,
                    borderColor: on ? c.accent : c.lineStrong,
                    backgroundColor: on ? c.accentSoft : "transparent",
                    opacity: pressed ? 0.85 : 1,
                  })}
                >
                  <Text style={{ ...type.body, fontWeight: on ? "600" : "400", color: c.ink }}>{k.nhan}</Text>
                  <Text style={{ ...type.label, color: on ? c.accent : c.inkSoft }}>{k.phu}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={{ backgroundColor: c.card, borderRadius: radius.base, padding: space.md, gap: space.sm }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={{ ...type.title, color: c.ink }}>Đồng bộ danh bạ</Text>
              <Text style={{ ...type.label, color: c.inkSoft }}>
                Tìm bạn bè đang dùng Rủ Đi
              </Text>
            </View>

            <Pressable
              onPress={() =>
                setQuyen((truoc) => (truoc.buoc === "tat" ? { buoc: "moi" } : { buoc: "tat" }))
              }
              disabled={dangHoi}
              {...toggleState("switch", quyen.buoc !== "tat")}
              aria-label="Đồng bộ danh bạ"
              style={({ pressed }) => ({
                width: 56, minHeight: 44, justifyContent: "center",
                opacity: pressed ? 0.85 : 1,
              })}
            >
              {/* The track carries the state as a shape as well as a fill: the
                  knob moves. Colour alone would fail the same rule the tiles
                  above are drawn against. */}
              <View
                style={{
                  height: 30, borderRadius: 15, padding: 3,
                  borderWidth: 1,
                  borderColor: quyen.buoc === "tat" ? c.lineStrong : c.ai,
                  backgroundColor: quyen.buoc === "tat" ? "transparent" : c.ai,
                  alignItems: quyen.buoc === "tat" ? "flex-start" : "flex-end",
                }}
              >
                <View
                  style={{
                    width: 22, height: 22, borderRadius: 11,
                    backgroundColor: quyen.buoc === "tat" ? c.lineStrong : c.aiInk,
                  }}
                />
              </View>
            </Pressable>
          </View>

          {quyen.buoc === "moi" || dangHoi ? (
            // The pre-prompt. It is a panel on this screen and not a modal on
            // purpose: the person can still see the switch they just moved, so
            // "Để sau" is visibly a way back rather than a dead end.
            <View
              style={{
                backgroundColor: c.aiSoft, borderColor: c.ai, borderWidth: 1,
                borderRadius: radius.base, padding: space.sm, gap: space.sm,
              }}
            >
              <Text style={{ ...type.body, color: c.ink }}>
                Rủ Đi so số điện thoại trong danh bạ với người đã có tài khoản,
                chỉ để gợi ý kết bạn. Không ai trong nhóm thấy danh bạ của bạn,
                và bạn tắt lại được bất cứ lúc nào.
              </Text>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <View style={{ flex: 1 }}>
                  <Button
                    label={dangHoi ? "Đang hỏi quyền…" : "Bật đồng bộ"}
                    onPress={hoiQuyen}
                    disabled={dangHoi}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Button
                    label="Để sau"
                    tone="quiet"
                    onPress={() => setQuyen({ buoc: "xong", ket: "tu-choi" })}
                    disabled={dangHoi}
                  />
                </View>
              </View>
            </View>
          ) : null}

          {quyen.buoc === "xong" ? (
            // `status`, not `alert`: none of the three outcomes is an error,
            // and an alert would interrupt somebody who is mid-tap elsewhere.
            <View role="status" style={{ paddingTop: space.xs }}>
              <Text style={{ ...type.label, color: c.inkSoft }}>{cauVeDanhBa(quyen.ket)}</Text>
            </View>
          ) : null}
        </View>

        <Button
          label="Hoàn tất"
          onPress={() => onXong(ketQua())}
          // Disabled only while the OS dialog is genuinely open. There is no
          // request behind "Hoàn tất" itself, so pretending to load here would
          // be inventing a wait that does not exist.
          disabled={dangHoi}
        />
      </ScrollView>
    </View>
  );
}
