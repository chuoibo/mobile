import { ReceiptReviewScreen } from "../../../src/rudi/screens/Bill";
import { ChiaBillLiveScreen } from "../../../src/rudi/screens/chia-bill/ChiaBillLive";
import { useRudiSession } from "../../../src/rudi/session";

// A real session runs the whole bill flow on the server in one stepper; the
// fixture build keeps the fixture paper, which the default Maestro table drives.
export default function ReceiptReviewRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien !== null) return <ChiaBillLiveScreen phien={phien} />;
  return <ReceiptReviewScreen />;
}
