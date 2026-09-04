import { Ionicons } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import * as Haptics from "expo-haptics";
import { Tabs, useRouter } from "expo-router";
import { Platform, Pressable, StyleSheet, useWindowDimensions, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useRudiTheme } from "../../src/rudi/theme";

export default function TabsLayout() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { colors, brand, dark } = useRudiTheme();
  const expanded = width >= 700;
  const bottom = Math.max(insets.bottom, 10);

  return (
    <View style={styles.root}>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.inkFaint,
          tabBarLabelStyle: styles.label,
          tabBarLabelPosition: "below-icon",
          tabBarPosition: expanded ? "left" : "bottom",
          tabBarVariant: expanded ? "material" : "uikit",
          tabBarActiveBackgroundColor: expanded ? colors.accentSoft : "transparent",
          tabBarItemStyle: expanded ? styles.railItem : undefined,
          tabBarStyle: [
            expanded ? styles.rail : styles.tabBar,
            {
              backgroundColor:
                Platform.OS === "ios" && !expanded ? "transparent" : colors.card,
              borderColor: colors.line,
              ...(expanded
                ? { width: 104, paddingBottom: 92 }
                : { height: 62 + bottom, paddingBottom: bottom }),
            },
          ],
          tabBarBackground: () =>
            Platform.OS === "ios" && !expanded ? (
              <BlurView intensity={78} tint={dark ? "dark" : "light"} style={StyleSheet.absoluteFill} />
            ) : null,
        }}
      >
        <Tabs.Screen
          name="explore"
          options={{
            title: "Khám phá",
            tabBarIcon: ({ color, focused }) => (
              <Ionicons color={color} name={focused ? "compass" : "compass-outline"} size={23} />
            ),
          }}
        />
        <Tabs.Screen
          name="plan"
          options={{
            title: "Lên plan",
            tabBarItemStyle: expanded ? styles.railItem : styles.beforeFab,
            tabBarIcon: ({ color, focused }) => (
              <Ionicons color={color} name={focused ? "map" : "map-outline"} size={23} />
            ),
          }}
        />
        <Tabs.Screen
          name="messages"
          options={{
            title: "Tin nhắn",
            tabBarItemStyle: expanded ? styles.railItem : styles.afterFab,
            tabBarIcon: ({ color, focused }) => (
              <Ionicons color={color} name={focused ? "chatbubbles" : "chatbubbles-outline"} size={23} />
            ),
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: "Cá nhân",
            tabBarIcon: ({ color, focused }) => (
              <Ionicons color={color} name={focused ? "person-circle" : "person-circle-outline"} size={24} />
            ),
          }}
        />
      </Tabs>
      <Pressable
        accessibilityLabel="Tạo mới"
        accessibilityRole="button"
        onPress={() => {
          void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
          router.push("/create");
        }}
        style={({ pressed }) => [
          styles.fab,
          expanded ? styles.railFab : styles.phoneFab,
          {
            bottom: expanded ? Math.max(insets.bottom, 24) : bottom + 27,
            backgroundColor: brand.coral,
            borderColor: colors.ground,
            shadowColor: colors.accent,
          },
          pressed && styles.fabPressed,
        ]}
      >
        <Ionicons color={colors.accentInk} name="add" size={30} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  tabBar: { position: "absolute", borderTopWidth: StyleSheet.hairlineWidth, elevation: 16 },
  rail: { borderRightWidth: StyleSheet.hairlineWidth, elevation: 5 },
  railItem: { width: 78, minHeight: 66, alignSelf: "center" },
  label: { fontSize: 10, lineHeight: 13, fontWeight: "700", marginTop: 1 },
  beforeFab: { marginRight: 22 },
  afterFab: { marginLeft: 22 },
  fab: {
    position: "absolute",
    width: 58,
    height: 58,
    borderRadius: 21,
    borderWidth: 4,
    alignItems: "center",
    justifyContent: "center",
    elevation: 12,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.28,
    shadowRadius: 12,
  },
  phoneFab: { left: "50%", marginLeft: -29 },
  railFab: { left: 23 },
  fabPressed: { opacity: 0.88, transform: [{ scale: 0.94 }] },
});
