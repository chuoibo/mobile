/**
 * Chọn điểm đến (M10): which city Khám phá is showing.
 *
 * The catalogue spans fifteen destinations, so the app has to ask. The list is
 * the server's; the choice is this phone's (AsyncStorage), because it is
 * browsing state rather than a fact about the person.
 *
 * «Gần tôi» is not on this screen yet: reading the device's position needs a
 * native module and a permission, and that arrives with its own build and its
 * own explanation screen (ADR-0018). What is here is the honest half -- pick a
 * city by name -- and it works with no permission at all.
 */
import { useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, thongDiepNguoiDoc } from "../../../api";
import {
  docDiemDen,
  docDiemDenDaChon,
  dongPhuDiemDen,
  luuDiemDen,
  type DiemDen,
} from "../../kham-pha/diem-den";
import { typography, useRudiTheme } from "../../theme";
import { Card, Divider, Heading, RudiButton, RudiScreen, SearchField, TopBar } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; ds: DiemDen[] }
  | { pha: "hong"; loi: string };

function khongDau(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase();
}

export function DiemDenScreen() {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [tim, setTim] = useState("");
  const [dangChon, setDangChon] = useState<string | null>(null);

  const nap = useCallback(async () => {
    setTrang({ pha: "dang-doc" });
    try {
      const [ds, daChon] = await Promise.all([docDiemDen(), docDiemDenDaChon()]);
      setDangChon(daChon);
      setTrang({ pha: "xong", ds: ds.diemDen });
    } catch (error) {
      setTrang({
        pha: "hong",
        loi: error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null),
      });
    }
  }, []);

  useEffect(() => {
    void nap();
  }, [nap]);

  const chon = async (diemDen: DiemDen) => {
    setDangChon(diemDen.id);
    await luuDiemDen(diemDen.id);
    router.back();
  };

  const loc =
    trang.pha === "xong"
      ? trang.ds.filter((d) => {
          const q = khongDau(tim.trim());
          if (q === "") return true;
          return khongDau(`${d.name} ${d.province ?? ""}`).includes(q);
        })
      : [];

  return (
    <RudiScreen testID="diem-den-screen">
      <TopBar title="Đi đâu?" />
      <SearchField
        onChangeText={setTim}
        placeholder="Tìm thành phố hoặc tỉnh"
        value={tim}
      />
      {trang.pha === "dang-doc" ? (
        <Card>
          <Text style={[typography.body, { color: colors.inkFaint }]}>Đang đọc danh sách…</Text>
        </Card>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <View style={styles.khoangTren}>
            <RudiButton label="Thử lại" onPress={() => void nap()} variant="outline" />
          </View>
        </Card>
      ) : null}
      {trang.pha === "xong" && loc.length === 0 ? (
        <Heading
          subtitle="RuDi mới biết mười lăm nơi. Thử tên khác, hoặc xoá ô tìm để xem hết."
          title="Chưa có nơi nào khớp"
        />
      ) : null}
      {loc.length > 0 ? (
        <Card style={styles.danhSach}>
          {loc.map((d, i) => (
            <View key={d.id}>
              {i > 0 ? <Divider /> : null}
              <Pressable
                accessibilityLabel={`Chọn ${d.name}`}
                accessibilityRole="button"
                onPress={() => void chon(d)}
                style={styles.hang}
              >
                <View style={styles.hangChu}>
                  <Text
                    style={[
                      typography.title,
                      { color: dangChon === d.id ? colors.accent : colors.ink },
                    ]}
                  >
                    {d.name}
                  </Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>
                    {dongPhuDiemDen(d)}
                  </Text>
                  {d.blurb === null ? null : (
                    <Text numberOfLines={2} style={[typography.caption, { color: colors.inkSoft }]}>
                      {d.blurb}
                    </Text>
                  )}
                </View>
              </Pressable>
            </View>
          ))}
        </Card>
      ) : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  danhSach: { paddingVertical: 6 },
  hang: { minHeight: 64, justifyContent: "center", paddingVertical: 10 },
  hangChu: { gap: 3 },
  khoangTren: { marginTop: 4 },
});
