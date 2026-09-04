import { useLocalSearchParams } from "expo-router";

import { GroupWallScreen } from "../../../src/rudi/screens/Memories";
import { GroupWallLiveScreen } from "../../../src/rudi/screens/ky-niem/GroupWallLive";
import { useRudiSession } from "../../../src/rudi/session";

function maNhom(id: unknown): string {
  if (typeof id === "string") return id;
  return "";
}

export default function WallRoute() {
  const params = useLocalSearchParams<{ id: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  const id = maNhom(params.id);
  if (phien !== null && id !== "") return <GroupWallLiveScreen contextId={id} phien={phien} />;
  return <GroupWallScreen />;
}
