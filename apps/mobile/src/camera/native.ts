/** The real `PhotoBackend`, wired to expo-camera and friends.
 *
 * This is the only file in `src/camera/` that imports a native module, which
 * is why it is the only one the node test runner cannot load. It is kept as
 * thin as it can be: every decision worth testing lives in `bill-photo.ts` or
 * `access.ts`, and what remains here is the adapter that `tsc --noEmit` and the
 * web export build check.
 *
 * All four modules used here ship inside Expo Go, deliberately. The phone path
 * from `scripts/phone_path.py` is "scan a QR with Expo Go"; a module that needs
 * a custom dev client would break that path for everyone, and we would find out
 * on a phone rather than in CI.
 */
import { Platform } from "react-native";
import type { CameraView } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { File } from "expo-file-system";

import { fitLongestEdge, type BillPhoto, type PhotoBackend, type TempPhoto } from "./bill-photo";

/** Whether `CameraView` can actually produce frames on this platform.
 *
 * The web branch is not pessimism about `react-native-web`: `getUserMedia` is
 * gated behind a secure context, and the demo runs over plain HTTP on a LAN
 * address, which is not one. A viewfinder there stays black with no error, so
 * the web path is the picker by construction rather than by fallback.
 */
export const HAS_CAMERA = Platform.OS !== "web";

/** Build the backend around a mounted `CameraView`.
 *
 * The ref is passed in rather than owned here because the frontend lane owns
 * where the viewfinder sits on screen. This module only needs to be able to
 * fire the shutter on whatever they mounted.
 */
export function nativeBackend(camera: { current: CameraView | null }): PhotoBackend {
  return {
    async capture(): Promise<TempPhoto> {
      const view = camera.current;
      if (view === null) {
        throw new Error("Camera chưa sẵn sàng — thử lại sau một nhịp.");
      }
      const shot = await view.takePictureAsync({
        // Full quality here, compression in the next step. Compressing twice
        // costs strokes on printed digits and buys nothing.
        quality: 1,
        // GPS lives in EXIF. A bill photo should not carry where the group
        // was sitting, so it is never written rather than stripped later.
        exif: false,
        // We want a file path, not a megabyte of base64 in the JS heap.
        base64: false,
        // Nothing here writes to the photo library, and no MediaLibrary
        // permission is requested anywhere in this app. `takePictureAsync`
        // writes into the app's own cache directory only.
      });
      if (shot === undefined) {
        throw new Error("Máy ảnh không trả về ảnh nào.");
      }
      return { uri: shot.uri, width: shot.width, height: shot.height };
    },

    async pick(): Promise<TempPhoto | null> {
      // No permission request on this path. Since SDK 51 the system picker
      // runs out of process and hands back only the chosen file, so asking for
      // library access would be asking for more than we use -- and on the web
      // there is no permission to ask for at all.
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 1,
        exif: false,
        allowsMultipleSelection: false,
      });
      if (result.canceled) return null;
      const asset = result.assets[0];
      if (asset === undefined) return null;
      return { uri: asset.uri, width: asset.width, height: asset.height };
    },

    async compress(source: TempPhoto, maxEdge: number, quality: number): Promise<BillPhoto> {
      const context = ImageManipulator.manipulate(source.uri);
      const target = fitLongestEdge(source.width, source.height, maxEdge);
      // `null` means it already fits. Re-encoding a small image at 0.7 only
      // softens the text we are about to ask a model to read.
      if (target !== null) context.resize({ width: target.width, height: target.height });

      const rendered = await context.renderAsync();
      const saved = await rendered.saveAsync({
        compress: quality,
        // JPEG, not PNG: a photo of paper is a photograph, and PNG would send
        // a lossless several-megabyte file for no readability gain.
        format: SaveFormat.JPEG,
        base64: false,
      });

      return {
        uri: saved.uri,
        width: saved.width,
        height: saved.height,
        bytes: await sizeOf(saved.uri),
      };
    },

    async discard(uri: string): Promise<void> {
      // Only ever our own cache. A uri from somewhere else is not ours to
      // delete, and on the web `blob:` urls are released by the browser.
      if (!uri.startsWith("file://")) return;
      const file = new File(uri);
      if (file.exists) file.delete();
    },
  };
}

/** Bytes of the encoded image, or 0 when it cannot be established.
 *
 * 0 is not a silent fallback: `compressForReading` treats a non-positive size
 * as "khong-doc-duoc" and refuses, rather than sending an image whose size we
 * never managed to measure. Guessing a plausible number here would disarm the
 * `MAX_BYTES` tripwire on exactly the platform where it is hardest to notice.
 *
 * Two platforms, two real measurements. On native the file is on disk. On the
 * web the manipulator hands back a `blob:` url, which has no filesystem behind
 * it but does answer a `fetch` from the same document.
 */
async function sizeOf(uri: string): Promise<number> {
  try {
    if (uri.startsWith("file://")) return new File(uri).size;
    const blob = await fetch(uri).then((response) => response.blob());
    return blob.size;
  } catch {
    return 0;
  }
}
