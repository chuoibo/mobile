import { ShareMomentScreen } from "../../src/rudi/screens/Memories";
import { ShareMomentLiveScreen } from "../../src/rudi/screens/ky-niem/ShareMomentLive";
import { useRudiSession } from "../../src/rudi/session";

export default function ShareMomentRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien !== null) return <ShareMomentLiveScreen phien={phien} />;
  return <ShareMomentScreen />;
}
