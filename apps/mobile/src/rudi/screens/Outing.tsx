import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { DEMO_GROUP, ITINERARY, PEOPLE, demoAssets, formatVnd } from "../fixtures";
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
  ProgressBar,
  RudiButton,
  RudiScreen,
  Segmented,
  TopBar,
} from "../ui";

export function CreateOutingScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [tripName, setTripName] = useState(DEMO_GROUP.tripName);
  const [selected, setSelected] = useState(PEOPLE.map((person) => person.id));

  const toggleMember = (id: string) => {
    setSelected((items) => (items.includes(id) ? items.filter((item) => item !== id) : [...items, id]));
  };

  return (
    <RudiScreen testID="create-outing-screen">
      <TopBar title="Tạo cuộc hẹn" right={<DemoBadge />} />
      <Heading
        title="Hội mình đi đâu?"
        subtitle="Tạo một nơi chung để chốt ngày, rủ bạn và cùng nhau lên plan."
      />
      <Card style={styles.formCard}>
        <Field
          icon="sparkles-outline"
          label="Tên cuộc hẹn"
          onChangeText={setTripName}
          placeholder="Ví dụ: Đà Lạt cuối tuần"
          value={tripName}
        />
        <Field
          icon="location-outline"
          label="Điểm đến"
          placeholder="Đà Lạt, Lâm Đồng"
          value="Đà Lạt, Lâm Đồng"
        />
        <Inline gap={10}>
          <View style={styles.flex}>
            <Field icon="calendar-outline" label="Ngày đi" value="17/10/2026" />
          </View>
          <View style={styles.flex}>
            <Field icon="calendar-outline" label="Ngày về" value="19/10/2026" />
          </View>
        </Inline>
        <Field
          icon="wallet-outline"
          keyboardType="number-pad"
          label="Ngân sách mỗi người"
          value={formatVnd(DEMO_GROUP.budgetPerPersonVnd)}
        />
      </Card>
      <View style={styles.section}>
        <View style={styles.sectionTitleRow}>
          <View>
            <Text style={[typography.title, { color: colors.ink }]}>Rủ hội bạn</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{selected.length}/8 thành viên được chọn</Text>
          </View>
          <Pressable accessibilityRole="button">
            <Text style={[typography.label, { color: colors.accent }]}>Chọn tất cả</Text>
          </Pressable>
        </View>
        <View style={styles.memberGrid}>
          {PEOPLE.map((person) => {
            const active = selected.includes(person.id);
            return (
              <Pressable
                key={person.id}
                accessibilityRole="checkbox"
                aria-checked={active}
                onPress={() => toggleMember(person.id)}
                style={({ pressed }) => [
                  styles.member,
                  {
                    backgroundColor: active ? colors.accentSoft : colors.card,
                    borderColor: active ? colors.accent : colors.line,
                  },
                  pressed && styles.pressed,
                ]}
              >
                <View>
                  <Avatar person={person} ring={active} size={46} />
                  {active ? (
                    <View style={[styles.memberCheck, { backgroundColor: colors.accent }]}>
                      <Ionicons color={colors.accentInk} name="checkmark" size={11} />
                    </View>
                  ) : null}
                </View>
                <Text numberOfLines={1} style={[typography.caption, { color: colors.ink }]}>{person.name.split(" ")[0]}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <Card style={styles.switchCard}>
        <View style={[styles.switchIcon, { backgroundColor: colors.aiSoft }]}>
          <Ionicons color={colors.ai} name="sparkles" size={22} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.label, { color: colors.ink }]}>Nhờ RuDi gợi ý lịch trình</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Dựa trên gu của {selected.length} thành viên</Text>
        </View>
        <View style={[styles.toggle, { backgroundColor: colors.ai }]}>
          <View style={styles.toggleThumb} />
        </View>
      </Card>
      <RudiButton
        disabled={!tripName || selected.length === 0}
        icon="arrow-forward"
        label="Tạo cuộc hẹn"
        onPress={() => router.replace(("/trips/" + DEMO_GROUP.id + "/timeline") as never)}
      />
    </RudiScreen>
  );
}

export function TripTimelineScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [day, setDay] = useState(0);

  return (
    <RudiScreen bottomInset={112} testID="trip-timeline-screen">
      <TopBar
        back={false}
        title={DEMO_GROUP.name}
        subtitle="17–19/10/2026"
        right={<IconButton accessibilityLabel="Tùy chọn" icon="ellipsis-horizontal" />}
      />
      <Photo
        height={245}
        radius={24}
        source={demoAssets.road}
        overlay={
          <>
            <LinearGradient
              colors={["rgba(20,8,2,0.02)", "rgba(30,10,3,0.82)"]}
              style={StyleSheet.absoluteFill}
            />
            <View style={styles.tripHeroBadge}><DemoBadge /></View>
            <View style={styles.tripHeroCopy}>
              <Text style={styles.tripKicker}>CHUYẾN ĐI SẮP TỚI</Text>
              <Text style={styles.tripTitle}>{DEMO_GROUP.tripName}</Text>
              <Inline gap={12}>
                <Inline gap={5}>
                  <Ionicons color="#FFFFFF" name="calendar-outline" size={15} />
                  <Text style={styles.tripMeta}>3 ngày 2 đêm</Text>
                </Inline>
                <Inline gap={5}>
                  <Ionicons color="#FFFFFF" name="people-outline" size={15} />
                  <Text style={styles.tripMeta}>8 người</Text>
                </Inline>
              </Inline>
            </View>
          </>
        }
      />
      <Card style={styles.tripOverview}>
        <View style={styles.overviewItem}>
          <Text style={[typography.money, { color: colors.ink }]}>2,1M</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>dự kiến/người</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.overviewItem}>
          <AvatarStack max={4} people={PEOPLE} />
          <Text style={[typography.caption, { color: colors.inkFaint }]}>8 đã tham gia</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.overviewItem}>
          <Text style={[typography.money, { color: colors.accent }]}>46</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>ngày nữa</Text>
        </View>
      </Card>
      <View style={styles.daySelector}>
        {ITINERARY.map((item, index) => (
          <Chip key={item.day} label={"Ngày " + (index + 1)} onPress={() => setDay(index)} selected={day === index} />
        ))}
      </View>
      <View style={styles.sectionTitleRow}>
        <View>
          <Text style={[typography.h2, { color: colors.ink }]}>{ITINERARY[day].day}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>{ITINERARY[day].items.length} hoạt động</Text>
        </View>
        <IconButton
          accessibilityLabel="Mở lịch trình AI"
          icon="sparkles"
          onPress={() => router.push(("/trips/" + DEMO_GROUP.id + "/itinerary") as never)}
          selected
          tone="ai"
        />
      </View>
      <Card style={styles.scheduleCard}>
        {ITINERARY[day].items.map(([time, title, icon, color], index) => (
          <View key={time + title} style={styles.scheduleRow}>
            <View style={styles.scheduleTime}>
              <Text style={[typography.label, { color: colors.ink }]}>{time}</Text>
              {index < ITINERARY[day].items.length - 1 ? <View style={[styles.scheduleLine, { backgroundColor: colors.line }]} /> : null}
            </View>
            <View style={[styles.scheduleIcon, { backgroundColor: color + "1A" }]}>
              <Ionicons color={color} name={icon} size={20} />
            </View>
            <View style={styles.flex}>
              <Text style={[typography.label, { color: colors.ink }]}>{title}</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>{index % 2 ? "Cả nhóm" : "Đã xác nhận"}</Text>
            </View>
            <Ionicons color={colors.inkFaint} name="chevron-forward" size={18} />
          </View>
        ))}
      </Card>
      <Card onPress={() => router.push("/check-ins/new")} style={styles.checkInCta}>
        <View style={[styles.checkInIcon, { backgroundColor: colors.accent }]}>
          <Ionicons color={colors.accentInk} name="location" size={22} />
        </View>
        <View style={styles.flex}>
          <Text style={[typography.title, { color: colors.ink }]}>Đến nơi rồi?</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Check-in để giữ lại khoảnh khắc cùng nhóm.</Text>
        </View>
        <Ionicons color={colors.accent} name="arrow-forward-circle" size={26} />
      </Card>
    </RudiScreen>
  );
}

