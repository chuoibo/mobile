import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, Share, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { PEOPLE, PLACES, DemoPlace } from "../fixtures";
import { PLACE_CATEGORIES, filterPlaces, type PlaceCategory } from "../places";
import { useRudiSession } from "../session";
import { bangMauFixture, lopPhu, mauSang, mauSao, mucTrenAnh, phuMau, typography, useRudiTheme } from "../theme";
import {
  AiNote,
  AvatarStack,
  Card,
  Chip,
  DemoBadge,
  Heading,
  IconButton,
  Inline,
  ListRow,
  Logo,
  Photo,
  PhotoShade,
  ResponsiveRow,
  RudiButton,
  RudiScreen,
  SearchField,
  SectionHeader,
  Spacer,
  TopBar,
} from "../ui";

function PlaceCard({
  place,
  saved,
  onSave,
  featured = false,
}: {
  place: DemoPlace;
  saved: boolean;
  onSave: () => void;
  featured?: boolean;
}) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { width } = useWindowDimensions();
  const compact = width < 700;
  return (
    <Card
      accessibilityLabel={"Mở " + place.name}
      onPress={() => router.push(("/places/" + place.id) as never)}
      style={[
        styles.placeCard,
        compact && styles.placeCardCompact,
        featured && styles.placeCardFeatured,
      ]}
    >
      <Photo
        height={compact ? 112 : featured ? 205 : 154}
        radius={16}
        source={place.image}
        style={compact && styles.placePhotoCompact}
        overlay={
          compact ? (
            featured ? (
              <View style={[styles.matchPill, styles.matchPillCompact]}>
                <Ionicons color={mucTrenAnh} name="sparkles" size={12} />
                <Text style={styles.matchPillText}>Hợp gu</Text>
              </View>
            ) : null
          ) : (
            <>
              <View style={styles.placePhotoTop}>
                <View style={styles.ratingPill}>
                  <Ionicons color={mauSao.dam} name="star" size={14} />
                  <Text style={styles.ratingText}>{place.rating}</Text>
                </View>
                <IconButton
                  accessibilityLabel={saved ? "Bỏ lưu địa điểm" : "Lưu địa điểm"}
                  icon={saved ? "heart" : "heart-outline"}
                  onPress={onSave}
                  selected={saved}
                />
              </View>
              {featured ? (
                <View style={styles.matchPill}>
                  <Ionicons color={mucTrenAnh} name="sparkles" size={13} />
                  <Text style={styles.matchPillText}>Rất hợp gu</Text>
                </View>
              ) : null}
            </>
          )
        }
      />
      <View style={[styles.placeBody, compact && styles.placeBodyCompact]}>
        <View style={styles.placeHeadingRow}>
          <View style={styles.flex}>
            <Text numberOfLines={1} style={[typography.title, { color: colors.ink }]}>{place.name}</Text>
            <Text numberOfLines={1} style={[typography.caption, { color: colors.inkFaint }]}>{place.subtitle}</Text>
          </View>
          {compact ? (
            <IconButton
              accessibilityLabel={saved ? "Bỏ lưu địa điểm" : "Lưu địa điểm"}
              icon={saved ? "heart" : "heart-outline"}
              onPress={onSave}
              quiet
              selected={saved}
            />
          ) : (
            <Ionicons color={colors.inkFaint} name="arrow-forward-outline" size={19} />
          )}
        </View>
        <Inline gap={12} wrap>
          {compact ? (
            <Inline gap={4}>
              <Ionicons color={mauSao.dam} name="star" size={14} />
              <Text style={[typography.caption, { color: colors.ink }]}>{place.rating}</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>({place.reviews})</Text>
            </Inline>
          ) : null}
          <Inline gap={4}>
            <Ionicons color={colors.inkFaint} name="navigate-outline" size={15} />
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{place.distance}</Text>
          </Inline>
          <Inline gap={4}>
            <Ionicons color={colors.inkFaint} name="wallet-outline" size={15} />
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{place.price}</Text>
          </Inline>
        </Inline>
      </View>
    </Card>
  );
}

