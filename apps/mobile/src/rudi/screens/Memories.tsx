import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { DEMO_GROUP, PEOPLE, demoAssets } from "../fixtures";
import { typography, useRudiTheme } from "../theme";
import {
  Avatar,
  AvatarStack,
  Card,
  Chip,
  DemoBadge,
  Field,
  Heading,
  IconButton,
  Inline,
  Photo,
  PhotoShade,
  RudiButton,
  RudiScreen,
  SectionHeader,
  Segmented,
  TopBar,
  widthPercent,
} from "../ui";

const MEMORY_PHOTOS = [
  demoAssets.dalatFriends,
  demoAssets.cafe,
  demoAssets.road,
  demoAssets.friends,
  demoAssets.cafe,
  demoAssets.dalatFriends,
  demoAssets.friends,
  demoAssets.road,
];

function FeedPost({
  personIndex,
  imageIndex,
  caption,
  time,
}: {
  personIndex: number;
  imageIndex: number;
  caption: string;
  time: string;
}) {
  const { colors } = useRudiTheme();
  const [liked, setLiked] = useState(false);
  const person = PEOPLE[personIndex];

  return (
    <Card style={styles.post}>
      <View style={styles.postHeader}>
        <Avatar person={person} size={43} />
        <View style={styles.flex}>
          <Text style={[typography.label, { color: colors.ink }]}>{person.name}</Text>
          <Inline gap={4}>
            <Ionicons color={colors.inkFaint} name="location-outline" size={13} />
            <Text style={[typography.caption, { color: colors.inkFaint }]}>Đà Lạt · {time}</Text>
          </Inline>
        </View>
        <IconButton accessibilityLabel="Tùy chọn bài viết" icon="ellipsis-horizontal" quiet />
      </View>
      <Text style={[typography.body, { color: colors.ink }]}>{caption}</Text>
      <Photo height={285} radius={18} source={MEMORY_PHOTOS[imageIndex]} />
      <View style={styles.reactions}>
        <Inline gap={6}>
          <View style={[styles.reactionDots, { backgroundColor: colors.accentSoft }]}>
            <Ionicons color={colors.accent} name="heart" size={13} />
          </View>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Minh Anh và 12 người khác</Text>
        </Inline>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>4 bình luận</Text>
      </View>
      <View style={[styles.postDivider, { backgroundColor: colors.line }]} />
      <Inline gap={8}>
        <Pressable
          accessibilityRole="button"
          onPress={() => setLiked((value) => !value)}
          style={({ pressed }) => [styles.postAction, pressed && styles.pressed]}
        >
          <Ionicons color={liked ? colors.accent : colors.inkFaint} name={liked ? "heart" : "heart-outline"} size={20} />
          <Text style={[typography.label, { color: liked ? colors.accent : colors.inkSoft }]}>Thích</Text>
        </Pressable>
        <Pressable accessibilityRole="button" style={({ pressed }) => [styles.postAction, pressed && styles.pressed]}>
          <Ionicons color={colors.inkFaint} name="chatbubble-outline" size={19} />
          <Text style={[typography.label, { color: colors.inkSoft }]}>Bình luận</Text>
        </Pressable>
        <Pressable accessibilityRole="button" style={({ pressed }) => [styles.postAction, pressed && styles.pressed]}>
          <Ionicons color={colors.inkFaint} name="share-social-outline" size={19} />
        </Pressable>
      </Inline>
    </Card>
  );
}

