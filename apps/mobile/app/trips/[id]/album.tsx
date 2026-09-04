import { useLocalSearchParams } from "expo-router";

import { TripAlbumScreen } from "../../../src/rudi/screens/Memories";
import { TripAlbumLiveScreen } from "../../../src/rudi/screens/ky-niem/AlbumLive";
import { useRudiSession } from "../../../src/rudi/session";

function chuoi(x: unknown): string {
  if (typeof x === "string") return x;
  return "";
}

export default function TripAlbumRoute() {
  const params = useLocalSearchParams<{ id: string; ctx?: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  const outingId = chuoi(params.id);
  const ctxParam = chuoi(params.ctx);
  if (phien !== null && outingId !== "") {
    // The album is the group's: the shelf passes `ctx`; a deep link without it
    // falls back to the session's group.
    const contextId = ctxParam !== "" ? ctxParam : phien.context_id;
    if (contextId !== null) return <TripAlbumLiveScreen contextId={contextId} outingId={outingId} phien={phien} />;
  }
  return <TripAlbumScreen />;
}
