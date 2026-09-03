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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FlatList,
  Keyboard,
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
import { Card, IconButton, TopBar } from "../../ui";
import { TheAiView } from "./TheAi";

const LENH = [
  { nhan: "/plan", goiY: "/plan tối nay đi đâu?", moTa: "Rủ Đi AI phác lịch trình" },
  { nhan: "/vote", goiY: "/vote Ăn gì? Bún bò | Phở", moTa: "Mở bình chọn: câu hỏi? A | B" },
  { nhan: "/chia-bill", goiY: "/chia-bill", moTa: "Đọc các khoản chi trong tin gần đây" },
  { nhan: "@Rủ Đi", goiY: "@Rủ Đi ", moTa: "Hỏi Rủ Đi AI một câu" },
] as const;

/** A body that calls on the model (not `/vote`, which the server answers itself). */
function goiMoHinh(body: string): boolean {
  return /^\/(plan|chia-?bill)\b/i.test(body) || /@(rủ đi|ru di|rudi)/i.test(body);
}

export function GroupChatLiveScreen({ contextId }: { contextId: string }) {
  const router = useRouter();
  const { colors, space } = useRudiTheme();
  const insets = useSafeAreaInsets();
  const { phien } = useRudiSession();
  const personId = phien?.person_id ?? "";
  const chat = useTinNhan(contextId, personId);
  const [nhap, setNhap] = useState("");
  const [dangGui, setDangGui] = useState(false);
  // The words in flight: drawn as a pending own bubble (and a pending AI row
  // for a command) until the server's rows replace them.
  const [dangGuiThan, setDangGuiThan] = useState<string | null>(null);
  const [banPhimMo, setBanPhimMo] = useState(false);
  // What the server said about the last command, drawn as a row in the thread
  // (where the pending card promised it), signed by who is speaking.
  const [thongBao, setThongBao] = useState<{ tu: string; cau: string; luc: string } | null>(null);
  const [dangChonPhanUng, setDangChonPhanUng] = useState<string | null>(null);
  const [tenTheoId, setTenTheoId] = useState<Record<string, string>>({});

  const tenNhom = phien?.contexts?.find((n) => n.id === contextId)?.display_name ?? "Nhóm";

  useEffect(() => {
    const hien = Keyboard.addListener("keyboardDidShow", () => setBanPhimMo(true));
    const an = Keyboard.addListener("keyboardDidHide", () => setBanPhimMo(false));
    return () => {
      hien.remove();
      an.remove();
    };
  }, []);

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
  const coChu = nhap.trim().length > 0;
  const moLenh = nhap.startsWith("/") && !nhap.includes(" ") || nhap === "@";

  // The list only auto-scrolls to new rows when the reader is already at the
  // newest end (see autoscrollToTopThreshold); a message you just sent must
  // always come into view, so the send jumps there explicitly.
  const danhSachRef = useRef<FlatList<HangHienThi>>(null);

  const gui = async () => {
    const body = nhap.trim();
    if (!body || dangGui) return;
    setDangGui(true);
    setDangGuiThan(body);
    setNhap("");
    setThongBao(null);
    try {
      const daGui = await chat.gui(body);
      danhSachRef.current?.scrollToOffset({ offset: 0, animated: true });
      const cau = cauYDinh(daGui);
      const tuAi = daGui.companion !== null && daGui.companion !== undefined && !daGui.companion.spoke;
      setThongBao(cau === null ? null : { tu: tuAi ? "Rủ Đi AI" : "Rủ Đi", cau, luc: new Date().toISOString() });
    } catch (error) {
      // Give the words back: a failed send must not eat what was typed.
      setNhap(body);
      setThongBao({
        tu: "Rủ Đi",
        cau: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
        luc: new Date().toISOString(),
      });
    } finally {
      setDangGui(false);
      setDangGuiThan(null);
    }
  };

  const phanUng = async (tin: Tin, kind: LoaiPhanUng) => {
    setDangChonPhanUng(null);
    const cuaToi = tin.reactions?.some((r) => r.kind === kind && r.mine) ?? false;
    try {
      await chat.doiPhanUng(tin.id, kind, cuaToi);
    } catch (error) {
      setThongBao({
        tu: "Rủ Đi",
        cau: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
        luc: new Date().toISOString(),
      });
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
            <TheAiView
              the={docTheAi(tin.card)}
              contextId={contextId}
              personId={personId}
              tenNguoi={tenNguoi}
              tacGia={tenNguoi(tin.author_id)}
            />
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
                hitSlop={8}
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
      {/* A bar with an edge: scrolled rows disappear under a defined line, not
          into bare ground. */}
      <View style={[styles.dau, { paddingHorizontal: space.md, borderBottomColor: colors.line }]}>
        <TopBar title={tenNhom} />
        {/* The roster lives under the title, not in the top-right corner: on a
            development build the dev-launcher's floating gear covers that
            corner, and a target nobody can reach on the build we test on is a
            target nobody has tested. Messenger puts group info here too. */}
        <Pressable
          accessibilityLabel="Thành viên nhóm"
          accessibilityRole="button"
          onPress={() => router.push(`/groups/${contextId}/members` as never)}
          style={[styles.thanhVien, { borderColor: colors.line, backgroundColor: colors.card }]}
        >
          <Text style={[typography.caption, { color: colors.inkSoft }]}>
            {Object.keys(tenTheoId).length || 1} thành viên · xem và mời
          </Text>
        </Pressable>
      </View>
      {/* Drawn outside the inverted list: the list flips its own children
          back upright, and an extra flip here once mirrored this copy. */}
      {!chat.dangNap && chat.tin.length === 0 && dangGuiThan === null ? (
        <View style={[styles.rong, { paddingHorizontal: space.md }]}>
          <Text style={[typography.title, { color: colors.ink }]}>Chưa có tin nhắn nào</Text>
          <Text style={[typography.caption, styles.giua, { color: colors.inkSoft }]}>
            Nhắn gì đó cho hội, hoặc gõ / để rủ Rủ Đi AI vào.
          </Text>
        </View>
      ) : null}
      <FlatList
        ref={danhSachRef}
        contentContainerStyle={[styles.danhSach, { paddingHorizontal: space.md }]}
        data={hang}
        inverted
        keyExtractor={khoaHang}
        // Inverted, so the header sits at the newest end: what is being sent
        // shows there at once, and a command shows the model is being asked.
        ListHeaderComponent={
          dangGuiThan === null && thongBao !== null ? (
            <View style={styles.hang}>
              <View style={[styles.khoi, styles.khoiAi]}>
                <Card tone="ai" style={styles.choAi}>
                  <Text style={[typography.caption, { color: colors.ai }]}>{thongBao.tu}</Text>
                  <Text style={[typography.body, { color: colors.ink }]}>{thongBao.cau}</Text>
                </Card>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>{gioPhut(thongBao.luc)}</Text>
              </View>
            </View>
          ) : dangGuiThan !== null ? (
            <View style={styles.choGui}>
              <View style={[styles.hang, styles.hangToi]}>
                <View style={[styles.khoi, styles.khoiToi, styles.mo]}>
                  <View style={[styles.bong, { backgroundColor: colors.accent, borderColor: colors.accent }]}>
                    <Text style={[typography.body, { color: colors.accentInk }]}>{dangGuiThan}</Text>
                  </View>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang gửi...</Text>
                </View>
              </View>
              {goiMoHinh(dangGuiThan) ? (
                <View style={styles.hang}>
                  <View style={[styles.khoi, styles.khoiAi]}>
                    <Card tone="ai" style={styles.choAi}>
                      <Text style={[typography.caption, { color: colors.ai }]}>Đang hỏi Rủ Đi AI...</Text>
                      <Text style={[typography.caption, { color: colors.inkSoft }]}>
                        Câu trả lời sẽ hiện ở đây trong vài giây, hoặc lý do nó không trả lời.
                      </Text>
                    </Card>
                  </View>
                </View>
              ) : null}
            </View>
          ) : null
        }
        ListFooterComponent={
          chat.dangNapCu ? (
            <Text style={[typography.caption, styles.giua, { color: colors.inkFaint }]}>Đang tải tin cũ...</Text>
          ) : null
        }
        // Hold the reader's place while older pages load above, but when they
        // are within a bubble of the newest end, new rows (own sends, the AI's
        // answer, a friend's message) scroll into view instead of landing
        // under the composer.
        maintainVisibleContentPosition={{ minIndexForVisible: 0, autoscrollToTopThreshold: 120 }}
        onEndReached={() => void chat.napCuHon()}
        onEndReachedThreshold={0.6}
        renderItem={renderItem}
        testID="chat-list"
      />
      {chat.loi ? (
        <Text style={[typography.caption, { color: colors.warn, paddingHorizontal: space.md }]}>{chat.loi}</Text>
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
            // With the keyboard up the IME covers the navigation bar, so the
            // bottom inset would only float the composer above the keys.
            marginBottom: banPhimMo ? 6 : Math.max(insets.bottom, 8),
          },
        ]}
      >
        <TextInput
          accessibilityLabel="Ô soạn tin"
          cursorColor={colors.accent}
          multiline
          onChangeText={setNhap}
          placeholder="Nhắn cho hội, hoặc gõ / để gọi Rủ Đi AI"
          placeholderTextColor={colors.inkFaint}
          selectionColor={colors.accentSoft}
          style={[typography.body, styles.oNhap, { color: colors.ink }]}
          value={nhap}
        />
        <IconButton
          accessibilityLabel="Gửi tin nhắn"
          dim={!coChu && !dangGui}
          disabled={!coChu && !dangGui}
          icon="arrow-up"
          loading={dangGui}
          onPress={() => void gui()}
          solid={coChu || dangGui}
        />
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  man: { flex: 1 },
  thanhVien: { alignSelf: "center", borderWidth: 1, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6, marginTop: -6 },
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
  chip: { minHeight: 32, justifyContent: "center", borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  thanhPhanUng: { flexDirection: "row", gap: 4, borderWidth: 1, borderRadius: 999, padding: 4, alignSelf: "flex-start" },
  nutPhanUng: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  glyph: { fontSize: 20 },
  dau: { paddingBottom: 10, borderBottomWidth: StyleSheet.hairlineWidth },
  rong: { alignItems: "center", gap: 6, paddingVertical: 40 },
  choGui: { gap: 12 },
  mo: { opacity: 0.62 },
  choAi: { gap: 4 },
  giua: { textAlign: "center", paddingVertical: 8 },
  lenh: { borderWidth: 1, borderRadius: 16, padding: 6, gap: 2 },
  lenhHang: { paddingHorizontal: 10, paddingVertical: 8, gap: 1 },
  soan: { flexDirection: "row", alignItems: "flex-end", gap: 6, padding: 6, borderWidth: 1, borderRadius: 22 },
  oNhap: { flex: 1, maxHeight: 120, paddingHorizontal: 10, paddingVertical: 8 },
});
