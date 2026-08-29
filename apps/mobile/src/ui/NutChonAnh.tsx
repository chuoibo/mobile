/** The control that turns "there is an upload API" into "I can add a photo".
 *
 * One component rather than a button on each screen, because the part worth not
 * duplicating is not the rectangle -- it is the three states, and two of them
 * are the ones a hand-rolled second copy always forgets:
 *
 *   1. **In flight.** The button reports what is happening and *cannot be
 *      pressed again*. Both halves matter and they are different mechanisms: a
 *      person tapping twice on a slow connection would otherwise pick a second
 *      file, and `voiAnhDaChon` would open a second picker over the first.
 *      Disabled is not styling here, it is the guard.
 *   2. **Refused.** One Vietnamese sentence naming the next move, announced to a
 *      screen reader rather than only painted, and never a status code. The
 *      sentences live in `api.ts` and `camera/anh-nhom.ts` next to the failures
 *      they describe; this file only decides where they appear.
 *   3. **Done.** The caller is told, and it is the caller's job to show the new
 *      photograph without a reload. This component holds no picture of its own,
 *      which is what stops it from being a second, disagreeing copy of the wall.
 *
 * The whole lifecycle is owned here rather than handed back as a `pick()` the
 * caller drives, for the same reason `voiAnhDaChon` is `with`-shaped: a caller
 * that has to remember a step will eventually not. What a caller supplies is
 * the one thing only it knows -- where these bytes are going.
 *
 * Cancelling the picker is not an error. It leaves no message, no alert and no
 * state change, because a person who backed out did not fail at anything.
 */
