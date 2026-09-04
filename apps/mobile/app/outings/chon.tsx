import { Redirect } from "expo-router";

import { PickOutingLiveScreen } from "../../src/rudi/screens/keo/PickOutingLive";
import { useRudiSession } from "../../src/rudi/session";

export default function PickOutingRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;
  return <PickOutingLiveScreen phien={phien} />;
}
