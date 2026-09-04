import { Redirect, useLocalSearchParams } from "expo-router";

import { AlbumNhomLiveScreen } from "../../../src/rudi/screens/ky-niem/AlbumLive";
import { useRudiSession } from "../../../src/rudi/session";

function maNhom(id: unknown): string {
  if (typeof id === "string") return id;
  return "";
}

export default function GroupAlbumRoute() {
  const params = useLocalSearchParams<{ id: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  const id = maNhom(params.id);
  if (phien !== null && id !== "") return <AlbumNhomLiveScreen contextId={id} phien={phien} />;
  // The fixture album lives under the trip route; a group shelf has no fixture.
  return <Redirect href="/welcome" />;
}
