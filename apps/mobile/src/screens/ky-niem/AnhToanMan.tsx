/** One photograph of the group, large.
 *
 * The wall draws every picture as a 47%-wide square, cropped to `cover`, because
 * a wall only reads as a wall when the rows line up. That is the right decision
 * for a grid and the wrong one for looking at a photograph: a group shot ends up
 * with the two people on the ends cut off, and there was nowhere in the app to
 * see the whole frame. This is that nowhere.
 *
 * `GET /contexts/{context_id}/photos/{photo_id}` is what serves the bytes, and
 * it is members-only. The request has to carry `X-Actor-ID`, an `<img>` cannot,
 * and the failure is silent -- a 401 lands in `Anh`'s stand-in, which is exactly
 * what a group with no photographs looks like. So `nguoiXem` is threaded down
 * here as it is everywhere else, and this screen is one more place where getting
 * it wrong would be visible rather than invisible.
 *
 * `contain` and not `cover`. This is the one surface in the app whose job is the
 * whole picture, so it letterboxes on a dark ground rather than filling the
 * screen with a crop. Deliberately the opposite of the tile it was opened from.
 */
import React from "react";
import { Modal, Pressable, Text, View } from "react-native";
import { space, type, usePalette } from "../../theme";
import { Anh } from "../../ui/Anh";
import { Gradient, HERO_SUNSET } from "../../navigation/Gradient";
import type { KyNiemWire } from "../../api";

const HIT = 44;

export function AnhToanMan({
  kyNiem,
  personId,
  contextId,
  onDong,
}: {
  /** The row to show, or `null` for closed. Held by the wall so that only one
   *  photograph can be open and the modal has no state of its own to get out of
   *  step with it. */
  kyNiem: KyNiemWire | null;
  personId: string;
  contextId: string;
  onDong: () => void;
}) {
  const c = usePalette();
  const chuThich = kyNiem?.caption?.trim() ?? "";

  return (
    <Modal
      visible={kyNiem !== null}
      transparent
      animationType="fade"
      // Android's hardware back closes it. Without this the only way out is the
      // button, and a full-screen overlay you cannot back out of is a trap.
      onRequestClose={onDong}
    >
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.92)" }}>
        <View
          style={{
            flexDirection: "row",
            justifyContent: "flex-end",
            padding: space.sm,
            paddingTop: space.lg,
          }}
        >
          <Pressable
            onPress={onDong}
            accessibilityRole="button"
            accessibilityLabel="Đóng ảnh"
            style={{
              minWidth: HIT,
              minHeight: HIT,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ fontSize: 28, lineHeight: 32, fontWeight: "700", color: "#ffffff" }}>
              ×
            </Text>
          </Pressable>
        </View>

        {kyNiem ? (
          <>
            <View style={{ flex: 1, justifyContent: "center" }}>
              <Anh
                uri={kyNiem.image_url}
                alt={chuThich ? `Ảnh kỷ niệm: ${chuThich}` : "Ảnh kỷ niệm của nhóm, xem toàn màn hình"}
                nguoiXem={personId}
                nhom={contextId}
                vua="contain"
                style={{ width: "100%", aspectRatio: 1 }}
                cho={<Gradient colors={HERO_SUNSET} style={{ flex: 1 }} />}
              />
            </View>

            {/* On its own ground rather than over the picture: the photograph
                underneath is somebody's real one and can be any brightness, and
                a caption that disappears into a white sky is a caption nobody
                wrote. */}
            <View style={{ backgroundColor: c.card, padding: space.md, gap: 2 }}>
              {chuThich ? (
                <Text style={{ ...type.body, color: c.ink }}>{chuThich}</Text>
              ) : (
                <Text style={{ ...type.body, color: c.inkFaint }}>Ảnh chưa có chú thích.</Text>
              )}
              <Text style={{ ...type.micro, color: c.inkFaint }}>
                Chỉ thành viên nhóm mở được tấm này. App gửi kèm danh tính người
                đang xem, nên mở bằng link trần sẽ bị máy chủ từ chối.
              </Text>
            </View>
          </>
        ) : null}
      </View>
    </Modal>
  );
}
