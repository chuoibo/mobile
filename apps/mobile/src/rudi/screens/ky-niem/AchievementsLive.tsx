/**
 * Thành tích on a real session (M6). There is no achievements route: every
 * badge, level and weekly challenge here is App B's `thanh-tich.ts` over
 * `GET /people/{id}/finance`, so each one is explainable from the ledger and
 * nothing is awarded on the phone's say-so. A badge the ledger cannot decide
 * yet says "chưa đo được" rather than pretending to be locked.
 */
import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import type { Phien } from "../../../phien";
import { FinanceError } from "../../../screens/ca-nhan/tai-chinh";
import { phanSo, tiLe } from "../../../screens/thanh-tich/thanh-tich";
import { demHuyHieuMo, docThanhTich, type HuyHieu, type ThanhTich } from "../../ky-niem/ky-niem";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, ListRow, RudiButton, RudiScreen, SectionHeader, TopBar, type IconName } from "../../ui";

type Trang = { pha: "dang-doc" } | { pha: "xong"; tt: ThanhTich } | { pha: "hong"; loi: string };

function loiRaChu(error: unknown): string {
  if (error instanceof FinanceError) return error.message;
  if (error instanceof Error && error.message !== "") return error.message;
  return "Chưa đọc được sổ để tính thành tích.";
}

function chuTrangThai(h: HuyHieu): string {
  if (h.trangThai === "mo") return "Đã mở";
  if (h.trangThai === "chua-do-duoc") return "Chưa đo được";
  if (h.daDat !== undefined && h.can !== undefined) return `${phanSo(h.daDat, h.can)}`;
  return "Chưa đạt";
}

/** Three states, three glyphs: a badge the ledger cannot decide yet is not a locked one. */
function bieuTuongHuyHieu(h: HuyHieu): IconName {
  if (h.trangThai === "mo") return "ribbon";
  if (h.trangThai === "chua-do-duoc") return "help-circle-outline";
  return "lock-closed-outline";
}

/** The rule, plus what is missing, in a member's words (App B's `thieuGi` spoke to developers). */
function phuHuyHieu(h: HuyHieu): string {
  if (h.trangThai === "chua-do-duoc") return `${h.dieuKien} · Sổ chưa ghi mục này theo từng người, nên chưa đo được.`;
  if (h.thieuGi !== undefined && h.thieuGi !== "") return `${h.dieuKien} · ${h.thieuGi}`;
  return h.dieuKien;
}

export function AchievementsLiveScreen({ phien }: { phien: Phien }) {
  const { colors, radius } = useRudiTheme();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });

  const doc = async () => {
    try {
      setTrang({ pha: "xong", tt: await docThanhTich(phien.person_id) });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  };
  useEffect(() => {
    let song = true;
    void docThanhTich(phien.person_id)
      .then((tt) => {
        if (song) setTrang({ pha: "xong", tt });
      })
      .catch((error: unknown) => {
        if (song) setTrang({ pha: "hong", loi: loiRaChu(error) });
      });
    return () => {
      song = false;
    };
  }, [phien.person_id]);

  if (trang.pha === "dang-doc") {
    return (
      <RudiScreen testID="achievements-screen">
        <TopBar title="Thành tích" />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc sổ để tính thành tích…</Text>
      </RudiScreen>
    );
  }
  if (trang.pha === "hong") {
    return (
      <RudiScreen testID="achievements-screen">
        <TopBar title="Thành tích" />
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void doc()} variant="outline" />
        </Card>
      </RudiScreen>
    );
  }
  const { tienDo, huyHieu, thuThach, so } = trang.tt;
  const phanTram = Math.round(tiLe(tienDo.diemTrongCap, tienDo.diemMoiCap) * 100);
  return (
    <RudiScreen testID="achievements-screen">
      <TopBar title="Thành tích" />
      <Card style={styles.hero} tone="accent">
        <Text style={[styles.cap, { color: colors.ink }]}>Cấp {tienDo.cap}</Text>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          {tienDo.diemTrongCap}/{tienDo.diemMoiCap} điểm tới cấp {tienDo.cap + 1} · tính từ {so.expense_count} khoản chi, {so.group_count} nhóm trong sổ của bạn
        </Text>
        <View accessibilityLabel={`Tiến độ ${phanTram} phần trăm tới cấp sau`} style={[styles.thanh, { backgroundColor: colors.line, borderRadius: radius.pill }]}>
          <View style={[styles.thanhDay, { backgroundColor: colors.accent, borderRadius: radius.pill, width: `${phanTram}%` }]} />
        </View>
      </Card>

      <SectionHeader title="Huy hiệu" />
      <Card style={styles.danhSach}>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>{demHuyHieuMo(huyHieu)} · mỗi huy hiệu là một luật đọc từ sổ</Text>
        {huyHieu.map((h) => (
          <ListRow
            icon={bieuTuongHuyHieu(h)}
            key={h.id}
            subtitle={phuHuyHieu(h)}
            title={h.ten}
            trailing={<Text style={[typography.label, { color: h.trangThai === "mo" ? colors.accent : colors.inkSoft }]}>{chuTrangThai(h)}</Text>}
          />
        ))}
      </Card>

      <SectionHeader title="Thử thách tuần này" />
      {thuThach.length === 0 ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Tuần này chưa có thử thách nào đo được từ sổ.</Text> : null}
      {thuThach.map((t) => (
        <Card key={t.id} style={styles.hang}>
          <Ionicons color={t.xong ? colors.accent : colors.inkFaint} name={t.xong ? "checkmark-circle" : "ellipse-outline"} size={24} />
          <View style={styles.flex}>
            <Text style={[typography.label, { color: colors.ink }]}>{t.ten}</Text>
            <Text style={[typography.caption, { color: colors.inkSoft }]}>{phanSo(t.daDat, t.can)}{t.xong ? " · xong" : ""}</Text>
          </View>
        </Card>
      ))}
      <Text style={[typography.caption, { color: colors.inkFaint }]}>Thành tích tính lại mỗi lần mở, từ đúng những gì có trong sổ. Không có điểm thưởng nào cấp ngoài sổ.</Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  hero: { gap: 6 },
  cap: { fontSize: 32, lineHeight: 38, fontWeight: "900", letterSpacing: -0.8 },
  thanh: { height: 10, overflow: "hidden", marginTop: 6 },
  thanhDay: { height: 10 },
  hang: { flexDirection: "row", alignItems: "center", gap: 12 },
  danhSach: { gap: 2, paddingVertical: 8 },
});
