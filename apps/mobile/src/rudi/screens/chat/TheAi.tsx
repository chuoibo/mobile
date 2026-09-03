/**
 * Server cards inside the chat (M3): text, places, itinerary, poll, expense draft.
 *
 * Every card is read through `docTheAi`, which trusts nothing about the shape.
 * The poll card carries only ids and labels; counts and «phiếu của tôi» come
 * from `GET /votes/{id}` and a tap goes to `POST /votes/{id}/ballots` -- the
 * vote table is the truth, never a card. An expense draft is shown as exactly
 * that: numbers the server read from chat, marked as needing review, with no
 * button that could turn them into a ledger entry from here (M5 owns that).
 */
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, boPhieu, docBinhChon, thongDiepNguoiDoc, type CuocBinhChonWire } from "../../../api";
import { type TheAi } from "../../chat/tin-song";
import { typography, useRudiTheme } from "../../theme";
import { AiNote, Card } from "../../ui";

function tienVnd(n: number): string {
  return `${new Intl.NumberFormat("vi-VN").format(n)}đ`;
}

export function TheAiView({
  the,
  contextId,
  personId,
  tenNguoi,
}: {
  the: TheAi;
  contextId: string;
  personId: string;
  tenNguoi: (id: string | null) => string;
}) {
  const { colors } = useRudiTheme();
  switch (the.loai) {
    case "text":
      return (
        <Card tone="ai" style={styles.card}>
          <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI</Text>
          <Text style={[typography.body, { color: colors.ink }]}>{the.text}</Text>
        </Card>
      );
    case "places":
      return (
        <Card tone="ai" style={styles.card}>
          <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI gợi ý</Text>
          <Text style={[typography.title, { color: colors.ink }]}>{the.title}</Text>
          {the.items.map((it) => (
            <View key={it.place_id} style={styles.dong}>
              <Text style={[typography.body, { color: colors.ink }]}>{it.name ?? "Địa điểm trong danh mục"}</Text>
              {it.reason ? <Text style={[typography.caption, { color: colors.inkSoft }]}>{it.reason}</Text> : null}
            </View>
          ))}
        </Card>
      );
    case "itinerary":
      return (
        <Card tone="ai" style={styles.card}>
          <Text style={[typography.caption, { color: colors.ai }]}>Rủ Đi AI phác lịch trình</Text>
          <Text style={[typography.title, { color: colors.ink }]}>{the.title}</Text>
          {the.days.map((d, i) => (
            <View key={`${d.label ?? "ngay"}-${i}`} style={styles.dong}>
              <Text style={[typography.label, { color: colors.ink }]}>{d.label ?? `Ngày ${i + 1}`}</Text>
              {d.stops.map((s, j) => (
                <Text key={`${s.place_id ?? s.name ?? j}`} style={[typography.caption, { color: colors.inkSoft }]}>
                  {s.time ? `${s.time} · ` : ""}
                  {s.name ?? "Chặng chưa có tên"}
                </Text>
              ))}
            </View>
          ))}
          <AiNote>Bản nháp của AI. Nhóm sửa được trước khi chốt; không gì ở đây tự thành kèo.</AiNote>
        </Card>
      );
    case "poll":
      return <ThePoll the={the} contextId={contextId} personId={personId} />;
    case "expense_draft":
      return (
        <Card tone="split" style={styles.card}>
          <Text style={[typography.caption, { color: colors.split }]}>Nháp chia bill từ chat</Text>
          {the.drafts.map((d, i) => (
            <View key={`${d.title}-${i}`} style={styles.dong}>
              <Text style={[typography.body, { color: colors.ink }]}>{d.title}</Text>
              <Text style={[typography.money, { color: colors.split }]}>{tienVnd(d.amount_vnd)}</Text>
              <Text style={[typography.caption, { color: colors.inkSoft }]}>
                {tenNguoi(d.paid_by_id)} trả · chia cho {d.shared_by.length} người
                {d.needs_review ? " · cần xem lại" : ""}
              </Text>
            </View>
          ))}
          <Text style={[typography.caption, { color: colors.inkFaint }]}>
            Đây là bản đọc từ tin nhắn, chưa ghi vào sổ. Xác nhận khoản chi ở mục Chia bill.
          </Text>
        </Card>
      );
    default:
      return (
        <Card tone="ai" style={styles.card}>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Một thẻ bản này chưa hiển thị được.</Text>
        </Card>
      );
  }
}

function ThePoll({
  the,
  contextId,
  personId,
}: {
  the: Extract<TheAi, { loai: "poll" }>;
  contextId: string;
  personId: string;
}) {
  const { colors } = useRudiTheme();
  const [ketQua, setKetQua] = useState<CuocBinhChonWire | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangBo, setDangBo] = useState<string | null>(null);

  const nap = useCallback(async () => {
    try {
      setKetQua(await docBinhChon(the.vote_id, personId, contextId));
    } catch (error) {
      setLoi(error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null));
    }
  }, [the.vote_id, personId, contextId]);

  useEffect(() => {
    void nap();
  }, [nap]);

  const bo = async (optionId: string) => {
    setDangBo(optionId);
    try {
      await boPhieu(the.vote_id, optionId, personId, contextId);
      await nap();
    } catch (error) {
      setLoi(error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null));
    } finally {
      setDangBo(null);
    }
  };

  const dem = new Map<string, number>();
  for (const o of ketQua?.options ?? []) dem.set(o.id, o.ballot_count);
  const tong = ketQua?.total_ballots ?? 0;

  return (
    <Card style={styles.card}>
      <Text style={[typography.caption, { color: colors.accent }]}>Bình chọn</Text>
      <Text style={[typography.title, { color: colors.ink }]}>{the.question}</Text>
      {the.options.map((o) => {
        const cuaToi = ketQua?.my_option_id === o.id;
        const so = dem.get(o.id) ?? 0;
        return (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Bỏ phiếu ${o.label}`}
            disabled={dangBo !== null || ketQua?.is_closed === true}
            key={o.id}
            onPress={() => void bo(o.id)}
            style={[
              styles.luaChon,
              { borderColor: cuaToi ? colors.accent : colors.lineStrong, backgroundColor: cuaToi ? colors.accentSoft : colors.card },
            ]}
          >
            <Text style={[typography.body, { color: colors.ink }]}>{o.label}</Text>
            <Text style={[typography.caption, { color: cuaToi ? colors.accent : colors.inkSoft }]}>
              {so} phiếu{cuaToi ? " · của bạn" : ""}
            </Text>
          </Pressable>
        );
      })}
      <Text style={[typography.caption, { color: colors.inkFaint }]}>
        {tong} phiếu{ketQua?.is_closed ? " · đã đóng" : ""}
      </Text>
      {loi ? <Text style={[typography.caption, { color: colors.warn }]}>{loi}</Text> : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: 8 },
  dong: { gap: 2, paddingVertical: 4 },
  luaChon: { borderWidth: 1.5, borderRadius: 14, paddingHorizontal: 12, paddingVertical: 10, gap: 2 },
});
