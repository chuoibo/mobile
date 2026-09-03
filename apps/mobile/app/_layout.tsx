import { Stack, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef } from "react";
import { Linking, LogBox, Platform } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { diemVaoTuUrl, manDau } from "../src/rudi/duong-vao";
import { datLoiMoiDen } from "../src/rudi/loi-moi-den";
import { RudiSessionProvider, useRudiSession } from "../src/rudi/session";
import { useRudiTheme } from "../src/rudi/theme";

// Module level, before the first frame: `index.ts` never runs under
// `expo-router/entry`, so the call that used to live in the legacy App.tsx never
// ran on this shell. Measured on Expo Go 57 / Android 15: the LogBox strip sat
// over the tab bar and swallowed the "Tạo mới" button -- the door to the hero
// flow -- with no error and no navigation. Only the *notification* is silenced:
// uncaught errors still open LogBox full-screen, and warnings still reach the
// console and logcat. No-op in release builds and on web.
LogBox.ignoreAllLogs();

/*
 * Direction contract (Impeccable, code-led; RN has no HTML to carry it):
 * THESIS  -- A warm evening with friends, organised by a calm assistant: every
 *            screen tells one group what happens next and what it costs, nothing more.
 * OWN-WORLD -- Cream ground, white cards, one leading tone per screen (accent =
 *            brand action, split = money, ai = machine output); brand gradients
 *            only on hero and primary CTA, never under small text.
 * STORY   -- Discover -> plan together in chat -> go -> photograph the bill ->
 *            everyone sees their own share; the screen never invents a number.
 * FIRST VIEWPORT -- The tab bar and one decision above it, on a 360x800 phone,
 *            with real data or an honest empty state; no fixture text in production.
 * FORM    -- expo-router stack + 4 tabs + create sheet; 44pt targets, 12px floor,
 *            tabular-nums for money, motion <= 220ms.
 * FINISH: the shipped screens are reviewed on the emulator, not on the web export.
 */
/** Decides the first screen of a cold start, and routes warm links.
 *
 * The URL decision lives in `src/rudi/duong-vao.ts` so it can be tested
 * without a device; see the docstring there for the deep link this used to
 * swallow. The session decision (`manDau`) lives beside it for the same
 * reason: a pathless launch means «welcome» only for somebody signed out. */
function LegacyFragmentAdapter() {
  const router = useRouter();
  const { phien, phienDaDoc } = useRudiSession();
  // Once. The effect below re-runs when the session changes (sign-in, sign-out)
  // and must not replay the cold-start redirect on top of wherever the person
  // navigated to since.
  const daQuyetDinh = useRef(false);

  useEffect(() => {
    if (Platform.OS === "web") return;
    // Not before the disk has answered: deciding on `phien === null` while
    // SecureStore is still reading would send every signed-in person to the
    // welcome screen on every launch.
    if (!phienDaDoc || daQuyetDinh.current) return;
    daQuyetDinh.current = true;
    let live = true;
    void Linking.getInitialURL().then((url) => {
      // Re-checked after the await, not before it. The guard that was only
      // checked before is the whole of the defect.
      if (!live) return;
      const diem = diemVaoTuUrl(url);
      if (diem.kieu === "loi-moi") {
        // The code goes through a module, never through a route param: a
        // single-use bearer secret should not land in navigation state. See
        // `src/rudi/loi-moi-den.ts`.
        datLoiMoiDen(diem.ma);
        router.replace("/moi" as never);
        return;
      }
      if (diem.kieu !== "doi-huong") return;
      // «welcome» from the URL alone becomes «back where you were» when a
      // session survived the restart. Same function `app/index.tsx` uses.
      const toi = diem.toi === "/welcome" ? manDau(phien) : diem.toi;
      router.replace(toi as never);
    });
    return () => {
      live = false;
    };
  }, [router, phien, phienDaDoc]);

  useEffect(() => {
    if (Platform.OS === "web") return;
    // Warm links: the app is already open when a friend's invite arrives, or
    // when the dev client (whose launcher swallows cold `rudi://` links) hands
    // one over after the bundle is up. Same decision function, same routes.
    // A separate effect with its own lifetime: the cold-start one above ends
    // after a single decision, and this listener must outlive it.
    const sub = Linking.addEventListener("url", ({ url }) => {
      const diem = diemVaoTuUrl(url);
      if (diem.kieu === "loi-moi") {
        datLoiMoiDen(diem.ma);
        router.replace("/moi" as never);
        return;
      }
      if (diem.kieu === "doi-huong") router.replace(diem.toi as never);
    });
    return () => sub.remove();
  }, [router]);

  return null;
}

export default function RootLayout() {
  const { dark, colors } = useRudiTheme();

  // Design contract: warm editorial surfaces, one semantic leading tone per
  // screen, native 44pt targets, real text, restrained motion, and no visual
  // treatment that could blur the boundary between demo and live money data.
  return (
    <SafeAreaProvider>
      <RudiSessionProvider>
        <StatusBar style={dark ? "light" : "dark"} />
        <LegacyFragmentAdapter />
        <Stack
          screenOptions={{
            animation: "slide_from_right",
            contentStyle: { backgroundColor: colors.ground },
            headerShown: false,
          }}
        >
          <Stack.Screen name="(tabs)" options={{ animation: "fade" }} />
          <Stack.Screen
            name="create"
            options={{ animation: "slide_from_bottom", presentation: "transparentModal" }}
          />
          <Stack.Screen
            name="check-ins/new"
            options={{ animation: "slide_from_bottom", presentation: "modal" }}
          />
          <Stack.Screen
            name="moments/new"
            options={{ animation: "slide_from_bottom", presentation: "modal" }}
          />
        </Stack>
      </RudiSessionProvider>
    </SafeAreaProvider>
  );
}
