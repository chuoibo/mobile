/**
 * The «Tin nhắn» tab for a real session: the groups this person is in.
 *
 * Read from `GET /people/me/contexts` (ADR-0016) on every focus, so a group
 * created on another phone, or an invitation a friend just sent, shows up
 * without a restart. Rows carry what the server knows -- member count, unread
 * count, the newest message -- and nothing invented.
 *
 * An `invited` row is not a conversation yet: it carries «Đồng ý», and only the
 * press makes the person a member (`vaoNhom`). Tapping an active row makes
 * that group the current one (`chonNhom`, so the money screens read it) and
 * opens its chat (M3); the roster and invite tools sit behind the chat header.
 *
 * On the fixture build (`cheDo !== "live"`) the tab still renders the fixture
 * chat, unchanged, so the default Maestro table keeps its ground.
 */
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { docNhomCuaToi, ganDanhSachNhom, chonNhom, vaoNhom, type NhomTomTat, type Phien } from "../../../phien";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, RudiButton, RudiScreen } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; nhom: NhomTomTat[] }
  | { pha: "hong"; loi: string };

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function ConversationsScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const { datPhien } = useRudiSession();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [dangBam, setDangBam] = useState<string | null>(null);

  const nap = useCallback(async () => {
    try {
      const nhom = await docNhomCuaToi(phien.person_id);
      setTrang({ pha: "xong", nhom });
      // Keep the session's own copy fresh too: it is what the empty state and
      // the entry decision read on the next cold start.
      datPhien(await ganDanhSachNhom(phien, nhom));
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
    // `phien` changes identity on every `datPhien`; refetching on that would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phien.person_id]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  const moNhom = async (nhom: NhomTomTat) => {
    setDangBam(nhom.id);
    try {
      const moi = await chonNhom({ ...phien, contexts: trang.pha === "xong" ? trang.nhom : phien.contexts }, nhom.id);
      datPhien(moi);
      router.push(`/groups/${nhom.id}/chat` as never);
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    } finally {
      setDangBam(null);
    }
  };

  const dongY = async (nhom: NhomTomTat) => {
    setDangBam(nhom.id);
    try {
      const daVao = await vaoNhom({
        ...phien,
        context_id: nhom.id,
        membership_state: "invited",
        membership_id: nhom.membership_id,
      });
      datPhien(daVao);
      await nap();
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    } finally {
      setDangBam(null);
    }
  };

  return (
    <RudiScreen bottomInset={112} testID="conversations-screen">
      <View style={styles.top}>
        <View>
          <Text style={[typography.h1, { color: colors.ink }]}>Tin nhắn</Text>
          <Text style={[typography.caption, { color: colors.inkFaint }]}>Nhóm của bạn trên máy chủ</Text>
        </View>
        <RudiButton compact full={false} icon="add" label="Tạo nhóm" onPress={() => router.push("/groups/new")} />
      </View>
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc danh sách nhóm...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" && trang.nhom.length === 0 ? (
        <Heading
          title="Chưa có nhóm nào"
          subtitle="Mở một nhóm mới, hoặc nhận lời mời của người đã ở trong nhóm."
        />
      ) : null}
      {trang.pha === "xong"
        ? trang.nhom.map((nhom) => (
            <Card key={nhom.id} style={styles.hang}>
              <Pressable
                accessibilityRole="button"
                disabled={nhom.my_state !== "active" || dangBam !== null}
                onPress={() => void moNhom(nhom)}
                style={styles.hangChinh}
              >
                <View style={styles.hangChu}>
                  <Text style={[typography.title, { color: colors.ink }]}>{nhom.display_name}</Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>
                    {nhom.member_count} thành viên
                    {nhom.my_role === "admin" ? " · bạn quản trị" : ""}
                    {nhom.my_state === "invited" ? " · bạn được mời" : ""}
                  </Text>
                  <Text numberOfLines={1} style={[typography.caption, { color: colors.inkSoft }]}>
                    {nhom.last_message
                      ? `${nhom.last_message.author_display_name ?? "Rủ Đi AI"}: ${nhom.last_message.preview}`
                      : "Chưa có tin nhắn nào."}
                  </Text>
                </View>
                {nhom.unread_count > 0 ? (
                  <View style={[styles.chuaDoc, { backgroundColor: colors.accent }]}>
                    <Text style={[typography.caption, { color: colors.accentInk }]}>{nhom.unread_count}</Text>
                  </View>
                ) : null}
              </Pressable>
              {nhom.my_state === "invited" ? (
                <RudiButton
                  compact
                  disabled={dangBam !== null}
                  label="Đồng ý vào nhóm"
                  loading={dangBam === nhom.id}
                  onPress={() => void dongY(nhom)}
                />
              ) : null}
            </Card>
          ))
        : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  hang: { gap: 10 },
  hangChinh: { flexDirection: "row", alignItems: "center", gap: 12 },
  hangChu: { flex: 1, gap: 2 },
  chuaDoc: { minWidth: 26, height: 26, borderRadius: 13, alignItems: "center", justifyContent: "center", paddingHorizontal: 8 },
});
