/** Whether this device will let us open a camera, and what to do when it will not.
 *
 * Kept free of `expo-camera` on purpose. Everything here is a pure function of
 * a permission response, so the node test runner can walk every branch without
 * a device -- and a device is exactly what we do not have in CI. The native
 * calls live in `native.ts`, which this file never imports.
 *
 * The failure this file exists to prevent is a white screen. An app that asks
 * for the camera, gets "no", and renders nothing looks broken rather than
 * refused, and the person holding the phone has no way to tell which. So every
 * state below carries a sentence and a next action; there is no state that
 * means "render nothing".
 *
 * The distinction that actually matters is `denied` with `canAskAgain: false`.
 * Calling `requestPermission()` again in that state resolves immediately with
 * another `denied` and shows the user no dialog at all -- the OS has stopped
 * delivering the prompt. A button wired to "ask again" there is a button that
 * does nothing, which is worse than no button. That state has to route to
 * system settings instead, and `nextAction` says so.
 */

/** The shape `expo-camera` and `expo-image-picker` both return.
 *
 * Declared structurally rather than imported so this module stays out of the
 * native dependency graph. If expo changes the shape, `native.ts` stops
 * compiling -- that is the intended tripwire.
 */
export type PermissionSnapshot = {
  status: "granted" | "undetermined" | "denied";
  granted: boolean;
  canAskAgain: boolean;
};

/** What the camera surface should be doing right now. */
export type CameraAccessState =
  /** Permission has never been requested. Show the frame, ask on first tap. */
  | "chua-hoi"
  /** Good to go: open the viewfinder. */
  | "cho-phep"
  /** Refused, but the OS will still show the dialog. Asking again is real. */
  | "tu-choi-hoi-lai-duoc"
  /** Refused for good. Only system settings can undo this. */
  | "tu-choi-phai-vao-cai-dat"
  /** No camera on this platform at all -- the web. Fall back to picking a file. */
  | "khong-co-camera";

/** What the UI is allowed to offer in a given state. Exactly one of these. */
export type NextAction =
  /** Call `requestPermission()`. The OS dialog will actually appear. */
  | "xin-quyen"
  /** Open the viewfinder. */
  | "mo-camera"
  /** Send the user to system settings; asking again is a no-op. */
  | "mo-cai-dat"
  /** Open the file/photo picker instead. */
  | "chon-anh";

export type CameraAccess = {
  state: CameraAccessState;
  nextAction: NextAction;
  /** Never empty. A blank explanation is the white screen wearing a hat. */
  message: string;
};

/** Default Vietnamese copy.
 *
 * Exported so the frontend lane can replace the words without having to
 * replace the state machine -- they own how this reads, this file only owns
 * that *something* reads. Overriding a key is fine; deleting one is not, and
 * `assertNoBlankExplanation` below is what catches that.
 */
export const DEFAULT_MESSAGES: Record<CameraAccessState, string> = {
  "chua-hoi":
    "Chụp ảnh bill để app đọc từng món. Ảnh chỉ gửi tới máy chủ của nhóm, không lưu vào thư viện máy.",
  "cho-phep": "Đưa bill vào trong khung, chụp khi chữ đã rõ.",
  "tu-choi-hoi-lai-duoc":
    "App chưa được dùng camera nên chưa chụp được bill. Bấm “Cho phép” để hỏi lại — chỉ dùng lúc chụp, app không mở camera nền.",
  "tu-choi-phai-vao-cai-dat":
    "Quyền camera đang bị tắt trong Cài đặt, nên hỏi lại ở đây sẽ không hiện gì. Mở Cài đặt để bật lại, hoặc chọn một ảnh bill có sẵn.",
  "khong-co-camera":
    "Trình duyệt không mở được camera trong app này. Chọn một ảnh bill có sẵn — các bước sau y hệt trên điện thoại.",
};

/** Does this platform have a camera we can drive at all?
 *
 * `react-native-web` renders `CameraView` as a `<video>` that needs
 * `getUserMedia`, which is unavailable on plain HTTP outside localhost. Rather
 * than ship a viewfinder that stays black on the demo laptop, the web path is
 * "pick a file" by construction. `hasCamera` is passed in rather than read from
 * `Platform` here so tests can drive both sides.
 */
export function readAccess(
  permission: PermissionSnapshot | null,
  hasCamera: boolean,
  messages: Record<CameraAccessState, string> = DEFAULT_MESSAGES,
): CameraAccess {
  const state = readState(permission, hasCamera);
  return { state, nextAction: ACTION_FOR[state], message: messages[state] };
}

const ACTION_FOR: Record<CameraAccessState, NextAction> = {
  "chua-hoi": "xin-quyen",
  "cho-phep": "mo-camera",
  "tu-choi-hoi-lai-duoc": "xin-quyen",
  "tu-choi-phai-vao-cai-dat": "mo-cai-dat",
  "khong-co-camera": "chon-anh",
};

function readState(
  permission: PermissionSnapshot | null,
  hasCamera: boolean,
): CameraAccessState {
  // Checked before the permission, not after. A granted camera permission on a
  // browser that cannot open a camera is still no camera, and routing that to
  // "mo-camera" is how the black viewfinder gets shipped.
  if (!hasCamera) return "khong-co-camera";

  // `null` is the hook's first render, before it has read the OS. Treating it
  // as "denied" would flash a refusal screen on every cold start.
  if (permission === null) return "chua-hoi";

  if (permission.granted) return "cho-phep";
  if (permission.status === "undetermined") return "chua-hoi";

  // status === "denied" from here. The only thing that decides whether a
  // "try again" button is honest is `canAskAgain`.
  return permission.canAskAgain ? "tu-choi-hoi-lai-duoc" : "tu-choi-phai-vao-cai-dat";
}

/** Every state names a sentence, and none of them is blank.
 *
 * Called by the tests against both the default copy and any override the
 * frontend lane supplies, because "we replaced the strings" is the realistic
 * way a blank explanation gets back in.
 */
export function assertNoBlankExplanation(
  messages: Record<CameraAccessState, string>,
): void {
  for (const state of Object.keys(ACTION_FOR) as CameraAccessState[]) {
    const text = messages[state];
    if (typeof text !== "string" || text.trim() === "") {
      throw new Error(`Trạng thái "${state}" không có lời giải thích nào.`);
    }
  }
}
