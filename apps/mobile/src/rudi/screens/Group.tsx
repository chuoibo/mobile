import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { DEMO_GROUP, PEOPLE, PLACES, VOTE_PLACE_IDS } from "../fixtures";
import { noiLuu } from "../luu-tru";
import { useRudiSession } from "../session";
import { mucTrenAnh, typography, useRudiTheme } from "../theme";
import {
  AiNote,
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
  SectionHeader,
  TopBar,
} from "../ui";

function ChatBubble({
  person,
  time,
  children,
  own = false,
}: {
  person: (typeof PEOPLE)[number];
  time: string;
  children: string;
  own?: boolean;
}) {
  const { colors } = useRudiTheme();
  return (
    <View style={[styles.messageRow, own && styles.messageOwn]}>
      {!own ? <Avatar person={person} size={34} /> : null}
      <View style={[styles.messageBlock, own && styles.messageBlockOwn]}>
        {!own ? <Text style={[styles.sender, { color: person.color }]}>{person.name}</Text> : null}
        <View
          style={[
            styles.bubble,
            {
              backgroundColor: own ? colors.accent : colors.card,
              borderColor: own ? colors.accent : colors.line,
            },
          ]}
        >
          <Text style={[typography.body, { color: own ? colors.accentInk : colors.ink }]}>{children}</Text>
        </View>
        <Text style={[styles.messageTime, { color: colors.inkFaint }]}>{time}</Text>
      </View>
    </View>
  );
}

export function GroupChatScreen({ embeddedInTabs = false }: { embeddedInTabs?: boolean } = {}) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const [draft, setDraft] = useState("");
  const [attachmentOpen, setAttachmentOpen] = useState(false);

  const sendMessage = () => {
    const message = draft.trim();
    if (!message) return;
    session.sendChat(message);
    setDraft("");
    setAttachmentOpen(false);
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  };

  const attach = (label: string) => {
    setDraft((current) => `${current}${current ? " " : ""}${label}`);
    setAttachmentOpen(false);
  };

  const composer = (
    <View style={styles.composerShell}>
      {attachmentOpen ? (
        <Card style={styles.attachmentTray}>
          <Chip icon="images-outline" label="Ảnh" onPress={() => attach("[Ảnh chuyến đi]")} />
          <Chip icon="location-outline" label="Vị trí" onPress={() => attach("[Vị trí]")} />
          <Chip icon="receipt-outline" label="Chi phí" onPress={() => attach("[Khoản chi]")} />
        </Card>
      ) : null}
      <Card style={styles.composer}>
        <IconButton
          accessibilityLabel={attachmentOpen ? "Đóng tệp đính kèm" : "Đính kèm"}
          icon={attachmentOpen ? "close" : "add-circle-outline"}
          onPress={() => setAttachmentOpen((value) => !value)}
          quiet
          selected={attachmentOpen}
        />
        <View style={styles.flex}>
          <Field
            onChangeText={setDraft}
            onSubmitEditing={sendMessage}
            placeholder="Nhắn Team Đà Lạt..."
            returnKeyType="send"
            value={draft}
          />
        </View>
        <IconButton
          accessibilityLabel="Gửi tin nhắn"
          icon="arrow-up"
          onPress={sendMessage}
          selected={draft.trim().length > 0}
        />
      </Card>
    </View>
  );

  return (
    <RudiScreen
      bottomInset={16}
      footer={composer}
      footerInset={embeddedInTabs ? 92 : 14}
      testID="group-chat-screen"
    >
      <TopBar
        back={!embeddedInTabs}
        title={DEMO_GROUP.name}
        subtitle="8 thành viên · đang hoạt động"
        right={
          <IconButton
            accessibilityLabel="Thông tin nhóm"
            icon="information-circle-outline"
            onPress={() => router.push(("/groups/" + DEMO_GROUP.id + "/wall") as never)}
          />
        }
      />
      <Card onPress={() => router.push(session.tripPath("/timeline") as never)} style={styles.tripPin}>
        <Photo height={74} radius={14} source={PLACES[2].image} style={styles.tripPinPhoto} />
        <View style={styles.tripPinText}>
          <Text style={[typography.caption, { color: colors.accent }]}>CHUYẾN ĐI SẮP TỚI</Text>
          <Text style={[typography.title, { color: colors.ink }]}>{DEMO_GROUP.tripName}</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>17–19/10/2026 · 8 người</Text>
        </View>
        <Ionicons color={colors.inkFaint} name="chevron-forward" size={20} />
      </Card>
      <View style={styles.dayDivider}>
        <View style={[styles.line, { backgroundColor: colors.line }]} />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Hôm nay</Text>
        <View style={[styles.line, { backgroundColor: colors.line }]} />
      </View>
      <View style={styles.messages}>
        <ChatBubble person={PEOPLE[1]} time="09:42">Cuối tuần tháng 10 đi Đà Lạt không mọi người?</ChatBubble>
        <ChatBubble person={PEOPLE[2]} time="09:44">Đi chứ! Tớ vote săn mây với BBQ nha 🌤️</ChatBubble>
        <ChatBubble person={PEOPLE[0]} time="09:46" own>Để Rủ Đi gom gu rồi lên lịch trình thử nhé.</ChatBubble>
        <Card style={styles.aiChatCard} tone="ai">
          <View style={styles.aiChatHeader}>
            <View style={[styles.aiOrb, { backgroundColor: colors.ai }]}>
              <Ionicons color={colors.aiInk} name="sparkles" size={18} />
            </View>
            <View style={styles.flex}>
              <Text style={[typography.title, { color: colors.ink }]}>Rủ Đi đã phác một plan</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>3 ngày 2 đêm · trong ngân sách</Text>
            </View>
            <DemoBadge label="AI nháp" />
          </View>
          <AiNote>
            Mình ưu tiên đồ ăn local, săn mây và các điểm di chuyển gần nhau để nhóm đỡ mệt.
          </AiNote>
          <View style={styles.aiStats}>
            <View style={styles.aiStat}>
              <Text style={[typography.title, { color: colors.ai }]}>9</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>điểm đến</Text>
            </View>
            <View style={[styles.statLine, { backgroundColor: colors.line }]} />
            <View style={styles.aiStat}>
              <Text style={[typography.title, { color: colors.ai }]}>~2,1M</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>mỗi người</Text>
            </View>
            <View style={[styles.statLine, { backgroundColor: colors.line }]} />
            <View style={styles.aiStat}>
              <Text style={[typography.title, { color: colors.ai }]}>Rất hợp</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>gu của nhóm</Text>
            </View>
          </View>
          <Inline gap={9}>
            <RudiButton
              full={false}
              label="Xem lịch trình"
              onPress={() => router.push(session.tripPath("/itinerary") as never)}
              style={styles.flex}
              tone="ai"
            />
            <IconButton
              accessibilityLabel="Mở bình chọn"
              icon="stats-chart-outline"
              onPress={() => router.push("/votes/diem-den")}
              tone="ai"
            />
          </Inline>
        </Card>
        <ChatBubble person={PEOPLE[3]} time="09:51">Plan xịn đó, mình bình chọn chỗ BBQ trước đi.</ChatBubble>
        {session.chatMessages.map((message, index) => (
          <ChatBubble key={`${message}-${index}`} person={PEOPLE[0]} time="Bây giờ" own>
            {message}
          </ChatBubble>
        ))}
      </View>
    </RudiScreen>
  );
}

