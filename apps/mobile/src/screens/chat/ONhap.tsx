/** Why the unused buttons speak instead of sitting still.
 *
 * A compose row with a plus, an emoji and a microphone that do nothing is
 * how a demo audience decides the product is broken: they tap, nothing
 * happens, and the next sentence out of someone's mouth is "the send is
 * broken too". The three controls are not built. Pressing one has to say
 * that, out loud, in Vietnamese, through the same banner the tab shell uses
 * for a create action that is still a hole. Silence is the defect.
 *
 * Send is the one control that is real. It is off when the box is empty or
 * a send is already in flight, and the off state is `aria-disabled` as well
 * as `disabled`, because `accessibilityState` is a dead prop on this stack
 * (react-native-web 0.21.2 forwards none of it). The box itself is a
 * control, so its edge is `lineStrong`, the token that clears the 3:1
 * non-text floor. `line` here is how a 1.21:1 input happened once already.
 *
 * Why "Hỏi Rủ Đi AI" is its own row above, and not a sixth control in the
 * compose row: that row already walked off a 390px viewport once, and the
 * fix was `minWidth: 0` on the input, not spare room. A sixth 44px target
 * spends the margin that fix bought back. The strip above is also where the
 * mockup puts its quick actions, so the slot is drawn, not invented.
 *
 * Purple. The direction contract spends `ai` on four things, and this is the
 * fourth: the control that summons the machine reads in the machine's colour,
 * or the one button in the app that talks to the AI looks like the three that
 * are not built. Outline and tint, never a filled slab -- a solid purple bar
 * across the bottom would out-shout Send, which is the control that matters
 * more often.
 */
import React from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";

export function ONhap({
  value,
  onChangeText,
  onGui,
  dangGui,
  onChuaDung,
  onHoiAi,
  dangHoiAi,
}: {
  value: string;
  onChangeText: (text: string) => void;
  onGui: () => void;
  dangGui: boolean;
  onChuaDung: (text: string) => void;
  /** Ask the companion for a turn on the thread as it stands. Sends no
   *  message: this is the group asking, not the group saying. */
  onHoiAi: () => void;
  dangHoiAi: boolean;
}) {
  const c = usePalette();
  const tat = value.trim() === "" || dangGui;

  return (
    <View>
      <View
        style={{
          flexDirection: "row",
          paddingHorizontal: space.sm,
          paddingTop: space.xs,
          backgroundColor: c.ground,
        }}
      >
        <Pressable
          onPress={onHoiAi}
          disabled={dangHoiAi}
          accessibilityRole="button"
          // The label stays put while the text inside changes, so a screen
          // reader user can still find this control mid-request, and so the
          // browser gate measures one name across both states.
          accessibilityLabel="Hỏi Rủ Đi AI"
          aria-label="Hỏi Rủ Đi AI"
          aria-disabled={dangHoiAi}
          style={({ pressed }) => ({
            minHeight: 44,
            justifyContent: "center",
            paddingHorizontal: space.sm,
            borderRadius: radius.pill,
            borderWidth: 1,
            // Colour does not move when the button is busy. Fading it is how a
            // pending control drops under the contrast floor exactly when the
            // person is staring at it waiting.
            borderColor: c.ai,
            backgroundColor: c.aiSoft,
            opacity: pressed && !dangHoiAi ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>
            {dangHoiAi ? "Đang hỏi Rủ Đi AI…" : "Hỏi Rủ Đi AI"}
          </Text>
        </Pressable>
      </View>

      <View
        style={{
        flexDirection: "row",
        alignItems: "center",
        gap: space.xs,
        paddingHorizontal: space.sm,
        paddingVertical: space.sm,
        backgroundColor: c.ground,
        borderTopColor: c.line,
        borderTopWidth: 1,
      }}
    >
      <NutIcon
        label="Thêm ảnh hoặc tệp"
        onPress={() => onChuaDung("Thêm ảnh và tệp chưa dựng, mới có chỗ nút.")}
      >
        <Text style={{ ...type.title, color: c.ink }}>+</Text>
      </NutIcon>

      <TextInput
        value={value}
        onChangeText={onChangeText}
        editable={!dangGui}
        placeholder="Nhắn cho nhóm"
        placeholderTextColor={c.inkFaint}
        accessibilityLabel="Ô nhập tin nhắn"
        aria-label="Ô nhập tin nhắn"
        style={{
          ...type.body,
          flex: 1,
          // `flex: 1` alone does not let this shrink. CSS `min-width` defaults
          // to `auto`, so on react-native-web the input holds its intrinsic
          // content width, the row grows past the viewport, and the controls
          // to its right walk off the edge -- at 390 the send button, at 320
          // the emoji and microphone with it. Measured in
          // `tests/nhom-chat-web.test.mjs`; the desktop width hid it.
          minWidth: 0,
          minHeight: 44,
          color: c.ink,
          backgroundColor: c.card,
          borderColor: c.lineStrong,
          borderWidth: 1,
          borderRadius: radius.control,
          paddingHorizontal: space.sm,
          paddingVertical: space.xs,
        }}
      />

      <NutIcon
        label="Chèn biểu tượng cảm xúc"
        onPress={() => onChuaDung("Chèn biểu tượng cảm xúc chưa dựng.")}
      >
        <Text style={{ ...type.title, color: c.ink }}>☺</Text>
      </NutIcon>

      <NutIcon
        label="Ghi âm"
        onPress={() => onChuaDung("Ghi âm chưa dựng, mới có chỗ nút.")}
      >
        <View
          style={{
            width: 14,
            height: 20,
            borderRadius: radius.pill,
            backgroundColor: c.ink,
          }}
        />
      </NutIcon>

      <Pressable
        onPress={onGui}
        disabled={tat}
        accessibilityRole="button"
        accessibilityLabel="Gửi tin nhắn"
        aria-disabled={tat}
        style={({ pressed }) => ({
          minWidth: 44,
          minHeight: 44,
          paddingHorizontal: space.sm,
          borderRadius: radius.control,
          borderWidth: 1,
          borderColor: tat ? c.line : c.accent,
          backgroundColor: tat ? c.line : c.accent,
          alignItems: "center",
          justifyContent: "center",
          opacity: pressed && !tat ? 0.85 : 1,
        })}
      >
        <Text
          style={{
            ...type.label,
            fontWeight: "700",
            color: tat ? c.inkSoft : c.accentInk,
          }}
        >
          Gửi
        </Text>
      </Pressable>
      </View>
    </View>
  );
}

function NutIcon({
  label,
  onPress,
  children,
}: {
  label: string;
  onPress: () => void;
  children: React.ReactNode;
}) {
  const c = usePalette();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: 44,
        height: 44,
        borderRadius: radius.control,
        borderWidth: 1,
        borderColor: c.lineStrong,
        alignItems: "center",
        justifyContent: "center",
        opacity: pressed ? 0.85 : 1,
      })}
    >
      {children}
    </Pressable>
  );
}
