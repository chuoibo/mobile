import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { DEMO_GROUP, PEOPLE, demoAssets, formatVnd } from "../fixtures";
import { typography, useRudiTheme } from "../theme";
import {
  Avatar,
  Card,
  Chip,
  DemoBadge,
  Heading,
  IconButton,
  Inline,
  ListRow,
  Photo,
  PhotoShade,
  ProgressBar,
  RudiButton,
  RudiScreen,
  SectionHeader,
  Segmented,
  TopBar,
  widthPercent,
} from "../ui";

export function ProfileScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();

  return (
    <RudiScreen bottomInset={112} testID="profile-screen">
      <View style={styles.profileTop}>
        <View>
          <Text style={[typography.h1, { color: colors.ink }]}>Cá nhân</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Không gian của riêng bạn</Text>
        </View>
        <Inline gap={8}>
          <DemoBadge />
          <IconButton accessibilityLabel="Cài đặt" icon="settings-outline" />
        </Inline>
      </View>
      <Card style={styles.profileHero}>
        <LinearGradient
          colors={["rgba(252,123,55,0.16)", "rgba(131,80,246,0.12)"]}
          end={{ x: 1, y: 1 }}
          start={{ x: 0, y: 0 }}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.avatarLarge}>
          <Avatar person={PEOPLE[0]} ring size={86} />
          <View style={[styles.levelBadge, { backgroundColor: colors.accent }]}>
            <Ionicons color={colors.accentInk} name="sparkles" size={12} />
            <Text style={styles.levelText}>12</Text>
          </View>
        </View>
        <Text style={[typography.h1, { color: colors.ink }]}>Minh Anh</Text>
        <Text style={[typography.body, { color: colors.inkSoft }]}>Đi để nhớ, tụ họp để thương 🌿</Text>
        <Inline gap={7} wrap>
          <Chip icon="location-outline" label="TP. Hồ Chí Minh" />
          <Chip icon="calendar-outline" label="Thành viên từ 2026" />
        </Inline>
        <RudiButton compact full={false} icon="create-outline" label="Chỉnh hồ sơ" variant="outline" />
      </Card>
      <Card style={styles.profileStats}>
        <View style={styles.statItem}>
          <Text style={[typography.money, { color: colors.accent }]}>12</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>chuyến đi</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.statItem}>
          <Text style={[typography.money, { color: colors.ai }]}>6</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>hội bạn</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.statItem}>
          <Text style={[typography.money, { color: colors.split }]}>{DEMO_GROUP.photos}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>kỷ niệm</Text>
        </View>
      </Card>
      <View>
        <SectionHeader title="Sắp tới" />
        <View style={styles.sectionGap} />
        <Card onPress={() => router.push(("/trips/" + DEMO_GROUP.id + "/timeline") as never)} style={styles.upcoming}>
          <Photo
            height={155}
            radius={17}
            source={demoAssets.road}
            overlay={
              <PhotoShade>
                <Text style={styles.upcomingTitle}>{DEMO_GROUP.tripName}</Text>
                <Text style={styles.upcomingMeta}>17–19/10/2026 · Team Đà Lạt</Text>
              </PhotoShade>
            }
          />
          <View style={styles.countdown}>
            <Text style={[typography.money, { color: colors.accent }]}>46</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>ngày nữa</Text>
          </View>
        </Card>
      </View>
      <Card style={styles.menuCard}>
        <ListRow
          icon="wallet-outline"
          onPress={() => router.push("/finance")}
          subtitle="Chi tiêu, công nợ và lịch sử"
          title="Tài chính của tôi"
          tone="split"
        />
        <View style={[styles.rowLine, { backgroundColor: colors.line }]} />
        <ListRow
          icon="trophy-outline"
          onPress={() => router.push("/achievements")}
          subtitle="12 huy hiệu đã mở khóa"
          title="Thành tích"
          tone="ai"
        />
        <View style={[styles.rowLine, { backgroundColor: colors.line }]} />
        <ListRow icon="bookmark-outline" subtitle="18 địa điểm" title="Đã lưu" />
        <View style={[styles.rowLine, { backgroundColor: colors.line }]} />
        <ListRow icon="shield-checkmark-outline" subtitle="Quyền riêng tư và bảo mật" title="Tài khoản" />
      </Card>
    </RudiScreen>
  );
}

