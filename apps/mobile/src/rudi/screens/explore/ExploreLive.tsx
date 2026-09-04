/**
 * Khám phá on a real session (M4): the server's catalogue, its categories,
 * saved places that live on the server, and a natural-language search that
 * Rủ Đi AI ranks. Typing filters by name at once; submitting asks the model.
 *
 * No photographs travel on the wire (the catalogue has none), so a place is
 * a typographic tile: category glyph, name, kinds, then the numbers the
 * server actually measured.
 */
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import type { Phien } from "../../../phien";
import {
  formatDistance,
  formatPriceBand,
  formatRating,
  matchLabel,
  type Category,
  type Place,
} from "../../../screens/kham-pha/places";
import { askSearch, hieuDuocGi, type TimKiemState } from "../../../screens/kham-pha/tim-kiem";
import {
  bieuTuongLoai,
  boLuuDiaDiem,
  cauMoCua,
  cauTimKiem,
  daoLuu,
  docDaLuu,
  docDanhMuc,
  dongPhu,
  locTheoTen,
  luuDiaDiem,
} from "../../kham-pha/dia-diem";
import { typography, useRudiTheme } from "../../theme";
import {
  Card,
  Chip,
  Heading,
  IconButton,
  Inline,
  Logo,
  RudiButton,
  RudiScreen,
  SearchField,
  SectionHeader,
} from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; places: Place[]; categories: Category[] }
  | { pha: "hong"; loi: string };

const CAU_MAU = "quán nướng cho 6 người, 200k mỗi người";

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

/** Tapping the selected category clears the filter; tapping another selects it. */
function loaiSauBam(dangChon: boolean, id: string): string | null {
  if (dangChon) return null;
  return id;
}

function tenNhom(phien: Phien): string {
  const nhom = phien.contexts?.find((n) => n.id === phien.context_id);
  if (nhom === undefined) return "nhóm của bạn";
  return nhom.display_name;
}

