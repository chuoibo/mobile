import { Stack, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { Linking, Platform } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { diemVaoTuUrl } from "../src/rudi/duong-vao";
import { RudiSessionProvider } from "../src/rudi/session";
import { useRudiTheme } from "../src/rudi/theme";

/** Translates a legacy `#fragment` entry, and nothing else.
 *
 * The decision lives in `src/rudi/duong-vao.ts` so it can be tested without a
 * device; see the docstring there for the deep link this used to swallow. */
function LegacyFragmentAdapter() {
  const router = useRouter();

  useEffect(() => {
    if (Platform.OS === "web") return;
    let live = true;
    void Linking.getInitialURL().then((url) => {
      // Re-checked after the await, not before it. The guard that was only
      // checked before is the whole of the defect.
      if (!live) return;
      const diem = diemVaoTuUrl(url);
      if (diem.kieu !== "doi-huong") return;
      router.replace(diem.toi as never);
    });
    return () => {
      live = false;
    };
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