export function GroupWallScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();

  return (
    <RudiScreen testID="group-wall-screen">
      <TopBar
        title={DEMO_GROUP.name}
        subtitle="Không gian kỷ niệm"
        right={<IconButton accessibilityLabel="Tùy chọn nhóm" icon="ellipsis-horizontal" />}
      />
      <Photo
        height={245}
        radius={24}
        source={demoAssets.friends}
        overlay={
          <PhotoShade>
            <View style={styles.wallHero}>
              <DemoBadge />
              <Text style={styles.wallTitle}>Team Đà Lạt</Text>
              <View style={styles.wallMeta}>
                <AvatarStack max={5} people={PEOPLE} />
                <Text style={styles.wallMetaText}>8 thành viên · 3 chuyến đi</Text>
              </View>
            </View>
          </PhotoShade>
        }
      />
      <Card style={styles.memorySummary}>
        <Pressable onPress={() => router.push(("/trips/" + DEMO_GROUP.id + "/album") as never)} style={styles.summaryItem}>
          <Text style={[typography.money, { color: colors.accent }]}>{DEMO_GROUP.photos}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>ảnh</Text>
        </Pressable>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <Pressable onPress={() => router.push(("/trips/" + DEMO_GROUP.id + "/album") as never)} style={styles.summaryItem}>
          <Text style={[typography.money, { color: colors.ai }]}>{DEMO_GROUP.videos}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>video</Text>
        </Pressable>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.summaryItem}>
          <Text style={[typography.money, { color: colors.split }]}>{DEMO_GROUP.checkIns}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>check-in</Text>
        </View>
      </Card>
      <Card onPress={() => router.push("/moments/new")} style={styles.sharePrompt}>
        <Avatar person={PEOPLE[0]} size={43} />
        <View style={[styles.promptField, { backgroundColor: colors.ground, borderColor: colors.line }]}>
          <Text style={[typography.label, { color: colors.inkFaint }]}>Chia sẻ khoảnh khắc với cả nhóm...</Text>
        </View>
        <View style={[styles.photoAction, { backgroundColor: colors.accentSoft }]}>
          <Ionicons color={colors.accent} name="images-outline" size={21} />
        </View>
      </Card>
      <SectionHeader
        action="Mở album"
        onAction={() => router.push(("/trips/" + DEMO_GROUP.id + "/album") as never)}
        title="Chuyện của hội mình"
      />
      <FeedPost
        caption="Sáng Đà Lạt lạnh nhưng cả hội vẫn dậy đúng giờ săn mây. Xứng đáng ghê! ☁️"
        imageIndex={2}
        personIndex={2}
        time="2 giờ"
      />
      <FeedPost
        caption="Một chiếc ảnh đủ 8 người sau bao lần hẹn mãi mới đủ mặt 🌿"
        imageIndex={0}
        personIndex={1}
        time="Hôm qua"
      />
    </RudiScreen>
  );
}