const TRANSACTIONS = [
  { icon: "restaurant-outline", title: "Tiệm Nướng Xóm Lèo", detail: "Team Đà Lạt · 17/10", amount: -320_000, tone: "#F97316" },
  { icon: "arrow-down-circle-outline", title: "Tuấn Kiệt đã trả", detail: "Quyết toán Đà Lạt", amount: 320_000, tone: "#00756B" },
  { icon: "home-outline", title: "Homestay Pine Hill", detail: "Team Đà Lạt · đặt cọc", amount: -625_000, tone: "#7D49EF" },
] as const;

export function FinanceScreen() {
  const { colors } = useRudiTheme();
  const [period, setPeriod] = useState(0);

  return (
    <RudiScreen tone="split" testID="finance-screen">
      <TopBar title="Tài chính của tôi" right={<DemoBadge />} />
      <Segmented items={["Tháng này", "3 tháng", "Năm 2026"]} onSelect={setPeriod} selected={period} tone="split" />
      <Card style={styles.financeHero} tone="split">
        <View style={styles.financeHeroTop}>
          <View>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>Tổng chi tháng 10</Text>
            <Text style={[styles.financeMoney, { color: colors.ink }]}>{formatVnd(2_840_000)}</Text>
          </View>
          <View style={[styles.walletIcon, { backgroundColor: colors.split }]}>
            <Ionicons color={colors.splitInk} name="wallet" size={25} />
          </View>
        </View>
        <View style={styles.budgetCopy}>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Ngân sách vui chơi</Text>
          <Text style={[typography.caption, { color: colors.split }]}>71% của 4.000.000đ</Text>
        </View>
        <ProgressBar tone="split" value={71} />
      </Card>
      <Inline gap={10}>
        <Card style={styles.financeMini}>
          <View style={[styles.miniIcon, { backgroundColor: colors.accentSoft }]}>
            <Ionicons color={colors.accent} name="arrow-up" size={19} />
          </View>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Cần trả</Text>
          <Text style={[typography.money, { color: colors.warn }]}>{formatVnd(200_000)}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>2 khoản</Text>
        </Card>
        <Card style={styles.financeMini}>
          <View style={[styles.miniIcon, { backgroundColor: colors.splitSoft }]}>
            <Ionicons color={colors.split} name="arrow-down" size={19} />
          </View>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Sẽ nhận</Text>
          <Text style={[typography.money, { color: colors.split }]}>{formatVnd(780_000)}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Từ 4 người</Text>
        </Card>
      </Inline>
      <View>
        <SectionHeader action="Xem chi tiết" title="Chi theo nhóm" />
        <View style={styles.sectionGap} />
        <Card style={styles.groupSpend}>
          {[
            ["Team Đà Lạt", 1_920_000, 68, colors.accent],
            ["Hội cuối tuần", 610_000, 22, colors.ai],
            ["Đồng nghiệp vui vẻ", 310_000, 10, colors.split],
          ].map(([name, amount, percent, color]) => (
            <View key={String(name)} style={styles.spendRow}>
              <View style={styles.spendTitle}>
                <Text style={[typography.label, { color: colors.ink }]}>{String(name)}</Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>{formatVnd(Number(amount))}</Text>
              </View>
              <View style={[styles.spendTrack, { backgroundColor: colors.line }]}>
                <View style={[styles.spendFill, { backgroundColor: String(color), width: widthPercent(Number(percent)) }]} />
              </View>
            </View>
          ))}
        </Card>
      </View>
      <View>
        <SectionHeader action="Tất cả" title="Giao dịch gần đây" />
        <View style={styles.sectionGap} />
        <Card style={styles.transactions}>
          {TRANSACTIONS.map((transaction, index) => (
            <View key={transaction.title}>
              <View style={styles.transaction}>
                <View style={[styles.transactionIcon, { backgroundColor: transaction.tone + "18" }]}>
                  <Ionicons color={transaction.tone} name={transaction.icon} size={20} />
                </View>
                <View style={styles.flex}>
                  <Text style={[typography.label, { color: colors.ink }]}>{transaction.title}</Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>{transaction.detail}</Text>
                </View>
                <Text style={[typography.label, { color: transaction.amount > 0 ? colors.split : colors.ink }]}>
                  {transaction.amount > 0 ? "+" : "−"}{formatVnd(Math.abs(transaction.amount))}
                </Text>
              </View>
              {index < TRANSACTIONS.length - 1 ? <View style={[styles.rowLine, { backgroundColor: colors.line }]} /> : null}
            </View>
          ))}
        </Card>
      </View>
      <Card style={styles.financeFootnote}>
        <Ionicons color={colors.split} name="calculator-outline" size={20} />
        <Text style={[typography.caption, styles.flex, { color: colors.inkSoft }]}>
          Số dư được tính lại từ sổ cái. Dữ liệu trên màn này chỉ là bản demo, không phải số dư ngân hàng.
        </Text>
      </Card>
    </RudiScreen>
  );
}

