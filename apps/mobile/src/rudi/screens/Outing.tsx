import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { DEMO_GROUP, PEOPLE, demoAssets, formatVnd } from "../fixtures";
import { noiLuu, noiLuuNgan } from "../luu-tru";
import { useRudiSession } from "../session";
import { lopPhu, mauSang, mucTrenAnh, phuMau, typography, useRudiTheme } from "../theme";
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
  ProgressBar,
  RudiButton,
  RudiScreen,
  TopBar,
} from "../ui";

export function CreateOutingScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const selected = session.selectedMemberIds;

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
          onChangeText={session.setTripName}
          placeholder="Ví dụ: Đà Lạt cuối tuần"
          value={session.tripName}
        />
        <Field
          icon="location-outline"
          label="Điểm đến"
          onChangeText={session.setDestination}
          placeholder="Đà Lạt, Lâm Đồng"
          value={session.destination}
        />
        <Inline gap={10}>
          <View style={styles.flex}>
            <Field icon="calendar-outline" label="Ngày đi" value={session.startDate} />
          </View>
          <View style={styles.flex}>
            <Field icon="calendar-outline" label="Ngày về" value={session.endDate} />
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
          <Pressable accessibilityRole="button" onPress={() => session.selectAllMembers()}>
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
                onPress={() => session.toggleMember(person.id)}
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
          <Text style={[typography.label, { color: colors.ink }]}>Nhờ Rủ Đi gợi ý lịch trình</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Dựa trên gu của {selected.length} thành viên</Text>
        </View>
        <Pressable
          accessibilityRole="switch"
          aria-checked={session.aiSuggest}
          onPress={() => session.setAiSuggest(!session.aiSuggest)}
          style={[styles.toggle, { backgroundColor: session.aiSuggest ? colors.ai : colors.line }]}
        >
          <View style={[styles.toggleThumb, !session.aiSuggest && { alignSelf: "flex-start" }]} />
        </Pressable>
      </Card>
      <RudiButton
        disabled={!session.tripName || selected.length === 0}
        icon="arrow-forward"
        label="Tạo cuộc hẹn"
        onPress={() => router.replace(session.tripPath("/timeline") as never)}
      />
    </RudiScreen>
  );
}

