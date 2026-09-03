/**
 * Chi tiết địa điểm on a real session (M4): everything the server knows about
 * one catalogue place, said in its own words. No gallery (no images on the
 * wire), a match card only when the model actually scored this place for the
 * group, directions through the phone's map app, and a save that lives on
 * the server. «Thêm vào kèo» picks one of the group's outings.
 */
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import type { Phien } from "../../../phien";
import type { PlaceDetail } from "../../../screens/kham-pha/chi-tiet-dia-diem";
import {
  formatDistance,
  formatPriceBand,
  formatRating,
  matchLabel,
} from "../../../screens/kham-pha/places";
import {
  bieuTuongLoai,
  boLuuDiaDiem,
  cauMoCua,
  daoLuu,
  docChiTiet,
  docDaLuu,
  dongPhu,
  duongChiDuong,
  luuDiaDiem,
} from "../../kham-pha/dia-diem";
import { typography, useRudiTheme } from "../../theme";
import { AiNote, Card, Chip, Heading, Inline, ListRow, RudiButton, RudiScreen, SectionHeader, TopBar } from "../../ui";

type Trang = { pha: "dang-doc" } | { pha: "xong"; place: PlaceDetail } | { pha: "hong"; loi: string };

/** A route param is a string or nothing; an array or undefined is nothing. */
function thamSoChuoi(v: unknown): string {
  if (typeof v === "string") return v;
  return "";
}

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function PlaceDetailLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const { colors } = useRudiTheme();
  // The pinned footer must clear the gesture bar (the shell pads top/left/right only).
  const { bottom: menDuoi } = useSafeAreaInsets();
  const placeId = thamSoChuoi(params.id);
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [daLuu, setDaLuu] = useState<string[]>([]);
  const [dangLuu, setDangLuu] = useState(false);
  const [thongBao, setThongBao] = useState<string | null>(null);

  const nap = useCallback(async () => {
    if (!placeId) {
      setTrang({ pha: "hong", loi: "Thiếu địa điểm để mở." });
      return;
    }
    try {
      const [place, luu] = await Promise.all([docChiTiet(placeId), docDaLuu(phien.person_id)]);
      setTrang({ pha: "xong", place });
      setDaLuu(luu);
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [placeId, phien.person_id]);

  useEffect(() => {
    void nap();
  }, [nap]);

  const doiLuu = async (id: string) => {
    const truoc = daLuu;
    setDangLuu(true);
    setDaLuu(daoLuu(daLuu, id));
    setThongBao(null);
    try {
      if (truoc.includes(id)) await boLuuDiaDiem(phien.person_id, id);
      else await luuDiaDiem(phien.person_id, id);
    } catch (error) {
      setDaLuu(truoc);
      setThongBao(loiRaChu(error));
    } finally {
      setDangLuu(false);
    }
  };

  const chiDuong = async (place: PlaceDetail) => {
    try {
      await Linking.openURL(duongChiDuong(place));
    } catch {
      setThongBao("Máy này chưa có ứng dụng bản đồ để chỉ đường.");
    }
  };

  const daLuuChoNay = trang.pha === "xong" && daLuu.includes(trang.place.id);
  return (
    <RudiScreen
      footer={
        trang.pha === "xong" ? (
          <View style={styles.hanhDong}>
            <View style={styles.flex}>
              <RudiButton icon="navigate-outline" label="Chỉ đường" onPress={() => void chiDuong(trang.place)} variant="outline" />
            </View>
            <View style={styles.flex}>
              <RudiButton
                icon={daLuuChoNay ? "heart" : "heart-outline"}
                label={daLuuChoNay ? "Đã lưu" : "Lưu địa điểm"}
                loading={dangLuu}
                onPress={() => void doiLuu(trang.place.id)}
                variant={daLuuChoNay ? "soft" : "solid"}
              />
            </View>
          </View>
        ) : null
      }
      bottomInset={110}
      footerInset={14 + menDuoi}
      testID="place-detail-screen"
    >
      <TopBar title="Địa điểm" />
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc từ máy chủ...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Về Khám phá" onPress={() => router.back()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" ? <ThanChiTiet
        onChiDuong={() => void chiDuong(trang.place)}
        onThemVaoKeo={() => router.push(`/outings/chon?place=${encodeURIComponent(trang.place.id)}` as never)}
        place={trang.place}
        thongBao={thongBao}
      /> : null}
    </RudiScreen>
  );
}

