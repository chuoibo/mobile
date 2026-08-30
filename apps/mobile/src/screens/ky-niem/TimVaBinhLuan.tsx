/** Hearts and comments under one photograph on the group's wall (rd-fe-33).
 *
 * The mockup's first screen (product/features/05-ky-niem-cua-nhom.png) draws a
 * social wall: a heart with a count, a comment count, the comments themselves,
 * and a box to write one. Everything here is that row and what opens under it.
 *
 * ## Why this file can exist now, and could not before
 *
 * `KyNiem.tsx`'s own docblock says reactions and comments "have nothing behind
 * them: there is no reactions table, no comments table". That stopped being
 * true when the four routes landed. What has NOT changed is the rule that
 * produced that sentence: a control is drawn only when pressing it can work.
 *
 * So the wall does not ask a feature flag or a version string whether hearts
 * exist. It asks the data. A server holding the tables sends `reaction_count`,
 * `comment_count` and `viewer_has_reacted` on every row of the feed; one
 * without them sends none of the three, and `coTuongTac` is false, and this
 * component is never mounted. The wall then looks exactly as it did before,
 * down to the sentence at the foot naming hearts as unbuilt.
 *
 * That is worth spelling out because the tempting version -- draw the heart
 * always, show an error when it 404s -- produces a screen that says "your tap
 * did not register" for a feature nobody ever wrote. A person cannot tell that
 * apart from a bug in their own account.
 *
 * ## Where the counts come from
 *
 * Not from here. After a heart or a comment lands, this asks the wall to
 * re-read itself, and the number that comes back is the server's. The counts
 * are recomputed from rows on every read -- there is no stored counter to drift
 * -- so a local `count + 1` would be a second implementation of a number the
 * server already owns, and the two disagree the moment somebody else presses
 * at the same time. This screen's ledger half already refuses to do arithmetic
 * for the same reason; hearts are cheaper than money and the rule is the same.
 *
 * The visible cost is that a heart takes a round trip to fill in. That is the
 * honest trade: the alternative is a filled heart that is not recorded.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { toggleState } from "../../ui/a11y";
import {
  attemptFor,
  boTim,
  docBinhLuan,
  guiBinhLuan,
  thaTim,
  BINH_LUAN_TOI_DA,
  type Attempt,
  type BinhLuanWire,
  type KyNiemWire,
} from "../../api";

/** The sentence a refused call left behind, or a plain one when it left none.
 *
 * `ApiError` carries a Vietnamese sentence chosen by `XA_HOI_REFUSALS`; this
 * only has to catch the case where something else threw, and say so without
 * showing whatever English the runtime put in `message`. */
function cauLoi(error: unknown, khiKhong: string): string {
  return error instanceof Error && error.message.trim() !== "" ? error.message : khiKhong;
}

