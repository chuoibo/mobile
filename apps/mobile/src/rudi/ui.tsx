import { Ionicons } from "@expo/vector-icons";
import { BlurView } from "expo-blur";
import { Image, ImageSource } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import type { ComponentProps, ReactNode } from "react";
import {
  ActivityIndicator,
  DimensionValue,
  GestureResponderEvent,
  Platform,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  TextStyle,
  useWindowDimensions,
  View,
  ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DemoPerson } from "./fixtures";
import { useRudiSession } from "./session";
import {
  cardShadow,
  RudiTone,
  toneColor,
  toneSoftColor,
  typography,
  useRudiTheme,
} from "./theme";

export type IconName = ComponentProps<typeof Ionicons>["name"];

type ScreenProps = {
  children: ReactNode;
  scroll?: boolean;
  tone?: RudiTone;
  padded?: boolean;
  bottomInset?: number;
  footer?: ReactNode;
  footerInset?: number;
  contentStyle?: StyleProp<ViewStyle>;
  testID?: string;
};

export function RudiScreen({
  children,
  scroll = true,
  tone = "accent",
  padded = true,
  bottomInset = 32,
  footer,
  footerInset = 0,
  contentStyle,
  testID,
}: ScreenProps) {
  const { colors, dark, space } = useRudiTheme();
  const { width } = useWindowDimensions();
  const tablet = width >= 700;
  const inner = [
    styles.screenInner,
    padded && { paddingHorizontal: tablet ? space.lg : space.md },
    { paddingBottom: bottomInset },
    tablet && styles.tabletInner,
    contentStyle,
  ];

  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={[styles.safeArea, { backgroundColor: colors.ground }]}
      testID={testID}
    >
      <AmbientBackdrop tone={tone} />
      {scroll ? (
        <ScrollView
          contentContainerStyle={inner}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          style={styles.flex}
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[inner, styles.flex]}>{children}</View>
      )}
      {footer ? (
        <View
          style={[
            styles.screenFooter,
            { paddingHorizontal: tablet ? space.lg : space.md, paddingBottom: footerInset },
            tablet && styles.tabletInner,
          ]}
        >
          {footer}
        </View>
      ) : null}
      {Platform.OS === "web" && dark ? null : null}
    </SafeAreaView>
  );
}

function AmbientBackdrop({ tone }: { tone: RudiTone }) {
  const { colors } = useRudiTheme();
  const color = toneSoftColor(colors, tone);

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={[styles.glow, styles.glowTop, { backgroundColor: color }]} />
      <View
        style={[
          styles.glow,
          styles.glowBottom,
          { backgroundColor: colors.accentSoft },
        ]}
      />
    </View>
  );
}

