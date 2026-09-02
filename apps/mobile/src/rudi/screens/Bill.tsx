import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, BASE_URL, scanReceipt } from "../../api";
import { docQuyetToanLive, tenCua, type QuyetToanLive } from "../doc-live";
import { DEMO_PEOPLE } from "../../navigation/nhom-demo";
import { BILL_ITEMS, COLLECTOR_INDEX, DEMO_GROUP, PEOPLE, demoAssets, formatVnd } from "../fixtures";
import { noiLuuNgan } from "../luu-tru";
import { useRudiSession } from "../session";
import { typography, useRudiTheme } from "../theme";
import {
  AiNote,
  Avatar,
  Card,
  Chip,
  DemoBadge,
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
  const session = useRudiSession();
  const [busy, setBusy] = useState(false);
  const [scanNote, setScanNote] = useState<string | null>(null);

  const pickPhoto = async () => {
    setBusy(true);
    setScanNote(null);
    try {
      const picked = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 0.8,
      });
      if (picked.canceled || !picked.assets[0]) {
        setScanNote("Không chọn ảnh.");
        return;
      }
      session.setReceiptPicked(true);
      try {
        await scanReceipt(
          { uri: picked.assets[0].uri, bytes: picked.assets[0].fileSize ?? 0 },
          DEMO_PEOPLE[0].personId,
        );
        setScanNote("Máy chủ nhận ảnh. Dòng trên giấy vẫn là payload canonical Xóm Lèo cho đến khi OCR thật thay thế.");
      } catch (error) {
        const message = error instanceof ApiError ? error.message : `Không đọc được bill tại ${BASE_URL}.`;
        setScanNote(message);
      }
    } finally {
      setBusy(false);
    }
  };

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
        <ReceiptPaper />
        <View style={[styles.cropCorner, styles.cropTopLeft]} />
        <View style={[styles.cropCorner, styles.cropTopRight]} />
        <View style={[styles.cropCorner, styles.cropBottomLeft]} />
        <View style={[styles.cropCorner, styles.cropBottomRight]} />
      </View>
      <Card style={styles.detectCard} tone="split">
        <View style={[styles.detectIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name="receipt-outline" size={19} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.label, { color: colors.ink }]}>Giấy mẫu Tiệm Nướng Xóm Lèo</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>
            6 dòng canonical · tổng {formatVnd(DEMO_GROUP.billTotalVnd)}. Đây không phải kết quả OCR.
          </Text>
        </View>
      </Card>
      <Inline gap={10}>
        <RudiButton
          full={false}
          icon="images-outline"
          label="Chọn ảnh bill"
          loading={busy}
          onPress={() => void pickPhoto()}
          style={styles.flex}
          tone="split"
          variant="outline"
        />
        <RudiButton
          full={false}
          icon="arrow-forward"
          label="Dùng giấy mẫu"
          onPress={() => router.push(("/smart-split/" + DEMO_GROUP.id + "/assignment") as never)}
          style={styles.flex}
          tone="split"
        />
      </Inline>
      {scanNote ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>{scanNote}</Text>
      ) : (
        <Inline gap={7} style={styles.hint}>
          <Ionicons color={colors.inkFaint} name="information-circle-outline" size={18} />
          <Text style={[typography.caption, { color: colors.inkFaint }]}>
            {session.receiptPicked
              ? "Đã chọn ảnh trên máy. OCR chỉ chạy khi máy chủ nhận được POST /receipts/scan."
              : "Chọn ảnh từ thư viện để thử OCR. Không có camera giả."}
          </Text>
        </Inline>
      )}
    </RudiScreen>
  );
}

