import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { BILL_ITEMS, DEMO_GROUP, PEOPLE, demoAssets, formatVnd } from "../fixtures";
import { typography, useRudiTheme } from "../theme";
import {
  AiNote,
  Avatar,
  AvatarStack,
  Card,
  Chip,
  DemoBadge,
  Heading,
  IconButton,
  Inline,
  ProgressBar,
  RudiButton,
  RudiScreen,
  SectionHeader,
  TopBar,
} from "../ui";

function ReceiptPaper({ compact = false }: { compact?: boolean }) {
  const { colors } = useRudiTheme();
  const detectedTotal = BILL_ITEMS.reduce((sum, item) => sum + item.amount, 0);

  return (
    <LinearGradient
      colors={["#FFFDF7", "#F4E8D7", "#FFF9EC"]}
      end={{ x: 1, y: 1 }}
      start={{ x: 0, y: 0 }}
      style={[styles.receipt, compact && styles.receiptCompact]}
    >
      <View pointerEvents="none" style={styles.paperHighlight} />
      <View pointerEvents="none" style={styles.paperFold} />
      <Text style={styles.receiptStore}>TIỆM NƯỚNG XÓM LÈO</Text>
      <Text style={styles.receiptSmall}>Đà Lạt, Lâm Đồng</Text>
      <View style={styles.receiptDash} />
      <Text style={styles.receiptTitle}>HÓA ĐƠN THANH TOÁN</Text>
      <Text style={styles.receiptSmall}>Bàn: 07</Text>
      <Text style={styles.receiptSmall}>Ngày: 17/10/2026 19:45</Text>
      <View style={styles.receiptDash} />
      {!compact ? (
        <>
          <View style={styles.receiptHeader}>
            <Text style={[styles.receiptCell, styles.receiptIndex]}>STT</Text>
            <Text style={[styles.receiptCell, styles.receiptName]}>MÓN</Text>
            <Text style={[styles.receiptCell, styles.receiptAmount]}>THÀNH TIỀN</Text>
          </View>
          {BILL_ITEMS.map((item, index) => (
            <View key={item.name} style={styles.receiptRow}>
              <Text style={[styles.receiptCell, styles.receiptIndex]}>{index + 1}</Text>
              <Text style={[styles.receiptCell, styles.receiptName]}>{item.name}</Text>
              <Text style={[styles.receiptCell, styles.receiptAmount]}>{item.amount.toLocaleString("vi-VN")}</Text>
            </View>
          ))}
        </>
      ) : null}
      <View style={styles.receiptDash} />
      <View style={styles.receiptTotal}>
        <Text style={styles.receiptTotalLabel}>TỔNG CỘNG</Text>
        <Text style={styles.receiptTotalValue}>{formatVnd(detectedTotal)}</Text>
      </View>
      {!compact ? <Text style={[styles.receiptThanks, { color: colors.inkSoft }]}>Cảm ơn quý khách!</Text> : null}
    </LinearGradient>
  );
}

