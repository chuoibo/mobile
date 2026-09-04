import { GroupChatScreen } from "../../src/rudi/screens/Group";
import { ConversationsScreen } from "../../src/rudi/screens/groups/Conversations";
import { useRudiSession } from "../../src/rudi/session";

export default function MessagesTab() {
  const { phien, phienDaDoc } = useRudiSession();
  // A real session gets the real list; the fixture build keeps the fixture
  // chat, which is what the default Maestro table drives.
  if (!phienDaDoc) return null;
  if (phien !== null) return <ConversationsScreen phien={phien} />;
  return <GroupChatScreen embeddedInTabs />;
}