export function TripTimelineScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const [day, setDay] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const days = session.itinerary;
  const current = days[day] ?? days[0];

  return (
    <RudiScreen bottomInset={112} testID="trip-timeline-screen">
      <TopBar
        back={false}
        title={DEMO_GROUP.name}
        subtitle="17–19/10/2026"
        right={
          <IconButton
            accessibilityLabel="Tùy chọn"
            icon="ellipsis-horizontal"
            onPress={() => setMenuOpen((value) => !value)}
          />
        }
      />
      {menuOpen ? (
        <Card>
          <RudiButton
            label="Mở lịch trình AI"
            onPress={() => router.push(session.tripPath("/itinerary") as never)}
            variant="ghost"
          />
          <RudiButton label="Check-in nhóm" onPress={() => router.push("/check-ins/new")} variant="ghost" />
          <RudiButton
            label="Tường nhóm"
            onPress={() => router.push(("/groups/" + DEMO_GROUP.id + "/wall") as never)}
            variant="ghost"
          />
        </Card>
      ) : null}
      <Photo
        height={245}
        radius={24}
        source={demoAssets.road}
        overlay={
          <>
            <LinearGradient
              colors={[lopPhu.toi(0.02), lopPhu.toi(0.82)]}
              style={StyleSheet.absoluteFill}
            />
            <View style={styles.tripHeroBadge}><DemoBadge /></View>
            <View style={styles.tripHeroCopy}>
              <Text style={styles.tripKicker}>CHUYẾN ĐI SẮP TỚI</Text>
              <Text style={styles.tripTitle}>{session.tripName}</Text>
              <Inline gap={12}>
                <Inline gap={5}>
                  <Ionicons color={mucTrenAnh} name="calendar-outline" size={15} />
                  <Text style={styles.tripMeta}>3 ngày 2 đêm</Text>
                </Inline>
                <Inline gap={5}>
                  <Ionicons color={mucTrenAnh} name="people-outline" size={15} />
                  <Text style={styles.tripMeta}>{session.selectedMemberIds.length} người</Text>
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
          <Text style={[typography.caption, { color: colors.inkFaint }]}>{session.selectedMemberIds.length} đã tham gia</Text>
        </View>
        <View style={[styles.verticalLine, { backgroundColor: colors.line }]} />
        <View style={styles.overviewItem}>
          <Text style={[typography.money, { color: colors.accent }]}>46</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>ngày nữa</Text>
        </View>
      </Card>
      <View style={styles.daySelector}>
        {days.map((item, index) => (
          <Chip key={item.day} label={"Ngày " + (index + 1)} onPress={() => setDay(index)} selected={day === index} />
        ))}
      </View>
      <View style={styles.sectionTitleRow}>
        <View>
          <Text style={[typography.h2, { color: colors.ink }]}>{current.day}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>{current.items.length} hoạt động</Text>
        </View>
        <IconButton
          accessibilityLabel="Mở lịch trình AI"
          icon="sparkles"
          onPress={() => router.push(session.tripPath("/itinerary") as never)}
          selected
          tone="ai"
        />
      </View>
      <Card style={styles.scheduleCard}>
        {current.items.map((slot, index) => (
          <View key={slot.time + slot.title + index} style={styles.scheduleRow}>
            <View style={styles.scheduleTime}>
              <Text style={[typography.label, { color: colors.ink }]}>{slot.time}</Text>
              {index < current.items.length - 1 ? <View style={[styles.scheduleLine, { backgroundColor: colors.line }]} /> : null}
            </View>
            <View style={[styles.scheduleIcon, { backgroundColor: slot.color + "1A" }]}>
              <Ionicons color={slot.color} name={slot.icon as never} size={20} />
            </View>
            <View style={styles.flex}>
              <Text style={[typography.label, { color: colors.ink }]}>{slot.title}</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>{slot.placeId ? "Đã gắn địa điểm" : "Cả nhóm"}</Text>
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
  const session = useRudiSession();
  const arrived = session.checkedInIds.length;
  const missing = PEOPLE.filter((person) => !session.checkedInIds.includes(person.id));

  return (
    <RudiScreen testID="check-in-screen">
      <TopBar title="Check-in nhóm" right={<DemoBadge />} />
      <Card>
        <Text style={[typography.h2, { color: colors.ink }]}>{arrived}/{PEOPLE.length} thành viên đã tới</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Quảng trường Lâm Viên · Đà Lạt</Text>
        <AvatarStack max={8} people={PEOPLE.filter((person) => session.checkedInIds.includes(person.id))} />
      </Card>
      <Card style={session.locationSharing ? styles.shareOn : undefined}>
        <Inline gap={10}>
          <View style={styles.flex}>
            <Text style={[typography.label, { color: colors.ink }]}>
              {session.locationSharing ? "Đang chia sẻ vị trí đến 11:30" : "Chưa chia sẻ vị trí"}
            </Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>
              Opt-in, có hạn. Bản trải nghiệm không đọc GPS máy, trạng thái {noiLuu(session.luuTruSong)}.
            </Text>
          </View>
        </Inline>
        <RudiButton
          label={session.locationSharing ? "Dừng chia sẻ" : "Chia vị trí trực tiếp"}
          onPress={() => session.setLocationSharing(!session.locationSharing)}
          variant="outline"
        />
      </Card>
      <Card style={styles.mapPlaceholder}>
        <Ionicons color={colors.inkFaint} name="map-outline" size={36} />
        <Text style={[typography.label, { color: colors.ink }]}>Bản đồ Quảng trường Lâm Viên</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Placeholder. GPS thật là Pha D.</Text>
      </Card>
      <View style={styles.section}>
        <Text style={[typography.title, { color: colors.ink }]}>Ai đã tới</Text>
        {PEOPLE.map((person) => {
          const here = session.checkedInIds.includes(person.id);
          return (
            <Pressable
              key={person.id}
              accessibilityRole="checkbox"
              aria-checked={here}
              onPress={() => session.toggleCheckIn(person.id)}
              style={styles.checkRow}
            >
              <Avatar person={person} ring={here} size={40} />
              <View style={styles.flex}>
                <Text style={[typography.label, { color: colors.ink }]}>{person.name}</Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>{here ? "Đã check-in" : "Chưa tới"}</Text>
              </View>
              <Ionicons color={here ? colors.split : colors.inkFaint} name={here ? "checkmark-circle" : "ellipse-outline"} size={22} />
            </Pressable>
          );
        })}
      </View>
      {missing.length ? (
        <Text style={[typography.caption, { color: colors.warn }]}>
          {missing.map((person) => person.name).join(", ")} chưa check-in.
        </Text>
      ) : (
        <Text style={[typography.caption, { color: colors.split }]}>Đủ 8 người.</Text>
      )}
      <Card>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Điểm đến tiếp theo</Text>
        <Text style={[typography.title, { color: colors.ink }]}>Still Cafe · 10:00</Text>
      </Card>
      <Inline gap={10}>
        <RudiButton
          full={false}
          icon="notifications-outline"
          label="Nhắc thành viên"
          onPress={() => session.remindPending()}
          style={styles.flex}
          variant="outline"
        />
        <RudiButton
          full={false}
          icon="location"
          label="Đánh dấu tôi đã tới"
          onPress={() => {
            session.checkInSelf();
            router.replace(("/groups/" + DEMO_GROUP.id + "/wall") as never);
          }}
          style={styles.flex}
        />
      </Inline>
      {session.remindedPending ? (
        <Text style={[typography.caption, styles.demoNote, { color: colors.accent }]}>
          Đã ghi nhắc {missing.length} người {noiLuuNgan(session.luuTruSong)}. Chưa gửi push.
        </Text>
      ) : null}
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
  toggleThumb: { width: 23, height: 23, borderRadius: 12, backgroundColor: mucTrenAnh },
  pressed: { opacity: 0.75, transform: [{ scale: 0.98 }] },
  tripHeroBadge: { position: "absolute", right: 12, top: 12 },
  tripHeroCopy: { position: "absolute", left: 18, right: 18, bottom: 17, gap: 7 },
  tripKicker: { color: lopPhu.trang(0.78), fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  tripTitle: { color: mucTrenAnh, fontSize: 29, lineHeight: 34, fontWeight: "900", letterSpacing: -0.8 },
  tripMeta: { color: mucTrenAnh, fontSize: 12, fontWeight: "700" },
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
  locationCard: { flexDirection: "row", alignItems: "center", gap: 10, padding: 11, borderRadius: 16, backgroundColor: lopPhu.xam(0.58), borderWidth: 1, borderColor: lopPhu.trang(0.24) },
  locationPin: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  locationTitle: { color: mucTrenAnh, fontSize: 15, fontWeight: "800" },
  locationSubtitle: { color: lopPhu.trang(0.75), fontSize: 11, fontWeight: "600" },
  taggedCard: { gap: 10 },
  demoNote: { textAlign: "center", paddingHorizontal: 20 },
  mapPlaceholder: { minHeight: 160, alignItems: "center", justifyContent: "center", gap: 8 },
  checkRow: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: 10 },
  shareOn: { borderColor: phuMau(mauSang.split, 0.35) },
});