const BADGES = [
  ["airplane", "Chân đi", "Hoàn thành 10 chuyến", "#F97316", true],
  ["people", "Kết nối", "Đi cùng 25 người bạn", "#7D49EF", true],
  ["restaurant", "Foodie", "Thử 20 món local", "#E11D48", true],
  ["camera", "Ký ức", "Đăng 100 khoảnh khắc", "#0EA5E9", true],
  ["leaf", "Xanh", "5 chuyến ngoài trời", "#16A34A", true],
  ["map", "Nhà thám hiểm", "Ghé 15 tỉnh thành", "#C93900", false],
] as const;

export function AchievementsScreen() {
  const { colors } = useRudiTheme();

  return (
    <RudiScreen tone="ai" testID="achievements-screen">
      <TopBar title="Thành tích" right={<DemoBadge />} />
      <Card style={styles.levelHero}>
        <LinearGradient
          colors={["#7D49EF", "#C9344A"]}
          end={{ x: 1, y: 1 }}
          start={{ x: 0, y: 0 }}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.levelHeroTop}>
          <View style={styles.levelSeal}>
            <Ionicons color="#7D49EF" name="sparkles" size={27} />
            <Text style={styles.levelNumber}>12</Text>
          </View>
          <View style={styles.flex}>
            <Text style={styles.levelKicker}>NHÀ THÁM HIỂM</Text>
            <Text style={styles.levelTitle}>Minh Anh · Cấp 12</Text>
            <Text style={styles.levelSubtitle}>1.240 XP nữa để lên cấp 13</Text>
          </View>
        </View>
        <View style={styles.levelTrack}>
          <View style={styles.levelFill} />
        </View>
        <View style={styles.levelProgressText}>
          <Text style={styles.levelSmall}>3.760 XP</Text>
          <Text style={styles.levelSmall}>5.000 XP</Text>
        </View>
      </Card>
      <Card style={styles.achievementStats}>
        <View style={styles.statItem}>
          <Text style={[typography.money, { color: colors.ai }]}>12</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>huy hiệu</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.statItem}>
          <Text style={[typography.money, { color: colors.accent }]}>8</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>hiếm</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.statItem}>
          <Text style={[typography.money, { color: colors.split }]}>68%</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>bộ sưu tập</Text>
        </View>
      </Card>
      <SectionHeader action="12/18 đã mở" title="Huy hiệu của bạn" />
      <View style={styles.badgeGrid}>
        {BADGES.map(([icon, name, detail, color, unlocked]) => (
          <Card key={name} style={[styles.badgeCard, !unlocked && styles.badgeLocked]}>
            <View style={[styles.badgeIcon, { backgroundColor: color + "18", borderColor: color + "36" }]}>
              <Ionicons color={unlocked ? color : colors.inkFaint} name={unlocked ? icon : "lock-closed"} size={27} />
            </View>
            <Text style={[typography.title, styles.badgeName, { color: colors.ink }]}>{name}</Text>
            <Text style={[typography.caption, styles.badgeDetail, { color: colors.inkFaint }]}>{detail}</Text>
            {unlocked ? (
              <View style={[styles.unlocked, { backgroundColor: color + "18" }]}>
                <Ionicons color={color} name="checkmark-circle" size={13} />
                <Text style={[styles.unlockedText, { color }]}>Đã mở khóa</Text>
              </View>
            ) : (
              <View style={[styles.unlocked, { backgroundColor: colors.ground }]}>
                <Text style={[styles.unlockedText, { color: colors.inkFaint }]}>12/15 tỉnh</Text>
              </View>
            )}
          </Card>
        ))}
      </View>
      <Card style={styles.nextQuest} tone="ai">
        <View style={[styles.questIcon, { backgroundColor: colors.ai }]}>
          <Ionicons color={colors.aiInk} name="flag" size={23} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.title, { color: colors.ink }]}>Thử thách tiếp theo</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Check-in thêm 3 tỉnh để mở “Nhà thám hiểm”.</Text>
          <View style={styles.questProgress}><ProgressBar tone="ai" value={80} /></View>
        </View>
      </Card>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  profileTop: { minHeight: 54, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  profileHero: { alignItems: "center", overflow: "hidden", gap: 8, paddingVertical: 23 },
  avatarLarge: { position: "relative" },
  levelBadge: { position: "absolute", right: -7, bottom: 1, minWidth: 37, height: 24, borderRadius: 999, borderWidth: 2, borderColor: "#FFFFFF", flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 2, paddingHorizontal: 5 },
  levelText: { color: "#FFFFFF", fontSize: 10, fontWeight: "900" },
  profileStats: { flexDirection: "row", alignItems: "center", paddingHorizontal: 8 },
  statItem: { flex: 1, alignItems: "center", gap: 3, paddingVertical: 5 },
  verticalLine: { width: StyleSheet.hairlineWidth, height: 38 },
  sectionGap: { height: 10 },
  upcoming: { padding: 7, position: "relative" },
  upcomingTitle: { color: "#FFFFFF", fontSize: 19, lineHeight: 24, fontWeight: "900" },
  upcomingMeta: { color: "rgba(255,255,255,0.8)", fontSize: 11, fontWeight: "700" },
  countdown: { position: "absolute", right: 15, top: 15, minWidth: 74, alignItems: "center", padding: 8, borderRadius: 15, backgroundColor: "rgba(255,255,255,0.93)" },
  menuCard: { paddingVertical: 5 },
  rowLine: { height: StyleSheet.hairlineWidth, marginLeft: 52 },
  financeHero: { gap: 13 },
  financeHeroTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  financeMoney: { fontSize: 34, lineHeight: 41, fontWeight: "900", letterSpacing: -0.9, fontVariant: ["tabular-nums"] },
  walletIcon: { width: 50, height: 50, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  budgetCopy: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  financeMini: { flex: 1, gap: 5 },
  miniIcon: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center", marginBottom: 3 },
  groupSpend: { gap: 14 },
  spendRow: { gap: 7 },
  spendTitle: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  spendTrack: { height: 9, overflow: "hidden", borderRadius: 999 },
  spendFill: { height: "100%", borderRadius: 999 },
  transactions: { paddingVertical: 5 },
  transaction: { minHeight: 64, flexDirection: "row", alignItems: "center", gap: 11 },
  transactionIcon: { width: 41, height: 41, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  financeFootnote: { flexDirection: "row", alignItems: "flex-start", gap: 9 },
  levelHero: { overflow: "hidden", gap: 14, padding: 19 },
  levelHeroTop: { flexDirection: "row", alignItems: "center", gap: 14 },
  levelSeal: { width: 72, height: 72, borderRadius: 23, backgroundColor: "#FFFFFF", alignItems: "center", justifyContent: "center" },
  levelNumber: { color: "#7D49EF", fontSize: 17, fontWeight: "900", marginTop: -3 },
  levelKicker: { color: "rgba(255,255,255,0.72)", fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  levelTitle: { color: "#FFFFFF", fontSize: 22, lineHeight: 27, fontWeight: "900" },
  levelSubtitle: { color: "rgba(255,255,255,0.79)", fontSize: 11, lineHeight: 16, fontWeight: "600" },
  levelTrack: { height: 9, borderRadius: 999, backgroundColor: "rgba(255,255,255,0.24)", overflow: "hidden" },
  levelFill: { width: "75%", height: "100%", borderRadius: 999, backgroundColor: "#FFFFFF" },
  levelProgressText: { flexDirection: "row", justifyContent: "space-between" },
  levelSmall: { color: "rgba(255,255,255,0.82)", fontSize: 10, fontWeight: "800" },
  achievementStats: { flexDirection: "row", alignItems: "center", paddingHorizontal: 8 },
  badgeGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  badgeCard: { flexGrow: 1, flexBasis: 145, alignItems: "center", gap: 6, padding: 14 },
  badgeLocked: { opacity: 0.62 },
  badgeIcon: { width: 61, height: 61, borderRadius: 20, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  badgeName: { textAlign: "center" },
  badgeDetail: { textAlign: "center", minHeight: 32 },
  unlocked: { flexDirection: "row", alignItems: "center", gap: 4, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 5 },
  unlockedText: { fontSize: 9, lineHeight: 12, fontWeight: "900" },
  nextQuest: { flexDirection: "row", alignItems: "flex-start", gap: 11 },
  questIcon: { width: 44, height: 44, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  questProgress: { marginTop: 9 },
});