export function OcrAssignmentScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const detectedTotal = session.money.billTotal;

  return (
    <RudiScreen tone="split" testID="ocr-assignment-screen">
      <TopBar title="Ai dùng món nào?" right={<DemoBadge label="Nháp trên máy" />} />
      <Card style={styles.ocrSummary} tone="split">
        <View style={[styles.scanIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name="scan" size={24} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.title, { color: colors.ink }]}>Gán người từng dòng</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>
            6 khoản · tổng không đổi khi bạn sửa người
          </Text>
        </View>
        <Text style={[typography.money, { color: colors.split }]}>{formatVnd(detectedTotal)}</Text>
      </Card>
      <AiNote>
        Rủ Đi gợi ý người dùng món. Chạm avatar để sửa. Tổng bill giữ nguyên; phần mỗi người đổi và chảy sang quyết toán.
      </AiNote>
      <View style={styles.billItems}>
        {BILL_ITEMS.map((item, itemIndex) => (
          <Card key={item.name} style={styles.billItem}>
            <View style={styles.billItemTop}>
              <View style={styles.flex}>
                <Text style={[typography.title, { color: colors.ink }]}>{item.name}</Text>
                <Inline gap={5}>
                  <Ionicons color={colors.split} name="people-outline" size={13} />
                  <Text style={[typography.caption, { color: colors.split }]}>
                    {session.assignments[itemIndex].length} người · cần kiểm tra
                  </Text>
                </Inline>
              </View>
              <Text style={[typography.money, { color: colors.ink }]}>{formatVnd(item.amount)}</Text>
            </View>
            <View style={[styles.itemDivider, { backgroundColor: colors.line }]} />
            <View style={styles.assignmentRow}>
              <View>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>Chia cho</Text>
                <Text style={[typography.label, { color: colors.ink }]}>{session.assignments[itemIndex].length} người</Text>
              </View>
              <View style={styles.assignmentPeople}>
                {PEOPLE.map((person, personIndex) => {
                  const active = session.assignments[itemIndex].includes(personIndex);
                  return (
                    <Pressable
                      key={person.id}
                      accessibilityRole="checkbox"
                      aria-checked={active}
                      onPress={() => session.toggleAssignment(itemIndex, personIndex)}
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
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Tổng hóa đơn Xóm Lèo</Text>
          <Text style={[typography.h2, { color: colors.ink }]}>Không gồm homestay / xăng</Text>
        </View>
        <Text style={[typography.money, { color: colors.split }]}>{formatVnd(detectedTotal)}</Text>
      </Card>
      <RudiButton
        disabled={session.assignments.some((people) => people.length === 0)}
        icon="checkmark-circle-outline"
        label="Xác nhận cách chia"
        onPress={() => router.replace(("/settlements/" + DEMO_GROUP.id) as never)}
        tone="split"
      />
    </RudiScreen>
  );
}

/**
 * Two screens behind one name, and the switch is `nguon`, never a probe.
 *
 * The draft below is a picture of a fixture; the live one is a picture of a
 * ledger. Deciding between them by asking whether a server happens to answer
 * would let the two swap places with no action by the person holding the phone,
 * which is the failure this whole seam exists to prevent. See `src/rudi/nguon.ts`.
 */
export function SettlementScreen() {
  const session = useRudiSession();
  if (session.nguon.kieu === "live") {
    return <QuyetToanLive actorId={session.nguon.actorId} contextId={session.nguon.contextId} />;
  }
  return <QuyetToanNhap />;
}

/**
 * The settlement as the ledger has it.
 *
 * Nothing here computes money. `/contexts/{id}/balances` recomputes the net and
 * the minimal transfer set per request, and re-deriving either on the phone
 * would be the second allocator this repo has already thrown out once.
 */
function QuyetToanLive({ actorId, contextId }: { actorId: string; contextId: string }) {
  const { colors } = useRudiTheme();
  const [du, setDu] = useState<QuyetToanLive | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let song = true;
    void docQuyetToanLive(actorId, contextId, BASE_URL)
      .then((ketQua) => {
        if (song) setDu(ketQua);
      })
      .catch((error: unknown) => {
        // The real sentence from the real failure. Falling back to the fixture
        // here would answer a broken request with somebody else's money.
        if (!song) return;
        setLoi(
          error instanceof ApiError
            ? error.message
            : `Không đọc được quyết toán tại ${BASE_URL}.`,
        );
      });
    return () => {
      song = false;
    };
  }, [actorId, contextId]);

  if (loi !== null) {
    return (
      <RudiScreen tone="split" testID="settlement-screen">
        <TopBar title="Quyết toán chuyến đi" />
        <Card>
          <Text style={[typography.title, { color: colors.warn }]}>Chưa đọc được sổ</Text>
          <Text style={[typography.caption, { color: colors.inkSoft }]}>{loi}</Text>
        </Card>
      </RudiScreen>
    );
  }
  if (du === null) {
    return (
      <RudiScreen tone="split" testID="settlement-screen">
        <TopBar title="Quyết toán chuyến đi" />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc sổ…</Text>
      </RudiScreen>
    );
  }
  return (
    <RudiScreen tone="split" testID="settlement-screen">
      <TopBar title="Quyết toán chuyến đi" />
      <Card style={styles.settlementHero} tone="split">
        <View style={[styles.balanceIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name="wallet" size={26} />
        </View>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Tổng chi tiêu ({du.nguoi.length} người)
        </Text>
        <Text style={[styles.bigMoney, { color: colors.ink }]}>
          {du.tongChuyen === null ? "Chưa có số" : formatVnd(du.tongChuyen)}
        </Text>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          {du.tongChuyen === null
            ? "Máy chủ chưa có tổng cho nhóm này. Chuyến chưa kết thúc thì chưa vào recap, và chưa có số không phải là 0đ."
            : "Số này máy chủ tính lại từ sổ mỗi lần hỏi."}
        </Text>
      </Card>
      <SectionHeader title="Các khoản chuyển" />
      <View style={styles.transferList}>
        {du.chuyenTien.map((row) => (
          <Card key={`${row.fromId}-${row.toId}`} style={styles.transfer}>
            <View style={styles.flex}>
              <Text style={[typography.label, { color: colors.ink }]}>
                {tenCua(du.nguoi, row.fromId)} → {tenCua(du.nguoi, row.toId)}
              </Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>Đề xuất, chưa phải nghĩa vụ</Text>
            </View>
            <Text style={[typography.money, { color: colors.split }]}>{formatVnd(row.amountVnd)}</Text>
          </Card>
        ))}
      </View>
      <Card style={styles.safetyNote}>
        <Ionicons color={colors.warn} name="shield-checkmark-outline" size={21} />
        <Text style={[typography.caption, styles.flex, { color: colors.inkSoft }]}>
          {du.toiThieu
            ? "Máy chủ chứng minh đây là danh sách chuyển ngắn nhất."
            : "Danh sách này chưa được chứng minh là ngắn nhất."}{" "}
          Nghĩa vụ chỉ tồn tại sau khi một đợt thu được publish.
        </Text>
      </Card>
    </RudiScreen>
  );
}

function QuyetToanNhap() {
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const picture = session.money;
  const collector = PEOPLE[COLLECTOR_INDEX];
  const paidCount = session.paidFromIndexes.length;
  const pendingCount = picture.transfers.filter((row) => !session.paidFromIndexes.includes(row.fromIndex)).length;
  const paidSum = picture.transfers
    .filter((row) => session.paidFromIndexes.includes(row.fromIndex))
    .reduce((sum, row) => sum + row.amount, 0);

  return (
    <RudiScreen tone="split" testID="settlement-screen">
      <TopBar title="Quyết toán chuyến đi" right={<DemoBadge />} />
      <Card style={styles.settlementHero} tone="split">
        <View style={[styles.balanceIcon, { backgroundColor: colors.split }]}>
          <Ionicons color={colors.splitInk} name="wallet" size={26} />
        </View>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Tổng chi tiêu cả chuyến (8 người)</Text>
        <Text style={[styles.bigMoney, { color: colors.ink }]}>{formatVnd(picture.tripTotal)}</Text>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          Gồm bill Xóm Lèo {formatVnd(picture.billTotal)} và phần còn lại {formatVnd(picture.otherTotal)} (homestay + xăng).
        </Text>
        <Text style={[typography.caption, { color: colors.warn }]}>
          Số dưới là nháp trên máy, chưa confirm vào sổ cái.
        </Text>
        <View style={styles.settlementStats}>
          <View style={styles.settlementStat}>
            <Text style={[typography.title, { color: colors.ink }]}>{String(paidCount)}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>đã trả</Text>
          </View>
          <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
          <View style={styles.settlementStat}>
            <Text style={[typography.title, { color: colors.warn }]}>{String(pendingCount)}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>đang chờ</Text>
          </View>
          <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
          <View style={styles.settlementStat}>
            <Text style={[typography.title, { color: colors.split }]}>{String(PEOPLE.length)}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>thành viên</Text>
          </View>
        </View>
      </Card>
      <Card style={styles.receiveCard}>
        <View style={styles.receiveTop}>
          <Avatar person={collector} size={49} />
          <View style={styles.flex}>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{collector.name} sẽ nhận (bill Xóm Lèo)</Text>
            <Text style={[typography.money, { color: colors.split }]}>{formatVnd(picture.collectorReceives)}</Text>
          </View>
          <Chip icon="shield-checkmark-outline" label="Người thu bill" selected tone="split" />
        </View>
        <ProgressBar
          tone="split"
          value={picture.collectorReceives === 0 ? 0 : (paidSum * 100) / picture.collectorReceives}
        />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Đã nhận {formatVnd(paidSum)} · còn {formatVnd(picture.collectorReceives - paidSum)}
        </Text>
      </Card>
      <SectionHeader title="Các khoản chuyển (chỉ bill Xóm Lèo)" />
      <View style={styles.transferList}>
        {picture.transfers.map((item) => {
          const person = PEOPLE[item.fromIndex];
          const paid = session.paidFromIndexes.includes(item.fromIndex);
          return (
            <Card key={person.id} style={styles.transfer}>
              <Avatar person={person} size={44} />
              <View style={styles.flex}>
                <Text style={[typography.label, { color: colors.ink }]}>{person.name} → {collector.name}</Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>
                  {paid ? "Đã xác nhận trong ứng dụng" : "Chờ người nhận xác nhận"}
                </Text>
              </View>
              <View style={styles.transferRight}>
                <Text style={[typography.label, { color: colors.ink }]}>{formatVnd(item.amount)}</Text>
                <Pressable
                  onPress={() => session.markPaid(item.fromIndex)}
                  style={[styles.status, { backgroundColor: paid ? colors.splitSoft : colors.accentSoft }]}
                >
                  <Ionicons color={paid ? colors.split : colors.warn} name={paid ? "checkmark-circle" : "time"} size={13} />
                  <Text style={[styles.statusText, { color: paid ? colors.split : colors.warn }]}>
                    {paid ? "Đã trả" : "Đánh dấu đã trả"}
                  </Text>
                </Pressable>
              </View>
            </Card>
          );
        })}
      </View>
      <Card style={styles.safetyNote}>
        <Ionicons color={colors.warn} name="shield-checkmark-outline" size={21} />
        <Text style={[typography.caption, styles.flex, { color: colors.inkSoft }]}>
          “Đã trả” là xác nhận trong Rủ Đi, không phải bằng chứng ngân hàng. VietQR theo từng người nhận, chưa phát trên bản nháp này.
        </Text>
      </Card>
      <RudiButton
        icon="notifications-outline"
        label={
          session.remindedPending
            ? `Đã nhắc ${pendingCount} người ${noiLuuNgan(session.luuTruSong)}`
            : `Nhắc ${pendingCount} người đang chờ`
        }
        onPress={() => session.remindPending()}
        tone="split"
      />
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
