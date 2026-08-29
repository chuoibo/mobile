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
}: {
  value: string;
  onChangeText: (text: string) => void;
  onGui: () => void;
  dangGui: boolean;
  onChuaDung: (text: string) => void;
}) {
  const c = usePalette();
  const tat = value.trim() === "" || dangGui;

  return (
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