/**
 * Whose group this screen is talking about.
 *
 * Until M4 ports Explore to `/places`, the catalogue on this screen is the
 * sample one. With a REAL session that must be said out loud and the story
 * must stop naming «Team Đà Lạt» for a group somebody just created: the
 * sentence names their group and calls the suggestions samples. On the
 * fixture build the fixture story stands.
 */
function tenNhomHienTai(session: ReturnType<typeof useRudiSession>): string {
  if (session.cheDo !== "live") return "Team Đà Lạt";
  const phien = session.phien;
  const nhom = phien?.contexts?.find((ung) => ung.id === phien.context_id);
  return nhom?.display_name ?? "nhóm của bạn";
}

export function ExploreScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const song = session.cheDo === "live";
  const tenNhom = tenNhomHienTai(session);
  const [category, setCategory] = useState<PlaceCategory | null>(null);
  const [query, setQuery] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [matchOnly, setMatchOnly] = useState(false);
  const [nearOnly, setNearOnly] = useState(false);
  const [savedOnly, setSavedOnly] = useState(false);

  const visiblePlaces = useMemo(
    () =>
      filterPlaces(PLACES, {
        query,
        category,
        matchOnly,
        nearOnly,
        savedOnly,
        savedIds: session.savedPlaceIds,
      }),
    [category, matchOnly, nearOnly, query, savedOnly, session.savedPlaceIds],
  );

  const filtering = Boolean(query.trim()) || matchOnly || nearOnly || savedOnly || category !== null;
  const primaryPlaces = filtering ? visiblePlaces : visiblePlaces.slice(0, 2);
  const moodPlaces = filtering ? [] : visiblePlaces.slice(2);

  const resetFilters = () => {
    setQuery("");
    setCategory(null);
    setMatchOnly(false);
    setNearOnly(false);
    setSavedOnly(false);
  };

  const toggleSaved = (id: string) => {
    void Haptics.selectionAsync();
    session.toggleSaved(id);
  };

  return (
    <RudiScreen bottomInset={112} testID="explore-screen">
      <View style={styles.exploreHeader}>
        <View style={styles.exploreBrand}>
          <Logo compact />
          <Inline gap={4} style={styles.location}>
            <Ionicons color={colors.accent} name="location" size={14} />
            <Text style={[typography.caption, { color: colors.inkSoft }]}>
              {song ? "Khu vực chưa chọn" : "Đà Lạt, Lâm Đồng"}
            </Text>
            <Ionicons color={colors.inkFaint} name="chevron-down" size={13} />
          </Inline>
        </View>
        <Inline gap={8}>
          <DemoBadge />
          <IconButton
            accessibilityLabel="Thông báo"
            icon="notifications-outline"
            onPress={() => session.setInboxOpen(true)}
            selected={session.inboxOpen}
          />
        </Inline>
      </View>
      {session.inboxOpen ? (
        <Card>
          <Heading size="h2" title="Thông báo" subtitle="Chưa có hộp thư máy chủ. Bản trải nghiệm không đẩy thông báo." />
          <RudiButton label="Đóng" onPress={() => session.setInboxOpen(false)} variant="outline" />
        </Card>
      ) : null}
      <View style={styles.searchRow}>
        <View style={styles.flex}>
          <SearchField
            onChangeText={setQuery}
            onSubmitEditing={() => setFiltersOpen(false)}
            value={query}
          />
        </View>
        <IconButton
          accessibilityLabel={filtersOpen ? "Đóng bộ lọc" : "Mở bộ lọc"}
          icon="options-outline"
          onPress={() => setFiltersOpen((value) => !value)}
          selected={filtersOpen}
        />
      </View>
      {filtersOpen ? (
        <Card style={styles.filterPanel}>
          <View style={styles.filterHeader}>
            <View>
              <Text style={[typography.title, { color: colors.ink }]}>Lọc nhanh</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>Cập nhật kết quả ngay khi chọn.</Text>
            </View>
            <Chip label="Xóa lọc" onPress={resetFilters} />
          </View>
          <Inline gap={7} wrap>
            <Chip icon="sparkles-outline" label="Từ 90% hợp gu" onPress={() => setMatchOnly((value) => !value)} selected={matchOnly} />
            <Chip icon="navigate-outline" label="Trong 2 km" onPress={() => setNearOnly((value) => !value)} selected={nearOnly} />
            <Chip icon="heart-outline" label="Đã lưu" onPress={() => setSavedOnly((value) => !value)} selected={savedOnly} />
          </Inline>
        </Card>
      ) : null}
      <Card onPress={() => router.push("/ai-match")} style={styles.aiDiscovery} tone="ai">
        <View style={styles.aiDiscoveryIcon}>
          <Ionicons color={colors.aiInk} name="sparkles" size={24} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.title, { color: colors.ink }]}>Match gu cả nhóm bằng AI</Text>
          <Text style={[typography.caption, { color: colors.inkSoft }]}>
            {song
              ? `Gợi ý mẫu cho ${tenNhom}: ${PLACES.length} nơi, chưa lọc theo gu nhóm bạn.`
              : `Rủ Đi đã tìm thấy ${PLACES.length} nơi hợp Team Đà Lạt.`}
          </Text>
        </View>
        <Ionicons color={colors.ai} name="arrow-forward-circle" size={27} />
      </Card>
      <View style={styles.categoryGrid}>
        {PLACE_CATEGORIES.map((label, index) => {
          const icons = ["restaurant-outline", "cafe-outline", "game-controller-outline", "moon-outline"] as const;
          const colorsChip = [bangMauFixture.cam, bangMauFixture.vangSam, mauSang.ai, bangMauFixture.ngocDam] as const;
          const icon = icons[index];
          const color = colorsChip[index];
          const active = category === label;
          return (
            <Pressable
              key={label}
              accessibilityRole="button"
              aria-pressed={active}
              onPress={() => setCategory(active ? null : label)}
              style={({ pressed }) => [
                styles.category,
                {
                  backgroundColor: active ? color + "18" : colors.card,
                  borderColor: active ? color : colors.line,
                },
                pressed && styles.pressed,
              ]}
            >
              <View style={[styles.categoryIcon, { backgroundColor: color + "1F" }]}>
                <Ionicons color={color} name={icon} size={23} />
              </View>
              <Text style={[typography.caption, { color: active ? color : colors.ink }]}>{label}</Text>
            </Pressable>
          );
        })}
      </View>
      <SectionHeader
        action={filtering ? "Xóa lọc" : "Xem tất cả"}
        onAction={filtering ? resetFilters : () => setFiltersOpen(true)}
        title={
          filtering
            ? `${visiblePlaces.length} kết quả phù hợp`
            : song
              ? "Mẫu minh hoạ"
              : "Gần bạn, đúng gu"
        }
      />
      {song ? (
        // The cards below carry distances, ratings and prices. For a real
        // session those are sample numbers until M4 reads the catalogue from
        // the server, and a number that looks measured must say it is not.
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          Khoảng cách, đánh giá và giá ở đây là số mẫu. Gợi ý thật cho khu vực của nhóm đến ở bản
          sau.
        </Text>
      ) : null}
      {primaryPlaces.length ? (
        <ResponsiveRow minItemWidth={320}>
          {primaryPlaces.map((place, index) => (
            <View key={place.id} style={styles.placeCell}>
              <PlaceCard
                featured={index === 0}
                onSave={() => toggleSaved(place.id)}
                place={place}
                saved={session.savedPlaceIds.includes(place.id)}
              />
            </View>
          ))}
        </ResponsiveRow>
      ) : (
        <Card style={styles.emptyResults}>
          <View style={[styles.emptyIcon, { backgroundColor: colors.accentSoft }]}>
            <Ionicons color={colors.accent} name="search-outline" size={24} />
          </View>
          <Heading
            align="center"
            size="h2"
            title="Chưa thấy nơi phù hợp"
            subtitle="Thử từ khóa khác hoặc xóa bớt bộ lọc nhé."
          />
          <RudiButton label="Xóa bộ lọc" onPress={resetFilters} variant="outline" />
        </Card>
      )}
      {moodPlaces.length ? (
        <>
          <SectionHeader action="Đổi mood" title="Tối nay đi đâu?" />
          <ResponsiveRow minItemWidth={320}>
            {moodPlaces.map((place) => (
              <View key={place.id} style={styles.placeCell}>
                <PlaceCard
                  onSave={() => toggleSaved(place.id)}
                  place={place}
                  saved={session.savedPlaceIds.includes(place.id)}
                />
              </View>
            ))}
          </ResponsiveRow>
        </>
      ) : null}
    </RudiScreen>
  );
}

