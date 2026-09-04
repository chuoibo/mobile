import { useLocalSearchParams } from "expo-router";

import { DotThuLiveScreen } from "../../../src/rudi/screens/dot-thu/DotThuLive";
import { useRudiSession } from "../../../src/rudi/session";
import { RudiButton, RudiScreen, Heading, TopBar } from "../../../src/rudi/ui";
import { useRouter } from "expo-router";

function maDot(id: unknown): string {
  if (typeof id === "string") return id;
  return "";
}

export default function BatchRoute() {
  const params = useLocalSearchParams<{ id: string }>();
  const { phien, phienDaDoc } = useRudiSession();
  const router = useRouter();
  if (!phienDaDoc) return null;
  const id = maDot(params.id);
  if (phien !== null && id !== "") return <DotThuLiveScreen batchId={id} phien={phien} />;
  // No fixture round exists: the settlement fixture never opens one. Say so.
  return (
    <RudiScreen tone="split" testID="collection-batch-screen">
      <TopBar title="Đợt thu" />
      <Heading title="Cần đăng nhập" subtitle="Đợt thu đọc từ máy chủ; bản trải nghiệm không có đợt thu nào." />
      <RudiButton label="Quay lại" onPress={() => router.back()} tone="split" variant="outline" />
    </RudiScreen>
  );
}