export function CheckInScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [visibility, setVisibility] = useState(0);
  const [caption, setCaption] = useState("Cả hội vừa chạm Đà Lạt rồi! 🌲");

  return (
    <RudiScreen testID="check-in-screen">
      <TopBar title="Check-in" right={<DemoBadge />} />
      <Photo
        height={315}
        radius={24}
        source={demoAssets.dalatFriends}
        overlay={
          <PhotoShade>
            <View style={styles.locationCard}>
              <View style={[styles.locationPin, { backgroundColor: colors.accent }]}>
                <Ionicons color={colors.accentInk} name="location" size={19} />
              </View>
              <View style={styles.flex}>
                <Text style={styles.locationTitle}>Quảng trường Lâm Viên</Text>
                <Text style={styles.locationSubtitle}>Đà Lạt, Lâm Đồng · vừa xong</Text>
              </View>
              <Ionicons color="#FFFFFF" name="checkmark-circle" size={22} />
            </View>
          </PhotoShade>
        }
      />
      <Field
        label="Khoảnh khắc này có gì?"
        multiline
        onChangeText={setCaption}
        placeholder="Kể hội bạn nghe..."
        value={caption}
      />
      <Card style={styles.taggedCard}>
        <View style={styles.sectionTitleRow}>
          <View>
            <Text style={[typography.label, { color: colors.ink }]}>Cùng với</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>8 thành viên Team Đà Lạt</Text>
          </View>
          <AvatarStack max={5} people={PEOPLE} />
        </View>
      </Card>
      <View style={styles.section}>
        <Text style={[typography.label, { color: colors.ink }]}>Ai có thể xem?</Text>
        <Segmented
          items={["Chỉ nhóm", "Bạn bè"]}
          onSelect={setVisibility}
          selected={visibility}
        />
      </View>
      <Inline gap={10}>
        <RudiButton
          full={false}
          icon="camera-outline"
          label="Đổi ảnh"
          style={styles.flex}
          variant="outline"
        />
        <RudiButton
          full={false}
          icon="paper-plane-outline"
          label="Đăng check-in"
          onPress={() => router.replace(("/groups/" + DEMO_GROUP.id + "/wall") as never)}
          style={styles.flex}
        />
      </Inline>
      <Text style={[typography.caption, styles.demoNote, { color: colors.inkFaint }]}>
        Ảnh và vị trí trên màn này là dữ liệu minh họa, không phải vị trí thực.
      </Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  formCard: { gap: 15 },
  section: { gap: 10 },
  sectionTitleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  memberGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  member: { flexBasis: 72, flexGrow: 1, alignItems: "center", gap: 7, borderWidth: 1, borderRadius: 17, padding: 10 },
  memberCheck: { position: "absolute", right: -3, bottom: -2, width: 18, height: 18, borderRadius: 9, alignItems: "center", justifyContent: "center" },
  switchCard: { flexDirection: "row", alignItems: "center", gap: 11 },
  switchIcon: { width: 43, height: 43, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  toggle: { width: 50, height: 29, borderRadius: 999, padding: 3, alignItems: "flex-end" },
  toggleThumb: { width: 23, height: 23, borderRadius: 12, backgroundColor: "#FFFFFF" },
  pressed: { opacity: 0.75, transform: [{ scale: 0.98 }] },
  tripHeroBadge: { position: "absolute", right: 12, top: 12 },
  tripHeroCopy: { position: "absolute", left: 18, right: 18, bottom: 17, gap: 7 },
  tripKicker: { color: "rgba(255,255,255,0.78)", fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  tripTitle: { color: "#FFFFFF", fontSize: 29, lineHeight: 34, fontWeight: "900", letterSpacing: -0.8 },
  tripMeta: { color: "#FFFFFF", fontSize: 12, fontWeight: "700" },
  tripOverview: { minHeight: 94, flexDirection: "row", alignItems: "center", paddingHorizontal: 10 },
  overviewItem: { flex: 1, alignItems: "center", justifyContent: "center", gap: 4 },
  verticalLine: { width: StyleSheet.hairlineWidth, height: 44 },
  daySelector: { flexDirection: "row", gap: 8 },
  scheduleCard: { paddingVertical: 8 },
  scheduleRow: { minHeight: 64, flexDirection: "row", alignItems: "flex-start", gap: 10 },
  scheduleTime: { width: 47, alignItems: "center", alignSelf: "stretch", paddingTop: 10 },
  scheduleLine: { position: "absolute", top: 32, bottom: -1, width: 2 },
  scheduleIcon: { width: 40, height: 40, borderRadius: 13, alignItems: "center", justifyContent: "center", marginTop: 2 },
  checkInCta: { flexDirection: "row", alignItems: "center", gap: 12 },
  checkInIcon: { width: 46, height: 46, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  locationCard: { flexDirection: "row", alignItems: "center", gap: 10, padding: 11, borderRadius: 16, backgroundColor: "rgba(16,11,8,0.58)", borderWidth: 1, borderColor: "rgba(255,255,255,0.24)" },
  locationPin: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  locationTitle: { color: "#FFFFFF", fontSize: 15, fontWeight: "800" },
  locationSubtitle: { color: "rgba(255,255,255,0.75)", fontSize: 11, fontWeight: "600" },
  taggedCard: { gap: 10 },
  demoNote: { textAlign: "center", paddingHorizontal: 20 },
});
