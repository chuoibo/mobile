import { Redirect } from "expo-router";

import { isLegacyWebAddress, LegacyEntry } from "../src/rudi/LegacyEntry";

export default function LegacyCatchAllRoute() {
  if (isLegacyWebAddress()) return <LegacyEntry />;
  return <Redirect href="/welcome" />;
}
