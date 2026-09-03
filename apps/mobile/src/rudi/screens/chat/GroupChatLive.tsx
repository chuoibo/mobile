/**
 * The group chat, on the real API (M3).
 *
 * Messenger shape: an inverted FlatList (newest at the bottom, older pages on
 * pull-up), one composer pinned above the keyboard, day dividers, bubbles
 * with the author's name from the roster, reaction chips under a bubble and a
 * quick bar on long-press. The companion is a member of the roster called
 * «Rủ Đi AI»: its cards render inline, and a slash command or `@Rủ Đi` is how
 * a person calls on it -- the server answers in the same POST, so what it did
 * (or why it stayed quiet) is shown right under the composer.
 *
 * Keyboard: `KeyboardAvoidingView` with `padding`; the geometry is measured on
 * the emulator (flow 30 + `scripts/do_ban_phim.py`), not assumed from a prop.
 */
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { chuDau } from "../../../screens/ca-nhan/ban-be";
import { danhSachThanhVien } from "../../../screens/vao-cua/cong-api";
import {
  PHAN_UNG,
  cauYDinh,
  docTheAi,
  gioPhut,
  glyphPhanUng,
  khoaHang,
  nhomTheoNgay,
  type HangHienThi,
  type LoaiPhanUng,
  type Tin,
} from "../../chat/tin-song";
import { TAT_KAV_QA } from "../../chat/qa-ban-phim";
import { useTinNhan } from "../../chat/useTinNhan";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { IconButton, TopBar } from "../../ui";
import { TheAiView } from "./TheAi";

const LENH = [
  { nhan: "/plan", goiY: "/plan tối nay đi đâu?", moTa: "Rủ Đi AI phác lịch trình" },
  { nhan: "/vote", goiY: "/vote Ăn gì? Bún bò | Phở", moTa: "Mở bình chọn: câu hỏi? A | B" },
  { nhan: "/chia-bill", goiY: "/chia-bill", moTa: "Đọc các khoản chi trong tin gần đây" },
  { nhan: "@Rủ Đi", goiY: "@Rủ Đi ", moTa: "Hỏi Rủ Đi AI một câu" },
] as const;

