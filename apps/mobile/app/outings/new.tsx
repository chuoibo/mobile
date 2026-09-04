import { CreateOutingScreen } from "../../src/rudi/screens/Outing";
import { CreateOutingLiveScreen } from "../../src/rudi/screens/keo/CreateOutingLive";
import { useRudiSession } from "../../src/rudi/session";

export default function NewOutingRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien !== null) return <CreateOutingLiveScreen phien={phien} />;
  return <CreateOutingScreen />;
}