export function AiMatchScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [filter, setFilter] = useState("Tất cả");
  const visible = filter === "Tất cả"
    ? PLACES
    : filter === "Dưới 250K"
      ? PLACES.filter((place) => !place.price.includes("320K") && !place.price.includes("260K"))
      : PLACES.filter((place) =>
          filter === "Ăn uống"
            ? place.category === "Quán ăn"
            : filter === "Cafe"
              ? place.category === "Cafe"
              : place.category === "Vui chơi",
        );

  return (
    <RudiScreen tone="ai" testID="ai-match-screen">
      <TopBar title="Match gu cả nhóm" right={<DemoBadge />} />
      <Heading
        title={`Rủ Đi tìm được ${visible.length} nơi`}
        subtitle={`Gợi ý từ ${PLACES.length} địa điểm fixture, sở thích 8 thành viên. Không phải kết quả LLM.`}
      />
      <Card style={styles.groupMatchCard} tone="ai">
        <View style={styles.groupMatchTop}>
          <AvatarStack max={5} people={PEOPLE} />
          <View style={styles.groupCount}>
            <Text style={[typography.title, { color: colors.ai }]}>8/8</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>đã có gu</Text>
          </View>
        </View>
        <AiNote>
          Nhóm mê đồ ăn local, không gian ngoài trời và nơi đủ rộng để ngồi cùng nhau.
        </AiNote>
      </Card>
      <Inline gap={8} wrap>
        {["Tất cả", "Ăn uống", "Cafe", "Vui chơi", "Dưới 250K"].map((item) => (
          <Chip
            key={item}
            label={item}
            onPress={() => setFilter(item)}
            selected={filter === item}
            tone="ai"
          />
        ))}
      </Inline>
      <View style={styles.matchList}>
        {visible.map((place, index) => (
          <Card
            key={place.id}
            onPress={() => router.push(("/places/" + place.id) as never)}
            style={styles.matchCard}
          >
            <Photo height={142} radius={16} source={place.image} />
            <View style={styles.matchBody}>
              <View style={styles.matchScoreRow}>
                <View style={[styles.matchScore, { backgroundColor: colors.aiSoft }]}>
                  <Ionicons color={colors.ai} name="sparkles" size={15} />
                  <Text style={[typography.caption, { color: colors.ai }]}>Rất hợp gu</Text>
                </View>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>#{index + 1}</Text>
              </View>
              <Text style={[typography.title, { color: colors.ink }]}>{place.name}</Text>
              <Text numberOfLines={2} style={[typography.caption, { color: colors.inkSoft }]}>{place.subtitle}</Text>
              <Inline gap={6} wrap>
                {place.tags.slice(0, 2).map((tag) => <Chip key={tag} label={tag} tone="ai" />)}
              </Inline>
              <View style={styles.matchMembers}>
                <AvatarStack max={4} people={PEOPLE.slice(index, index + 6)} />
                <Text style={[typography.caption, { color: colors.inkFaint }]}>
                  {Math.max(5, 8 - index)}/8 sẽ thích
                </Text>
              </View>
            </View>
          </Card>
        ))}
      </View>
      <AiNote>Đây là gợi ý có thể chỉnh. Rủ Đi không tự thêm nơi vào kế hoạch của nhóm.</AiNote>
    </RudiScreen>
  );
}

