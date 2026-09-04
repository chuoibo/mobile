/**
 * The profile card for a real session (M2): what `GET /people/me` says.
 *
 * Name, bio and city are the person's own words; the five numbers are the
 * server's counts, each from the table that owns it (friends, active groups,
 * outings of those groups, distinct stops checked in at, memories authored).
 * Nothing on this card is derived on the phone, and nothing comes from the
 * fixture -- which is the whole reason it exists: the fixture hero showed
 * «Minh Anh · Cấp 12» to whoever signed in.
 *
 * Editing goes through `PATCH /people/me` and the card re-reads the server's
 * answer rather than trusting the form.
 */
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import { chuDau } from "../../../screens/ca-nhan/ban-be";
import { docHoSoToi, suaHoSoToi, type HoSoToi, type Phien } from "../../../phien";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Field, Inline, RudiButton } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; hoSo: HoSoToi }
  | { pha: "hong"; loi: string };

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

const NHAN_CUA: Record<string, string> = { phone: "số điện thoại", google: "Google" };

export function HoSoSong({ phien }: { phien: Phien }) {
  const { colors } = useRudiTheme();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [dangSua, setDangSua] = useState(false);
  const [ten, setTen] = useState("");
  const [bio, setBio] = useState("");
  const [city, setCity] = useState("");
  const [dangLuu, setDangLuu] = useState(false);
  const [loiLuu, setLoiLuu] = useState<string | null>(null);

  const nap = useCallback(async () => {
    try {
      setTrang({ pha: "xong", hoSo: await docHoSoToi(phien.person_id) });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [phien.person_id]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  const moSua = (hoSo: HoSoToi) => {
    setTen(hoSo.display_name);
    setBio(hoSo.bio ?? "");
    setCity(hoSo.city ?? "");
    setLoiLuu(null);
    setDangSua(true);
  };

  const luu = async () => {
    if (ten.trim() === "") {
      setLoiLuu("Tên hiển thị không được rỗng.");
      return;
    }
    setDangLuu(true);
    try {
      const hoSo = await suaHoSoToi(phien.person_id, { display_name: ten.trim(), bio, city });
      setTrang({ pha: "xong", hoSo });
      setDangSua(false);
    } catch (error) {
      setLoiLuu(loiRaChu(error));
    } finally {
      setDangLuu(false);
    }
  };

  if (trang.pha === "dang-doc") {
    return (
      <Card>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc hồ sơ từ máy chủ...</Text>
      </Card>
    );
  }
  if (trang.pha === "hong") {
    return (
      <Card>
        <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
        <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
      </Card>
    );
  }
  const { hoSo } = trang;

  if (dangSua) {
    return (
      <Card style={styles.card}>
        <Text style={[typography.title, { color: colors.ink }]}>Chỉnh hồ sơ</Text>
        <Field accessibilityLabel="Ô tên hiển thị" label="Tên" maxLength={200} onChangeText={setTen} value={ten} />
        <Field
          accessibilityLabel="Ô giới thiệu"
          label="Giới thiệu"
          maxLength={500}
          multiline
          onChangeText={setBio}
          placeholder="Vài chữ về bạn"
          value={bio}
        />
        <Field
          accessibilityLabel="Ô thành phố"
          label="Thành phố"
          maxLength={120}
          onChangeText={setCity}
          placeholder="Bạn hay ở đâu"
          value={city}
        />
        {loiLuu ? <Text style={[typography.body, { color: colors.warn }]}>{loiLuu}</Text> : null}
        <RudiButton disabled={dangLuu} label="Lưu hồ sơ" loading={dangLuu} onPress={() => void luu()} />
        <RudiButton disabled={dangLuu} label="Huỷ" onPress={() => setDangSua(false)} variant="ghost" />
      </Card>
    );
  }

  const soDem: { gia: number; nhan: string }[] = [
    { gia: hoSo.counts.friends, nhan: "bạn bè" },
    { gia: hoSo.counts.contexts, nhan: "nhóm" },
    { gia: hoSo.counts.outings, nhan: "kèo" },
    { gia: hoSo.counts.places_checked_in, nhan: "nơi đã tới" },
    { gia: hoSo.counts.memories, nhan: "kỷ niệm" },
  ];

  return (
    <>
      <Card style={styles.card}>
        <View style={styles.dau}>
          <View style={[styles.chuDau, { backgroundColor: colors.accentSoft }]}>
            <Text style={[typography.h1, { color: colors.accent }]}>{chuDau(hoSo.display_name)}</Text>
          </View>
          <View style={styles.dauChu}>
            <Text style={[typography.h1, { color: colors.ink }]}>{hoSo.display_name}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>
              Đăng nhập bằng {hoSo.login_methods.map((m) => NHAN_CUA[m] ?? m).join(", ") || "lời mời"}
            </Text>
          </View>
        </View>
        {hoSo.bio ? <Text style={[typography.body, { color: colors.inkSoft }]}>{hoSo.bio}</Text> : null}
        <Inline gap={7} wrap>
          {hoSo.city ? <Chip icon="location-outline" label={hoSo.city} /> : null}
          <Chip icon="calendar-outline" label={`Thành viên từ ${new Date(hoSo.created_at).getFullYear()}`} />
        </Inline>
        <RudiButton
          compact
          full={false}
          icon="create-outline"
          label="Chỉnh hồ sơ"
          onPress={() => moSua(hoSo)}
          variant="outline"
        />
      </Card>
      <Card style={styles.soDem}>
        {soDem.map((muc) => (
          <View key={muc.nhan} style={styles.mucDem}>
            <Text style={[typography.money, { color: colors.accent }]}>{String(muc.gia)}</Text>
            <Text style={[typography.caption, { color: colors.inkFaint }]}>{muc.nhan}</Text>
          </View>
        ))}
      </Card>
    </>
  );
}

const styles = StyleSheet.create({
  card: { gap: 12 },
  dau: { flexDirection: "row", alignItems: "center", gap: 14 },
  dauChu: { flex: 1, gap: 2 },
  chuDau: { width: 64, height: 64, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  soDem: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: 12 },
  mucDem: { minWidth: "18%", alignItems: "center", gap: 2 },
});
