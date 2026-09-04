import { Redirect } from "expo-router";

import { OcrAssignmentScreen } from "../../../src/rudi/screens/Bill";
import { useRudiSession } from "../../../src/rudi/session";

// On a real session the assignment lives inside the bill stepper (review route).
export default function OcrAssignmentRoute() {
  const { phien, phienDaDoc } = useRudiSession();
  if (!phienDaDoc) return null;
  if (phien !== null) return <Redirect href="/smart-split/moi/review" />;
  return <OcrAssignmentScreen />;
}
