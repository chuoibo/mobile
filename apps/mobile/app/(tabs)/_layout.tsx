import { Tabs } from "expo-router";

import { RudiTabBar } from "../../src/rudi/ui/RudiTabBar";
import { useAdaptiveLayout } from "../../src/rudi/ui/useAdaptiveLayout";

/**
 * Four destinations and one create action (ADR-0013). The bar itself is
 * `RudiTabBar`, the notebook's edge strip with the FAB as its own column; on a
 * medium or expanded window the same component stands as a left rail.
 */
export default function TabsLayout() {
  const layout = useAdaptiveLayout();
  return (
    <Tabs
      screenOptions={{ headerShown: false, tabBarPosition: layout.rail ? "left" : "bottom" }}
      tabBar={(props) => <RudiTabBar {...props} />}
    >
      <Tabs.Screen name="explore" options={{ title: "Khám phá" }} />
      <Tabs.Screen name="plan" options={{ title: "Lên plan" }} />
      <Tabs.Screen name="messages" options={{ title: "Tin nhắn" }} />
      <Tabs.Screen name="profile" options={{ title: "Cá nhân" }} />
    </Tabs>
  );
}
