import { StyleSheet, View } from "react-native";

import { lopPhu } from "../theme";
import { Wordmark, WORDMARK_RATIO } from "./Wordmark";

export interface WordmarkEmbossedProps {
  height: number;
  /** Ink of the raised face; the cover uses `coverInk`. */
  color: string;
}

/**
 * The wordmark pressed into the cloth: a dark layer a hair down-right, a light
 * layer a hair up-left, the face on top. Three vector layers, no raster.
 */
export function WordmarkEmbossed({ height, color }: WordmarkEmbossedProps) {
  const offset = Math.max(1, Math.round(height / 40));
  const width = Math.round(height * WORDMARK_RATIO);
  return (
    <View style={{ width: width + offset * 2, height: height + offset * 2 }} accessibilityLabel="Rủ Đi">
      <View style={[styles.layer, { left: offset * 2, top: offset * 2 }]}>
        <Wordmark height={height} color={lopPhu.toi(0.55)} accessibilityLabel="" />
      </View>
      <View style={[styles.layer, { left: 0, top: 0 }]}>
        <Wordmark height={height} color={lopPhu.trang(0.22)} accessibilityLabel="" />
      </View>
      <View style={[styles.layer, { left: offset, top: offset }]}>
        <Wordmark height={height} color={color} accessibilityLabel="" />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({ layer: { position: "absolute" } });
