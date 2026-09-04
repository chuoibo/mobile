import { PlaceDetailScreen } from "../../../src/rudi/screens/Discovery";
import { PlaceDetailLiveScreen } from "../../../src/rudi/screens/explore/PlaceDetailLive";
import { useRudiSession } from "../../../src/rudi/session";

export default function PlaceDetailRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien !== null) return <PlaceDetailLiveScreen phien={phien} />;
  return <PlaceDetailScreen />;
}
