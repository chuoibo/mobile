/** What [+] opens: the four things a group starts from the bar.
 *
 * One of the four reaches real behaviour today. The other three are drawn to
 * the same spec and marked `vỏ`, because the alternative -- four identical
 * rows, three of which do nothing -- is the failure the brief names outright:
 * a shell is fine, a shell hiding that it is one is not. The mark is a word,
 * not a disabled state, because a disabled row cannot be pressed and so cannot
 * explain itself.
 *
 * Built as an overlay inside the shell rather than a `<Modal>`. Modal on
 * react-native-web renders into a portal outside the app root, which puts it
 * out of reach of a screenshot of the app container and out of the tree the
 * detector scans -- the sheet would be the one surface nothing could check.
 */
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../theme";
import {
  IconChuyen,
  IconKhoanChi,
  IconKyNiem,
  IconNhom,
  type IconProps,
} from "./icons";
import { CREATE_ACTIONS, type CreateActionId } from "./tabs";

const GLYPHS: Record<CreateActionId, (p: IconProps) => React.ReactElement> = {
  "tao-chuyen": IconChuyen,
  "tao-khoan-chi": IconKhoanChi,
  "dang-ky-niem": IconKyNiem,
  "tao-nhom": IconNhom,
};

export function MenuTao({ onPick, onClose }: {
  onPick: (id: CreateActionId) => void;
  onClose: () => void;
}) {
  const c = usePalette();

  return (
    // Declared a modal, now that `useInertBackground` in VoTab actually takes
    // the screen and the bar out of the tree while this is open. Saying
    // `aria-modal` without that would be a label on a door that is not shut.
    <View
      role="dialog"
      aria-modal
      accessibilityLabel="Tạo gì đây?"
      style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, justifyContent: "flex-end" }}
    >
      {/* Backdrop. A real control, not decoration: tapping outside a sheet to
          dismiss it is the gesture people try first. */}
      <Pressable
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Đóng menu tạo mới"
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(15,8,20,0.45)" }}
      />

      <View
        style={{
          backgroundColor: c.card,
          borderTopLeftRadius: radius.base,
          borderTopRightRadius: radius.base,
          borderTopColor: c.line,
          borderTopWidth: 1,
          paddingTop: space.sm,
          paddingBottom: space.lg,
          paddingHorizontal: space.md,
          gap: space.sm,
        }}
      >
        {/* Grab handle. Says "this slides" without a word. */}
        <View
          style={{
            alignSelf: "center",
            width: 40,
            height: 4,
            borderRadius: radius.pill,
            backgroundColor: c.line,
            marginBottom: space.xs,
          }}
        />

        <Text style={{ ...type.title, color: c.ink }}>Tạo gì đây?</Text>

        <ScrollView contentContainerStyle={{ gap: space.xs }} showsVerticalScrollIndicator={false}>
          {CREATE_ACTIONS.map((a) => {
            const Glyph = GLYPHS[a.id];
            return (
              <Pressable
                key={a.id}
                onPress={() => onPick(a.id)}
                accessibilityRole="button"
                accessibilityLabel={
                  a.built ? `${a.label}. ${a.hint}` : `${a.label}. ${a.hint}. Màn này còn là vỏ.`
                }
                style={({ pressed }) => ({
                  flexDirection: "row",
                  alignItems: "center",
                  gap: space.md,
                  minHeight: 60,
                  paddingVertical: space.sm,
                  paddingHorizontal: space.sm,
                  borderRadius: radius.control,
                  backgroundColor: pressed ? c.accentSoft : "transparent",
                })}
              >
                <View
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: radius.control,
                    alignItems: "center",
                    justifyContent: "center",
                    // The built row is the only one wearing the accent. The
                    // others are not greyed out -- they are simply not first.
                    backgroundColor: a.built ? c.accentSoft : c.ground,
                  }}
                >
                  <Glyph color={a.built ? c.accent : c.inkSoft} size={24} />
                </View>

                <View style={{ flex: 1, gap: 2 }}>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
                    <Text style={{ ...type.body, fontWeight: "600", color: c.ink }}>{a.label}</Text>
                    {a.built ? null : <ChipVo />}
                  </View>
                  <Text style={{ ...type.label, color: c.inkSoft }}>{a.hint}</Text>
                </View>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>
    </View>
  );
}

/** The honesty mark. `ink` on `ground`, 13.93:1 -- readable, not shouted. */
function ChipVo() {
  const c = usePalette();
  return (
    <View
      style={{
        paddingHorizontal: space.xs,
        paddingVertical: 2,
        borderRadius: radius.small,
        backgroundColor: c.ground,
        borderColor: c.line,
        borderWidth: 1,
      }}
    >
      <Text style={{ ...type.micro, color: c.inkSoft }}>vỏ</Text>
    </View>
  );
}
