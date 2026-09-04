/**
 * The library picker and the wall's compression, as two steps instead of App
 * B's one: the share screen shows the chosen photo before anything is sent,
 * so the pick has to come back first and the compress-and-discard runs only
 * when the person confirms. Same backend, same limits, same cleanup.
 *
 * Kept apart from `ky-niem.ts` so the bridge stays loadable in node tests:
 * the backend is a native module.
 */
import { nenLai, type GiaiDoanTaiAnh } from "../../camera/anh-nhom";
import type { PhotoBackend, TempPhoto } from "../../camera/bill-photo";
import { backendThuVien } from "../../camera/native";

export type { GiaiDoanTaiAnh, TempPhoto };

let backend: PhotoBackend | null = null;
function thuVien(): PhotoBackend {
  if (backend === null) backend = backendThuVien();
  return backend;
}

/** `null` when the person closed the picker without choosing. The file stays until `nenVaDung` or `boAnh`. */
export function chonAnh(): Promise<TempPhoto | null> {
  return thuVien().pick();
}

/** Shrink to the wall's limits, hand the result to `use`, then discard both temp files. */
export async function nenVaDung<T>(
  daChon: TempPhoto,
  use: (anh: { uri: string }) => Promise<T>,
  onGiaiDoan?: (giaiDoan: GiaiDoanTaiAnh) => void,
): Promise<T> {
  onGiaiDoan?.("chuan-bi-anh");
  const tam: string[] = [daChon.uri];
  try {
    const anh = await nenLai(thuVien(), daChon);
    if (anh.uri !== daChon.uri) tam.push(anh.uri);
    onGiaiDoan?.("dang-gui");
    return await use(anh);
  } finally {
    for (const uri of tam) {
      try {
        await thuVien().discard(uri);
      } catch {
        // A temp file that would not delete is not the person's problem.
      }
    }
  }
}

/** Drop a picked photo the person decided not to share. */
export async function boAnh(daChon: TempPhoto): Promise<void> {
  try {
    await thuVien().discard(daChon.uri);
  } catch {
    // Same as above.
  }
}
