/**
 * Đăng bài (M8): write one post, to one of F42's four audiences.
 *
 * The four audiences are a vocabulary, not a ladder (`bai-dang.ts`): `friends`
 * and `group` reach two disjoint sets and neither contains the other. They are
 * drawn as four rows, each carrying the sentence that names who it reaches --
 * not a slider, not a narrow-to-wide chip row, not a lock that opens in steps.
 *
 * Text only for now. A post's `image_url` has to point at a group photo, which
 * only members of that group may read, so an image on a `friends` or `public`
 * post would be an address most readers cannot open.
 */
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { newAttempt } from "../../../api";
import {
  AUDIENCES,
  MAC_DINH_NGUOI_DOC,
  MUC_NGUOI_DOC,
  coTheDang,
  guiBai,
  type Audience,
} from "../../../screens/ca-nhan/bai-dang";
import { docNhomCuaToi, type NhomTomTat } from "../../../phien";
import { loiRaChu } from "../../nguoi/ho-so-nguoi";
import { useRudiSession } from "../../session";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Field, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

export function DangBaiScreen() {
  const router = useRouter();
  const { colors, radius } = useRudiTheme();
  const { phien, phienDaDoc } = useRudiSession();
  const [than, setThan] = useState("");
  const [muc, setMuc] = useState<Audience>(MAC_DINH_NGUOI_DOC);
  const [nhom, setNhom] = useState<NhomTomTat[]>([]);
  const [nhomChon, setNhomChon] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    if (phien === null) return;
    let con = true;
    void (async () => {
      try {
        const ds = await docNhomCuaToi(phien.person_id);
        if (!con) return;
        const dangO = ds.filter((n) => n.my_state === "active");
        setNhom(dangO);
        setNhomChon((truoc) => {
          // Statement form on purpose (see the id-default gate): this id is a
          // selection, never a label, and the gate reads shape rather than use.
          if (truoc !== null) return truoc;
          const dau = dangO[0];
          if (dau === undefined) return null;
          return dau.id;
        });
      } catch {
        // A group list that does not answer only costs the «Một nhóm» option;
        // the other three audiences still work, so this is not screen-fatal.
      }
    })();
    return () => {
      con = false;
    };
  }, [phien]);

  if (!phienDaDoc) return null;

  const form = { body: than, audience: muc, contextId: muc === "group" ? nhomChon : null };
  const guiDuoc = phien !== null && coTheDang(form) && !dangGui;

  const gui = async () => {
    if (phien === null) return;
    setDangGui(true);
    setLoi(null);
    try {
      await guiBai(phien.person_id, form, newAttempt());
      router.replace(`/people/${phien.person_id}`);
    } catch (error) {
      setLoi(loiRaChu(error));
    } finally {
      setDangGui(false);
    }
  };

  return (
    <RudiScreen testID="dang-bai-screen">
      <TopBar title="Đăng bài" />
      <Card>
        <Field
          label="Bạn muốn kể gì?"
          multiline
          numberOfLines={5}
          onChangeText={setThan}
          placeholder="Chuyến vừa rồi, quán mới, hay chỉ một câu."
          value={than}
        />
      </Card>
      <Heading subtitle="Chọn ai đọc được bài này. Bốn mức không xếp từ hẹp tới rộng: bạn bè và nhóm là hai tập khác nhau." title="Ai đọc được?" />
      <Card style={styles.danhSach}>
        {AUDIENCES.map((a) => {
          const chon = muc === a;
          return (
            <Pressable
              // Named so a driver (and a screen reader) can pick this row and
              // not the sentence under a neighbour, which mentions «Bạn bè» too.
              accessibilityLabel={`Mức người đọc: ${MUC_NGUOI_DOC[a].nhan}`}
              accessibilityRole="radio"
              accessibilityState={{ selected: chon }}
              key={a}
              onPress={() => setMuc(a)}
              style={[
                styles.hang,
                { borderRadius: radius.control },
                chon && { backgroundColor: colors.accentSoft },
              ]}
            >
              <View style={styles.hangChu}>
                <Text style={[typography.label, { color: chon ? colors.accent : colors.ink }]}>
                  {MUC_NGUOI_DOC[a].nhan}
                </Text>
                <Text style={[typography.caption, { color: colors.inkFaint }]}>
                  {MUC_NGUOI_DOC[a].giaiThich}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </Card>
      {muc === "group" ? (
        <Card>
          <Text style={[typography.label, { color: colors.ink }]}>Nhóm nào?</Text>
          {nhom.length === 0 ? (
            <Text style={[typography.caption, { color: colors.inkFaint }]}>
              Bạn chưa ở nhóm nào đang hoạt động, nên chưa đăng cho nhóm được.
            </Text>
          ) : (
            <View style={styles.chips}>
              {nhom.map((n) => (
                <Chip
                  key={n.id}
                  label={n.display_name}
                  onPress={() => setNhomChon(n.id)}
                  selected={nhomChon === n.id}
                />
              ))}
            </View>
          )}
        </Card>
      ) : null}
      {loi ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{loi}</Text>
        </Card>
      ) : null}
      <RudiButton
        disabled={!guiDuoc}
        icon="send-outline"
        label="Đăng"
        loading={dangGui}
        onPress={() => void gui()}
      />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  danhSach: { gap: 4 },
  hang: { minHeight: 56, justifyContent: "center", paddingHorizontal: 10, paddingVertical: 8 },
  hangChu: { gap: 2 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