export function TimVaBinhLuan({
  kyNiem,
  contextId,
  personId,
  moRong,
  onDoiMoRong,
  onDoiTuong,
  doc = docBinhLuan,
  gui = guiBinhLuan,
  tha = thaTim,
  bo = boTim,
}: {
  kyNiem: KyNiemWire;
  contextId: string;
  personId: string;
  /** Whether this photograph's comments are open. Held by the wall rather than
   *  here, so opening one closes the last: two open panels in a two-column grid
   *  push each other around and neither is readable. */
  moRong: boolean;
  onDoiMoRong: () => void;
  /** Re-read the wall, which is where the new counts come from. */
  onDoiTuong: () => void | Promise<void>;
  doc?: typeof docBinhLuan;
  gui?: typeof guiBinhLuan;
  tha?: typeof thaTim;
  bo?: typeof boTim;
}) {
  const c = usePalette();
  const [dangDoiTim, setDangDoiTim] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const daTha = kyNiem.viewer_has_reacted === true;
  const soTim = kyNiem.reaction_count ?? 0;
  const soBinhLuan = kyNiem.comment_count ?? 0;

  const doiTim = useCallback(async () => {
    setDangDoiTim(true);
    setLoi(null);
    try {
      // Which way to go is read from the server's answer, not from a local
      // guess. Pressing twice is a 409 by contract rather than a silent
      // toggle, so a client that decided for itself would eventually send the
      // wrong verb and show a refusal for a press that was perfectly sensible.
      if (daTha) await bo(contextId, kyNiem.id, personId);
      else await tha(contextId, kyNiem.id, personId);
      await onDoiTuong();
    } catch (error) {
      setLoi(cauLoi(error, "Chưa gửi được tim của bạn. Thử lại giúp mình."));
    } finally {
      setDangDoiTim(false);
    }
  }, [daTha, bo, tha, contextId, kyNiem.id, personId, onDoiTuong]);

  return (
    <View style={{ gap: space.xs, padding: space.xs }}>
      <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap" }}>
        <Pressable
          onPress={doiTim}
          disabled={dangDoiTim}
          // `switch` rather than a button carrying `aria-pressed`: `toggleState`
          // is the one spelling measured to survive react-native-web 0.21.2,
          // which forwards no `accessibilityState` at all. See `ui/a11y.ts`.
          {...toggleState("switch", daTha)}
          // The state is in the words too, not only in the attribute. A count
          // beside a glyph tells a sighted person everything and a screen
          // reader user nothing about which way the heart is set.
          accessibilityLabel={
            daTha
              ? `Bỏ tim. Ảnh này đang có ${soTim} tim, trong đó có tim của bạn.`
              : `Thả tim. Ảnh này đang có ${soTim} tim.`
          }
          aria-disabled={dangDoiTim}
          style={({ pressed }) => ({
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            minHeight: 44,
            paddingHorizontal: space.xs,
            borderRadius: radius.pill,
            opacity: pressed || dangDoiTim ? 0.6 : 1,
          })}
        >
          {/* Filled versus hollow, not two colours of the same glyph: colour
              alone cannot carry a state (WCAG 1.4.1), and a red heart on a
              wall of warm photographs is not reliably distinguishable from a
              grey one at this size. */}
          <Text style={{ ...type.body, color: daTha ? c.accent : c.inkSoft }}>
            {daTha ? "♥" : "♡"}
          </Text>
          <Text style={{ ...type.micro, color: c.inkSoft }}>{soTim}</Text>
        </Pressable>

        <Pressable
          onPress={onDoiMoRong}
          accessibilityRole="button"
          accessibilityLabel={
            moRong
              ? "Ẩn bình luận của ảnh này"
              : soBinhLuan === 0
                ? "Viết bình luận đầu tiên cho ảnh này"
                : `Xem ${soBinhLuan} bình luận của ảnh này`
          }
          style={({ pressed }) => ({
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            minHeight: 44,
            paddingHorizontal: space.xs,
            borderRadius: radius.pill,
            opacity: pressed ? 0.6 : 1,
          })}
        >
          <Text style={{ ...type.body, color: c.inkSoft }}>☰</Text>
          <Text style={{ ...type.micro, color: c.inkSoft }}>{soBinhLuan}</Text>
        </Pressable>
      </View>

      {loi ? (
        <Text style={{ ...type.micro, color: c.ink }} accessibilityRole="alert">
          {loi}
        </Text>
      ) : null}

      {moRong ? (
        <KhungBinhLuan
          kyNiem={kyNiem}
          contextId={contextId}
          personId={personId}
          onDoiTuong={onDoiTuong}
          doc={doc}
          gui={gui}
        />
      ) : null}
    </View>
  );
}

/** The comments themselves, plus the box for writing one.
 *
 * Loads on open rather than with the wall: a wall of twenty photographs would
 * otherwise be twenty-one requests to draw a screen on which nineteen of the
 * comment lists are not visible. The counts in the row above come from the
 * feed, so the closed state is not lying about how many there are. */