export function AiItineraryScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const [activeDay, setActiveDay] = useState(0);
  const days = session.itinerary;
  const day = days[activeDay] ?? days[0];

  return (
    <RudiScreen tone="ai" testID="ai-itinerary-screen">
      <TopBar title="Lịch trình AI" right={<DemoBadge label="AI nháp" />} />
      <Card style={styles.itineraryHero} tone="ai">
        <Inline gap={12}>
          <View style={[styles.itineraryIcon, { backgroundColor: colors.ai }]}>
            <Ionicons color={colors.aiInk} name="map" size={25} />
          </View>
          <View style={styles.flex}>
            <Text style={[typography.h2, { color: colors.ink }]}>{session.tripName}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>17–19/10/2026 · 3 ngày 2 đêm</Text>
          </View>
        </Inline>
        <AiNote>
          Lịch trình xếp theo quãng đường. Chỉnh bằng nút lên/xuống hoặc xoá slot. Chưa kéo thả được.
        </AiNote>
      </Card>
      <View style={styles.dayTabs}>
        {days.map((item, index) => (
          <Chip
            key={item.day}
            label={"Ngày " + (index + 1)}
            onPress={() => setActiveDay(index)}
            selected={activeDay === index}
            tone="ai"
          />
        ))}
      </View>
      <Heading
        size="h2"
        title={day.day}
        subtitle={session.itineraryEditing ? "Đang chỉnh: lên, xuống hoặc xoá." : "Xem trước. Bấm Chỉnh lịch trình để sửa."}
      />
      <Card style={styles.timelineCard}>
        {day.items.map((slot, index) => (
          <View key={slot.time + slot.title + index} style={styles.timelineItem}>
            <View style={styles.timelineRail}>
              <View style={[styles.timelineDot, { backgroundColor: slot.color }]}>
                <Ionicons color={mucTrenAnh} name={slot.icon as never} size={16} />
              </View>
              {index < day.items.length - 1 ? (
                <View style={[styles.timelineLine, { backgroundColor: colors.line }]} />
              ) : null}
            </View>
            <Text style={[typography.caption, styles.timelineTime, { color: colors.inkFaint }]}>{slot.time}</Text>
            <View style={styles.timelineCopy}>
              <Text style={[typography.label, { color: colors.ink }]}>{slot.title}</Text>
              <Text style={[typography.caption, { color: colors.inkFaint }]}>
                {slot.placeId ? "Đã gắn địa điểm" : "Có thể thay đổi"}
              </Text>
            </View>
            {session.itineraryEditing ? (
              <Inline gap={4}>
                <IconButton accessibilityLabel="Lên" icon="chevron-up" onPress={() => session.moveItinerarySlot(activeDay, index, -1)} quiet />
                <IconButton accessibilityLabel="Xuống" icon="chevron-down" onPress={() => session.moveItinerarySlot(activeDay, index, 1)} quiet />
                <IconButton accessibilityLabel="Xóa" icon="trash-outline" onPress={() => session.removeItinerarySlot(activeDay, index)} quiet />
              </Inline>
            ) : (
              <Ionicons color={colors.inkFaint} name="reorder-three-outline" size={21} />
            )}
          </View>
        ))}
      </Card>
      <Card style={styles.budgetBar}>
        <View>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Dự kiến mỗi người</Text>
          <Text style={[typography.money, { color: colors.ink }]}>2.100.000đ</Text>
        </View>
        <View style={styles.budgetRight}>
          <Text style={[typography.caption, { color: colors.ai }]}>Còn 400.000đ ngân sách</Text>
          <ProgressBar tone="ai" value={84} />
        </View>
      </Card>
      <Inline gap={10}>
        <RudiButton
          full={false}
          icon="create-outline"
          label={session.itineraryEditing ? "Xong chỉnh" : "Chỉnh lịch trình"}
          onPress={() => session.setItineraryEditing(!session.itineraryEditing)}
          style={styles.flex}
          tone="ai"
          variant="outline"
        />
        <RudiButton
          full={false}
          icon="checkmark-circle-outline"
          label="Dùng plan này"
          onPress={() => {
            session.setItineraryEditing(false);
            router.replace(session.tripPath("/timeline") as never);
          }}
          style={styles.flex}
          tone="ai"
        />
      </Inline>
    </RudiScreen>
  );
}