export function ReceiptReviewScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [captured, setCaptured] = useState(true);

  return (
    <RudiScreen tone="split" testID="receipt-review-screen">
      <TopBar title="Xem lại hóa đơn" right={<DemoBadge />} />
      <View style={styles.wood}>
        <Image contentFit="cover" source={demoAssets.wood} style={StyleSheet.absoluteFill} />
        <View pointerEvents="none" style={styles.woodWarmth} />
        <LinearGradient
          colors={["rgba(17,7,2,0.34)", "rgba(17,7,2,0.02)", "rgba(17,7,2,0.38)"]}
          locations={[0, 0.52, 1]}
          style={StyleSheet.absoluteFill}
        />
        {captured ? (
          <ReceiptPaper />
        ) : (
          <View style={styles.cameraTarget}>
            <View style={styles.cameraTargetIcon}>
              <Ionicons color="#FFFFFF" name="camera-outline" size={32} />
            </View>
            <Text style={styles.cameraTargetTitle}>Căn đủ bốn góc hóa đơn</Text>
            <Text style={styles.cameraTargetCopy}>Camera demo · giữ máy thẳng và đủ sáng</Text>
          </View>
        )}
        <View style={[styles.cropCorner, styles.cropTopLeft]} />
        <View style={[styles.cropCorner, styles.cropTopRight]} />
        <View style={[styles.cropCorner, styles.cropBottomLeft]} />
        <View style={[styles.cropCorner, styles.cropBottomRight]} />
      </View>
      <Card style={styles.detectCard} tone="split">
        <View style={[styles.detectIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name={captured ? "checkmark" : "camera-outline"} size={19} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.label, { color: colors.ink }]}>
            {captured ? "Ảnh rõ và đủ bốn góc" : "Camera demo đã sẵn sàng"}
          </Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>
            {captured ? "Sẵn sàng đọc 6 dòng bằng OCR." : "Chạm nút chụp để tạo lại ảnh mẫu."}
          </Text>
        </View>
        <Text style={[typography.caption, { color: colors.split }]}>{captured ? "Tốt" : "Demo"}</Text>
      </Card>
      <Inline gap={10}>
        <RudiButton
          full={false}
          icon={captured ? "refresh-outline" : "close-outline"}
          label={captured ? "Chụp lại" : "Giữ ảnh cũ"}
          onPress={() => setCaptured((value) => !value)}
          style={styles.flex}
          tone="split"
          variant="outline"
        />
        <RudiButton
          full={false}
          icon={captured ? "scan-outline" : "camera"}
          label={captured ? "Dùng ảnh này" : "Mô phỏng chụp"}
          onPress={() =>
            captured
              ? router.push(("/smart-split/" + DEMO_GROUP.id + "/assignment") as never)
              : setCaptured(true)
          }
          style={styles.flex}
          tone="split"
        />
      </Inline>
      <Inline gap={7} style={styles.hint}>
        <Ionicons color={colors.inkFaint} name="information-circle-outline" size={18} />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          {captured
            ? "Hãy chụp rõ nét, đủ sáng và không cắt góc hóa đơn."
            : "Đây là camera mô phỏng; ứng dụng không lưu hay tải ảnh thật lên."}
        </Text>
      </Inline>
    </RudiScreen>
  );
}

