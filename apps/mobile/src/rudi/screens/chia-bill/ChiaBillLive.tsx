/**
 * Chia hóa đơn on a real session (M5): one route, five steps.
 *
 *   bắt đầu → xem lại (lines from the photo or typed) → gán món (the group
 *   picks who had what; the server holds the bill and the assignment) →
 *   kết quả (the server's split) → đã ghi (the expense is in the ledger,
 *   settlement reads it).
 *
 * Nothing here computes a share. The server splits; this screen draws.
 */
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, attemptFor, thongDiepNguoiDoc, type Attempt, type ChiaBill } from "../../../api";
import {
  blockingProblem as loiGanMon,
  everyoneShares,
  isOn,
  signature,
  toggle,
  type Assignment,
} from "../../../assignment";
import type { BillWire } from "../../../bill";
import type { Phien } from "../../../phien";
import {
  blockingProblem as loiHoaDon,
  disclosure,
  removeLine,
  renameLine,
  setLineTotal,
  setQuantity,
  type BillReading,
} from "../../../receipt";
import { danhSachThanhVien } from "../../../screens/vao-cua/cong-api";
import {
  cauSauKhiScanHong,
  cauTongMon,
  chiaTrenMayChu,
  docBillTuAnh,
  ghiVaoSo,
  hangKetQua,
  hoaDonTrong,
  luuGanMonTrenMayChu,
  taoBillTrenMayChu,
  tenCua,
  themMon,
  type ThanhVien,
} from "../../chia-bill/hoa-don";
import { typography, useRudiTheme } from "../../theme";
import { AiNote, Card, Chip, Field, Heading, Inline, RudiButton, RudiScreen, SectionHeader, TopBar } from "../../ui";

type Buoc =
  | { ten: "bat-dau" }
  | { ten: "xem-lai" }
  | { ten: "gan-mon"; bill: BillWire }
  | { ten: "ket-qua"; bill: BillWire; chia: ChiaBill }
  | { ten: "da-ghi"; expenseVersionId: string };

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

/** A member's display name, or the plain word when the server has none. */
function tenHienThi(ten: string | null | undefined): string {
  if (typeof ten === "string" && ten.trim() !== "") return ten;
  return "Thành viên";
}

