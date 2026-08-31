import { lazy, Suspense } from "react";
import { Platform } from "react-native";

const LegacyApp = lazy(() => import("../../App"));

export function isLegacyWebAddress() {
  if (Platform.OS !== "web") return false;
  if (typeof window === "undefined") return true;
  const params = new URLSearchParams(window.location.search);
  const fragment = window.location.hash.replace(/^#/, "");
  return (
    params.has("man") ||
    fragment.includes("=") ||
    window.location.pathname === "/" ||
    window.location.pathname.endsWith(".html")
  );
}

export function LegacyEntry() {
  return (
    <Suspense fallback={null}>
      <LegacyApp />
    </Suspense>
  );
}
