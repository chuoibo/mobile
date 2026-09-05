import { useEffect, useRef, useState } from "react";
import { Text, type StyleProp, type TextStyle } from "react-native";

import { dinhDangTienVnd } from "../../screens/chat/ke-hoach";
import { moneyCountUpMs } from "../motion";
import { typography, useRudiTheme } from "../theme";
import { useMotion } from "./useMotion";

export type MoneySize = "display" | "money" | "body" | "label" | "caption";
export type MoneyTone = "ink" | "inkSoft" | "split" | "accent" | "warn";

export interface MoneyProps {
  /** Integer đồng. Never a float; never a string the server did not send. */
  vnd: number;
  size?: MoneySize;
  tone?: MoneyTone;
  /** `auto` shows a minus for negatives only; `always` also shows a plus. */
  sign?: "auto" | "none" | "always";
  /**
   * Count up from the previous value over `standard`. Only allowed once the
   * domain state is valid; pass `false` (the default) while a number is still
   * provisional, and the figure simply appears.
   */
  countUp?: boolean;
  style?: StyleProp<TextStyle>;
  testID?: string;
  numberOfLines?: number;
  adjustsFontSizeToFit?: boolean;
}

/**
 * Every amount in the shell, one way.
 *
 * Tabular numerals from `typography.money` so a column of amounts reads as a
 * column; the one formatter the app already has (`dinhDangTienVnd`, integer
 * đồng, dotted thousands, «đ» suffix) so no screen grows a second one. Colour
 * is a tone with a meaning: `split` for a transfer being proposed, `warn` for
 * something owed and overdue, `ink` for a fact. Money never takes a brand
 * colour and is never animated before the ledger has spoken (`moneyCountUpMs`).
 */
export function Money({
  vnd,
  size = "money",
  tone = "ink",
  sign = "auto",
  countUp = false,
  style,
  testID,
  numberOfLines = 1,
  adjustsFontSizeToFit = false,
}: MoneyProps) {
  const { colors } = useRudiTheme();
  const shown = useCountUp(vnd, countUp);
  const text = withSign(dinhDangTienVnd(Math.abs(shown)), shown, sign);
  const base = size === "caption" ? typography.caption : size === "label" ? typography.label : size === "body" ? typography.body : size === "display" ? typography.display : typography.money;
  return (
    <Text
      testID={testID}
      numberOfLines={numberOfLines}
      adjustsFontSizeToFit={adjustsFontSizeToFit}
      accessibilityLabel={text}
      style={[base, { fontVariant: ["tabular-nums"], color: colors[tone] }, style]}
    >
      {text}
    </Text>
  );
}

function withSign(formatted: string, value: number, sign: MoneyProps["sign"]): string {
  if (sign === "none") return formatted;
  if (value < 0) return `-${formatted}`;
  if (sign === "always" && value > 0) return `+${formatted}`;
  return formatted;
}

/**
 * JS-thread interpolation, bounded by `moneyCountUpMs` (200 ms, or 0 under
 * Reduce Motion or while the state is provisional). Short enough that a few
 * dropped frames cost nothing, and it never runs on a first render: a number
 * that has just arrived is shown, not performed.
 */
function useCountUp(target: number, enabled: boolean): number {
  const motion = useMotion();
  const [shown, setShown] = useState(target);
  const previous = useRef(target);

  useEffect(() => {
    const from = previous.current;
    previous.current = target;
    const ms = moneyCountUpMs(enabled, motion.reduced);
    if (ms === 0 || from === target) {
      setShown(target);
      return;
    }
    let frame = 0;
    const started = Date.now();
    const tick = () => {
      const t = Math.min(1, (Date.now() - started) / ms);
      const eased = 1 - (1 - t) * (1 - t);
      setShown(Math.round(from + (target - from) * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, enabled, motion.reduced]);

  return shown;
}