export function PlaceDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const { colors } = useRudiTheme();
  const { width } = useWindowDimensions();
  const session = useRudiSession();
  const [added, setAdded] = useState(false);
  const place = useMemo(
    () => PLACES.find((item) => item.id === params.id) ?? PLACES[0],
    [params.id],
  );
  const saved = session.savedPlaceIds.includes(place.id);

  return (
    <RudiScreen padded={false} testID="place-detail-screen">
      <View style={styles.detailShell}>
        <Photo
          height={width >= 700 ? 430 : 330}
          radius={width >= 700 ? 30 : 0}
          source={place.image}
          overlay={
            <>
              <View style={styles.detailTop}>
                <IconButton accessibilityLabel="Quay lại" icon="chevron-back" onPress={() => router.back()} />
                <Inline gap={8}>
                  <IconButton
                    accessibilityLabel="Chia sẻ"
                    icon="share-social-outline"
                    onPress={() =>
                      void Share.share({
                        message: `${place.name}: ${place.subtitle}`,
                      })
                    }
                  />
                  <IconButton
                    accessibilityLabel={saved ? "Bỏ lưu" : "Lưu địa điểm"}
                    icon={saved ? "heart" : "heart-outline"}
                    onPress={() => session.toggleSaved(place.id)}
                    selected={saved}
                  />
                </Inline>
              </View>
              <PhotoShade>
                <Inline gap={8}>
                  <View style={styles.detailRating}>
                    <Ionicons color={mauSao.sang} name="star" size={15} />
                    <Text style={styles.detailRatingText}>{place.rating} · {place.reviews} đánh giá</Text>
                  </View>
                  <View style={styles.openPill}><Text style={styles.openText}>Đang mở</Text></View>
                </Inline>
              </PhotoShade>
            </>
          }
        />
        <View style={styles.detailContent}>
          <DemoBadge />
          <Heading title={place.name} subtitle={place.subtitle} />
          <Inline gap={8} wrap>
            {place.tags.map((tag) => <Chip key={tag} label={tag} selected />)}
          </Inline>
          <Card style={styles.quickFacts}>
            <ListRow icon="navigate-outline" title={place.distance} subtitle="Khoảng 6 phút đi xe" />
            <ListRow icon="wallet-outline" title={place.price} subtitle="Phù hợp ngân sách nhóm" />
            <ListRow icon="time-outline" title="10:00 - 22:30" subtitle="Mở cửa hôm nay" />
          </Card>
          <View>
            <SectionHeader title={`Vì sao hợp ${tenNhomHienTai(session)}?`} />
            <Spacer size={10} />
            <Card tone="ai">
              <View style={styles.memberMatchRow}>
                <AvatarStack max={6} people={PEOPLE} />
                <View style={styles.memberMatchText}>
                  <Text style={[typography.title, { color: colors.ai }]}>Rất hợp nhóm</Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>7/8 thành viên có thể thích</Text>
                </View>
              </View>
              <Spacer size={12} />
              <AiNote>View thoáng, món nướng dễ chia sẻ và đủ chỗ cho nhóm 8 người.</AiNote>
            </Card>
          </View>
          <View>
            <SectionHeader title="Không gian" />
            <Spacer size={10} />
            <ResponsiveRow minItemWidth={260}>
              {[PLACES[1].image, PLACES[2].image].map((image, index) => (
                <View key={index} style={styles.galleryCell}>
                  <Photo height={150} radius={17} source={image} />
                </View>
              ))}
            </ResponsiveRow>
          </View>
          <RudiButton
            icon="add-circle-outline"
            label={added ? `Đã thêm vào ${session.tripName}` : `Thêm vào ${session.tripName}`}
            onPress={() => {
              const ok = session.addPlaceToTrip(place.id);
              setAdded(ok);
              router.push(session.tripPath("/itinerary") as never);
            }}
          />
        </View>
      </View>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  exploreHeader: { minHeight: 55, flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 10 },
  exploreBrand: { minWidth: 130, flexShrink: 0 },
  location: { marginLeft: 49, marginTop: -8 },
  searchRow: { flexDirection: "row", alignItems: "flex-end", gap: 9 },
  filterPanel: { gap: 12, padding: 13 },
  filterHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  emptyResults: { alignItems: "center", gap: 14, paddingVertical: 24 },
  emptyIcon: { width: 52, height: 52, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  aiDiscovery: { flexDirection: "row", alignItems: "center", gap: 12, padding: 14 },
  aiDiscoveryIcon: { width: 46, height: 46, borderRadius: 16, backgroundColor: mauSang.ai, alignItems: "center", justifyContent: "center" },
  categoryGrid: { flexDirection: "row", gap: 9 },
  category: { flex: 1, minWidth: 70, minHeight: 87, borderRadius: 17, borderWidth: 1, alignItems: "center", justifyContent: "center", gap: 8, padding: 8 },
  categoryIcon: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  pressed: { opacity: 0.72, transform: [{ scale: 0.98 }] },
  placeCell: { flex: 1 },
  placeCard: { padding: 7, gap: 3 },
  placeCardCompact: { flexDirection: "row", alignItems: "center", gap: 4 },
  placeCardFeatured: { borderColor: phuMau(mauSang.accent, 0.18) },
  placePhotoCompact: { width: 112, flexShrink: 0 },
  placePhotoTop: { position: "absolute", left: 9, right: 9, top: 9, flexDirection: "row", justifyContent: "space-between" },
  ratingPill: { flexDirection: "row", alignItems: "center", gap: 4, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 6, backgroundColor: lopPhu.trang(0.94) },
  ratingText: { color: bangMauFixture.than, fontSize: 12, fontWeight: "800" },
  matchPill: { position: "absolute", left: 9, bottom: 9, flexDirection: "row", alignItems: "center", gap: 5, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 6, backgroundColor: phuMau(mauSang.ai, 0.92) },
  matchPillCompact: { left: 7, bottom: 7, paddingHorizontal: 7, paddingVertical: 5 },
  matchPillText: { color: mucTrenAnh, fontSize: 11, fontWeight: "800" },
  placeBody: { padding: 9, gap: 8 },
  placeBodyCompact: { flex: 1, padding: 8 },
  placeHeadingRow: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  groupMatchCard: { gap: 14 },
  groupMatchTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  groupCount: { alignItems: "flex-end" },
  matchList: { gap: 12 },
  matchCard: { padding: 8, flexDirection: "row", gap: 12 },
  matchBody: { flex: 1, gap: 7, paddingVertical: 4, paddingRight: 4 },
  matchScoreRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  matchScore: { flexDirection: "row", alignItems: "center", gap: 5, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 5 },
  matchMembers: { marginTop: 2, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  detailShell: { width: "100%", maxWidth: 960, alignSelf: "center" },
  detailTop: { position: "absolute", left: 14, right: 14, top: 14, flexDirection: "row", justifyContent: "space-between" },
  detailRating: { flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 10, paddingVertical: 7, borderRadius: 999, backgroundColor: lopPhu.xam(0.65) },
  detailRatingText: { color: mucTrenAnh, fontSize: 12, fontWeight: "700" },
  openPill: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 999, backgroundColor: phuMau(bangMauFixture.luc, 0.92) },
  openText: { color: mucTrenAnh, fontSize: 12, fontWeight: "800" },
  detailContent: { paddingHorizontal: 16, paddingTop: 19, gap: 19 },
  quickFacts: { paddingVertical: 5 },
  memberMatchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 14 },
  memberMatchText: { flex: 1, alignItems: "flex-end" },
  galleryCell: { flex: 1 },
});