function KhungBinhLuan({
  kyNiem,
  contextId,
  personId,
  onDoiTuong,
  doc,
  gui,
}: {
  kyNiem: KyNiemWire;
  contextId: string;
  personId: string;
  onDoiTuong: () => void | Promise<void>;
  doc: typeof docBinhLuan;
  gui: typeof guiBinhLuan;
}) {
  const c = usePalette();
  const [danhSach, setDanhSach] = useState<BinhLuanWire[] | null>(null);
  const [loiDoc, setLoiDoc] = useState<string | null>(null);
  const [chu, setChu] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loiGui, setLoiGui] = useState<string | null>(null);
  // Keyed per photograph and per text, so the retry after a failure that may
  // have landed replays the first answer instead of leaving the sentence twice.
  const soKhoa = React.useRef<Record<string, Attempt>>({});

  const tai = useCallback(async () => {
    try {
      setDanhSach(await doc(contextId, kyNiem.id, personId));
      setLoiDoc(null);
    } catch (error) {
      setLoiDoc(cauLoi(error, "Chưa đọc được bình luận của ảnh này."));
    }
  }, [doc, contextId, kyNiem.id, personId]);

  useEffect(() => {
    void tai();
  }, [tai]);

  const guiDi = useCallback(async () => {
    const sach = chu.trim();
    if (sach === "" || dangGui) return;
    setDangGui(true);
    setLoiGui(null);
    try {
      await gui(
        contextId,
        kyNiem.id,
        sach,
        personId,
        attemptFor(soKhoa.current, `binh-luan:${kyNiem.id}:${sach}`),
      );
      setChu("");
      await tai();
      // The count in the row above lives on the feed, so it only moves when the
      // wall re-reads. Without this the list grows by one and the number beside
      // it stays put, which reads as a comment that did not save.
      await onDoiTuong();
    } catch (error) {
      setLoiGui(cauLoi(error, "Chưa gửi được bình luận. Thử lại giúp mình."));
    } finally {
      setDangGui(false);
    }
  }, [chu, dangGui, gui, contextId, kyNiem.id, personId, tai, onDoiTuong]);

  const trong = chu.trim() === "";

  return (
    <View
      style={{
        gap: space.xs,
        borderTopWidth: 1,
        borderTopColor: c.line,
        paddingTop: space.xs,
      }}
    >
      {danhSach === null && loiDoc === null ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
          <ActivityIndicator color={c.accent} />
          <Text style={{ ...type.micro, color: c.inkSoft }}>Đang đọc bình luận…</Text>
        </View>
      ) : null}

      {loiDoc ? (
        <Text style={{ ...type.micro, color: c.ink }} accessibilityRole="alert">
          {loiDoc}
        </Text>
      ) : null}

      {danhSach !== null && danhSach.length === 0 ? (
        <Text style={{ ...type.micro, color: c.inkSoft }}>
          Chưa ai nói gì về tấm này. Bạn viết câu đầu tiên nhé.
        </Text>
      ) : null}

      {(danhSach ?? []).map((b) => (
        <View key={b.id} style={{ gap: 2 }}>
          {/* The server resolves the name. This does not fall back to the id:
              an id shown where a name belongs is not a degraded name, it is a
              different person's identifier printed on a group's private wall. */}
          <Text style={{ ...type.micro, fontWeight: "700", color: c.ink }}>
            {b.display_name}
          </Text>
          <Text style={{ ...type.micro, color: c.inkSoft }}>{b.body}</Text>
        </View>
      ))}

      <TextInput
        value={chu}
        onChangeText={setChu}
        editable={!dangGui}
        placeholder="Viết bình luận…"
        placeholderTextColor={c.inkFaint}
        accessibilityLabel="Ô viết bình luận cho ảnh này"
        aria-label="Ô viết bình luận cho ảnh này"
        // The server takes 1..2000. Stopping the 2001st keystroke is kinder
        // than accepting the paragraph and answering with a 422 about it.
        maxLength={BINH_LUAN_TOI_DA}
        onSubmitEditing={guiDi}
        enterKeyHint="send"
        blurOnSubmit={false}
        multiline
        style={{
          ...type.micro,
          minHeight: 44,
          // Without this the input holds its intrinsic content width on
          // react-native-web and pushes the send button off a 390pt screen.
          minWidth: 0,
          color: c.ink,
          backgroundColor: c.card,
          borderColor: c.lineStrong,
          borderWidth: 1,
          borderRadius: radius.control,
          paddingHorizontal: space.sm,
          paddingVertical: space.xs,
        }}
      />

      <Pressable
        onPress={guiDi}
        disabled={trong || dangGui}
        accessibilityRole="button"
        accessibilityLabel="Gửi bình luận"
        aria-disabled={trong || dangGui}
        style={({ pressed }) => ({
          alignSelf: "flex-start",
          minHeight: 44,
          justifyContent: "center",
          paddingHorizontal: space.md,
          borderRadius: radius.control,
          borderWidth: 1,
          borderColor: trong || dangGui ? c.line : c.lineStrong,
          opacity: pressed ? 0.85 : 1,
        })}
      >
        <Text
          style={{
            ...type.micro,
            fontWeight: "600",
            color: trong || dangGui ? c.inkFaint : c.ink,
          }}
        >
          {dangGui ? "Đang gửi…" : "Gửi"}
        </Text>
      </Pressable>

      {loiGui ? (
        <Text style={{ ...type.micro, color: c.ink }} accessibilityRole="alert">
          {loiGui}
        </Text>
      ) : null}
    </View>
  );
}
