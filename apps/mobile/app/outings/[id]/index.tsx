import { Redirect } from "expo-router";

import { OutingLiveScreen } from "../../../src/rudi/screens/keo/OutingLive";
import { useRudiSession } from "../../../src/rudi/session";

// Outings live on the server only; the fixture build has no route here.
export default function OutingRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien === null) return <Redirect href="/welcome" />;
  return <OutingLiveScreen phien={phien} />;
}
