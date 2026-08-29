/** Why a bubble has to say who is speaking before it says what they said.
 *
 * The defect this screen exists to prevent is a thread where the machine's
 * voice is indistinguishable from a friend's. That is not a styling
 * preference: once those two look the same, a grounded itinerary and a
 * sentence a person typed become the same kind of object, and the product
 * rule that the model may not invent a place has nothing left to point at.
 * So the three skins are not decoration. Own bubble: orange wash, right.
 * Someone else's: card, left, a container edge. The machine's: full width,
 * purple wash, purple edge, a purple avatar and the words "Rủ Đi AI", the
 * three places the palette's `ai` token is allowed to be spent.
 *
 * Reactions are absent on purpose. The mockup draws them. The server has no
 * endpoint that stores one, and painting a heart that resets on the next
 * load is the same class of lie as a canned itinerary: it looks like the
 * product remembers something it does not. The button is not hidden behind
 * a "coming soon"; it is not drawn.
 *
 * Avatar and name only on the first bubble of a run from the same author.
 * The clock is on every bubble, `micro`, because a thread without times
 * cannot be told apart from a screenshot.
 */
import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import type { MessageWire } from "./tin-nhan";
import { TheKeHoach } from "./TheKeHoach";
import type { KeHoach } from "./ke-hoach";

export type NguoiHienThi = {
  name: string;
  initials: string;
};

export function BongBong({
  message,
  nguoiGui,
  cuaMinh,
  dauChuoi,
  onXemKeHoach,
}: {
  message: MessageWire;
  /** Looked up from `nhom-demo.ts` by `author_id`. Null when the author is
   *  not in the demo group: we show a shortened id, never a made-up name. */
  nguoiGui: NguoiHienThi | null;
  cuaMinh: boolean;
  dauChuoi: boolean;
  onXemKeHoach: (keHoach: KeHoach) => void;
}) {
  const c = usePalette();
  const cuaAi = message.author_id === null || message.kind === "ai_card";

  const nen = cuaAi ? c.aiSoft : cuaMinh ? c.accentSoft : c.card;
  const vien = cuaAi ? c.ai : cuaMinh ? c.accentSoft : c.line;
  const le = cuaAi ? "stretch" : cuaMinh ? "flex-end" : "flex-start";

  return (
    <View
      style={{
        alignSelf: le,
        marginLeft: cuaMinh && !cuaAi ? space.xxl : 0,
        marginRight: !cuaMinh && !cuaAi ? space.xxl : 0,
        gap: space.xs,
      }}
    >
      {dauChuoi ? (
        cuaAi ? (
          <HangAi />
        ) : (
          <HangNguoi nguoiGui={nguoiGui} authorId={message.author_id} lechPhai={cuaMinh} />
        )
      ) : null}

      <View
        style={{
          backgroundColor: nen,
          borderColor: vien,
          borderWidth: 1,
          borderRadius: radius.base,
          paddingHorizontal: space.sm,
          paddingVertical: space.sm,
          gap: space.xs,
        }}
      >
        {message.kind === "ai_card" ? (
          <TheKeHoach card={message.card} onXemChiTiet={onXemKeHoach} />
        ) : message.kind === "image" ? (
          <Text style={{ ...type.body, color: c.ink }}>
            Tin này là ảnh, nhưng chưa có nơi lưu ảnh nên chưa hiện được.
          </Text>
        ) : (
          <Text style={{ ...type.body, color: c.ink }}>
            {message.body && message.body.trim() ? message.body : "Tin không có chữ."}
          </Text>
        )}
        <Text style={{ ...type.micro, color: c.inkFaint, alignSelf: cuaMinh && !cuaAi ? "flex-end" : "flex-start" }}>
          {gioTin(message.created_at)}
        </Text>
      </View>
    </View>
  );
}

function HangAi() {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
      <View
        style={{
          width: 32,
          height: 32,
          borderRadius: radius.pill,
          backgroundColor: c.ai,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ ...type.micro, fontWeight: "700", color: c.aiInk }}>AI</Text>
      </View>
      <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>Rủ Đi AI ✦</Text>
    </View>
  );
}

function HangNguoi({
  nguoiGui,
  authorId,
  lechPhai,
}: {
  nguoiGui: NguoiHienThi | null;
  authorId: string | null;
  lechPhai: boolean;
}) {
  const c = usePalette();
  const ten = nguoiGui?.name ?? (authorId ? authorId.slice(0, 8) : "Ẩn danh");
  const initials = nguoiGui?.initials ?? "?";
  return (
    <View
      style={{
        flexDirection: lechPhai ? "row-reverse" : "row",
        alignItems: "center",
        gap: space.xs,
      }}
    >
      <View
        style={{
          width: 32,
          height: 32,
          borderRadius: radius.pill,
          backgroundColor: c.accentSoft,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ ...type.micro, fontWeight: "700", color: c.accent }}>{initials}</Text>
      </View>
      <Text style={{ ...type.label, color: c.inkSoft }}>{ten}</Text>
    </View>
  );
}

/** Hours and minutes only. A full timestamp on every bubble is noise; a
 *  missing one makes a live thread look like a screenshot. Invalid input
 *  is an empty string, not the word "Invalid Date". */
function gioTin(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}
