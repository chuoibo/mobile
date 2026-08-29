/** Choosing a photograph to keep, and getting it off the phone cleanly.
 *
 * This is the group-photo and avatar counterpart to `bill-photo.ts`, and the
 * two are deliberately separate modules rather than one with a flag. They look
 * alike -- pick, shrink, hand the bytes to a caller, delete the temporary
 * files -- and they are answering different questions:
 *
 *   - A bill is read and thrown away. `MAX_BYTES` there is a tripwire proving
 *     compression actually ran, because an uncompressed 6 MB capture reaching
 *     the reader would look like success. Its sentences say "chụp lại gần hơn",
 *     which is advice about a piece of paper.
 *   - A memory photo is *kept*. It is going into the group's wall and people
 *     will look at it later, so shrinking it to bill dimensions would be
 *     destroying the thing the feature exists to store. Its sentences are about
 *     choosing a different picture, because there is nothing to re-photograph.
 *
 * Merging them would mean one function whose constants and whose words both
 * depend on a caller-supplied mode, which is two functions wearing one name.
 * What is shared is shared for real: the `PhotoBackend` contract and the
 * `BillPhoto` shape come from `bill-photo.ts` rather than being restated, so
 * there is still exactly one native adapter for both paths.
 *
 * The cleanup promise is the same and is the reason this is a `with`-shaped
 * function rather than a `pick()` that returns a uri. The caller is never
 * handed a file it has to remember to delete, so it cannot forget -- and the
 * file most worth deleting is the one left behind when the upload *failed*,
 * which is the path nobody exercises by hand.
 *
 * What this module deliberately does not do:
 *
 *  - **It does not strip EXIF, and does not claim to.** The server sanitises
 *    every uploaded image: it decodes, drops metadata, and re-encodes. Doing it
 *    here as well would be a second implementation of a privacy guarantee, and
 *    the weaker of the two -- this one runs only when this code path is used,
 *    the server's runs on every byte that arrives. `exif: false` at the picker
 *    is asked for anyway, because not reading a coordinate is strictly better
 *    than reading it and discarding it, but the guarantee is the server's.
 *  - **It does not know a URL.** Nothing here uploads. `api.ts` is the only
 *    file that names a host, which is what keeps "where can a photo of my
 *    friends go" answerable by reading one file.
 */
import { fitLongestEdge, type BillPhoto, type PhotoBackend, type TempPhoto } from "./bill-photo";

/** Longest edge kept, in pixels.
 *
 * 2048 rather than the bill path's 1600, and the difference is the point: this
 * image is the artefact, not a means of reading one. 2048 is still a real
 * reduction from a modern phone's 4000-px capture, so a wall of twenty photos
 * does not cost a hundred megabytes, and it is comfortably above what any
 * screen in this app displays -- the polaroid frames are under 200 pt wide.
 */
export const CANH_DAI_NHAT = 2048;

/** JPEG quality. Higher than the bill's 0.7 for the same reason as the edge. */
export const CHAT_LUONG = 0.85;

/** Refuse to send anything larger than this.
 *
 * The server's own ceiling is 10 MiB and it answers 413. This sits below it so
 * that the ordinary case -- a photo that did not compress because the
 * manipulator silently no-opped -- is caught before it costs somebody a slow
 * upload over mobile data that ends in a refusal. Reaching the server's 413 is
 * still handled, in `api.ts`; this is the cheaper of two nets, not the only one.
 */
export const NHIEU_BYTE_NHAT = 8 * 1024 * 1024;

export class AnhNhomError extends Error {
  constructor(
    readonly code: "qua-lon" | "khong-doc-duoc",
    message: string,
    /** The platform failure underneath, when there was one. Never rendered. */
    options?: { cause?: unknown },
  ) {
    super(message, options);
    this.name = "AnhNhomError";
  }
}

/** Where a chosen photo has got to.
 *
 * Two values, because there are two waits and they feel different: shrinking a
 * 12-megapixel photo takes a moment on an older phone, and the upload takes as
 * long as the network takes. A single "đang xử lý" spends most of a slow upload
 * describing the wrong step.
 *
 * Not a percentage. Nothing here knows how many bytes have left the device, and
 * a progress bar that moves on a timer is a lie with an animation.
 */
export type GiaiDoanTaiAnh = "chuan-bi-anh" | "dang-gui";

