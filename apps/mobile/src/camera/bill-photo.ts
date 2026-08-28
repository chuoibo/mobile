/** Getting a bill photo small enough to send, and gone once it is sent.
 *
 * A bill is sensitive: it carries what a group ate, where, when, and often a
 * bank line at the bottom. The repo rules say photos of bills never enter git;
 * the same reasoning applies to the phone. So this module holds three promises
 * and the tests pin all three:
 *
 *   1. **Never into the photo library.** We capture into the app's own cache
 *      directory and never call MediaLibrary. Nothing here asks for write
 *      access to the camera roll, and nothing should start.
 *   2. **Nowhere but our own API.** This module hands back bytes; it does not
 *      know a URL. Anything that uploads is `api.ts`, which talks to exactly
 *      one host.
 *   3. **Temporary files are deleted after reading.** Including when the read
 *      throws -- see `withBillPhoto`. A failed upload leaving the original
 *      full-resolution capture in the cache is the leak nobody notices,
 *      because the happy path looks clean.
 *
 * EXIF is dropped, and that is a privacy decision rather than a size one. A
 * phone camera writes GPS into every frame by default, so a bill photo says
 * where the group was sitting. The compression step re-encodes without it, and
 * `exif: false` at the capture call means it is never written in the first
 * place.
 *
 * The native calls are injected as `PhotoBackend` rather than imported. That is
 * what lets the node test runner drive the whole lifecycle -- including the
 * delete-on-failure path, which is impossible to trigger reliably on a real
 * device and is precisely the path worth testing.
 */

/** A photo sitting in the app's private cache, not yet read. */
export type TempPhoto = {
  uri: string;
  width: number;
  height: number;
};

/** A photo that has been shrunk and stripped, ready to send. */
export type BillPhoto = {
  uri: string;
  width: number;
  height: number;
  /** Bytes on disk. Used to prove compression happened, and to refuse absurdities. */
  bytes: number;
};

/** The native surface this module needs. Implemented for real in `native.ts`. */
export type PhotoBackend = {
  /** Take a picture with the open viewfinder. Must not touch the photo library. */
  capture(): Promise<TempPhoto>;
  /** Pick an existing image. The web path, and the fallback when permission is off. */
  pick(): Promise<TempPhoto | null>;
  /** Resize + re-encode as JPEG. Returns a NEW uri; the source is untouched. */
  compress(source: TempPhoto, maxEdge: number, quality: number): Promise<BillPhoto>;
  /** Remove a cache file. Must not throw when the file is already gone. */
  discard(uri: string): Promise<void>;
};

/** Longest edge we send, in pixels.
 *
 * 1600 is chosen against the reader, not against the network: below roughly
 * 1200 the printed line items on a Vietnamese receipt start losing strokes
 * once JPEG has had its turn, and a bill the model cannot read costs far more
 * than the extra kilobytes. Above 1600 the file grows without the text getting
 * any sharper, because phone camera output is already softer than its pixel
 * count suggests.
 */
export const MAX_EDGE = 1600;

/** JPEG quality. Same reasoning: legibility first, size second. */
export const QUALITY = 0.7;

/** Refuse to send anything larger than this.
 *
 * Not a performance guard. It is a tripwire: if compression silently no-ops --
 * a wrong uri, a backend returning its input, a platform where the manipulator
 * is a stub -- the original 4-6 MB capture would otherwise sail out to the API
 * and everything would look fine. This turns that into a visible failure.
 */
export const MAX_BYTES = 2 * 1024 * 1024;

export class BillPhotoError extends Error {
  constructor(
    readonly code: "qua-lon" | "khong-doc-duoc",
    message: string,
  ) {
    super(message);
    this.name = "BillPhotoError";
  }
}

/** Capture (or pick) a bill, shrink it, run `use`, then delete every temp file.
 *
 * `use` gets the compressed photo and does whatever comes next -- normally
 * uploading it. When `use` resolves, or rejects, or the compression itself
 * fails, both the original capture and the compressed copy are removed. The
 * caller cannot forget, because the caller is never handed a uri it has to
 * clean up.
 *
 * Returns whatever `use` returned, or `null` when the user cancelled the
 * picker. Cancelling is not an error and must not be rendered as one.
 */
export async function withBillPhoto<T>(
  backend: PhotoBackend,
  source: "camera" | "thu-vien",
  use: (photo: BillPhoto) => Promise<T>,
): Promise<T | null> {
  const captured = source === "camera" ? await backend.capture() : await backend.pick();
  if (captured === null) return null;

  // Collected as we go rather than at the end: if `compress` throws, the
  // original still has to be deleted, and it is only reachable from here.
  const temps: string[] = [captured.uri];
  try {
    const photo = await compressForReading(backend, captured);
    if (photo.uri !== captured.uri) temps.push(photo.uri);
    return await use(photo);
  } finally {
    // Sequential and individually guarded. One unlink failing must not leave
    // the rest of the files behind -- that is how a cleanup path turns into a
    // leak on the one device where it matters.
    for (const uri of temps) {
      try {
        await backend.discard(uri);
      } catch {
        // A file we cannot delete is not worth failing an upload over, and
        // `discard` is contractually allowed to find it already gone.
      }
    }
  }
}

/** Shrink and strip, then refuse the result if it did not actually shrink.
 *
 * When the result is refused, the refused file is deleted here rather than left
 * for the caller. By that point `compress` has already written it to disk, so
 * there is a real file that no one else has a uri for: `withBillPhoto` only
 * learns the compressed uri from a successful return, so anything thrown past
 * it would leak. And the file leaked this way is the worst one to leak -- the
 * size tripwire fires precisely when compression did NOT shrink the capture, so
 * what stays behind is the full-resolution bill.
 */
export async function compressForReading(
  backend: PhotoBackend,
  captured: TempPhoto,
): Promise<BillPhoto> {
  const photo = await backend.compress(captured, MAX_EDGE, QUALITY);

  const refuse = async (error: BillPhotoError): Promise<never> => {
    // Same guard as the cleanup in `withBillPhoto`: failing to unlink must not
    // replace the real complaint with a confusing one.
    if (photo.uri !== captured.uri) {
      try {
        await backend.discard(photo.uri);
      } catch {
        // `discard` is contractually allowed to find it already gone.
      }
    }
    throw error;
  };

  if (!Number.isFinite(photo.bytes) || photo.bytes <= 0) {
    return refuse(
      new BillPhotoError(
        "khong-doc-duoc",
        "Không đọc được ảnh vừa chụp. Chụp lại giúp mình một lần nữa.",
      ),
    );
  }
  if (photo.bytes > MAX_BYTES) {
    return refuse(
      new BillPhotoError(
        "qua-lon",
        "Ảnh bill quá lớn để gửi đi. Chụp lại gần hơn một chút.",
      ),
    );
  }
  return photo;
}

/** The longest-edge fit used by the real backend, kept here so it is testable.
 *
 * Returns `null` when the image is already small enough, which the backend
 * turns into "skip the resize" -- re-encoding a small image only makes it
 * blurrier. Only the longest edge is constrained; the other follows from
 * aspect ratio, because a bill is tall and forcing it into a square crops off
 * either the total or the items.
 */
export function fitLongestEdge(
  width: number,
  height: number,
  maxEdge: number,
): { width: number; height: number } | null {
  const longest = Math.max(width, height);
  if (longest <= maxEdge) return null;
  const scale = maxEdge / longest;
  // Round rather than floor: flooring a 1600-px edge can land on 1599 and make
  // "did it fit?" assertions fail for no visible reason.
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}