export function GroupChatLiveScreen({ contextId }: { contextId: string }) {
  const router = useRouter();
  const { colors, space } = useRudiTheme();
  const insets = useSafeAreaInsets();
  const { phien } = useRudiSession();
  const personId = phien?.person_id ?? "";
  const chat = useTinNhan(contextId, personId);
  const [nhap, setNhap] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [dangChonPhanUng, setDangChonPhanUng] = useState<string | null>(null);
  const [tenTheoId, setTenTheoId] = useState<Record<string, string>>({});

  const tenNhom = phien?.contexts?.find((n) => n.id === contextId)?.display_name ?? "Nhóm";

  useEffect(() => {
    let song = true;
    void danhSachThanhVien(contextId, personId)
      .then((ds) => {
        if (!song) return;
        const map: Record<string, string> = {};
        for (const tv of ds) if (tv.display_name) map[tv.person_id] = tv.display_name;
        setTenTheoId(map);
      })
      .catch(() => undefined);
    return () => {
      song = false;
    };
  }, [contextId, personId]);

  const tenNguoi = useCallback(
    (id: string | null) => (id === null ? "Rủ Đi AI" : id === personId ? "Bạn" : tenTheoId[id] ?? "Thành viên"),
    [tenTheoId, personId],
  );

  const hang = useMemo(() => nhomTheoNgay(chat.tin), [chat.tin]);
  const moLenh = nhap.startsWith("/") && !nhap.includes(" ") || nhap === "@";

  const gui = async () => {
    const body = nhap.trim();
    if (!body || dangGui) return;
    setDangGui(true);
    setThongBao(null);
    try {
      const daGui = await chat.gui(body);
      setNhap("");
      setThongBao(cauYDinh(daGui));
    } catch (error) {
      setThongBao(error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null));
    } finally {
      setDangGui(false);
    }
  };

  const phanUng = async (tin: Tin, kind: LoaiPhanUng) => {
    setDangChonPhanUng(null);
    const cuaToi = tin.reactions?.some((r) => r.kind === kind && r.mine) ?? false;
    try {
      await chat.doiPhanUng(tin.id, kind, cuaToi);
    } catch (error) {
      setThongBao(error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null));
    }
  };

  const renderItem = ({ item }: { item: HangHienThi }) => {
    if (item.loai === "ngay") {
      return (
        <View style={styles.ngay}>
          <View style={[styles.duong, { backgroundColor: colors.line }]} />
          <Text style={[typography.caption, { color: colors.inkFaint }]}>{item.nhan}</Text>
          <View style={[styles.duong, { backgroundColor: colors.line }]} />
        </View>
      );
    }
    const tin = item.tin;
    const cuaToi = tin.author_id === personId;
    const laAi = tin.kind === "ai_card";
    const chips = (tin.reactions ?? []).filter((r) => r.count > 0);
    return (
      <View style={[styles.hang, cuaToi && !laAi && styles.hangToi]}>
        {!cuaToi && !laAi ? (
          <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
            <Text style={[typography.caption, { color: colors.accent }]}>{chuDau(tenNguoi(tin.author_id))}</Text>
          </View>
        ) : null}
        <View style={[styles.khoi, cuaToi && !laAi && styles.khoiToi, laAi && styles.khoiAi]}>
          {!cuaToi && !laAi ? (
            <Text style={[typography.caption, { color: colors.inkSoft }]}>{tenNguoi(tin.author_id)}</Text>
          ) : null}
          {laAi ? (
            <TheAiView the={docTheAi(tin.card)} contextId={contextId} personId={personId} tenNguoi={tenNguoi} />
          ) : (
            <Pressable
              accessibilityLabel={`Tin nhắn: ${tin.body ?? ""}`}
              onLongPress={() => setDangChonPhanUng(tin.id)}
              style={[
                styles.bong,
                {
                  backgroundColor: cuaToi ? colors.accent : colors.card,
                  borderColor: cuaToi ? colors.accent : colors.line,
                },
              ]}
            >
              <Text style={[typography.body, { color: cuaToi ? colors.accentInk : colors.ink }]}>{tin.body}</Text>
            </Pressable>
          )}
          <View style={styles.duoiBong}>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{gioPhut(tin.created_at)}</Text>
            {chips.map((r) => (
              <Pressable
                accessibilityLabel={`${r.count} ${glyphPhanUng(r.kind)}`}
                key={r.kind}
                onPress={() => void phanUng(tin, r.kind)}
                style={[
                  styles.chip,
                  { borderColor: r.mine ? colors.accent : colors.line, backgroundColor: colors.card },
                ]}
              >
                <Text style={typography.caption}>
                  {glyphPhanUng(r.kind)} {r.count}
                </Text>
              </Pressable>
            ))}
          </View>
          {dangChonPhanUng === tin.id ? (
            <View style={[styles.thanhPhanUng, { backgroundColor: colors.card, borderColor: colors.line }]}>
              {PHAN_UNG.map((p) => (
                <Pressable
                  accessibilityLabel={p.nhan}
                  key={p.kind}
                  onPress={() => void phanUng(tin, p.kind)}
                  style={styles.nutPhanUng}
                >
                  <Text style={styles.glyph}>{p.glyph}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </View>
      </View>
    );
  };

  if (phien === null) return <Redirect href="/welcome" />;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      // Off only under the QA negative control; see `qa-ban-phim.ts`.
      enabled={!TAT_KAV_QA}
      style={[styles.man, { backgroundColor: colors.ground, paddingTop: insets.top }]}
    >
      <View style={{ paddingHorizontal: space.md }}>
        <TopBar
          title={tenNhom}
          subtitle={`${Object.keys(tenTheoId).length || 1} thành viên`}
          right={
            <IconButton
              accessibilityLabel="Thành viên nhóm"
              icon="people-outline"
              onPress={() => router.push(`/groups/${contextId}/members` as never)}
            />
          }
        />
      </View>
      <FlatList
        contentContainerStyle={[styles.danhSach, { paddingHorizontal: space.md }]}
        data={hang}
        inverted
        keyExtractor={khoaHang}
        ListEmptyComponent={
          chat.dangNap ? null : (
            <View style={styles.rong}>
              <Text style={[typography.title, { color: colors.ink }]}>Chưa có tin nhắn nào</Text>
              <Text style={[typography.caption, { color: colors.inkSoft }]}>
                Nhắn gì đó cho hội, hoặc gõ / để rủ Rủ Đi AI vào.
              </Text>
            </View>
          )
        }
        ListFooterComponent={
          chat.dangNapCu ? (
            <Text style={[typography.caption, styles.giua, { color: colors.inkFaint }]}>Đang tải tin cũ...</Text>
          ) : null
        }
        maintainVisibleContentPosition={{ minIndexForVisible: 0 }}
        onEndReached={() => void chat.napCuHon()}
        onEndReachedThreshold={0.6}
        renderItem={renderItem}
        testID="chat-list"
      />
      {chat.loi ? (
        <Text style={[typography.caption, { color: colors.warn, paddingHorizontal: space.md }]}>{chat.loi}</Text>
      ) : null}
      {thongBao ? (
        <Text style={[typography.caption, { color: colors.inkSoft, paddingHorizontal: space.md }]}>{thongBao}</Text>
      ) : null}
      {moLenh ? (
        <View style={[styles.lenh, { backgroundColor: colors.card, borderColor: colors.line, marginHorizontal: space.md }]}>
          {LENH.map((l) => (
            <Pressable accessibilityRole="button" key={l.nhan} onPress={() => setNhap(l.goiY)} style={styles.lenhHang}>
              <Text style={[typography.label, { color: colors.accent }]}>{l.nhan}</Text>
              <Text style={[typography.caption, { color: colors.inkSoft }]}>{l.moTa}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      <View
        style={[
          styles.soan,
          {
            backgroundColor: colors.card,
            borderColor: colors.line,
            marginHorizontal: space.md,
            marginBottom: Math.max(insets.bottom, 8),
          },
        ]}
      >
        <TextInput
          accessibilityLabel="Ô soạn tin"
          multiline
          onChangeText={setNhap}
          placeholder="Nhắn cho hội, hoặc gõ / để gọi Rủ Đi AI"
          placeholderTextColor={colors.inkFaint}
          style={[typography.body, styles.oNhap, { color: colors.ink }]}
          value={nhap}
        />
        <IconButton
          accessibilityLabel="Gửi tin nhắn"
          icon="arrow-up"
          onPress={() => void gui()}
          selected={nhap.trim().length > 0 && !dangGui}
        />
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  man: { flex: 1 },
  danhSach: { paddingVertical: 12, gap: 12 },
  ngay: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 6 },
  duong: { flex: 1, height: StyleSheet.hairlineWidth },
  hang: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
  hangToi: { justifyContent: "flex-end" },
  khoi: { maxWidth: "82%", gap: 4 },
  khoiToi: { alignItems: "flex-end" },
  khoiAi: { maxWidth: "100%", flex: 1 },
  chuDau: { width: 30, height: 30, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  bong: { borderWidth: 1, borderRadius: 17, paddingHorizontal: 13, paddingVertical: 10 },
  duoiBong: { flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" },
  chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  thanhPhanUng: { flexDirection: "row", gap: 4, borderWidth: 1, borderRadius: 999, padding: 4, alignSelf: "flex-start" },
  nutPhanUng: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  glyph: { fontSize: 20 },
  rong: { alignItems: "center", gap: 6, paddingVertical: 40, transform: [{ scaleY: -1 }] },
  giua: { textAlign: "center", paddingVertical: 8 },
  lenh: { borderWidth: 1, borderRadius: 16, padding: 6, gap: 2 },
  lenhHang: { paddingHorizontal: 10, paddingVertical: 8, gap: 1 },
  soan: { flexDirection: "row", alignItems: "flex-end", gap: 6, padding: 6, borderWidth: 1, borderRadius: 22 },
  oNhap: { flex: 1, maxHeight: 120, paddingHorizontal: 10, paddingVertical: 8 },
});
