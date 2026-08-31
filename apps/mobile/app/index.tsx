import { Redirect } from "expo-router";

import { isLegacyWebAddress, LegacyEntry } from "../src/rudi/LegacyEntry";

export default function IndexRoute() {
  if (isLegacyWebAddress()) return <LegacyEntry />;
  return <Redirect href="/welcome" />;
}