export function OcrAssignmentScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [assignments, setAssignments] = useState(
    BILL_ITEMS.map((item) => [...item.people] as number[]),
  );
  const detectedTotal = useMemo(
    () => BILL_ITEMS.reduce((sum, item) => sum + item.amount, 0),
    [],
  );

  const togglePerson = (itemIndex: number, personIndex: number) => {
    setAssignments((current) =>
      current.map((people, index) =>
        index !== itemIndex
          ? people
          : people.includes(personIndex)
            ? people.filter((person) => person !== personIndex)
            : [...people, personIndex],
      ),
    );
  };

  return (
    <RudiScreen tone="split" testID="ocr-assignment-screen">
      <TopBar title="Ai dùng món nào?" right={<DemoBadge label="OCR demo" />} />
      <Card style={styles.ocrSummary} tone="split">
        <View style={[styles.scanIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name="scan" size={24} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.title, { color: colors.ink }]}>Đã đọc xong hóa đơn</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>6/6 dòng · kiểm tra trước khi xác nhận</Text>
        </View>
        <Text style={[typography.money, { color: colors.split }]}>{formatVnd(detectedTotal)}</Text>
      </Card>
      <AiNote>
        RuDi chỉ gợi ý người dùng món. Chạm avatar để sửa; tổng tiền không thay đổi.
      </AiNote>
      <View style={styles.billItems}>
        {BILL_ITEMS.map((item, itemIndex) => (
          <Card key={item.name} style={styles.billItem}>
            <View style={styles.billItemTop}>
              <View style={styles.flex}>
                <Text style={[typography.title, { color: colors.ink }]}>{item.name}</Text>
                <Inline gap={5}>
                  <Ionicons color={colors.split} name="sparkles" size={13} />
                  <Text style={[typography.caption, { color: colors.split }]}>Đã nhận diện · cần kiểm tra</Text>
                </Inline>
              </View>
              <Text style={[typography.money, { color: colors.ink }]}>{formatVnd(item.amount)}</Text>
            </View>
            <View style={[styles.itemDivider, { backgroundColor: colors.line }]} />
            <View style={styles.assignmentRow}>
              <View>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>Chia cho</Text>
                <Text style={[typography.label, { color: colors.ink }]}>{assignments[itemIndex].length} người</Text>
              </View>
              <View style={styles.assignmentPeople}>
                {PEOPLE.map((person, personIndex) => {
                  const active = assignments[itemIndex].includes(personIndex);
                  return (
                    <Pressable
                      key={person.id}
                      accessibilityRole="checkbox"
                      aria-checked={active}
                      onPress={() => togglePerson(itemIndex, personIndex)}
                      style={({ pressed }) => [!active && styles.avatarInactive, pressed && styles.pressed]}
                    >
                      <Avatar person={person} ring={active} size={34} />
                    </Pressable>
                  );
                })}
              </View>
            </View>
          </Card>
        ))}
      </View>
      <Card style={styles.totalCard}>
        <View>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Tổng hóa đơn</Text>
          <Text style={[typography.h2, { color: colors.ink }]}>Tiệm Nướng Xóm Lèo</Text>
        </View>
        <Text style={[typography.money, { color: colors.split }]}>{formatVnd(detectedTotal)}</Text>
      </Card>
      <RudiButton
        disabled={assignments.some((people) => people.length === 0)}
        icon="checkmark-circle-outline"
        label="Xác nhận cách chia"
        onPress={() => router.replace(("/settlements/" + DEMO_GROUP.id) as never)}
        tone="split"
      />
    </RudiScreen>
  );
}

const SETTLEMENTS = [
  { person: PEOPLE[1], amount: 320_000, paid: true },
  { person: PEOPLE[2], amount: 260_000, paid: true },
  { person: PEOPLE[3], amount: 120_000, paid: false },
  { person: PEOPLE[4], amount: 80_000, paid: false },
] as const;

