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
  matchLabel,
  type Category,
  type Place,
} from "../../../screens/kham-pha/places";
import { askSearch, hieuDuocGi, type TimKiemState } from "../../../screens/kham-pha/tim-kiem";
import { SO_THICH } from "../../../screens/vao-cua/so-thich";
import { docDiemDenDaChon } from "../../kham-pha/diem-den";
import {
  anhBiaThe,
  bieuTuongLoai,
  boLuuDiaDiem,
  cauTimKiem,
  chiTietNgan,
  daoLuu,
  docDaLuu,
  cauChuaCo,
  cauGu,
  docDanhMucCoLui,
  dongPhu,
  type Gu,
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
import { MediaSlot } from "../../ui/MediaSlot";

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
  // Which city the list is of. The server always answers with one and says
  // which, so this starts as null and is filled from the answer -- the screen
  // never guesses a city name it has not been told.
  const [diemDen, setDiemDen] = useState<{ id: string; name: string } | null>(null);
  // Whose taste the badges are relative to. Starts as «chưa biết» because that
  // is true until the server has answered, and it is what the screen says.
  const [gu, setGu] = useState<Gu | null>(null);
  // Only words this build can name. A tag the server knows and this app does
  // not would otherwise print its storage key on screen, which is how «cafe»
  // becomes «mon-local» in front of somebody.
  const chuaCo = cauChuaCo(gu, (id) => SO_THICH.find((m) => m.id === id)?.nhan ?? "");

  const nap = useCallback(async () => {
    try {
      const daChon = await docDiemDenDaChon();
      const [danhMuc, luu] = await Promise.all([
        // A destination this phone remembers may be gone from the catalogue
        // (an import can drop one). That is a 404, and the right answer is the
        // server's default rather than an error screen about a city the person
        // chose last week; the stored choice is cleared so it stops asking.
        docDanhMucCoLui(daChon, phien.person_id),
        docDaLuu(phien.person_id),
      ]);
      setDiemDen(danhMuc.destination);
      setGu(danhMuc.gu);
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
          {/* The destination is a control, not a caption. It used to be the
              words «Đà Lạt · danh mục Rủ Đi» printed under the logo whatever
              the list actually held. */}
          <Pressable
            accessibilityLabel="Đổi điểm đến"
            accessibilityRole="button"
            onPress={() => router.push("/destinations")}
            style={styles.viTri}
          >
            <Ionicons color={colors.accent} name="location" size={14} />
            <Text style={[typography.caption, { color: colors.inkSoft }]}>
              {diemDen === null ? "Đang đọc điểm đến…" : `${diemDen.name} · đổi nơi khác`}
            </Text>
            <Ionicons color={colors.inkFaint} name="chevron-down" size={14} />
          </Pressable>
        </View>
      </View>
      <SearchField
        accessibilityLabel="Ô tìm địa điểm"
        onChangeText={(t) => {
          setQuery(t);
          if (timKiem.kind !== "chua-tim") setTimKiem({ kind: "chua-tim" });
        }}
        onSubmitEditing={() => void hoi()}
        placeholder="Tìm quán hoặc hỏi Rủ Đi AI"
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
          {/* Whose taste the badges follow (M11). The «chưa biết» sentence is a
              button, because it is the one state the person can fix. */}
          <Pressable
            accessibilityRole={gu === null || gu.co_so === "chua-biet" ? "button" : undefined}
            disabled={gu !== null && gu.co_so !== "chua-biet"}
            onPress={() => router.push("/personalization" as never)}
          >
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{cauGu(gu)}</Text>
            {chuaCo !== "" ? (
              <Text style={[typography.caption, { color: colors.inkFaint }]}>{chuaCo}</Text>
            ) : null}
          </Pressable>
          <SectionHeader
            action={dangLoc ? "Xóa lọc" : undefined}
            onAction={dangLoc ? boTim : undefined}
            // The city comes from the answer, not from a string typed here:
            // this line used to say «Đà Lạt» over a list of anywhere.
            title={
              dangLoc
                ? `${danhSach.length} kết quả`
                : `${trang.places.length} nơi ở ${diemDen === null ? "đây" : diemDen.name}`
            }
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
  // The picture replaces the glyph, and only when its credit came with it --
  // the credit is then a line in this card, so the photograph never appears
  // anywhere its author is not named (ADR-0017 §2.5).
  const bia = anhBiaThe(place);
  return (
    <Card accessibilityLabel={`Mở ${place.name}`} onPress={onMo} style={styles.the}>
      {bia === null ? (
        <View style={[styles.theIcon, { backgroundColor: colors.accentSoft }]}>
          <Ionicons color={colors.accent} name={bieuTuongLoai(place.category)} size={24} />
        </View>
      ) : (
        <MediaSlot alt={`Ảnh ${place.name}`} height={48} radius={16} source={bia.nguon} width={48} />
      )}
      <View style={styles.theChu}>
        <Text numberOfLines={1} style={[typography.title, { color: colors.ink }]}>
          {place.name}
        </Text>
        <Text numberOfLines={1} style={[typography.caption, { color: colors.inkSoft }]}>
          {dongPhu(place)}
        </Text>
        {/* Only the facts this place has (M9). Each item is ONE text node: a
            multi-word Text that shares a wrapping row with siblings keeps its
            first-row measurement and renders one word alone. */}
        <Inline gap={10} wrap>
          {chiTietNgan(place).map((muc) => (
            <Inline gap={4} key={muc.icon}>
              <Ionicons
                color={muc.icon === "star" ? colors.accent : colors.inkFaint}
                name={muc.icon}
                size={13}
              />
              <Text style={[typography.caption, { color: colors.inkFaint }]}>{muc.chu}</Text>
            </Inline>
          ))}
        </Inline>
        {hop !== null && hop.real ? (
          <View style={styles.huyHieu}>
            <Chip icon="sparkles-outline" label={hop.text} selected tone="ai" />
          </View>
        ) : null}
        {bia === null ? null : (
          <Text numberOfLines={2} style={[typography.caption, { color: colors.inkFaint }]}>
            {bia.giayPhep}
          </Text>
        )}
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