const VOTE_OPTIONS = VOTE_PLACE_IDS.map((id) => PLACES.find((place) => place.id === id)!);

export function VotingScreen() {
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const totalVotes = session.voteTallies.reduce((sum, n) => sum + n, 0);

  return (
    <RudiScreen testID="voting-screen">
      <TopBar title="Bình chọn" right={<DemoBadge />} />
      <Heading
        title="BBQ tối thứ Bảy ở đâu?"
        subtitle="Mỗi người chọn một nơi. Kết quả chỉ hiện sau khi bạn xác nhận."
      />
      <Inline gap={8}>
        <Chip icon="people-outline" label="8 đã xem" />
        <Chip icon="time-outline" label="Còn 3 giờ" selected />
      </Inline>
      <View style={styles.voteList}>
        {VOTE_OPTIONS.map((place, index) => {
          const active = session.voteChoice === index;
          const votes = session.voteTallies[index];
          const percent = session.voteConfirmed && totalVotes > 0 ? (votes * 100) / totalVotes : 0;
          return (
            <Pressable
              key={place.id}
              accessibilityRole="radio"
              aria-checked={active}
              onPress={() => session.setVoteChoice(index)}
              style={({ pressed }) => [
                styles.voteOption,
                {
                  backgroundColor: active ? colors.accentSoft : colors.card,
                  borderColor: active ? colors.accent : colors.line,
                },
                pressed && styles.pressed,
              ]}
            >
              <Photo height={112} radius={15} source={place.image} />
              <View style={styles.voteBody}>
                <View style={styles.voteTitleRow}>
                  <View style={styles.flex}>
                    <Text style={[typography.title, { color: colors.ink }]}>{place.name}</Text>
                    <Text style={[typography.caption, { color: colors.inkFaint }]}>{place.distance} · {place.price}</Text>
                  </View>
                  <Ionicons color={active ? colors.accent : colors.lineStrong} name={active ? "checkmark-circle" : "ellipse-outline"} size={25} />
                </View>
                {session.voteConfirmed ? (
                  <>
                    <ProgressBar value={percent} />
                    <View style={styles.voteMeta}>
                      <Text style={[typography.caption, { color: colors.inkSoft }]}>{votes} phiếu của bạn trên bản này</Text>
                    </View>
                  </>
                ) : (
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>
                    Kết quả ẩn đến khi xác nhận. Bản trải nghiệm chỉ ghi phiếu của bạn.
                  </Text>
                )}
              </View>
            </Pressable>
          );
        })}
      </View>
      {session.voteConfirmed && session.voteChoice !== null ? (
        <Card style={styles.voteSummary}>
          <View style={[styles.trophy, { backgroundColor: colors.accentSoft }]}>
            <Ionicons color={colors.accent} name="trophy" size={25} />
          </View>
          <View style={styles.flex}>
            <Text style={[typography.title, { color: colors.ink }]}>Bạn đã chọn {VOTE_OPTIONS[session.voteChoice].name}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>
              Phiếu {noiLuu(session.luuTruSong)}. Chưa gửi lên máy chủ.
            </Text>
          </View>
        </Card>
      ) : null}
      <RudiButton
        disabled={session.voteChoice === null}
        icon="checkmark"
        label={session.voteConfirmed ? "Đã xác nhận" : "Xác nhận lựa chọn của tôi"}
        onPress={() => session.confirmVote()}
      />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  tripPin: { flexDirection: "row", alignItems: "center", gap: 12, padding: 8 },
  tripPinPhoto: { width: 94 },
  tripPinText: { flex: 1, gap: 2 },
  dayDivider: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 20 },
  line: { flex: 1, height: StyleSheet.hairlineWidth },
  messages: { gap: 15 },
  messageRow: { flexDirection: "row", alignItems: "flex-end", gap: 8, maxWidth: "88%" },
  messageOwn: { alignSelf: "flex-end", justifyContent: "flex-end" },
  messageBlock: { alignItems: "flex-start", gap: 3 },
  messageBlockOwn: { alignItems: "flex-end" },
  sender: { fontSize: 11, lineHeight: 14, fontWeight: "800", marginLeft: 7 },
  bubble: { borderWidth: 1, borderRadius: 17, borderBottomLeftRadius: 5, paddingHorizontal: 13, paddingVertical: 10 },
  messageTime: { fontSize: 10, lineHeight: 12, paddingHorizontal: 7 },
  aiChatCard: { gap: 13 },
  aiChatHeader: { flexDirection: "row", alignItems: "center", gap: 10 },
  aiOrb: { width: 40, height: 40, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  aiStats: { flexDirection: "row", alignItems: "center", justifyContent: "space-around" },
  aiStat: { flex: 1, alignItems: "center", gap: 2 },
  statLine: { width: StyleSheet.hairlineWidth, height: 32 },
  composerShell: { gap: 8 },
  attachmentTray: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7, padding: 7 },
  composer: { flexDirection: "row", alignItems: "center", gap: 6, padding: 6 },
  itineraryHero: { gap: 14 },
  itineraryIcon: { width: 50, height: 50, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  dayTabs: { flexDirection: "row", gap: 8 },
  timelineCard: { paddingVertical: 7 },
  timelineItem: { minHeight: 70, flexDirection: "row", alignItems: "flex-start", gap: 9 },
  timelineRail: { width: 38, alignItems: "center", alignSelf: "stretch" },
  timelineDot: { width: 34, height: 34, borderRadius: 12, alignItems: "center", justifyContent: "center", zIndex: 1 },
  timelineLine: { position: "absolute", top: 33, bottom: -1, width: 2 },
  timelineTime: { width: 42, paddingTop: 8 },
  timelineCopy: { flex: 1, gap: 3, paddingTop: 6 },
  budgetBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 20 },
  budgetRight: { flex: 1, gap: 7, alignItems: "flex-end" },
  voteList: { gap: 11 },
  voteOption: { flexDirection: "row", gap: 11, borderRadius: 20, borderWidth: 1, padding: 8 },
  voteBody: { flex: 1, gap: 10, paddingVertical: 4, paddingRight: 4 },
  voteTitleRow: { flexDirection: "row", alignItems: "flex-start", gap: 7 },
  voteMeta: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  voteSummary: { flexDirection: "row", alignItems: "center", gap: 12 },
  trophy: { width: 48, height: 48, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  pressed: { opacity: 0.78, transform: [{ scale: 0.992 }] },
});
