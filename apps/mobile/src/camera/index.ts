/** The camera contract the bill screen uses.
 *
 * Split by lane: this directory owns the native half (permission, shutter,
 * compression, deleting temporary files); `src/ui/` and the screen own how any
 * of it looks. Nothing here renders, and nothing here decides layout -- the
 * viewfinder frame from the mockup is the frontend lane's to build.
 *
 * The intended shape of a bill screen:
 *
 * ```tsx
 * const camera = useRef<CameraView>(null);
 * const [permission, requestPermission] = useCameraPermissions();
 * const access = readAccess(permission, HAS_CAMERA);
 *
 * // access.nextAction says which single control to show:
 * //   "xin-quyen"   -> button calling requestPermission()
 * //   "mo-camera"   -> the shutter
 * //   "mo-cai-dat"  -> button calling openAppSettings()
 * //   "chon-anh"    -> button calling pick
 * // access.message is never empty, so there is always something to render.
 *
 * const result = await withBillPhoto(nativeBackend(camera), "camera",
 *   (photo) => uploadBill(photo));   // <- api.ts; the only place bytes leave
 * // Both temp files are gone by the time this resolves, upload or throw.
 * // `null` means the user cancelled the picker: not an error, do not alert.
 * ```
 *
 * `withBillPhoto` never hands out a uri the caller has to clean up, and that is
 * the point. A bill photo the app forgot to delete is the kind of leak that
 * only shows up on someone's real phone, months later.
 */
export {
  readAccess,
  assertNoBlankExplanation,
  DEFAULT_MESSAGES,
  type CameraAccess,
  type CameraAccessState,
  type NextAction,
  type PermissionSnapshot,
} from "./access";

export {
  withBillPhoto,
  compressForReading,
  fitLongestEdge,
  BillPhotoError,
  MAX_EDGE,
  MAX_BYTES,
  QUALITY,
  type BillPhoto,
  type GiaiDoanDocBill,
  type PhotoBackend,
  type TempPhoto,
} from "./bill-photo";

export { nativeBackend, HAS_CAMERA } from "./native";
export { openAppSettings } from "./settings";