export function TopBar({
  title,
  subtitle,
  back = true,
  right,
}: {
  title?: string;
  subtitle?: string;
  back?: boolean;
  right?: ReactNode;
}) {
  const router = useRouter();
  const { colors } = useRudiTheme();

  return (
    <View style={styles.topBar}>
      <View style={styles.topBarSide}>
        {back ? (
          <IconButton
            accessibilityLabel="Quay lại"
            icon="chevron-back"
            onPress={() => router.back()}
            quiet
          />
        ) : (
          <Logo compact />
        )}
      </View>
      <View style={styles.topBarTitleWrap}>
        {title ? (
          <Text numberOfLines={1} style={[typography.title, { color: colors.ink }]}>
            {title}
          </Text>
        ) : null}
        {subtitle ? (
          <Text
            numberOfLines={1}
            style={[typography.caption, { color: colors.inkFaint }]}
          >
            {subtitle}
          </Text>
        ) : null}
      </View>
      <View style={[styles.topBarSide, styles.topBarRight]}>{right}</View>
    </View>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  const { brand } = useRudiTheme();
  return (
    <View style={styles.logoRow} accessibilityLabel="Rủ Đi">
      <LinearGradient
        colors={[brand.logoGradient.from, brand.logoGradient.to]}
        end={{ x: 1, y: 1 }}
        start={{ x: 0, y: 0 }}
        style={[styles.logoMark, compact && styles.logoMarkCompact]}
      >
        <Text style={[styles.logoMarkType, compact && styles.logoMarkTypeCompact]}>
          Rủ{"\n"}Đi
        </Text>
      </LinearGradient>
      <View style={styles.logoWordmark}>
        <Text style={[styles.logoType, compact && styles.logoTypeCompact]}>Rủ</Text>
        <Text style={[styles.logoType, compact && styles.logoTypeCompact]}>Đi</Text>
      </View>
    </View>
  );
}

export function Eyebrow({ children, tone = "accent" }: { children: ReactNode; tone?: RudiTone }) {
  const { colors } = useRudiTheme();
  return (
    <View style={[styles.eyebrow, { backgroundColor: toneSoftColor(colors, tone) }]}>
      <View style={[styles.eyebrowDot, { backgroundColor: toneColor(colors, tone) }]} />
      <Text style={[typography.caption, { color: toneColor(colors, tone) }]}>{children}</Text>
    </View>
  );
}

/**
 * "Dữ liệu demo". A claim about where the numbers came from, so it reads the
 * mode rather than being placed by hand on the screens somebody remembered.
 *
 * Renders NOTHING in live mode. A badge saying "demo" over real money would be
 * the same lie as the reverse, pointed the other way.
 */
export function DemoBadge({ label = "Dữ liệu demo" }: { label?: string }) {
  const { colors } = useRudiTheme();
  const { cheDo } = useRudiSession();
  if (cheDo === "live") return null;
  return (
    <View style={[styles.demoBadge, { backgroundColor: colors.card, borderColor: colors.line }]}>
      <Ionicons color={colors.inkFaint} name="flask-outline" size={12} />
      <Text style={[styles.demoText, { color: colors.inkFaint }]}>{label}</Text>
    </View>
  );
}

export function Heading({
  title,
  subtitle,
  align = "left",
  size = "h1",
}: {
  title: string;
  subtitle?: string;
  align?: "left" | "center";
  size?: "display" | "h1" | "h2";
}) {
  const { colors } = useRudiTheme();
  return (
    <View style={[styles.heading, align === "center" && styles.center]}>
      <Text
        style={[
          typography[size],
          { color: colors.ink, textAlign: align },
        ]}
      >
        {title}
      </Text>
      {subtitle ? (
        <Text
          style={[
            typography.body,
            styles.headingSubtitle,
            { color: colors.inkSoft, textAlign: align },
          ]}
        >
          {subtitle}
        </Text>
      ) : null}
    </View>
  );
}

export function SectionHeader({
  title,
  action,
  onAction,
}: {
  title: string;
  action?: string;
  onAction?: () => void;
}) {
  const { colors } = useRudiTheme();
  return (
    <View style={styles.sectionHeader}>
      <Text style={[typography.h2, { color: colors.ink }]}>{title}</Text>
      {action ? (
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={onAction}
          style={({ pressed }) => pressed && styles.pressed}
        >
          <Text style={[typography.label, { color: colors.accent }]}>{action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Card({
  children,
  style,
  tone,
  onPress,
  accessibilityLabel,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  tone?: RudiTone;
  onPress?: (event: GestureResponderEvent) => void;
  accessibilityLabel?: string;
}) {
  const { colors, radius } = useRudiTheme();
  const cardStyle = [
    styles.card,
    cardShadow,
    {
      backgroundColor: tone ? toneSoftColor(colors, tone) : colors.card,
      borderColor: tone ? toneSoftColor(colors, tone) : colors.line,
      borderRadius: radius.base,
    },
    style,
  ];

  if (onPress) {
    return (
      <Pressable
        accessibilityLabel={accessibilityLabel}
        accessibilityRole="button"
        onPress={onPress}
        style={({ pressed }) => [cardStyle, pressed && styles.cardPressed]}
      >
        {children}
      </Pressable>
    );
  }
  return <View style={cardStyle}>{children}</View>;
}

type ButtonProps = {
  label: string;
  onPress?: () => void;
  icon?: IconName;
  tone?: RudiTone;
  variant?: "solid" | "soft" | "outline" | "ghost";
  disabled?: boolean;
  loading?: boolean;
  compact?: boolean;
  full?: boolean;
  style?: StyleProp<ViewStyle>;
};

export function RudiButton({
  label,
  onPress,
  icon,
  tone = "accent",
  variant = "solid",
  disabled = false,
  loading = false,
  compact = false,
  full = true,
  style,
}: ButtonProps) {
  const { colors, radius, brand } = useRudiTheme();
  const solid = variant === "solid";
  const foreground = solid ? colors[`${tone}Ink` as const] : toneColor(colors, tone);
  const base = [
    styles.button,
    compact && styles.buttonCompact,
    full && styles.buttonFull,
    { borderRadius: radius.control },
    variant === "soft" && { backgroundColor: toneSoftColor(colors, tone), borderColor: "transparent" },
    variant === "outline" && { backgroundColor: colors.card, borderColor: colors.lineStrong },
    variant === "ghost" && { backgroundColor: "transparent", borderColor: "transparent" },
    disabled && styles.disabled,
    style,
  ];
  const body = (
    <>
      {loading ? <ActivityIndicator color={foreground} size="small" /> : null}
      {!loading && icon ? <Ionicons color={foreground} name={icon} size={compact ? 18 : 20} /> : null}
      <Text style={[typography.label, styles.buttonLabel, { color: foreground }]}>{label}</Text>
    </>
  );

  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [base, pressed && !disabled && styles.buttonPressed]}
    >
      {solid ? (
        <LinearGradient
          colors={
            tone === "accent"
              ? [brand.actionGradient.from, brand.actionGradient.to]
              : [toneColor(colors, tone), toneColor(colors, tone)]
          }
          end={{ x: 1, y: 0.6 }}
          start={{ x: 0, y: 0 }}
          style={[StyleSheet.absoluteFill, { borderRadius: radius.control }]}
        />
      ) : null}
      {body}
    </Pressable>
  );
}

export function IconButton({
  icon,
  onPress,
  accessibilityLabel,
  selected = false,
  quiet = false,
  solid = false,
  dim = false,
  loading = false,
  disabled = false,
  tone = "accent",
}: {
  icon: IconName;
  onPress?: () => void;
  accessibilityLabel: string;
  selected?: boolean;
  quiet?: boolean;
  /** The surface's primary action: tone fill, ink-on-tone glyph. */
  solid?: boolean;
  /** Nothing to act on yet: faint glyph, no border. */
  dim?: boolean;
  loading?: boolean;
  disabled?: boolean;
  tone?: RudiTone;
}) {
  const { colors } = useRudiTheme();
  const background = solid
    ? toneColor(colors, tone)
    : selected
      ? toneSoftColor(colors, tone)
      : quiet || dim
        ? "transparent"
        : colors.card;
  const glyph = solid
    ? colors[`${tone}Ink` as const]
    : selected
      ? toneColor(colors, tone)
      : dim
        ? colors.inkFaint
        : colors.ink;
  return (
    <Pressable
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
      aria-busy={loading}
      aria-disabled={disabled || loading}
      aria-pressed={selected}
      disabled={disabled || loading}
      hitSlop={4}
      onPress={onPress}
      style={({ pressed }) => [
        styles.iconButton,
        { backgroundColor: background, borderColor: quiet || dim || solid ? "transparent" : colors.line },
        pressed && !disabled && styles.buttonPressed,
      ]}
    >
      {loading ? <ActivityIndicator color={glyph} size="small" /> : <Ionicons color={glyph} name={icon} size={22} />}
    </Pressable>
  );
}

export function Field({
  label,
  icon,
  trailing,
  multiline,
  style,
  ...inputProps
}: TextInputProps & {
  label?: string;
  icon?: IconName;
  trailing?: ReactNode;
  style?: StyleProp<TextStyle>;
}) {
  const { colors, radius } = useRudiTheme();
  return (
    <View style={styles.fieldBlock}>
      {label ? <Text style={[typography.label, { color: colors.ink }]}>{label}</Text> : null}
      <View
        style={[
          styles.field,
          multiline && styles.fieldMultiline,
          { backgroundColor: colors.card, borderColor: colors.lineStrong, borderRadius: radius.control },
        ]}
      >
        {icon ? <Ionicons color={colors.inkFaint} name={icon} size={20} /> : null}
        <TextInput
          {...inputProps}
          accessibilityLabel={inputProps.accessibilityLabel ?? label ?? inputProps.placeholder}
          multiline={multiline}
          placeholderTextColor={colors.inkFaint}
          style={[styles.fieldInput, typography.body, { color: colors.ink }, style]}
        />
        {trailing}
      </View>
    </View>
  );
}

export function SearchField({ placeholder = "Tìm địa điểm, món ăn...", ...props }: TextInputProps) {
  return <Field {...props} icon="search-outline" placeholder={placeholder} returnKeyType="search" />;
}

/**
 * Six boxes for a one-time code, one real input behind them.
 *
 * The boxes are paint; the `TextInput` stretched over them is what has focus,
 * receives the SMS autofill (`autoComplete="sms-otp"` / `oneTimeCode`) and
 * what a driver types into. One input rather than six keeps paste, autofill and
 * backspace ordinary, and keeps the value a single string the caller submits
 * when it reaches `length`. Its text is transparent, not its opacity: an
 * element with opacity 0 is also invisible to the accessibility tree.
 */
export function OtpBoxes({
  value,
  onChange,
  length = 6,
  disabled = false,
}: {
  value: string;
  onChange: (next: string) => void;
  length?: number;
  disabled?: boolean;
}) {
  const { colors, radius } = useRudiTheme();
  const oHienTai = Math.min(value.length, length - 1);
  return (
    <View style={styles.otpWrap}>
      <View pointerEvents="none" style={styles.otpRow}>
        {Array.from({ length }, (_, i) => (
          <View
            key={i}
            style={[
              styles.otpBox,
              {
                backgroundColor: colors.card,
                borderColor: i === oHienTai && !disabled ? colors.accent : colors.lineStrong,
                borderRadius: radius.control,
              },
            ]}
          >
            <Text style={[typography.title, { color: colors.ink }]}>{value[i] ?? ""}</Text>
          </View>
        ))}
      </View>
      <TextInput
        accessibilityLabel="Ô nhập mã"
        autoComplete="sms-otp"
        autoFocus
        caretHidden
        editable={!disabled}
        keyboardType="number-pad"
        maxLength={length}
        onChangeText={(text) => onChange(text.replace(/\D/g, "").slice(0, length))}
        style={styles.otpInput}
        testID="otp-input"
        textContentType="oneTimeCode"
        value={value}
      />
    </View>
  );
}

export function Chip({
  label,
  icon,
  selected = false,
  tone = "accent",
  onPress,
}: {
  label: string;
  icon?: IconName;
  selected?: boolean;
  tone?: RudiTone;
  onPress?: () => void;
}) {
  const { colors, radius } = useRudiTheme();
  const foreground = selected ? toneColor(colors, tone) : colors.inkSoft;
  return (
    <Pressable
      accessibilityRole="button"
      aria-pressed={selected}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        {
          backgroundColor: selected ? toneSoftColor(colors, tone) : colors.card,
          borderColor: selected ? toneColor(colors, tone) : colors.line,
          borderRadius: radius.pill,
        },
        pressed && styles.pressed,
      ]}
    >
      {icon ? <Ionicons color={foreground} name={icon} size={16} /> : null}
      <Text style={[typography.caption, { color: foreground }]}>{label}</Text>
    </Pressable>
  );
}

export function Avatar({
  person,
  size = 44,
  ring = false,
}: {
  person: DemoPerson;
  size?: number;
  ring?: boolean;
}) {
  const { colors } = useRudiTheme();
  return (
    <View
      accessibilityLabel={person.name}
      style={[
        styles.avatar,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: person.color,
          borderColor: ring ? colors.accent : colors.card,
          borderWidth: ring ? 2 : 2,
        },
      ]}
    >
      <Text style={[styles.avatarText, { fontSize: Math.max(10, size * 0.3) }]}>{person.initials}</Text>
    </View>
  );
}

export function AvatarStack({ people, max = 4 }: { people: DemoPerson[]; max?: number }) {
  const { colors } = useRudiTheme();
  const visible = people.slice(0, max);
  const remaining = people.length - visible.length;
  return (
    <View style={styles.avatarStack}>
      {visible.map((person, index) => (
        <View key={person.id} style={{ marginLeft: index ? -10 : 0, zIndex: visible.length - index }}>
          <Avatar person={person} size={34} />
        </View>
      ))}
      {remaining > 0 ? (
        <View style={[styles.avatarMore, { backgroundColor: colors.ink, borderColor: colors.card }]}>
          <Text style={styles.avatarMoreText}>+{remaining}</Text>
        </View>
      ) : null}
    </View>
  );
}

export function Photo({
  source,
  height = 190,
  radius = 20,
  overlay,
  style,
  contentFit = "cover",
}: {
  source: ImageSource;
  height?: number;
  radius?: number;
  overlay?: ReactNode;
  style?: StyleProp<ViewStyle>;
  contentFit?: "cover" | "contain";
}) {
  return (
    <View style={[styles.photo, { height, borderRadius: radius }, style]}>
      <Image contentFit={contentFit} source={source} style={StyleSheet.absoluteFill} transition={180} />
      {overlay}
    </View>
  );
}

export function PhotoShade({ children }: { children: ReactNode }) {
  return (
    <LinearGradient
      colors={["transparent", "rgba(15, 12, 10, 0.78)"]}
      end={{ x: 0.5, y: 1 }}
      start={{ x: 0.5, y: 0.3 }}
      style={[StyleSheet.absoluteFill, styles.photoShade]}
    >
      {children}
    </LinearGradient>
  );
}

export function Stat({
  value,
  label,
  icon,
  tone = "accent",
}: {
  value: string;
  label: string;
  icon?: IconName;
  tone?: RudiTone;
}) {
  const { colors } = useRudiTheme();
  return (
    <View style={styles.stat}>
      {icon ? (
        <View style={[styles.statIcon, { backgroundColor: toneSoftColor(colors, tone) }]}>
          <Ionicons color={toneColor(colors, tone)} name={icon} size={19} />
        </View>
      ) : null}
      <Text style={[typography.money, { color: colors.ink }]}>{value}</Text>
      <Text style={[typography.caption, { color: colors.inkFaint }]}>{label}</Text>
    </View>
  );
}

export function AiNote({ children }: { children: ReactNode }) {
  const { colors } = useRudiTheme();
  return (
    <View style={[styles.aiNote, { backgroundColor: colors.aiSoft, borderColor: colors.ai }]}>
      <View style={[styles.aiIcon, { backgroundColor: colors.ai }]}>
        <Ionicons color={colors.aiInk} name="sparkles" size={17} />
      </View>
      <View style={styles.flex}>
        <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI gợi ý</Text>
        <Text style={[typography.label, styles.aiText, { color: colors.ink }]}>{children}</Text>
      </View>
    </View>
  );
}

export function ProgressBar({ value, tone = "accent" }: { value: number; tone?: RudiTone }) {
  const { colors } = useRudiTheme();
  return (
    <View style={[styles.progressTrack, { backgroundColor: colors.line }]}>
      <View
        style={[
          styles.progressFill,
          { backgroundColor: toneColor(colors, tone), width: `${Math.min(100, Math.max(0, value))}%` },
        ]}
      />
    </View>
  );
}

export function Segmented({
  items,
  selected,
  onSelect,
  tone = "accent",
}: {
  items: string[];
  selected: number;
  onSelect: (index: number) => void;
  tone?: RudiTone;
}) {
  const { colors, radius } = useRudiTheme();
  return (
    <View style={[styles.segmented, { backgroundColor: colors.card, borderColor: colors.line, borderRadius: radius.control }]}>
      {items.map((item, index) => {
        const active = selected === index;
        return (
          <Pressable
            key={item}
            accessibilityRole="tab"
            aria-selected={active}
            onPress={() => onSelect(index)}
            style={[
              styles.segment,
              active && { backgroundColor: toneSoftColor(colors, tone), borderRadius: radius.small },
            ]}
          >
            <Text style={[typography.caption, { color: active ? toneColor(colors, tone) : colors.inkFaint }]}>
              {item}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function ListRow({
  icon,
  title,
  subtitle,
  trailing,
  tone = "accent",
  onPress,
}: {
  icon: IconName;
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  tone?: RudiTone;
  onPress?: () => void;
}) {
  const { colors } = useRudiTheme();
  return (
    <Pressable
      accessibilityRole={onPress ? "button" : undefined}
      onPress={onPress}
      style={({ pressed }) => [styles.listRow, pressed && styles.pressed]}
    >
      <View style={[styles.listIcon, { backgroundColor: toneSoftColor(colors, tone) }]}>
        <Ionicons color={toneColor(colors, tone)} name={icon} size={20} />
      </View>
      <View style={styles.listText}>
        <Text style={[typography.label, { color: colors.ink }]}>{title}</Text>
        {subtitle ? <Text style={[typography.caption, { color: colors.inkFaint }]}>{subtitle}</Text> : null}
      </View>
      {trailing ?? (onPress ? <Ionicons color={colors.inkFaint} name="chevron-forward" size={19} /> : null)}
    </Pressable>
  );
}

export function FloatingGlass({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const { dark, radius } = useRudiTheme();
  return (
    <BlurView
      intensity={Platform.OS === "android" ? 35 : 65}
      tint={dark ? "dark" : "light"}
      style={[styles.floatingGlass, { borderRadius: radius.base }, style]}
    >
      {children}
    </BlurView>
  );
}

export function ResponsiveRow({
  children,
  minItemWidth = 250,
  gap = 12,
}: {
  children: ReactNode;
  minItemWidth?: number;
  gap?: number;
}) {
  const { width } = useWindowDimensions();
  const column = width < minItemWidth * 2 + 64;
  return <View style={[styles.responsiveRow, { gap }, column && styles.responsiveColumn]}>{children}</View>;
}

export function Divider() {
  const { colors } = useRudiTheme();
  return <View style={[styles.divider, { backgroundColor: colors.line }]} />;
}

export function Inline({
  children,
  gap = 8,
  wrap = false,
  style,
}: {
  children: ReactNode;
  gap?: number;
  wrap?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.inline, { gap }, wrap && styles.wrap, style]}>{children}</View>;
}

export function Spacer({ size = 16 }: { size?: number }) {
  return <View style={{ height: size }} />;
}

export function SurfaceLabel({ children }: { children: ReactNode }) {
  const { colors } = useRudiTheme();
  return <Text style={[typography.caption, styles.surfaceLabel, { color: colors.inkFaint }]}>{children}</Text>;
}

export function widthPercent(value: number): DimensionValue {
  return (value + "%") as DimensionValue;
}

const styles = StyleSheet.create({
  otpWrap: { position: "relative", alignSelf: "center" },
  otpRow: { flexDirection: "row", gap: 8, justifyContent: "center" },
  otpBox: { width: 44, height: 54, borderWidth: 1.5, alignItems: "center", justifyContent: "center" },
  otpInput: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    color: "transparent",
    backgroundColor: "transparent",
    fontSize: 1,
  },
  flex: { flex: 1 },
  safeArea: { flex: 1, overflow: "hidden" },
  screenInner: { width: "100%", gap: 18, paddingTop: 8 },
  screenFooter: { width: "100%", paddingTop: 8, zIndex: 2 },
  tabletInner: { alignSelf: "center", maxWidth: 960, paddingTop: 22 },
  glow: { position: "absolute", width: 310, height: 310, borderRadius: 999, opacity: 0.52 },
  glowTop: { right: -170, top: -190 },
  glowBottom: { bottom: -220, left: -190, opacity: 0.34 },
  topBar: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  topBarSide: { width: 52, alignItems: "flex-start" },
  topBarRight: { alignItems: "flex-end" },
  topBarTitleWrap: { flex: 1, alignItems: "center", paddingHorizontal: 8 },
  logoRow: { flexDirection: "row", alignItems: "center", flexShrink: 0, gap: 9 },
  logoWordmark: { flexDirection: "row", alignItems: "center", flexShrink: 0, gap: 4 },
  logoMark: { width: 48, height: 48, borderRadius: 17, alignItems: "center", justifyContent: "center", transform: [{ rotate: "-4deg" }] },
  logoMarkCompact: { width: 40, height: 40, borderRadius: 14 },
  logoMarkType: { color: "#FFFFFF", fontSize: 14, lineHeight: 12, fontStyle: "italic", fontWeight: "900", letterSpacing: -0.8, textAlign: "center" },
  logoMarkTypeCompact: { fontSize: 12, lineHeight: 11 },
  logoType: { color: "#C93900", fontSize: 29, lineHeight: 34, fontStyle: "italic", fontWeight: "900", letterSpacing: -1.7 },
  logoTypeCompact: { fontSize: 18, lineHeight: 22, letterSpacing: -1.2 },
  eyebrow: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 999 },
  eyebrowDot: { width: 6, height: 6, borderRadius: 3 },
  demoBadge: { flexDirection: "row", alignItems: "center", alignSelf: "flex-start", gap: 5, borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 5 },
  demoText: { fontSize: 10, lineHeight: 12, fontWeight: "700", letterSpacing: 0.2 },
  heading: { gap: 8, maxWidth: 620 },
  center: { alignSelf: "center", alignItems: "center" },
  headingSubtitle: { maxWidth: 560 },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, marginTop: 3 },
  card: { borderWidth: 1, padding: 16 },
  cardPressed: { opacity: 0.94, transform: [{ scale: 0.992 }] },
  pressed: { opacity: 0.68 },
  button: { minHeight: 52, overflow: "hidden", borderWidth: 1, borderColor: "transparent", paddingHorizontal: 18, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 9 },
  buttonFull: { width: "100%" },
  buttonCompact: { minHeight: 44, paddingHorizontal: 14 },
  buttonLabel: { zIndex: 1 },
  buttonPressed: { opacity: 0.82, transform: [{ scale: 0.98 }] },
  disabled: { opacity: 0.45 },
  iconButton: { width: 48, height: 48, borderRadius: 16, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  fieldBlock: { gap: 7 },
  field: { minHeight: 52, borderWidth: 1, paddingHorizontal: 14, flexDirection: "row", alignItems: "center", gap: 10 },
  fieldMultiline: { minHeight: 108, alignItems: "flex-start", paddingTop: 13 },
  fieldInput: { flex: 1, minHeight: 40, paddingVertical: 0 },
  chip: { minHeight: 48, borderWidth: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 10 },
  avatar: { alignItems: "center", justifyContent: "center" },
  avatarText: { color: "#FFFFFF", fontWeight: "800", letterSpacing: -0.2 },
  avatarStack: { flexDirection: "row", alignItems: "center" },
  avatarMore: { width: 34, height: 34, marginLeft: -10, borderRadius: 17, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  avatarMoreText: { color: "#FFFFFF", fontSize: 10, fontWeight: "800" },
  photo: { position: "relative", overflow: "hidden", backgroundColor: "#E7DACE" },
  photoShade: { justifyContent: "flex-end", padding: 16 },
  stat: { flex: 1, minWidth: 88, alignItems: "center", gap: 4, paddingVertical: 5 },
  statIcon: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center", marginBottom: 2 },
  aiNote: { flexDirection: "row", gap: 11, borderLeftWidth: 3, borderRadius: 14, padding: 13 },
  aiIcon: { width: 32, height: 32, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  aiText: { marginTop: 2 },
  progressTrack: { height: 8, borderRadius: 999, overflow: "hidden" },
  progressFill: { height: "100%", borderRadius: 999 },
  segmented: { flexDirection: "row", padding: 4, borderWidth: 1 },
  segment: { flex: 1, minHeight: 48, paddingHorizontal: 6, alignItems: "center", justifyContent: "center" },
  listRow: { minHeight: 58, flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 7 },
  listIcon: { width: 40, height: 40, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  listText: { flex: 1, gap: 2 },
  floatingGlass: { overflow: "hidden", borderWidth: 1, borderColor: "rgba(255,255,255,0.7)" },
  responsiveRow: { flexDirection: "row", alignItems: "stretch" },
  responsiveColumn: { flexDirection: "column" },
  divider: { width: "100%", height: StyleSheet.hairlineWidth },
  inline: { flexDirection: "row", alignItems: "center" },
  wrap: { flexWrap: "wrap" },
  surfaceLabel: { textTransform: "uppercase", letterSpacing: 0.7 },
});