function ThanChiTiet({
  place,
  thongBao,
  onChiDuong,
  onThemVaoKeo,
}: {
  place: PlaceDetail;
  thongBao: string | null;
  onChiDuong: () => void;
  onThemVaoKeo: () => void;
}) {
  const { colors, radius } = useRudiTheme();
  const hop = matchLabel(place.match);
  const coMatch = place.match !== null && place.match.source === "ai";
  return (
    <>
      {/* The screen's one hero moment: a full-width band in the leading tone,
          glyph at focal size, then the facts as one line of text. */}
      <View style={[styles.hero, { backgroundColor: colors.accentSoft, borderRadius: radius.base }]}>
        <View style={[styles.heroIcon, { backgroundColor: colors.card }]}>
          <Ionicons color={colors.accent} name={bieuTuongLoai(place.category)} size={40} />
        </View>
        <Heading title={place.name} subtitle={dongPhu(place)} />
        <Inline gap={6} wrap>
          <Ionicons color={colors.accent} name="star" size={14} />
          <Text style={[typography.label, { color: colors.ink }]}>{formatRating(place.rating, place.ratingCount)}</Text>
          <Text style={[typography.caption, { color: colors.inkSoft }]}>· {formatDistance(place.distanceKm)} ·</Text>
          <Text style={[typography.caption, styles.trangThai, { color: place.openNow ? colors.accent : colors.split }]}>
            {place.openNow ? "Đang mở" : "Đã đóng"}
          </Text>
        </Inline>
        {hop !== null && hop.real ? (
          <View style={styles.huyHieu}>
            <Chip icon="sparkles-outline" label={hop.text} selected tone="ai" />
          </View>
        ) : null}
      </View>
      <RudiButton icon="add-circle-outline" label="Thêm vào kèo" onPress={onThemVaoKeo} variant="soft" />
      {place.description ? <Text style={[typography.body, { color: colors.ink }]}>{place.description}</Text> : null}
      <Card style={styles.suKien}>
        <ListRow icon="navigate-outline" onPress={onChiDuong} subtitle={`${formatDistance(place.distanceKm)} · ${place.travelMinutes} phút đi xe`} title={place.address} />
        <ListRow icon="time-outline" title={cauMoCua(place)} subtitle="Giờ mở cửa theo danh mục" />
        <ListRow icon="wallet-outline" title={`${formatPriceBand(place.priceMinVnd, place.priceMaxVnd)} một người`} subtitle="Khoảng giá theo danh mục" />
      </Card>
      {place.traits.length > 0 ? (
        <Inline gap={8} wrap>
          {place.traits.map((t) => (
            <Chip key={t} label={t} />
          ))}
        </Inline>
      ) : null}
      <View>
        <SectionHeader title="Vì sao hợp nhóm?" />
        {coMatch && place.match !== null ? (
          <Card tone="ai" style={styles.khoi}>
            <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI chấm cho nhóm bạn</Text>
            <AiNote>{place.match.reason}</AiNote>
            {place.match.factors.map((f) => (
              <Text key={f.label} style={[typography.caption, { color: colors.inkSoft }]}>
                {f.label}: {f.detail}
              </Text>
            ))}
          </Card>
        ) : (
          <Text style={[typography.caption, { color: colors.inkSoft }]}>
            Chưa có điểm theo gu nhóm cho nơi này. Ở Khám phá, gõ một câu cho Rủ Đi AI để nó chấm.
          </Text>
        )}
      </View>
      {place.reviews.length > 0 ? (
        <View>
          <SectionHeader title={`${place.reviews.length} nhận xét`} />
          <Card style={styles.khoi}>
            {place.reviews.map((r, i) => (
              <View key={`${r.author}-${i}`} style={styles.nhanXet}>
                <Text style={[typography.label, { color: colors.ink }]}>
                  {r.author} · {r.rating}/5
                </Text>
                <Text style={[typography.caption, { color: colors.inkSoft }]}>{r.body}</Text>
              </View>
            ))}
          </Card>
        </View>
      ) : null}
      {thongBao !== null ? <Text style={[typography.caption, { color: colors.warn }]}>{thongBao}</Text> : null}
    </>
  );
}

const styles = StyleSheet.create({
  hero: { gap: 12, padding: 18 },
  heroIcon: { width: 80, height: 80, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  huyHieu: { flexDirection: "row" },
  trangThai: { flexShrink: 0 },
  suKien: { paddingVertical: 5 },
  khoi: { gap: 8 },
  nhanXet: { gap: 2, paddingVertical: 6 },
  flex: { flex: 1 },
  hanhDong: { flexDirection: "row", gap: 10 },
});
