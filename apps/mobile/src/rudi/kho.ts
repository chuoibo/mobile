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
 * Two stores, not one, and the split is not stylistic:
 *
 *   - `AsyncStorage` for the draft session. Plain, unencrypted, and correct for
 *     what it holds -- a fixture trip, a display name somebody typed, which
 *     places they tapped a heart on.
 *   - `SecureStore` for the session token, per ADR-0014 section 9. A bearer in
 *     `AsyncStorage` is a bearer in a world-readable file on a rooted device.
 *     Nothing calls the token half yet; it is the address the token will have.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const KHOA_PHIEN = "rudi.phien.v1";
const KHOA_TOKEN = "rudi.token";

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

/** ADR-0014 section 9. Nothing calls these until the session route exists. */
export async function docTokenAsync(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(KHOA_TOKEN);
  } catch {
    return null;
  }
}

export async function ghiTokenAsync(token: string): Promise<KetQuaGhi> {
  try {
    await SecureStore.setItemAsync(KHOA_TOKEN, token);
    return { ok: true };
  } catch (error) {
    return { ok: false, ly_do: error instanceof Error ? error.message : String(error) };
  }
}

export async function xoaTokenAsync(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(KHOA_TOKEN);
  } catch {
    // A token that cannot be deleted is a token that will be rejected by the
    // server on its next use; the 401 path handles that.
  }
}
