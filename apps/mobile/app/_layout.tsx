import { Stack, usePathname, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { Linking, Platform } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useRudiTheme } from "../src/rudi/theme";

const LEGACY_FRAGMENT_ROUTES: Record<string, string> = {
  "": "/welcome",
  explore: "/explore",
  "lap-ke-hoach": "/plan",
  plan: "/plan",
  "tin-nhan": "/messages",
  messages: "/messages",
  "ca-nhan": "/profile",
  profile: "/profile",
};

function LegacyFragmentAdapter() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (Platform.OS === "web") return;
    if (pathname !== "/") return;

    void Linking.getInitialURL().then((url) => {
      const fragment = url?.split("#")[1]?.replace(/^\//, "") ?? "";
      if (fragment.includes("=") || url?.includes("?man=")) return;
      router.replace(LEGACY_FRAGMENT_ROUTES[fragment] ?? "/welcome");
    });
  }, [pathname, router]);

  return null;
}

export default function RootLayout() {
  const { dark, colors } = useRudiTheme();

  // Design contract: warm editorial surfaces, one semantic leading tone per
  // screen, native 44pt targets, real text, restrained motion, and no visual
  // treatment that could blur the boundary between demo and live money data.
  return (
    <SafeAreaProvider>
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
    </SafeAreaProvider>
  );
}
