/** Sending someone to the OS settings page for this app.
 *
 * Needed by exactly one state: permission denied with `canAskAgain: false`.
 * There, `requestPermission()` resolves with another denial and shows no
 * dialog, so settings is the only door left. Wiring that state to "ask again"
 * gives the user a button that visibly does nothing.
 *
 * `Linking.openSettings()` is a no-op on the web, which is correct rather than
 * unfortunate: the web never reaches that state, because `HAS_CAMERA` is false
 * there and access resolves to "khong-co-camera" first.
 */
import { Linking, Platform } from "react-native";

export async function openAppSettings(): Promise<void> {
  if (Platform.OS === "web") return;
  await Linking.openSettings();
}
