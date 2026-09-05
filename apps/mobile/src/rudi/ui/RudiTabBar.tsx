import { Ionicons } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import { Tabs, useRouter } from "expo-router";
import type { ComponentProps } from "react";
import { useEffect } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { typography, useRudiTheme } from "../theme";
import { PressScale } from "./PressScale";
import { useAdaptiveLayout } from "./useAdaptiveLayout";
import { useMotion } from "./useMotion";

type TabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>["tabBar"]>>[0];

/** Icon per destination, filled when current; ADR-0013 fixes the four names. */
const ICONS: Record<string, [keyof typeof Ionicons.glyphMap, keyof typeof Ionicons.glyphMap]> = {
  explore: ["compass-outline", "compass"],
  plan: ["map-outline", "map"],
  messages: ["chatbubbles-outline", "chatbubbles"],
  profile: ["person-circle-outline", "person-circle"],
};

export const TAB_BAR_HEIGHT = 64;
export const RAIL_WIDTH = 104;
const FAB = 56;

/**
 * The notebook's bottom edge: a paper strip with an ink hairline, four
 * destinations, and the create stamp in the middle. Replaces the stock bar
 * that had a FAB glued beside it with `marginRight: 22` notches; here the FAB
 * is the fifth column, so the geometry cannot drift. The active tab carries a
 * short washi strip that slides between destinations over `standard`; on a
 * medium or expanded window the same bar stands as a left rail.
 */
export function RudiTabBar({ state, descriptors, navigation }: TabBarProps) {
  const { colors, brand, dark } = useRudiTheme();
  const insets = useSafeAreaInsets();
  const layout = useAdaptiveLayout();
  const router = useRouter();
  const motion = useMotion();

  const routes = state.routes;
  const count = routes.length;
  const fabAt = Math.floor(count / 2); // between plan and messages
  const columns = count + 1;

  const indicator = useSharedValue(state.index);
  useEffect(() => {
    indicator.value = withTiming(state.index, motion.timing("standard"));
  }, [state.index, indicator, motion]);

  const indicatorStyle = useAnimatedStyle(() => {
    const column = indicator.value >= fabAt ? indicator.value + 1 : indicator.value;
    return layout.rail
      ? { transform: [{ translateY: column * 72 }] }
      : { left: `${(column / columns) * 100}%` as const };
  });

  const openCreate = () => {
    motion.haptic.impact();
    router.push("/create");
  };

  const items = routes.map((route, index) => {
    const { options } = descriptors[route.key];
    const focused = state.index === index;
    const [outline, filled] = ICONS[route.name] ?? ["ellipse-outline", "ellipse"];
    const label = typeof options.title === "string" ? options.title : route.name;
    const onPress = () => {
      const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
      if (!focused && !event.defaultPrevented) {
        motion.haptic.select();
        navigation.navigate(route.name);
      }
    };
    return (
      <Pressable
        key={route.key}
        accessibilityRole="tab"
        accessibilityState={{ selected: focused }}
        accessibilityLabel={label}
        onPress={onPress}
        style={[styles.item, layout.rail && styles.railItem]}
      >
        <Ionicons color={focused ? colors.accent : colors.inkFaint} name={focused ? filled : outline} size={24} />
        <Text numberOfLines={1} style={[typography.caption, styles.label, { color: focused ? colors.accent : colors.inkFaint }]}>
          {label}
        </Text>
      </Pressable>
    );
  });

  const fab = (
    <View key="fab" style={[styles.item, layout.rail && styles.railItem, styles.fabSlot]}>
      <PressScale
        accessibilityLabel="Tạo mới"
        accessibilityRole="button"
        haptic="none"
        onPress={openCreate}
        pressedScale={0.94}
        style={[
          styles.fab,
          layout.rail ? null : styles.fabRaised,
          { backgroundColor: brand.coral, borderColor: colors.ground, shadowColor: colors.accent },
        ]}
      >
        <Ionicons color={colors.accentInk} name="add" size={30} />
      </PressScale>
    </View>
  );

  items.splice(fabAt, 0, fab);

  const bottom = Math.max(insets.bottom, 10);
  const glass = Platform.OS === "ios" && !layout.rail;

  return (
    <View
      style={[
        layout.rail ? styles.rail : styles.bar,
        {
          backgroundColor: glass ? "transparent" : colors.card,
          borderColor: colors.line,
          ...(layout.rail
            ? { width: RAIL_WIDTH, paddingTop: insets.top + 12, paddingBottom: Math.max(insets.bottom, 12) }
            : { height: TAB_BAR_HEIGHT + bottom, paddingBottom: bottom }),
        },
      ]}
    >
      {glass ? <BlurView intensity={78} tint={dark ? "dark" : "light"} style={StyleSheet.absoluteFill} /> : null}
      <Animated.View
        pointerEvents="none"
        style={[
          layout.rail ? styles.railIndicator : styles.indicator,
          layout.rail ? { backgroundColor: colors.accent, width: 4 } : { width: `${100 / columns}%` },
          indicatorStyle,
        ]}
      >
        {layout.rail ? null : <View style={[styles.tape, { backgroundColor: colors.accent }]} />}
      </Animated.View>
      {items}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "stretch",
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  rail: {
    flexDirection: "column",
    alignItems: "stretch",
    borderRightWidth: StyleSheet.hairlineWidth,
    height: "100%",
  },
  item: { flex: 1, minHeight: 48, alignItems: "center", justifyContent: "center", gap: 2, paddingTop: 8 },
  railItem: { flex: 0, height: 72, paddingTop: 0 },
  label: { fontSize: 12, lineHeight: 14 },
  fabSlot: { justifyContent: "flex-start" },
  fab: {
    width: FAB,
    height: FAB,
    borderRadius: FAB / 2,
    borderWidth: 4,
    alignItems: "center",
    justifyContent: "center",
    elevation: 6,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.22,
    shadowRadius: 10,
  },
  fabRaised: { marginTop: -22 },
  indicator: { position: "absolute", top: 0, height: 6, alignItems: "center", backgroundColor: "transparent" },
  tape: { width: 28, height: 4, borderBottomLeftRadius: 4, borderBottomRightRadius: 4 },
  railIndicator: { position: "absolute", left: 0, top: 0, height: 72 },
});