/**
 * Pick a photo, shrink it, run `use`, then delete every temporary file.
 *
 * Returns whatever `use` returned, or `null` when the person backed out of the
 * picker. Cancelling is not an error and must never be rendered as one -- that
 * was the whole reason the picker's `null` is a distinct value rather than a
 * throw.
 *
 * `use` runs while both temp files still exist and they are removed afterwards,
 * including when `use` rejects. A failed upload leaving the full-resolution
 * original in the app's cache is the leak nobody notices, because the happy
 * path looks identical.
 */
export async function voiAnhDaChon<T>(
  backend: PhotoBackend,
  use: (photo: BillPhoto) => Promise<T>,
  onGiaiDoan?: (giaiDoan: GiaiDoanTaiAnh) => void,
): Promise<T | null> {
  const daChon = await backend.pick();
  if (daChon === null) return null;
  // Announced after the cancel check: somebody who backed out never started,
  // and naming a stage for them would be the screen inventing work.
  onGiaiDoan?.("chuan-bi-anh");

  // Collected as we go rather than at the end: if `nenLai` throws, the original
  // still has to be deleted, and this is the only place holding its uri.
  const tam: string[] = [daChon.uri];
  try {
    const anh = await nenLai(backend, daChon);
    if (anh.uri !== daChon.uri) tam.push(anh.uri);
    onGiaiDoan?.("dang-gui");
    return await use(anh);
  } finally {
    // Sequential and individually guarded. One unlink failing must not leave
    // the rest behind -- that is how a cleanup path becomes a leak.
    for (const uri of tam) {
      try {
        await backend.discard(uri);
      } catch {
        // `discard` is contractually allowed to find it already gone, and a
        // file we cannot delete is not worth failing an upload over.
      }
    }
  }
}

/** Shrink and re-encode, then refuse a result that is obviously wrong.
 *
 * A refused file is deleted here rather than left for the caller. By this point
 * `compress` has written a real file that nobody else holds a uri for, and the
 * one refused by the size check is the worst one to leak: the check fires
 * precisely when compression did *not* shrink the original.
 */
export async function nenLai(
  backend: PhotoBackend,
  daChon: TempPhoto,
): Promise<BillPhoto> {
  let anh: BillPhoto;
  try {
    anh = await backend.compress(daChon, CANH_DAI_NHAT, CHAT_LUONG);
  } catch (problem) {
    throw loiKhongMoDuoc(problem);
  }

  const tuChoi = async (error: AnhNhomError): Promise<never> => {
    if (anh.uri !== daChon.uri) {
      try {
        await backend.discard(anh.uri);
      } catch {
        // Failing to unlink must not replace the real complaint with a
        // confusing one.
      }
    }
    throw error;
  };

  if (!Number.isFinite(anh.bytes) || anh.bytes <= 0) {
    return tuChoi(
      new AnhNhomError(
        "khong-doc-duoc",
        "Không mở được tấm ảnh này. Chọn một tấm khác giúp mình.",
      ),
    );
  }
  if (anh.bytes > NHIEU_BYTE_NHAT) {
    return tuChoi(
      new AnhNhomError(
        "qua-lon",
        "Tấm ảnh này nặng quá nên chưa gửi lên được. Chọn một tấm nhẹ hơn giúp mình.",
      ),
    );
  }
  return anh;
}

/** What a person is told when the platform could not open the file at all.
 *
 * The same three shapes `bill-photo.ts` documents at length, and the same
 * reading of them -- see bug-010822 there for the measurement. Restated here
 * with this screen's words rather than imported, because the sentences are the
 * part that differs: telling somebody choosing a holiday photo to "chụp lại"
 * sends them to a camera when what they need is a different file.
 *
 * The middle case is the load-bearing one. `expo-image-manipulator` on the web
 * rejects with the `HTMLCanvasElement` it was going to draw into when the
 * browser cannot decode the source, so a non-`Error` rejection from this one
 * backend means exactly "that file is not an image". Being wrong about it costs
 * a slightly-too-specific sentence; the third branch catches everything else
 * and never puts the platform's English on screen.
 */
function loiKhongMoDuoc(problem: unknown): AnhNhomError {
  if (problem instanceof AnhNhomError) return problem;
  if (!(problem instanceof Error)) {
    return new AnhNhomError(
      "khong-doc-duoc",
      "File bạn chọn không phải là ảnh nên máy không mở được. Chọn một tấm ảnh rồi thử lại.",
      { cause: problem },
    );
  }
  return new AnhNhomError(
    "khong-doc-duoc",
    "Không mở được tấm ảnh này. Chọn một tấm khác giúp mình.",
    { cause: problem },
  );
}

export { fitLongestEdge };
