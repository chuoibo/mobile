import { TripTimelineScreen } from "../../src/rudi/screens/Outing";
import { PlanLiveScreen } from "../../src/rudi/screens/keo/PlanLive";
import { useRudiSession } from "../../src/rudi/session";

export default function PlanTab() {
  const { phien, phienDaDoc } = useRudiSession();
  // A real session lists the group's outings from the server; the fixture
  // build keeps the fixture trip, which is what the default Maestro table drives.
  if (!phienDaDoc) return null;
  if (phien !== null) return <PlanLiveScreen phien={phien} />;
  return <TripTimelineScreen />;
}
