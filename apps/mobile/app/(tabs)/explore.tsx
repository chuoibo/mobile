import { ExploreScreen } from "../../src/rudi/screens/Discovery";
import { ExploreLiveScreen } from "../../src/rudi/screens/explore/ExploreLive";
import { useRudiSession } from "../../src/rudi/session";

export default function ExploreTab() {
  const { phien, phienDaDoc } = useRudiSession();
  // A real session reads the server's catalogue; the fixture build keeps the
  // fixture places, which is what the default Maestro table drives.
  if (!phienDaDoc) return null;
  if (phien !== null) return <ExploreLiveScreen phien={phien} />;
  return <ExploreScreen />;
}