export function TripAlbumScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { width } = useWindowDimensions();
  const [segment, setSegment] = useState(0);
  const [newestFirst, setNewestFirst] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selectedPhotos, setSelectedPhotos] = useState<number[]>([]);
  const columns = width >= 820 ? 4 : width >= 560 ? 3 : 2;
  const videoIndexes = [2, 6];
  const visiblePhotos = MEMORY_PHOTOS.map((photo, originalIndex) => ({ photo, originalIndex }))
    .filter(({ originalIndex }) =>
      segment === 0 || (segment === 1 ? !videoIndexes.includes(originalIndex) : videoIndexes.includes(originalIndex)),
    );
  if (newestFirst) visiblePhotos.reverse();

  const togglePhoto = (index: number) => {
    setSelectedPhotos((items) =>
      items.includes(index) ? items.filter((item) => item !== index) : [...items, index],
    );
  };

  const toggleSelectionMode = () => {
    setSelecting((value) => {
      if (value) setSelectedPhotos([]);
      return !value;
    });
  };

  return (
    <RudiScreen testID="trip-album-screen">
      <TopBar
        title="Album Đà Lạt"
        subtitle="17–19/10/2026"
        right={<IconButton accessibilityLabel="Thêm ảnh" icon="add" onPress={() => router.push("/moments/new")} />}
      />
      <Photo
        height={215}
        radius={23}
        source={demoAssets.road}
        overlay={
          <PhotoShade>
            <Text style={styles.albumKicker}>ĐÀ LẠT CUỐI TUẦN</Text>
            <Text style={styles.albumTitle}>Những ngày mình đi cùng nhau</Text>
            <Text style={styles.albumDate}>17–19 tháng 10, 2026 · Team Đà Lạt</Text>
          </PhotoShade>
        }
      />
      <Card style={styles.albumStats}>
        <View style={styles.summaryItem}>
          <Text style={[typography.money, { color: colors.ink }]}>{DEMO_GROUP.photos}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>ảnh</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.summaryItem}>
          <Text style={[typography.money, { color: colors.ink }]}>{DEMO_GROUP.videos}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>video</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.summaryItem}>
          <Text style={[typography.money, { color: colors.ink }]}>{DEMO_GROUP.checkIns}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>check-in</Text>
        </View>
      </Card>
      <Segmented items={["Tất cả", "Ảnh", "Video"]} onSelect={setSegment} selected={segment} />
      <View style={styles.albumToolbar}>
        <Text style={[typography.h2, { color: colors.ink }]}>
          {selecting ? `${selectedPhotos.length} ảnh đã chọn` : "Khoảnh khắc"}
        </Text>
        <Inline gap={7}>
          <Chip
            icon="calendar-outline"
            label={newestFirst ? "Mới trước" : "Theo ngày"}
            onPress={() => setNewestFirst((value) => !value)}
            selected={newestFirst}
          />
          <IconButton
            accessibilityLabel={selecting ? "Đóng chọn ảnh" : "Chọn ảnh"}
            icon={selecting ? "close-circle" : "checkmark-circle-outline"}
            onPress={toggleSelectionMode}
            selected={selecting}
          />
        </Inline>
      </View>
      <View style={styles.photoGrid}>
        {visiblePhotos.map(({ photo, originalIndex }, index) => {
          const selected = selectedPhotos.includes(originalIndex);
          return (
          <Pressable
            key={originalIndex}
            accessibilityLabel={
              selecting
                ? `${selected ? "Bỏ chọn" : "Chọn"} ảnh ${originalIndex + 1}`
                : `Mở ảnh ${originalIndex + 1}`
            }
            accessibilityRole={selecting ? "checkbox" : "button"}
            aria-checked={selecting ? selected : undefined}
            onPress={() => {
              if (!selecting) setSelecting(true);
              togglePhoto(originalIndex);
            }}
            style={({ pressed }) => [
              styles.gridPhoto,
              {
                width: widthPercent(100 / columns),
                paddingRight: index % columns === columns - 1 ? 0 : 4,
                height: index % 3 === 0 ? 190 : 145,
              },
              pressed && styles.pressed,
            ]}
          >
            <Photo height={index % 3 === 0 ? 186 : 141} radius={15} source={photo} />
            {videoIndexes.includes(originalIndex) ? (
              <View style={styles.videoBadge}>
                <Ionicons color="#FFFFFF" name="play" size={14} />
                <Text style={styles.videoText}>0:{originalIndex === 2 ? "18" : "24"}</Text>
              </View>
            ) : null}
            {selecting ? (
              <View style={[styles.selectionBadge, selected && { backgroundColor: colors.accent }]}>
                <Ionicons color="#FFFFFF" name={selected ? "checkmark" : "ellipse-outline"} size={17} />
              </View>
            ) : null}
          </Pressable>
          );
        })}
      </View>
      <RudiButton
        disabled={selecting && selectedPhotos.length === 0}
        icon={selecting ? "share-social-outline" : "cloud-upload-outline"}
        label={selecting ? `Chia sẻ ${selectedPhotos.length} ảnh` : "Thêm khoảnh khắc"}
        onPress={() => router.push("/moments/new")}
      />
    </RudiScreen>
  );
}

