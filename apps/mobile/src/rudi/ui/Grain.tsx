import { Image, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { chatLieu } from "../textures";

export interface GrainProps {
  material: keyof typeof chatLieu;
  /** 0.04–0.12: enough to read at 1x, never enough to change the measured colour. */
  opacity?: number;
  style?: StyleProp<ViewStyle>;
}

/**
 * A material laid over a surface: the tile repeats across the whole box and
 * never catches touches. Cloth on the cover, paper on the pages, paper again
 * inside a stamp so its fill is imperfect like ink on fibre.
 */
export function Grain({ material, opacity = 0.08, style }: GrainProps) {
  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, style]}>
      <Image
        accessibilityElementsHidden
        importantForAccessibility="no"
        resizeMode="repeat"
        source={chatLieu[material]}
        style={[StyleSheet.absoluteFill, { opacity }]}
      />
    </View>
  );
}
