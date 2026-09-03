import { Redirect, useLocalSearchParams } from "expo-router";

import { GroupChatScreen } from "../../../src/rudi/screens/Group";
import { GroupChatLiveScreen } from "../../../src/rudi/screens/chat/GroupChatLive";
import { useRudiSession } from "../../../src/rudi/session";

export default function GroupChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  // A real session gets the real conversation; the fixture build keeps the
  // fixture chat the default Maestro table drives.
  if (phien !== null) {
    if (typeof id !== "string") return <Redirect href="/messages" />;
    return <GroupChatLiveScreen contextId={id} />;
  }
  return <GroupChatScreen />;
}