export function ExploreLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [daLuu, setDaLuu] = useState<string[]>([]);
  const [loiLuu, setLoiLuu] = useState<string | null>(null);
  const [loai, setLoai] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [timKiem, setTimKiem] = useState<TimKiemState>({ kind: "chua-tim" });

  const nap = useCallback(async () => {
    try {
      const [danhMuc, luu] = await Promise.all([docDanhMuc(), docDaLuu(phien.person_id)]);
      setTrang({ pha: "xong", places: danhMuc.places, categories: danhMuc.categories });
      setDaLuu(luu);
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [phien.person_id]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  const doiLuu = async (place: Place) => {
    const truoc = daLuu;
    setDaLuu(daoLuu(daLuu, place.id));
    setLoiLuu(null);
    try {
      if (truoc.includes(place.id)) await boLuuDiaDiem(phien.person_id, place.id);
      else await luuDiaDiem(phien.person_id, place.id);
    } catch (error) {
      setDaLuu(truoc);
      setLoiLuu(loiRaChu(error));
    }
  };

  const hoi = async () => {
    const cau = query.trim();
    if (!cau) return;
    setTimKiem({ kind: "dang-tim", query: cau });
    setTimKiem(await askSearch(cau, { actorId: phien.person_id }));
  };

  const boTim = () => {
    setTimKiem({ kind: "chua-tim" });
    setQuery("");
    setLoai(null);
  };

  const danhSach = useMemo(() => {
    if (trang.pha !== "xong") return [];
    if (timKiem.kind === "co-ket-qua") return timKiem.places;
    const theoLoai = loai === null ? trang.places : trang.places.filter((p) => p.category === loai);
    return locTheoTen(theoLoai, query);
  }, [trang, timKiem, loai, query]);

  const dangLoc = loai !== null || query.trim().length > 0 || timKiem.kind === "co-ket-qua";
  const cauLoi = cauTimKiem(timKiem);

  return (
    <RudiScreen bottomInset={112} testID="explore-screen">
      <View style={styles.dau}>
        <View>
          <Logo compact />
          <Inline gap={4} style={styles.viTri}>
            <Ionicons color={colors.accent} name="location" size={14} />
            <Text style={[typography.caption, { color: colors.inkSoft }]}>Đà Lạt · danh mục Rủ Đi</Text>
          </Inline>
        </View>
      </View>
      <SearchField
        accessibilityLabel="Ô tìm địa điểm"
        onChangeText={(t) => {
          setQuery(t);
          if (timKiem.kind !== "chua-tim") setTimKiem({ kind: "chua-tim" });
        }}
        onSubmitEditing={() => void hoi()}
        placeholder="Tìm tên quán, hoặc gõ một câu cho Rủ Đi AI"
        value={query}
      />
      <Card onPress={() => setQuery(CAU_MAU)} style={styles.theAi} tone="ai">
        <View style={styles.theAiIcon}>
          <Ionicons color={colors.ai} name="sparkles" size={22} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.title, { color: colors.ink }]}>Hỏi Rủ Đi AI theo gu {tenNhom(phien)}</Text>
          <Text style={[typography.caption, { color: colors.inkSoft }]}>
            Gõ một câu như «{CAU_MAU}» rồi bấm tìm. Rủ Đi xếp hạng theo ngân sách, số người và khoảng cách.
          </Text>
        </View>
      </Card>
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc danh mục từ máy chủ...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" ? (
        <>
          <View style={styles.luoiLoai}>
            {trang.categories.map((c) => {
              const chon = loai === c.id;
              return (
                <Pressable
                  accessibilityRole="button"
                  aria-pressed={chon}
                  key={c.id}
                  onPress={() => setLoai(loaiSauBam(chon, c.id))}
                  style={({ pressed }) => [
                    styles.oLoai,
                    {
                      backgroundColor: chon ? colors.accentSoft : colors.card,
                      borderColor: chon ? colors.accent : colors.line,
                    },
                    pressed && styles.bam,
                  ]}
                >
                  <View style={[styles.oLoaiIcon, { backgroundColor: chon ? colors.card : colors.accentSoft }]}>
                    <Ionicons color={colors.accent} name={bieuTuongLoai(c.id)} size={22} />
                  </View>
                  <Text numberOfLines={2} style={[typography.caption, styles.nhanLoai, { color: chon ? colors.accent : colors.ink }]}>
                    {c.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {timKiem.kind === "dang-tim" ? (
            <Card tone="ai">
              <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI</Text>
              <Text style={[typography.body, { color: colors.ink }]}>Đang đọc câu «{timKiem.query}»...</Text>
            </Card>
          ) : null}
          {cauLoi !== null ? (
            <Card tone="ai">
              <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI</Text>
              <Text style={[typography.body, { color: colors.ink }]}>{cauLoi}</Text>
            </Card>
          ) : null}
          {timKiem.kind === "co-ket-qua" ? (
            <Card tone="ai">
              <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI hiểu câu «{timKiem.query}»</Text>
              {hieuDuocGi(timKiem.understood, trang.categories).map((d) => (
                <Text key={d.label} style={[typography.body, { color: colors.ink }]}>
                  {d.label}: {d.value}
                </Text>
              ))}
              {hieuDuocGi(timKiem.understood, trang.categories).length === 0 ? (
                <Text style={[typography.body, { color: colors.ink }]}>Chưa rút được ngân sách, số người hay khu vực; xếp theo gu chung.</Text>
              ) : null}
            </Card>
          ) : null}
          {loiLuu !== null ? <Text style={[typography.caption, { color: colors.warn }]}>{loiLuu}</Text> : null}
          <SectionHeader
            action={dangLoc ? "Xóa lọc" : undefined}
            onAction={dangLoc ? boTim : undefined}
            title={dangLoc ? `${danhSach.length} kết quả` : `${trang.places.length} nơi ở Đà Lạt`}
          />
          {danhSach.length === 0 ? (
            <Card style={styles.rong}>
              <Heading align="center" size="h2" title="Chưa thấy nơi phù hợp" subtitle="Thử từ khóa khác hoặc xóa bớt bộ lọc nhé." />
              <RudiButton label="Xóa lọc" onPress={boTim} variant="outline" />
            </Card>
          ) : (
            danhSach.map((place) => (
              <TheDiaDiem
                daLuu={daLuu.includes(place.id)}
                key={place.id}
                onLuu={() => void doiLuu(place)}
                onMo={() => router.push(`/places/${place.id}` as never)}
                place={place}
              />
            ))
          )}
        </>
      ) : null}
    </RudiScreen>
  );
}

function TheDiaDiem({
  place,
  daLuu,
  onLuu,
  onMo,
}: {
  place: Place;
  daLuu: boolean;
  onLuu: () => void;
  onMo: () => void;
}) {
  const { colors } = useRudiTheme();
  const hop = matchLabel(place.match);
  return (
    <Card accessibilityLabel={`Mở ${place.name}`} onPress={onMo} style={styles.the}>
      <View style={[styles.theIcon, { backgroundColor: colors.accentSoft }]}>
        <Ionicons color={colors.accent} name={bieuTuongLoai(place.category)} size={24} />
      </View>
      <View style={styles.theChu}>
        <Text numberOfLines={1} style={[typography.title, { color: colors.ink }]}>
          {place.name}
        </Text>
        <Text numberOfLines={1} style={[typography.caption, { color: colors.inkSoft }]}>
          {dongPhu(place)}
        </Text>
        <Inline gap={10} wrap>
          <Inline gap={4}>
            <Ionicons color={colors.accent} name="star" size={13} />
            <Text style={[typography.caption, { color: colors.ink }]}>{formatRating(place.rating, place.ratingCount)}</Text>
          </Inline>
          <Inline gap={4}>
            <Ionicons color={colors.inkFaint} name="navigate-outline" size={13} />
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{formatDistance(place.distanceKm)}</Text>
          </Inline>
          <Inline gap={4}>
            <Ionicons color={colors.inkFaint} name="wallet-outline" size={13} />
            {/* Price and status in ONE text node: a separate text item in a
                wrapping row keeps its first-row (one-word) measurement and
                rendered «Đang» alone. */}
            <Text style={[typography.caption, { color: colors.inkFaint }]}>
              {formatPriceBand(place.priceMinVnd, place.priceMaxVnd)} ·{" "}
              <Text style={{ color: place.openNow ? colors.accent : colors.split }}>{place.openNow ? "Đang mở" : "Đã đóng"}</Text>
            </Text>
          </Inline>
        </Inline>
        {hop !== null && hop.real ? (
          <View style={styles.huyHieu}>
            <Chip icon="sparkles-outline" label={hop.text} selected tone="ai" />
          </View>
        ) : null}
      </View>
      <IconButton
        accessibilityLabel={daLuu ? `Bỏ lưu ${place.name}` : `Lưu ${place.name}`}
        icon={daLuu ? "heart" : "heart-outline"}
        onPress={onLuu}
        quiet
        selected={daLuu}
      />
    </Card>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  dau: { minHeight: 55, flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 10 },
  viTri: { marginLeft: 49, marginTop: -8 },
  theAi: { flexDirection: "row", alignItems: "center", gap: 12, padding: 14 },
  theAiIcon: { width: 44, height: 44, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  luoiLoai: { flexDirection: "row", gap: 9 },
  // Glyphs share one baseline whatever the label does: the label slot is always
  // two caption lines tall, so «Quán ăn local» wrapping does not lift its tile.
  oLoai: { flex: 1, minWidth: 70, borderRadius: 17, borderWidth: 1, alignItems: "center", justifyContent: "flex-start", gap: 8, paddingHorizontal: 6, paddingTop: 10, paddingBottom: 8 },
  nhanLoai: { textAlign: "center", minHeight: 32 },
  huyHieu: { flexDirection: "row" },
  oLoaiIcon: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  giua: { textAlign: "center" },
  bam: { opacity: 0.72, transform: [{ scale: 0.98 }] },
  rong: { alignItems: "center", gap: 14, paddingVertical: 24 },
  the: { flexDirection: "row", alignItems: "flex-start", gap: 12, padding: 12 },
  theIcon: { width: 48, height: 48, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  theChu: { flex: 1, gap: 6 },
});
