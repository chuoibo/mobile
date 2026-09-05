/**
 * Chi tiết địa điểm on a real session (M4): everything the server knows about
 * one catalogue place, said in its own words. A match card only when the model
 * actually scored this place for the group, directions through the phone's map
 * app, and a save that lives on the server. «Thêm vào kèo» picks one of the
 * group's outings.
 *
 * M12 adds the two things the screen could not say before: licensed
 * photographs of the venue, each with its author and licence printed under it,
 * and «nên làm gì ở đây» -- sentences written when the place was imported out
 * of its own map tags. Both are absent for most places, and absent is drawn as
 * nothing at all rather than as an empty frame.
 */
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import type { Phien } from "../../../phien";
import type { PlaceDetail } from "../../../screens/kham-pha/chi-tiet-dia-diem";
import {
  matchLabel,
} from "../../../screens/kham-pha/places";
import {
  bieuTuongLoai,
  boLuuDiaDiem,
  CAU_ANH_NHOM,
  CAU_NGUON_ANH,
  cauDuongDi,
  cauGia,
  cauHoatDong,
  cauMoCua,
  cauNguonDuLieu,
  chiTietNgan,
  daoLuu,
  docAnhDiaDiem,
  docAnhNhom,
  docChiTiet,
  docDaLuu,
  dongPhu,
  duongChiDuong,
  luuDiaDiem,
  nguonAnhDiaDiem,
  TIEN_TO_ANH,
  type AnhDiaDiem,
  type AnhNhom,
} from "../../kham-pha/dia-diem";
import { typography, useRudiTheme } from "../../theme";
import { AiNote, Card, Chip, Heading, Inline, ListRow, RudiButton, RudiScreen, SectionHeader, TopBar } from "../../ui";
import { nguonAnh } from "../../ky-niem/ky-niem";
import { MediaSlot } from "../../ui/MediaSlot";

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
  const [anh, setAnh] = useState<AnhDiaDiem[]>([]);
  const [loiAnh, setLoiAnh] = useState<string | null>(null);
  const [anhNhom, setAnhNhom] = useState<AnhNhom[]>([]);

  const nap = useCallback(async () => {
    if (!placeId) {
      setTrang({ pha: "hong", loi: "Thiếu địa điểm để mở." });
      return;
    }
    try {
      const [place, luu] = await Promise.all([docChiTiet(placeId), docDaLuu(phien.person_id)]);
      setTrang({ pha: "xong", place });
      setDaLuu(luu);
      // Ảnh của nhóm: một request nữa, và im lặng khi hỏng. Không có ảnh nào
      // và không đọc được là cùng một màn ở đây — cả hai đều là «không có gì
      // của nhóm bạn để xem», và không có câu nào đúng hơn để nói.
      try {
        setAnhNhom(await docAnhNhom(placeId, phien.person_id));
      } catch {
        setAnhNhom([]);
      }
      // A second request, and a failing one costs the pictures and nothing
      // else: the facts are already on the screen. The screen still says so --
      // «chưa tải được» is a different thing to go and check from a place that
      // simply has no photograph.
      if (!place.photosAvailable) {
        setAnh([]);
        setLoiAnh(null);
        return;
      }
      try {
        setAnh(await docAnhDiaDiem(placeId));
        setLoiAnh(null);
      } catch {
        setAnh([]);
        setLoiAnh("Chưa tải được ảnh của nơi này.");
      }
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
        anh={anh}
        anhNhom={anhNhom}
        loiAnh={loiAnh}
        onThemAnhNhom={() =>
          router.push(
            `/moments/new?place=${encodeURIComponent(trang.place.id)}&ten=${encodeURIComponent(trang.place.name)}` as never,
          )
        }
        personId={phien.person_id}
        onChiDuong={() => void chiDuong(trang.place)}
        onThemVaoKeo={() => router.push(`/outings/chon?place=${encodeURIComponent(trang.place.id)}` as never)}
        place={trang.place}
        thongBao={thongBao}
      /> : null}
    </RudiScreen>
  );
}

/**
 * The photographs, side by side, each carrying its own credit.
 *
 * One strip and not a grid: a licensed photograph is only allowed on this
 * screen while its author and licence are legible next to it, and a caption
 * under a full-width frame stays legible where a caption under a thumbnail
 * does not.
 */
function DaiAnh({ anh }: { anh: AnhDiaDiem[] }) {
  const { radius } = useRudiTheme();
  return (
    <ScrollView
      contentContainerStyle={styles.dai}
      horizontal
      showsHorizontalScrollIndicator={false}
      testID="place-photos"
    >
      {anh.map((a) => (
        <MediaSlot
          alt={a.title ?? "Ảnh có giấy phép chụp quanh đây"}
          attribution={{ author: a.author, license: a.license, prefix: TIEN_TO_ANH }}
          key={a.id}
          radius={radius.base}
          source={nguonAnhDiaDiem(a)}
          style={styles.oAnh}
          width="100%"
        />
      ))}
    </ScrollView>
  );
}

/**
 * The group's own pictures of this place, and the line saying who can see them.
 *
 * A separate strip from the licensed one, never merged into it: those are
 * public and carry a credit, these are a group's and carry a membership. One
 * strip holding both would be the first step towards a group's photograph
 * illustrating a restaurant for strangers.
 */