export function ShareMomentScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [caption, setCaption] = useState("Đà Lạt có lạnh, nhưng hội mình thì không 🌲✨");
  const [visibility, setVisibility] = useState(0);
  const [selectedPeople, setSelectedPeople] = useState([0, 1, 2, 3]);

  const toggle = (index: number) => {
    setSelectedPeople((items) => (items.includes(index) ? items.filter((item) => item !== index) : [...items, index]));
  };

  return (
    <RudiScreen testID="share-moment-screen">
      <TopBar title="Chia sẻ khoảnh khắc" right={<DemoBadge />} />
      <Photo
        height={330}
        radius={24}
        source={demoAssets.dalatFriends}
        overlay={
          <>
            <View style={styles.photoEditTop}>
              <IconButton accessibilityLabel="Cắt ảnh" icon="crop-outline" />
              <IconButton accessibilityLabel="Xóa ảnh" icon="trash-outline" />
            </View>
            <View style={styles.photoCount}>
              <Ionicons color="#FFFFFF" name="images" size={15} />
              <Text style={styles.photoCountText}>1 ảnh</Text>
            </View>
          </>
        }
      />
      <Field
        label="Viết vài dòng"
        multiline
        onChangeText={setCaption}
        placeholder="Kể hội bạn nghe về khoảnh khắc này..."
        value={caption}
      />
      <View style={styles.section}>
        <Text style={[typography.label, { color: colors.ink }]}>Gắn thẻ bạn bè</Text>
        <View style={styles.peoplePicker}>
          {PEOPLE.map((person, index) => {
            const active = selectedPeople.includes(index);
            return (
              <Pressable
                key={person.id}
                accessibilityRole="checkbox"
                aria-checked={active}
                onPress={() => toggle(index)}
                style={[styles.personPick, !active && styles.avatarInactive]}
              >
                <Avatar person={person} ring={active} size={45} />
                <Text numberOfLines={1} style={[styles.personName, { color: colors.inkSoft }]}>{person.name.split(" ")[0]}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <Card style={styles.locationRow}>
        <View style={[styles.locationIcon, { backgroundColor: colors.accentSoft }]}>
          <Ionicons color={colors.accent} name="location" size={21} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.label, { color: colors.ink }]}>Đà Lạt, Lâm Đồng</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Vị trí demo</Text>
        </View>
        <Ionicons color={colors.inkFaint} name="chevron-forward" size={19} />
      </Card>
      <View style={styles.section}>
        <Text style={[typography.label, { color: colors.ink }]}>Chia sẻ với</Text>
        <Segmented items={["Chỉ nhóm", "Bạn bè"]} onSelect={setVisibility} selected={visibility} />
      </View>
      <RudiButton
        icon="paper-plane-outline"
        label="Đăng vào tường nhóm"
        onPress={() => router.replace(("/groups/" + DEMO_GROUP.id + "/wall") as never)}
      />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  post: { gap: 13, padding: 11 },
  postHeader: { flexDirection: "row", alignItems: "center", gap: 10 },
  reactions: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  reactionDots: { width: 25, height: 25, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  postDivider: { height: StyleSheet.hairlineWidth },
  postAction: { minHeight: 36, flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 },
  pressed: { opacity: 0.7, transform: [{ scale: 0.985 }] },
  wallHero: { gap: 7 },
  wallTitle: { color: "#FFFFFF", fontSize: 28, lineHeight: 33, fontWeight: "900", letterSpacing: -0.8 },
  wallMeta: { flexDirection: "row", alignItems: "center", gap: 9 },
  wallMetaText: { color: "rgba(255,255,255,0.84)", fontSize: 12, fontWeight: "700" },
  memorySummary: { flexDirection: "row", alignItems: "center", paddingHorizontal: 8 },
  summaryItem: { flex: 1, alignItems: "center", gap: 3, paddingVertical: 6 },
  verticalLine: { width: StyleSheet.hairlineWidth, height: 37 },
  sharePrompt: { flexDirection: "row", alignItems: "center", gap: 9, padding: 10 },
  promptField: { flex: 1, minHeight: 43, borderWidth: 1, borderRadius: 15, paddingHorizontal: 12, justifyContent: "center" },
  photoAction: { width: 41, height: 41, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  albumKicker: { color: "rgba(255,255,255,0.74)", fontSize: 10, fontWeight: "900", letterSpacing: 1.1 },
  albumTitle: { color: "#FFFFFF", fontSize: 24, lineHeight: 29, fontWeight: "900", letterSpacing: -0.6 },
  albumDate: { color: "rgba(255,255,255,0.8)", fontSize: 11, fontWeight: "700" },
  albumStats: { flexDirection: "row", alignItems: "center", paddingHorizontal: 8 },
  albumToolbar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  photoGrid: { flexDirection: "row", flexWrap: "wrap", marginHorizontal: -2 },
  gridPhoto: { position: "relative", paddingLeft: 2, paddingBottom: 4 },
  selectionBadge: { position: "absolute", top: 9, right: 9, width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(15,10,8,0.5)", borderWidth: 2, borderColor: "#FFFFFF" },
  videoBadge: { position: "absolute", right: 9, bottom: 12, flexDirection: "row", alignItems: "center", gap: 3, borderRadius: 999, backgroundColor: "rgba(15,10,8,0.68)", paddingHorizontal: 7, paddingVertical: 5 },
  videoText: { color: "#FFFFFF", fontSize: 10, fontWeight: "800" },
  photoEditTop: { position: "absolute", top: 11, right: 11, flexDirection: "row", gap: 8 },
  photoCount: { position: "absolute", left: 11, bottom: 11, flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 9, paddingVertical: 6, borderRadius: 999, backgroundColor: "rgba(15,10,8,0.68)" },
  photoCountText: { color: "#FFFFFF", fontSize: 11, fontWeight: "800" },
  section: { gap: 10 },
  peoplePicker: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  personPick: { width: 60, alignItems: "center", gap: 4 },
  personName: { width: 60, textAlign: "center", fontSize: 10, fontWeight: "700" },
  avatarInactive: { opacity: 0.34 },
  locationRow: { flexDirection: "row", alignItems: "center", gap: 11 },
  locationIcon: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center" },
});