export function ChiaBillLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const contextId = phien.context_id;
  const [buoc, setBuoc] = useState<Buoc>({ ten: "bat-dau" });
  const [reading, setReading] = useState<BillReading>(hoaDonTrong());
  const [assignment, setAssignment] = useState<Assignment>({});
  const [roster, setRoster] = useState<ThanhVien[]>([]);
  const [payerId, setPayerId] = useState(phien.person_id);
  const [occasion, setOccasion] = useState("");
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [ban, setBan] = useState(false);
  const attempts = useRef<Record<string, Attempt>>({});

  useEffect(() => {
    if (contextId === null) return;
    let song = true;
    void danhSachThanhVien(contextId, phien.person_id)
      .then((ds) => {
        if (!song) return;
        setRoster(ds.map((tv) => ({ id: tv.person_id, name: tenHienThi(tv.display_name) })));
      })
      .catch((error: unknown) => {
        if (song) setThongBao(loiRaChu(error));
      });
    return () => {
      song = false;
    };
  }, [contextId, phien.person_id]);

  if (contextId === null) {
    return (
      <RudiScreen tone="split" testID="receipt-review-screen">
        <TopBar title="Chia hóa đơn" />
        <Heading title="Vào một nhóm trước" subtitle="Hóa đơn là của nhóm; chưa có nhóm thì chưa có ai để chia." />
        <RudiButton label="Tới Tin nhắn" onPress={() => router.push("/(tabs)/messages" as never)} variant="outline" />
      </RudiScreen>
    );
  }
  const ctx = contextId;
  const rosterIds = roster.map((tv) => tv.id);

  const chay = async (viec: () => Promise<void>) => {
    setBan(true);
    setThongBao(null);
    try {
      await viec();
    } catch (error) {
      setThongBao(loiRaChu(error));
    } finally {
      setBan(false);
    }
  };

  const chonAnh = () =>
    chay(async () => {
      const picked = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.8 });
      if (picked.canceled || !picked.assets[0]) {
        setThongBao("Không chọn ảnh.");
        return;
      }
      const anh = picked.assets[0];
      try {
        setReading(await docBillTuAnh({ uri: anh.uri, bytes: anh.fileSize === undefined ? 0 : anh.fileSize }, phien.person_id));
        setBuoc({ ten: "xem-lai" });
      } catch (error) {
        setThongBao(cauSauKhiScanHong(loiRaChu(error)));
      }
    });

  const nhapTay = () => {
    setReading(themMon(hoaDonTrong()));
    setBuoc({ ten: "xem-lai" });
  };

  const sangGanMon = () =>
    chay(async () => {
      const loi = loiHoaDon(reading);
      if (loi !== null) {
        setThongBao(loi);
        return;
      }
      const a = everyoneShares(reading.lines, rosterIds);
      const bill = await taoBillTrenMayChu(reading, ctx, a, phien.person_id, attemptFor(attempts.current, `tao-bill:${signature(reading, rosterIds, a)}`));
      setAssignment(a);
      setBuoc({ ten: "gan-mon", bill });
    });

  const xemKetQua = (bill: BillWire) =>
    chay(async () => {
      const loi = loiGanMon(reading, rosterIds, assignment);
      if (loi !== null) {
        setThongBao(loi);
        return;
      }
      const sig = signature(reading, rosterIds, assignment);
      const daLuu = await luuGanMonTrenMayChu(bill.id, reading, assignment, phien.person_id, ctx, attemptFor(attempts.current, `gan-mon:${bill.id}:${sig}`));
      const chia = await chiaTrenMayChu(daLuu.id, phien.person_id, ctx, attemptFor(attempts.current, `chia:${daLuu.id}:${sig}`));
      setBuoc({ ten: "ket-qua", bill: daLuu, chia });
    });

  const ghi = () =>
    chay(async () => {
      const ten = occasion.trim() === "" ? "Hóa đơn của nhóm" : occasion.trim();
      const kq = await ghiVaoSo({ reading, assignment, roster, contextId: ctx, payerId, occasion: ten, attempts: attempts.current });
      setBuoc({ ten: "da-ghi", expenseVersionId: kq.expenseVersionId });
    });

  // One step back inside the flow; the TopBar's own back leaves the flow.
  const quayLai = () => {
    if (buoc.ten === "xem-lai") setBuoc({ ten: "bat-dau" });
    else if (buoc.ten === "gan-mon") setBuoc({ ten: "xem-lai" });
    else if (buoc.ten === "ket-qua") setBuoc({ ten: "gan-mon", bill: buoc.bill });
  };

  const tieuDe =
    buoc.ten === "bat-dau" ? "Chia hóa đơn" : buoc.ten === "xem-lai" ? "Xem lại hóa đơn" : buoc.ten === "gan-mon" ? "Ai dùng món nào?" : buoc.ten === "ket-qua" ? "Máy chủ chia" : "Đã ghi vào sổ";

  return (
    <RudiScreen tone="split" testID="receipt-review-screen">
      <TopBar title={tieuDe} />
      {thongBao !== null ? <Text style={[typography.body, { color: colors.warn }]}>{thongBao}</Text> : null}

      {buoc.ten === "bat-dau" ? (
        <>
          <Heading title="Bill hôm nay" subtitle="Chụp hoặc chọn ảnh hóa đơn để máy chủ đọc món, hoặc gõ tay. Ai dùng món nào thì hỏi ở bước sau." />
          <RudiButton disabled={ban} icon="images-outline" label="Chọn ảnh bill" loading={ban} onPress={() => void chonAnh()} tone="split" />
          <RudiButton disabled={ban} icon="create-outline" label="Nhập tay" onPress={nhapTay} tone="split" variant="outline" />
        </>
      ) : null}

      {buoc.ten === "xem-lai" ? (
        <>
          <Heading title={cauTongMon(reading)} subtitle={disclosure(reading).text} />
          {reading.warnings.map((w) => (
            <AiNote key={w}>{w}</AiNote>
          ))}
          {reading.lines.map((line, i) => (
            <Card key={line.id} style={styles.mon}>
              <Field
                accessibilityLabel={`Ô tên món ${i + 1}`}
                label="Món"
                onChangeText={(t) => setReading((r) => renameLine(r, line.id, t))}
                placeholder="Ví dụ: Bún bò"
                value={line.name}
              />
              <View style={styles.hang}>
                <View style={styles.oNho}>
                  <Field
                    accessibilityLabel={`Ô số lượng món ${i + 1}`}
                    keyboardType="number-pad"
                    label="Số lượng"
                    onChangeText={(t) => {
                      const kq = setQuantity(reading, line.id, t);
                      if (kq.ok) setReading(kq.reading);
                    }}
                    value={String(line.quantity)}
                  />
                </View>
                <View style={styles.flex}>
                  <Field
                    accessibilityLabel={`Ô tiền món ${i + 1}`}
                    keyboardType="number-pad"
                    label="Thành tiền (đồng)"
                    onChangeText={(t) => {
                      const kq = setLineTotal(reading, line.id, t);
                      if (kq.ok) setReading(kq.reading);
                    }}
                    value={line.lineTotalVnd === 0 ? "" : String(line.lineTotalVnd)}
                  />
                </View>
              </View>
              <RudiButton compact full={false} label="Bỏ món này" onPress={() => setReading((r) => removeLine(r, line.id))} variant="ghost" />
            </Card>
          ))}
          <RudiButton icon="add" label="Thêm món" onPress={() => setReading((r) => themMon(r))} variant="soft" tone="split" />
          <RudiButton disabled={ban} label="Tiếp: ai dùng món nào?" loading={ban} onPress={() => void sangGanMon()} tone="split" />
          <RudiButton label="Bước trước" onPress={quayLai} variant="ghost" />
        </>
      ) : null}

      {buoc.ten === "gan-mon" ? (
        <>
          <Heading title={cauTongMon(reading)} subtitle="Chạm tên để bật hoặc tắt một người trên từng món. Máy chủ giữ bản gán này." />
          {reading.lines.map((line) => (
            <Card key={line.id} style={styles.monGan}>
              <View style={styles.dongMon}>
                <Text style={[typography.label, styles.flex, { color: colors.ink }]}>{line.name}</Text>
                <Text style={[typography.label, { color: colors.ink }]}>{cauTongMon({ ...reading, lines: [line] }).split(" · ")[1]}</Text>
              </View>
              <Inline gap={6} wrap>
                {roster.map((tv) => (
                  <Chip
                    accessibilityLabel={`${tv.name} · ${line.name}`}
                    key={tv.id}
                    label={tv.name}
                    onPress={() => setAssignment((a) => toggle(a, line.id, tv.id))}
                    selected={isOn(assignment, line.id, tv.id)}
                    tone="split"
                  />
                ))}
              </Inline>
            </Card>
          ))}
          <RudiButton disabled={ban} label="Xem kết quả" loading={ban} onPress={() => void xemKetQua(buoc.bill)} tone="split" />
          <RudiButton label="Bước trước" onPress={quayLai} variant="ghost" />
        </>
      ) : null}

      {buoc.ten === "ket-qua" ? (
        <>
          <Heading title={cauTongMon(reading)} subtitle={buoc.chia.assignmentState === "confirmed" ? "Máy chủ chia theo bản gán đã chốt." : "Máy chủ chia theo bản gán đang gợi ý."} />
          <SectionHeader title="Mỗi người" />
          <Card style={styles.ketQua}>
            {hangKetQua(buoc.chia, roster).map((h) => (
              <View key={h.id} style={styles.dongMon}>
                <Text style={[typography.body, styles.flex, { color: colors.ink }]}>{h.ten}</Text>
                <Text style={[typography.money, { color: colors.ink }]}>{h.tien}</Text>
              </View>
            ))}
          </Card>
          {buoc.chia.roundingGainers.length > 0 ? (
            <Text style={[typography.caption, { color: colors.inkSoft }]}>
              Lẻ đồng dồn về: {buoc.chia.roundingGainers.map((id) => tenCua(roster, id)).join(", ")} (máy chủ quyết, tổng vẫn khớp).
            </Text>
          ) : null}
          {buoc.chia.warnings.map((w) => (
            <AiNote key={w}>{w}</AiNote>
          ))}
          <SectionHeader title="Ai đã trả bill?" />
          <Inline gap={6} wrap>
            {roster.map((tv) => (
              <Chip accessibilityLabel={`Người trả ${tv.name}`} key={tv.id} label={tv.name} onPress={() => setPayerId(tv.id)} selected={payerId === tv.id} tone="split" />
            ))}
          </Inline>
          <Field accessibilityLabel="Ô tên khoản chi" label="Gọi khoản này là" onChangeText={setOccasion} placeholder="Ví dụ: Tối nay Xóm Lào" value={occasion} />
          <RudiButton disabled={ban} icon="book-outline" label="Ghi vào sổ" loading={ban} onPress={() => void ghi()} tone="split" />
          <Text style={[typography.caption, { color: colors.inkSoft }]}>
            Ghi vào sổ là tạo khoản chi với đúng các số ở trên; máy chủ tự kiểm tổng khớp trước khi ghi.
          </Text>
          <RudiButton label="Bước trước" onPress={quayLai} variant="ghost" />
        </>
      ) : null}

      {buoc.ten === "da-ghi" ? (
        <>
          <Heading title="Đã ghi vào sổ" subtitle="Khoản chi đã có phiên bản trên máy chủ. Quyết toán của nhóm tính lại từ sổ." />
          <RudiButton icon="wallet-outline" label="Xem quyết toán" onPress={() => router.replace(`/settlements/${ctx}` as never)} tone="split" />
          <RudiButton label="Về Tin nhắn" onPress={() => router.replace("/(tabs)/messages" as never)} variant="outline" />
        </>
      ) : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  hang: { flexDirection: "row", gap: 10 },
  oNho: { width: 120 },
  mon: { gap: 10 },
  monGan: { gap: 10 },
  dongMon: { flexDirection: "row", alignItems: "center", gap: 10 },
  ketQua: { gap: 10 },
});