function DaiAnhNhom({ anh, personId }: { anh: AnhNhom[]; personId: string }) {
  const { colors, radius } = useRudiTheme();
  return (
    <View style={styles.khoi}>
      <SectionHeader title="Ảnh của nhóm bạn" />
      <ScrollView
        contentContainerStyle={styles.dai}
        horizontal
        showsHorizontalScrollIndicator={false}
        testID="place-group-photos"
      >
        {anh.map((a) => {
          const nguon = nguonAnh(a.imageUrl, personId, a.contextId);
          if (nguon === null) return null;
          return (
            <View key={a.id} style={styles.oAnh}>
              <MediaSlot
                alt={a.caption ?? "Ảnh của nhóm bạn ở đây"}
                radius={radius.base}
                source={nguon}
                width="100%"
              />
              {a.caption === null ? null : (
                <Text numberOfLines={2} style={[typography.caption, { color: colors.inkSoft }]}>
                  {a.caption}
                </Text>
              )}
            </View>
          );
        })}
      </ScrollView>
      <Text style={[typography.caption, { color: colors.inkFaint }]}>{CAU_ANH_NHOM}</Text>
    </View>
  );
}

function ThanChiTiet({
  place,
  thongBao,
  anh,
  anhNhom,
  loiAnh,
  personId,
  onChiDuong,
  onThemVaoKeo,
  onThemAnhNhom,
}: {
  place: PlaceDetail;
  thongBao: string | null;
  anh: AnhDiaDiem[];
  anhNhom: AnhNhom[];
  loiAnh: string | null;
  personId: string;
  onChiDuong: () => void;
  onThemVaoKeo: () => void;
  onThemAnhNhom: () => void;
}) {
  const { colors, radius } = useRudiTheme();
  const hop = matchLabel(place.match);
  const coMatch = place.match !== null && place.match.source === "ai";
  const coAnh = anh.length > 0;
  return (
    <>
      {coAnh ? <DaiAnh anh={anh} /> : null}
      {coAnh ? (
        <Text style={[typography.caption, { color: colors.inkFaint }]}>{CAU_NGUON_ANH}</Text>
      ) : null}
      {loiAnh === null ? null : (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>{loiAnh}</Text>
      )}
      {/* The screen's one hero moment: a full-width band in the leading tone,
          glyph at focal size, then the facts as one line of text. The glyph
          stands in for a picture, so it goes when there is a real one -- two
          heroes above one name is neither. */}
      <View style={[styles.hero, { backgroundColor: colors.accentSoft, borderRadius: radius.base }]}>
        {coAnh ? null : (
          <View style={[styles.heroIcon, { backgroundColor: colors.card }]}>
            <Ionicons color={colors.accent} name={bieuTuongLoai(place.category)} size={40} />
          </View>
        )}
        <Heading title={place.name} subtitle={dongPhu(place)} />
        {/* Only what the row actually carries (M9). Each item is one text node
            and the status is a whole badge: at font 1.3 an inline word broke
            across lines («Đang / mở»). */}
        <Inline gap={8} wrap>
          {chiTietNgan(place)
            .filter((muc) => muc.icon !== "time-outline")
            .map((muc) => (
              <Inline gap={6} key={muc.icon}>
                <Ionicons
                  color={muc.icon === "star" ? colors.accent : colors.inkFaint}
                  name={muc.icon}
                  size={14}
                />
                <Text style={[typography.label, { color: colors.ink }]}>{muc.chu}</Text>
              </Inline>
            ))}
          {place.openNow === null ? null : (
            <Chip
              label={place.openNow ? "Đang mở" : "Đã đóng"}
              selected
              tone={place.openNow ? "accent" : "split"}
            />
          )}
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
        <ListRow
          icon="navigate-outline"
          onPress={onChiDuong}
          subtitle={cauDuongDi(place)}
          title={place.address ?? "Chưa có địa chỉ"}
        />
        <ListRow icon="time-outline" title={cauMoCua(place)} subtitle="Giờ mở cửa" />
        <ListRow icon="wallet-outline" title={cauGia(place)} subtitle="Khoảng giá" />
      </Card>
      {cauNguonDuLieu(place) === null ? null : (
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          {cauNguonDuLieu(place)}
        </Text>
      )}
      {place.traits.length > 0 ? (
        <Inline gap={8} wrap>
          {place.traits.map((t) => (
            <Chip key={t} label={t} />
          ))}
        </Inline>
      ) : null}
      {cauHoatDong(place.activities) === null ? null : (
        <View>
          <SectionHeader title={cauHoatDong(place.activities) ?? ""} />
          <Inline gap={8} wrap>
            {place.activities.map((viec) => (
              <Chip key={viec} label={viec} />
            ))}
          </Inline>
        </View>
      )}
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
      {anhNhom.length === 0 ? null : <DaiAnhNhom anh={anhNhom} personId={personId} />}
      <RudiButton
        icon="camera-outline"
        label={anhNhom.length === 0 ? "Thêm ảnh của nhóm ở đây" : "Thêm một ảnh nữa"}
        onPress={onThemAnhNhom}
        variant="outline"
      />
      {thongBao !== null ? <Text style={[typography.caption, { color: colors.warn }]}>{thongBao}</Text> : null}
    </>
  );
}

const styles = StyleSheet.create({
  dai: { gap: 12, paddingRight: 4 },
  oAnh: { width: 260 },
  hero: { gap: 12, padding: 18 },
  heroIcon: { width: 80, height: 80, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  huyHieu: { flexDirection: "row" },
  suKien: { paddingVertical: 5 },
  khoi: { gap: 8 },
  nhanXet: { gap: 2, paddingVertical: 6 },
  flex: { flex: 1 },
  hanhDong: { flexDirection: "row", gap: 10 },
});
