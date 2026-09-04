import { Redirect } from "expo-router";

/**
 * Any path the router does not know. App B (the legacy shell behind `/legacy`
 * and the `?man=` / `#vao=` web doors) is gone; the twelve flows and the deep
 * link contract that relied on "unknown URL -> /welcome" keep that behaviour.
 */
export default function UnknownRoute() {
  return <Redirect href="/welcome" />;
}
