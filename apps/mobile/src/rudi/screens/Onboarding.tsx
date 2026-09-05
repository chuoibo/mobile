import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { manDau } from "../duong-vao";
import {
  LOI_SO_THICH,
  cauLuuTru,
  docSoThich,
  docTuVung,
  luuSoThich,
  maLoi,
} from "../nguoi/so-thich-song";
import { NGAN_SACH, SO_THICH, doiMuc } from "../../screens/vao-cua/so-thich";
import { useRudiSession } from "../session";
import { typography, useRudiTheme } from "../theme";
import {
  Card,
  Chip,
  Heading,
  Inline,
  ProgressBar,
  RudiButton,
  RudiScreen,
  Spacer,
  TopBar,
} from "../ui";

/** One icon per taste word the SERVER knows. The words themselves come from
 *  `so-thich.ts`, which `tests/test_interest_vocabulary_matches_client.py`
 *  keeps equal to the server's list; the icon is decoration and lives here. */
const BIEU_TUONG: Record<string, keyof typeof Ionicons.glyphMap> = {
  "an-uong": "restaurant-outline",
  cafe: "cafe-outline",
  nightlife: "wine-outline",
  "mon-local": "fast-food-outline",
  outdoor: "trail-sign-outline",
  shopping: "bag-handle-outline",
  karaoke: "mic-outline",
  game: "game-controller-outline",
};

export function PersonalizationScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const session = useRudiSession();
  const personId = session.phien?.person_id ?? null;

  const [muc, setMuc] = useState<string[]>([]);
  const [khoang, setKhoang] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Which words the server will accept. Null until it answers, and null forever
  // if it cannot be reached -- the screen renders the local list either way.
  const [tuVung, setTuVung] = useState<string[] | null>(null);

  useEffect(() => {
    let con = true;
    void docTuVung().then((ds) => con && setTuVung(ds));
    return () => {
      con = false;
    };
  }, []);

  const danhSach = tuVung === null ? SO_THICH : SO_THICH.filter((m) => tuVung.includes(m.id));

  // What this person already told the server, so re-opening the step shows
  // their answers rather than an empty screen that looks like a reset.
  useEffect(() => {
    if (personId === null) return;
    let con = true;
    void docSoThich(personId)
      .then((da) => {
        if (!con) return;
        setMuc(da.muc);
        setKhoang(da.khoang);
      })
      .catch(() => undefined);
    return () => {
      con = false;
    };
  }, [personId]);

  /** Tapping the chosen band again clears it: «bỏ qua» has to stay reachable
   *  after somebody has answered, or the first answer is permanent. */
  const doiKhoang = (id: string) => {
    void Haptics.selectionAsync();
    if (khoang === id) {
      setKhoang(null);
      return;
    }
    setKhoang(id);
  };

  const doiMucChon = (id: string) => {
    void Haptics.selectionAsync();
    setMuc(doiMuc(muc, id));
  };

  const xong = async () => {
    setLoi(null);
    if (personId === null) {
      // The dev fixture door reaches this screen with no session. Nothing to
      // attach the answers to, and writing them to a file a later sign-in
      // adopts would make one phone's guesses look like somebody's taste.
      router.replace("/explore");
      return;
    }
    setDangLuu(true);
    try {
      await luuSoThich(personId, { muc, khoang });
      router.replace(manDau(session.phien));
    } catch (error) {
      const ma = maLoi(error);
      setLoi((ma !== null ? LOI_SO_THICH[ma] : null) ?? "Chưa lưu được. Thử lại giúp mình nhé.");
    } finally {
      setDangLuu(false);
    }
  };

  return (
    <RudiScreen contentStyle={styles.personalization} testID="personalization-screen">
      <TopBar
        right={
          <Pressable accessibilityRole="button" onPress={() => router.replace(manDau(session.phien))}>
            {/* Not a gate. The step is editable forever from Cá nhân, and a
                required question on the first screen of a new account is a
                toll booth, not a personalization. */}
            <Text style={[typography.label, { color: colors.inkFaint }]}>Bỏ qua</Text>
          </Pressable>
        }
      />
      <ProgressBar value={100} />
      <Heading
        title="Cho Rủ Đi biết gu của bạn"
        subtitle="Chọn ít nhất 3 sở thích. Rủ Đi xếp gợi ý theo đúng những gì bạn chọn."
      />
      <Card style={styles.preferenceCard}>
        <Text style={[typography.title, { color: colors.ink }]}>Bạn thường mê gì?</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Chọn mọi thứ khiến bạn muốn xách balo lên.</Text>
        <View style={styles.interestGrid}>
          {danhSach.map((m) => {
            const selected = muc.includes(m.id);
            return (
              <Pressable
                key={m.id}
                accessibilityRole="checkbox"
                aria-checked={selected}
                onPress={() => doiMucChon(m.id)}
                style={({ pressed }) => [
                  styles.interest,
                  {
                    backgroundColor: selected ? colors.accentSoft : colors.card,
                    borderColor: selected ? colors.accent : colors.line,
                  },
                  pressed && styles.pressed,
                ]}
              >
                <View style={[styles.interestIcon, { backgroundColor: selected ? colors.accent : colors.ground }]}>
                  <Ionicons color={selected ? colors.accentInk : colors.inkSoft} name={BIEU_TUONG[m.id] ?? "sparkles-outline"} size={23} />
                </View>
                <Text style={[typography.label, { color: selected ? colors.accent : colors.ink }]}>{m.nhan}</Text>
                {selected ? <Ionicons color={colors.accent} name="checkmark-circle" size={18} /> : null}
              </Pressable>
            );
          })}
        </View>
      </Card>
      <View style={styles.vibeBlock}>
        <Text style={[typography.title, { color: colors.ink }]}>Mỗi lần đi chơi bạn tiêu khoảng</Text>
        <Text style={[typography.caption, { color: colors.inkFaint }]}>
          Bỏ qua cũng được. Rủ Đi để trống chỗ này chứ không đoán thay bạn.
        </Text>
        <Inline gap={8} wrap>
          {NGAN_SACH.map((k) => (
            <Chip key={k.id} label={k.nhan} onPress={() => doiKhoang(k.id)} selected={khoang === k.id} />
          ))}
        </Inline>
      </View>
      <Spacer size={4} />
      {loi !== null ? <Text style={[typography.body, { color: colors.warn }]}>{loi}</Text> : null}
      <RudiButton
        disabled={muc.length < 3 || dangLuu}
        icon="sparkles"
        label={dangLuu ? "Đang lưu…" : "Tạo không gian của tôi"}
        onPress={() => void xong()}
      />
      <Text style={[typography.caption, styles.privacyText, { color: colors.inkFaint }]}>
        {cauLuuTru(personId !== null)}
      </Text>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  pressed: { opacity: 0.7 },
  personalization: { maxWidth: 760 },
  privacyText: { textAlign: "center", paddingHorizontal: 18 },
  preferenceCard: { gap: 8 },
  interestGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 7 },
  interest: { minHeight: 62, minWidth: "47%", flexGrow: 1, flexBasis: 150, borderRadius: 16, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 9, padding: 10 },
  interestIcon: { width: 39, height: 39, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  vibeBlock: { gap: 11 },
});