export function SettlementScreen() {
  const { colors } = useRudiTheme();
  const paid = SETTLEMENTS.filter((item) => item.paid).reduce((sum, item) => sum + item.amount, 0);
  const total = SETTLEMENTS.reduce((sum, item) => sum + item.amount, 0);

  return (
    <RudiScreen tone="split" testID="settlement-screen">
      <TopBar title="Quyết toán chuyến đi" right={<DemoBadge />} />
      <Card style={styles.settlementHero} tone="split">
        <View style={[styles.balanceIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name="wallet" size={26} />
        </View>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Tổng chi tiêu của nhóm</Text>
        <Text style={[styles.bigMoney, { color: colors.ink }]}>{formatVnd(DEMO_GROUP.tripTotalVnd)}</Text>
        <Text style={[typography.caption, { color: colors.split }]}>Đã chốt từ sổ cái · 8 thành viên</Text>
        <View style={styles.settlementStats}>
          <View style={styles.settlementStat}>
            <Text style={[typography.title, { color: colors.ink }]}>2</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>đã trả</Text>
          </View>
          <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
          <View style={styles.settlementStat}>
            <Text style={[typography.title, { color: colors.warn }]}>2</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>đang chờ</Text>
          </View>
          <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
          <View style={styles.settlementStat}>
            <Text style={[typography.title, { color: colors.split }]}>8</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>thành viên</Text>
          </View>
        </View>
      </Card>
      <Card style={styles.receiveCard}>
        <View style={styles.receiveTop}>
          <Avatar person={PEOPLE[0]} size={49} />
          <View style={styles.flex}>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>Minh Anh sẽ nhận</Text>
            <Text style={[typography.money, { color: colors.split }]}>{formatVnd(total)}</Text>
          </View>
          <Chip icon="shield-checkmark-outline" label="Người thu" selected tone="split" />
        </View>
        <ProgressBar tone="split" value={(paid * 100) / total} />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Đã nhận {formatVnd(paid)} · còn {formatVnd(total - paid)}
        </Text>
      </Card>
      <SectionHeader title="Các khoản chuyển" />
      <View style={styles.transferList}>
        {SETTLEMENTS.map((item) => (
          <Card key={item.person.id} style={styles.transfer}>
            <Avatar person={item.person} size={44} />
            <View style={styles.flex}>
              <Text style={[typography.label, { color: colors.ink }]}>{item.person.name} → Minh Anh</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>
                {item.paid ? "Đã xác nhận trong ứng dụng" : "Chờ người nhận xác nhận"}
              </Text>
            </View>
            <View style={styles.transferRight}>
              <Text style={[typography.label, { color: colors.ink }]}>{formatVnd(item.amount)}</Text>
              <View style={[styles.status, { backgroundColor: item.paid ? colors.splitSoft : colors.accentSoft }]}>
                <Ionicons color={item.paid ? colors.split : colors.warn} name={item.paid ? "checkmark-circle" : "time"} size={13} />
                <Text style={[styles.statusText, { color: item.paid ? colors.split : colors.warn }]}>
                  {item.paid ? "Đã trả" : "Đang chờ"}
                </Text>
              </View>
            </View>
          </Card>
        ))}
      </View>
      <Card style={styles.safetyNote}>
        <Ionicons color={colors.warn} name="shield-checkmark-outline" size={21} />
        <Text style={[typography.caption, styles.flex, { color: colors.inkSoft }]}>
          “Đã trả” là xác nhận trong RuDi, không phải bằng chứng từ ngân hàng. Chuyến đi chỉ hoàn tất theo chuyển trạng thái của hệ thống.
        </Text>
      </Card>
      <RudiButton icon="notifications-outline" label="Nhắc 2 người đang chờ" tone="split" />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  wood: { minHeight: 560, overflow: "hidden", borderRadius: 24, backgroundColor: "#4A2818", padding: 28, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "rgba(255,255,255,0.22)", elevation: 6, shadowColor: "#1B0902", shadowOpacity: 0.25, shadowRadius: 18, shadowOffset: { width: 0, height: 10 } },
  woodWarmth: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, backgroundColor: "rgba(73,28,6,0.12)" },
  receipt: { width: "88%", maxWidth: 390, minHeight: 500, borderRadius: 3, paddingHorizontal: 24, paddingVertical: 28, shadowColor: "#000000", shadowOpacity: 0.48, shadowRadius: 20, shadowOffset: { width: 0, height: 13 }, elevation: 14, transform: [{ rotate: "-1.2deg" }] },
  receiptCompact: { minHeight: 0, paddingVertical: 18 },
  paperHighlight: { position: "absolute", left: 8, top: 0, bottom: 0, width: 1, backgroundColor: "rgba(255,255,255,0.72)" },
  paperFold: { position: "absolute", right: -10, top: -10, width: 42, height: 42, borderRadius: 21, backgroundColor: "rgba(209,188,160,0.2)" },
  cameraTarget: { width: "88%", maxWidth: 390, minHeight: 500, borderWidth: 2, borderStyle: "dashed", borderColor: "rgba(255,255,255,0.8)", borderRadius: 20, alignItems: "center", justifyContent: "center", gap: 9, padding: 24, backgroundColor: "rgba(20,8,3,0.24)" },
  cameraTargetIcon: { width: 64, height: 64, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.18)", borderWidth: 1, borderColor: "rgba(255,255,255,0.34)" },
  cameraTargetTitle: { color: "#FFFFFF", fontSize: 18, lineHeight: 24, fontWeight: "900", textAlign: "center" },
  cameraTargetCopy: { color: "rgba(255,255,255,0.78)", fontSize: 12, lineHeight: 18, fontWeight: "700", textAlign: "center" },
  receiptStore: { color: "#241D18", textAlign: "center", fontSize: 19, lineHeight: 24, fontWeight: "900" },
  receiptSmall: { color: "#453B34", fontSize: 11, lineHeight: 18, fontWeight: "600" },
  receiptDash: { borderTopWidth: 1, borderStyle: "dashed", borderColor: "#51463E", marginVertical: 12 },
  receiptTitle: { color: "#241D18", fontSize: 13, lineHeight: 18, fontWeight: "900", textAlign: "center", marginBottom: 9 },
  receiptHeader: { flexDirection: "row", marginBottom: 8 },
  receiptRow: { flexDirection: "row", minHeight: 23 },
  receiptCell: { color: "#302923", fontSize: 11, lineHeight: 17 },
  receiptIndex: { width: 28 },
  receiptName: { flex: 1 },
  receiptAmount: { width: 80, textAlign: "right", fontVariant: ["tabular-nums"] },
  receiptTotal: { flexDirection: "row", justifyContent: "space-between" },
  receiptTotalLabel: { color: "#241D18", fontSize: 15, fontWeight: "900" },
  receiptTotalValue: { color: "#241D18", fontSize: 17, fontWeight: "900", fontVariant: ["tabular-nums"] },
  receiptThanks: { textAlign: "center", fontSize: 11, marginTop: 20 },
  cropCorner: { position: "absolute", width: 40, height: 40, borderColor: "#FFFFFF" },
  cropTopLeft: { left: 14, top: 14, borderLeftWidth: 3, borderTopWidth: 3, borderTopLeftRadius: 14 },
  cropTopRight: { right: 14, top: 14, borderRightWidth: 3, borderTopWidth: 3, borderTopRightRadius: 14 },
  cropBottomLeft: { left: 14, bottom: 14, borderLeftWidth: 3, borderBottomWidth: 3, borderBottomLeftRadius: 14 },
  cropBottomRight: { right: 14, bottom: 14, borderRightWidth: 3, borderBottomWidth: 3, borderBottomRightRadius: 14 },
  detectCard: { flexDirection: "row", alignItems: "center", gap: 11 },
  detectIcon: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  hint: { justifyContent: "center", paddingHorizontal: 10 },
  ocrSummary: { flexDirection: "row", alignItems: "center", gap: 11 },
  scanIcon: { width: 46, height: 46, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  billItems: { gap: 10 },
  billItem: { gap: 12 },
  billItemTop: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 10 },
  itemDivider: { height: StyleSheet.hairlineWidth },
  assignmentRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  assignmentPeople: { flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-end", gap: 4, flex: 1 },
  avatarInactive: { opacity: 0.27 },
  pressed: { opacity: 0.7 },
  totalCard: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  settlementHero: { alignItems: "center", gap: 6, paddingTop: 22 },
  balanceIcon: { width: 54, height: 54, borderRadius: 18, alignItems: "center", justifyContent: "center", marginBottom: 4 },
  bigMoney: { fontSize: 35, lineHeight: 42, fontWeight: "900", letterSpacing: -1, fontVariant: ["tabular-nums"] },
  settlementStats: { width: "100%", flexDirection: "row", alignItems: "center", marginTop: 12, paddingTop: 13, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "rgba(0,117,107,0.18)" },
  settlementStat: { flex: 1, alignItems: "center", gap: 2 },
  verticalLine: { height: 33, width: StyleSheet.hairlineWidth },
  receiveCard: { gap: 12 },
  receiveTop: { flexDirection: "row", alignItems: "center", gap: 11 },
  transferList: { gap: 9 },
  transfer: { flexDirection: "row", alignItems: "center", gap: 11, padding: 12 },
  transferRight: { alignItems: "flex-end", gap: 5 },
  status: { flexDirection: "row", alignItems: "center", gap: 3, borderRadius: 999, paddingHorizontal: 7, paddingVertical: 4 },
  statusText: { fontSize: 10, lineHeight: 12, fontWeight: "800" },
  safetyNote: { flexDirection: "row", alignItems: "flex-start", gap: 9, backgroundColor: "#FFF8ED" },
});
