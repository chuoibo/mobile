/**
 * Tạo kèo on a real session (M4): title, dates, headcount, budget a person,
 * validated by App B's `kiemTraTaoBuoiDi` and written with one Attempt.
 * Dates default to today; headcount defaults to the group's size (a real
 * number, not an invented one); the budget is the person's to type.
 */
import { Redirect, useRouter } from "expo-router";
import { useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, newAttempt, thongDiepNguoiDoc, type Attempt } from "../../../api";
import type { Phien } from "../../../phien";
import { kiemTraTaoBuoiDi } from "../../../screens/len-plan/buoi-di";
import { homNayIso, taoKeo } from "../../keo/keo";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Field, Heading, Inline, RudiButton, RudiScreen, TopBar } from "../../ui";
import { dinhDangTienVnd } from "../../../screens/chat/ke-hoach";

const MUC_NGAN_SACH = [
  { nhan: "200 nghìn", dong: 200000 },
  { nhan: "300 nghìn", dong: 300000 },
  { nhan: "500 nghìn", dong: 500000 },
  { nhan: "1 triệu", dong: 1000000 },
] as const;

/** What the digits typed mean in đồng, or nothing while they are not a whole number. */
function tienDaGo(chu: string): string | null {
  const t = chu.trim();
  if (!/^[0-9]+$/.test(t)) return null;
  return dinhDangTienVnd(Number(t));
}

function soThanhVien(phien: Phien): string {
  const nhom = phien.contexts?.find((n) => n.id === phien.context_id);
  if (nhom === undefined) return "";
  return String(nhom.member_count);
}

export function CreateOutingLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [title, setTitle] = useState("");
  const [startsOn, setStartsOn] = useState(homNayIso());
  const [endsOn, setEndsOn] = useState(homNayIso());
  const [headcount, setHeadcount] = useState(soThanhVien(phien));
  const [nganSach, setNganSach] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTao, setDangTao] = useState(false);
  const attempt = useRef<Attempt | null>(null);

  if (phien.context_id === null) return <Redirect href="/(tabs)/plan" />;
  const contextId = phien.context_id;

  const tao = async () => {
    const kq = kiemTraTaoBuoiDi({ title, starts_on: startsOn, ends_on: endsOn, headcount, nganSach });
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    if (attempt.current === null) attempt.current = newAttempt();
    setDangTao(true);
    setLoi(null);
    try {
      const keo = await taoKeo(contextId, phien.person_id, kq.body, attempt.current);
      router.replace(`/outings/${keo.id}` as never);
    } catch (error) {
      setLoi(error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null));
    } finally {
      setDangTao(false);
    }
  };

  return (
    <RudiScreen testID="create-outing-screen">
      <TopBar title="Kèo mới" />
      <Heading title="Hội mình đi đâu?" subtitle="Ngày, số người và ngân sách một người. Chặng và địa điểm thêm sau, trong kèo." />
      <Card style={styles.form}>
        <Field accessibilityLabel="Ô tên kèo" icon="flag-outline" label="Tên kèo" onChangeText={setTitle} placeholder="Ví dụ: Đà Lạt cuối tuần" value={title} />
        <View style={styles.hang}>
          <View style={styles.flex}>
            <Field accessibilityLabel="Ô ngày đi" icon="calendar-outline" keyboardType="numbers-and-punctuation" label="Ngày đi" onChangeText={setStartsOn} value={startsOn} />
          </View>
          <View style={styles.flex}>
            <Field accessibilityLabel="Ô ngày về" icon="calendar-outline" keyboardType="numbers-and-punctuation" label="Ngày về" onChangeText={setEndsOn} value={endsOn} />
          </View>
        </View>
        <Field accessibilityLabel="Ô số người" icon="people-outline" keyboardType="number-pad" label="Số người" onChangeText={setHeadcount} value={headcount} />
        <Field
          accessibilityLabel="Ô ngân sách một người"
          icon="wallet-outline"
          keyboardType="number-pad"
          label="Ngân sách một người (đồng)"
          onChangeText={setNganSach}
          placeholder="Ví dụ: 250000"
          value={nganSach}
        />
        <Inline gap={6} wrap>
          {MUC_NGAN_SACH.map((m) => (
            <Chip key={m.dong} label={m.nhan} onPress={() => setNganSach(String(m.dong))} selected={nganSach === String(m.dong)} />
          ))}
        </Inline>
        {tienDaGo(nganSach) !== null ? (
          <Text style={[typography.caption, { color: colors.inkSoft }]}>= {tienDaGo(nganSach)} một người</Text>
        ) : null}
        {loi !== null ? <Text style={[typography.body, { color: colors.warn }]}>{loi}</Text> : null}
        <RudiButton disabled={dangTao} label="Tạo kèo" loading={dangTao} onPress={() => void tao()} />
      </Card>
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  form: { gap: 14 },
  hang: { flexDirection: "row", gap: 10 },
});
