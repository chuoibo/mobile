import { AchievementsScreen } from "../src/rudi/screens/Profile";
import { AchievementsLiveScreen } from "../src/rudi/screens/ky-niem/AchievementsLive";
import { useRudiSession } from "../src/rudi/session";

export default function AchievementsRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien !== null) return <AchievementsLiveScreen phien={phien} />;
  return <AchievementsScreen />;
}
