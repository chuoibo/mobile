import { Redirect } from "expo-router";

import { manDau } from "../src/rudi/duong-vao";
import { useRudiSession } from "../src/rudi/session";

export default function IndexRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  // Nothing until SecureStore has answered: a redirect to /welcome decided on
  // an unread disk would show a signed-in person the carousel for a frame and
  // then jump. `manDau` is the same decision `app/_layout.tsx` makes for a
  // pathless cold start, so the two entries cannot disagree.
  if (!phienDaDoc) return null;
  return <Redirect href={manDau(phien)} />;
}