import React, { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { radius, space, type, usePalette } from "../theme";
// Imported by file, not through `src/camera/index.ts`, and the reason is that
// the barrel re-exports `native.ts` -- the one module in this app that pulls in
// expo-camera, expo-image-picker and expo-file-system. Reaching it from here
// would drag four native modules into the import graph of every screen that
// renders a button, and node cannot load any of them, so the test build stops
// at the first one. The real picker is loaded below, at the press, where it is
// actually needed.
import { voiAnhDaChon, type GiaiDoanTaiAnh } from "../camera/anh-nhom";
import type { PhotoBackend } from "../camera/bill-photo";
import { ApiError } from "../api";

/** What the button is doing. `null` is the resting state. */
type Pha = null | "dang-chon" | GiaiDoanTaiAnh;

/** What each stage says while it is happening.
 *
 * Three sentences rather than one, because the three waits are genuinely
 * different and a person can tell: the system picker is open and waiting on
 * *them*, shrinking happens on the phone and is quick, uploading is as slow as
 * the network. A single "đang xử lý" would spend most of a slow upload
 * describing a step that finished seconds ago, and would say "processing" while
 * the app is in fact doing nothing but waiting to be handed a file.
 *
 * `dang-chon` is this file's own, not one of `voiAnhDaChon`'s stages. That
 * function announces nothing until the picker has returned, correctly -- it has
 * no work to report yet. But the button still has to be *locked* for that whole
 * time, or a second tap opens a second picker over the first, so the state
 * exists here and is named for what is actually happening.
 */
const LOI_NHAN: Record<NonNullable<Pha>, string> = {
  "dang-chon": "Đang mở thư viện ảnh…",
  "chuan-bi-anh": "Đang chuẩn bị ảnh…",
  "dang-gui": "Đang tải ảnh lên…",
};

export function NutChonAnh({
  nhan,
  moTa,
  taiLen,
  onXong,
  kieu = "chinh",
  backend,
}: {
  /** What the button says at rest. */
  nhan: string;
  /** What a screen reader announces. Says what will happen, not what is drawn. */
  moTa: string;
  /** Where these bytes go. The one thing only the caller knows. */
  taiLen: (photo: { uri: string }) => Promise<void>;
  /** Called once the upload has been accepted, so the caller can show it. */
  onXong?: () => void;
  /** `chinh` is the filled call to action; `nhe` is the quiet one that sits on
   *  a photograph or beside content that already has the eye. */
  kieu?: "chinh" | "nhe";
  /** Injected so the whole lifecycle can be driven without a picker or a phone.
   *  Built lazily when absent rather than defaulted in the signature: a default
   *  parameter runs `backendThuVien()` on every render, which mints a new object
   *  every time and so invalidates the callback below on every render. */
  backend?: PhotoBackend;
}) {
  const c = usePalette();
  const [pha, setPha] = useState<Pha>(null);
  const [loi, setLoi] = useState<string | null>(null);
  // A ref, not state. It exists so two taps landing before React has re-rendered
  // still see the first one -- `dangChay` is read from a render's snapshot and
  // is a frame behind, which is exactly the window a double tap lands in.
  const dangBan = React.useRef(false);

  const dangChay = pha !== null;

  const bam = useCallback(async () => {
    if (dangBan.current) return;
    dangBan.current = true;
    setLoi(null);
    setPha("dang-chon");
    try {
      // Loaded here rather than at the top of the file. The native picker is
      // only needed once somebody has actually asked for one, and deferring it
      // keeps four expo modules out of every screen that merely renders this
      // button. Tests inject `backend` and so never reach this line at all.
      const thuc = backend ?? (await import("../camera/native")).backendThuVien();
      const ket = await voiAnhDaChon(thuc, async (anh) => {
        await taiLen(anh);
        return true;
      }, setPha);
      // `null` means the picker was cancelled. Nothing happened, so nothing is
      // reported -- not a message, and not `onXong`.
      if (ket === true) onXong?.();
    } catch (problem) {
      setLoi(cauNoiVeLoi(problem));
    } finally {
      setPha(null);
      dangBan.current = false;
    }
  }, [backend, onXong, taiLen]);

  const chinh = kieu === "chinh";

  return (
    <View style={{ gap: space.xs }}>
      <Pressable
        onPress={() => void bam()}
        disabled={dangChay}
        accessibilityRole="button"
        accessibilityLabel={moTa}
        // `aria-busy` and not the React Native spelling of it. On
        // react-native-web 0.21.2 the whole `accessibilityState` prop is
        // dropped before it reaches the DOM -- `busy`, `checked`, `selected`
        // and `expanded` alike -- so a button marked busy that way announces as
        // idle while it is uploading. `tests/aria-state.test.mjs` fails any file
        // in `src/` that spells it the other way.
        //
        // `disabled` above needs no aria twin: passing it to a `Pressable`
        // emits `aria-disabled` on web and overrides the native state, so
        // writing both would be two spellings of one fact.
        aria-busy={dangChay}
        style={({ pressed }) => ({
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          // 44pt is the touch-target floor, which is why this is padding around
          // a normal-sized label rather than a smaller box with bigger text.
          minHeight: 44,
          paddingVertical: 11,
          paddingHorizontal: space.md,
          borderRadius: radius.control,
          borderWidth: chinh ? 0 : 1,
          borderColor: c.lineStrong,
          backgroundColor: chinh ? c.accent : c.card,
          // Dimmed while running, and the dimming is never the only signal:
          // the label changes and a spinner appears beside it.
          opacity: pressed || dangChay ? 0.85 : 1,
        })}
      >
        {dangChay ? (
          <ActivityIndicator
            size="small"
            color={chinh ? c.accentInk : c.accent}
            // The label beside it already says what is happening, so the
            // spinner announcing itself a second time is noise.
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
            aria-hidden
          />
        ) : null}
        <Text
          style={{
            ...type.body,
            fontWeight: "600",
            color: chinh ? c.accentInk : c.ink,
          }}
        >
          {dangChay ? LOI_NHAN[pha] : nhan}
        </Text>
      </Pressable>

      {loi ? (
        // `alert` so the sentence is spoken when it appears. Painted-only error
        // text is invisible to exactly the people who most need to be told the
        // thing they just did did not happen.
        <Text style={{ ...type.label, color: c.ink }} accessibilityRole="alert">
          {loi}
        </Text>
      ) : null}
    </View>
  );
}

/**
 * One sentence for a person, from whatever was thrown.
 *
 * Everything reaching here already carries Vietnamese prose written next to the
 * failure it describes: `ApiError` messages come from `ANH_REFUSALS` or
 * `thongDiepNguoiDoc`, and `AnhNhomError` carries its own. So the shape check is
 * about what must *not* be shown -- a raw platform `Error` whose message is
 * English machine text, or a rejected value that is not an `Error` at all.
 *
 * The fallback is a written sentence rather than `String(problem)` deliberately.
 * bug-010822 was exactly this: a rejection carrying an `HTMLCanvasElement` was
 * stringified into a message slot, and "[object HTMLCanvasElement]" appeared on
 * screen where an explanation belonged.
 */
export function cauNoiVeLoi(problem: unknown): string {
  if (problem instanceof ApiError) return problem.message;
  // Named by shape rather than by class so this does not have to import the
  // camera module's error type only to test one field. Anything carrying a
  // `code` we minted and a message we wrote is ours to trust.
  if (
    problem instanceof Error &&
    problem.name === "AnhNhomError" &&
    problem.message.trim() !== ""
  ) {
    return problem.message;
  }
  return "Chưa gửi được tấm ảnh này. Thử lại sau một chút giúp mình.";
}
