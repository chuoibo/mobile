/** Making the screen behind a sheet genuinely unreachable.
 *
 * A sheet that covers the screen but leaves what is under it in the tab order
 * is the defect QA measured on the [+] menu: Tab walked onto four tab buttons
 * and the close button, every one of them 100% covered by the sheet and every
 * one still focusable and pressable. WCAG 2.4.3. Drawing something on top is a
 * paint operation; it says nothing to the focus order or to a screen reader.
 *
 * The web primitive for this is `inert`, which removes a whole subtree from
 * the tab order *and* from the accessibility tree in one attribute. It is not
 * reachable through react-native-web's prop list, so it is set on the host node
 * through a ref -- which is also why this is web-only and says so out loud
 * rather than pretending to be cross-platform. On iOS and Android a sheet is
 * drawn over the screen and VoiceOver/TalkBack scope differently; making that
 * correct is a separate change with its own evidence, and this hook does
 * nothing there instead of doing something unverified.
 *
 * Focus is also put back where it came from on close. Losing focus to `<body>`
 * when a menu closes means the next Tab restarts at the top of the page, which
 * is its own 2.4.3 problem and would have been introduced by fixing the first
 * one.
 */
import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import type { View } from "react-native";

/** `inert` is newer than the DOM lib this project compiles against on some
 *  TypeScript versions, so it is declared optional rather than asserted. */
type HostNode = HTMLElement & { inert?: boolean };

/**
 * Returns a ref to put on the container holding everything *behind* a sheet.
 * While `open`, that container cannot be tabbed into and is hidden from
 * assistive technology.
 */
export function useInertBackground(open: boolean) {
  const ref = useRef<View | null>(null);

  useEffect(() => {
    if (Platform.OS !== "web" || !open) return;
    const node = ref.current as unknown as HostNode | null;
    if (!node) return;

    // Read before the node goes inert: setting `inert` blurs whatever is
    // inside it, so asking afterwards returns `<body>` every time.
    const before = typeof document !== "undefined" ? document.activeElement : null;

    node.inert = true;
    node.setAttribute("aria-hidden", "true");

    return () => {
      node.inert = false;
      node.removeAttribute("aria-hidden");
      if (before instanceof HTMLElement && before.isConnected) before.focus();
    };
  }, [open]);

  return ref;
}
