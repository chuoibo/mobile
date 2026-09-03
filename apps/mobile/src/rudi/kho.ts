/**
 * Where the bytes actually live. Four calls, no logic.
 *
 * Split from `luu-tru.ts` on purpose: both modules below are native modules,
 * so importing either one makes this file impossible to compile into
 * `tsconfig.test.json` and impossible to exercise under bare `node`. Every
 * decision that can be WRONG lives in `luu-tru.ts`, which imports nothing and
 * is tested against deliberately corrupt input. This file is the part a test
 * could only re-assert by mocking, which proves nothing.
 *
 * `AsyncStorage` and nothing else, on purpose. What this holds is a draft over
 * a fixture -- a trip nobody took, a display name somebody typed, which places
 * they tapped a heart on. None of it is a credential.
 *
 * The session bearer lives in `src/phien.ts` (ADR-0014, shipped in PR #514),
 * which keeps it in SecureStore and imports that native module dynamically so
 * the node test suite can still load the API layer. An earlier draft of this
 * file grew a second token store beside it; two places holding one credential
 * is one place too many, and it was deleted rather than merged.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

const KHOA_PHIEN = "rudi.phien.v1";

/** Whether the last write reached the disk. `null` means nothing tried yet. */
export type KetQuaGhi = { ok: true } | { ok: false; ly_do: string };

export async function docPhienThoAsync(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(KHOA_PHIEN);
  } catch {
    // A read that fails is indistinguishable from a first launch, and both
    // answers are the same: use the seed.
    return null;
  }
}

/**
 * Write, and REPORT whether it worked.
 *
 * Not fire-and-forget. The screens say "lưu trên máy" out loud, and a silent
 * swallow here is how that sentence goes back to being a lie -- which is the
 * defect this whole branch exists to remove. The caller keeps the answer and
 * the copy follows it.
 */
export async function ghiPhienThoAsync(raw: string): Promise<KetQuaGhi> {
  try {
    await AsyncStorage.setItem(KHOA_PHIEN, raw);
    return { ok: true };
  } catch (error) {
    return { ok: false, ly_do: error instanceof Error ? error.message : String(error) };
  }
}

export async function xoaPhienAsync(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KHOA_PHIEN);
  } catch {
    // Logging out cannot fail into a state where the person is still logged in
    // from the screen's point of view; the in-memory reset has already happened.
  }
}
