/**
 * One kèo on a real session (M4): its stops in clock order with who has
 * arrived at each, a form to add a stop (optionally on a catalogue place),
 * and «Đánh dấu tôi đã tới» per stop. A stop with a place opens that place;
 * a stop without one opens the picker to attach one, so every row goes
 * somewhere.
 */
import { Ionicons } from "@expo/vector-icons";
import { Redirect, useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, newAttempt, thongDiepNguoiDoc } from "../../../api";
import type { Phien } from "../../../phien";
import type { Place } from "../../../screens/kham-pha/places";
import {
  nhanKhoangNgay,
  nhomCheckInTheoChang,
  tongDuKien,
  type BuoiDi,
  type ChangDung,
  type CheckIn,
} from "../../../screens/len-plan/buoi-di";
import { docDanhMuc } from "../../kham-pha/dia-diem";
import {
  cauDaToi,
  cauSoChang,
  danhDauToi,
  docDaToi,
  docKeoCuaNhom,
  ganDiaDiem,
  gioTiepTheo,
  kiemTraChangMoi,
  luuLichTrinh,
  themChang,
} from "../../keo/keo";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Field, Heading, Inline, RudiButton, RudiScreen, SectionHeader, TopBar } from "../../ui";
import { dinhDangTienVnd } from "../../../screens/chat/ke-hoach";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; keo: BuoiDi; daToi: CheckIn[] }
  | { pha: "hong"; loi: string };

/** A route param is a string or nothing. */
function thamSoChuoi(v: unknown): string {
  if (typeof v === "string") return v;
  return "";
}

/** The picked place's key, or nothing when none is picked. */
function idNeuCo(place: Place | null): string | null {
  if (place === null) return null;
  return place.id;
}

function tenNeuCo(place: Place | null): string | null {
  if (place === null) return null;
  return place.name;
}

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function OutingLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const { colors } = useRudiTheme();
  const outingId = thamSoChuoi(params.id);
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [dangGhi, setDangGhi] = useState(false);
  const [moThem, setMoThem] = useState(false);
  const [gio, setGio] = useState(gioTiepTheo());
  const [nhan, setNhan] = useState("");
  const [danhMuc, setDanhMuc] = useState<Place[]>([]);
  const [choDiaDiem, setChoDiaDiem] = useState<Place | null>(null);
  const [ganChoChang, setGanChoChang] = useState<ChangDung | null>(null);
  const contextId = phien.context_id;

  const nap = useCallback(async () => {
    if (contextId === null || !outingId) return;
    try {
      const keo = (await docKeoCuaNhom(contextId, phien.person_id)).find((k) => k.id === outingId);
      if (keo === undefined) {
        setTrang({ pha: "hong", loi: "Kèo này không còn trong nhóm." });
        return;
      }
      const daToi = await docDaToi(keo, phien.person_id);
      setTrang({ pha: "xong", keo, daToi });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  }, [contextId, outingId, phien.person_id]);

  useFocusEffect(
    useCallback(() => {
      void nap();
    }, [nap]),
  );

  const napDanhMuc = useCallback(async () => {
    if (danhMuc.length > 0) return;
    try {
      setDanhMuc((await docDanhMuc()).places);
    } catch (error) {
      setThongBao(loiRaChu(error));
    }
  }, [danhMuc.length]);

  const theoChang = useMemo<Record<string, CheckIn[]>>(
    () => (trang.pha === "xong" ? nhomCheckInTheoChang(trang.daToi) : {}),
    [trang],
  );

  if (contextId === null) return <Redirect href="/(tabs)/plan" />;

  const ghiLichTrinh = async (keo: BuoiDi, stops: ReturnType<typeof themChang>) => {
    setDangGhi(true);
    setThongBao(null);
    try {
      const moi = await luuLichTrinh(keo, stops, phien.person_id, newAttempt());
      setTrang({ pha: "xong", keo: moi, daToi: trang.pha === "xong" ? trang.daToi : [] });
      return true;
    } catch (error) {
      setThongBao(loiRaChu(error));
      return false;
    } finally {
      setDangGhi(false);
    }
  };

  const themChangMoi = async (keo: BuoiDi) => {
    const kq = kiemTraChangMoi(gio, nhan);
    if (!kq.ok) {
      setThongBao(kq.loi);
      return;
    }
    const ok = await ghiLichTrinh(
      keo,
      themChang(keo.stops, {
        at: gio.trim(),
        label: nhan.trim(),
        place_name: tenNeuCo(choDiaDiem),
        place_id: idNeuCo(choDiaDiem),
      }),
    );
    if (ok) {
      setMoThem(false);
      setNhan("");
      setChoDiaDiem(null);
      setGio(gioTiepTheo());
    }
  };

  const ganChang = async (keo: BuoiDi, stop: ChangDung, place: Place) => {
    const ok = await ghiLichTrinh(keo, ganDiaDiem(keo.stops, stop.id, place));
    if (ok) setGanChoChang(null);
  };

  const daToiChang = async (keo: BuoiDi, stop: ChangDung) => {
    setDangGhi(true);
    setThongBao(null);
    try {
      await danhDauToi(stop.id, keo.context_id, phien.person_id, newAttempt());
      setTrang({ pha: "xong", keo, daToi: await docDaToi(keo, phien.person_id) });
    } catch (error) {
      setThongBao(loiRaChu(error));
    } finally {
      setDangGhi(false);
    }
  };

  const moHang = (stop: ChangDung) => {
    if (stop.place_id !== null) {
      router.push(`/places/${stop.place_id}` as never);
      return;
    }
    setGanChoChang(stop);
    void napDanhMuc();
  };

  return (
    <RudiScreen testID="outing-screen">
      <TopBar title="Kèo" />
      {trang.pha === "dang-doc" ? (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>Đang đọc kèo từ máy chủ...</Text>
      ) : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Về Lên plan" onPress={() => router.back()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" ? (
        <>
          <Heading
            title={trang.keo.title}
            subtitle={`${nhanKhoangNgay(trang.keo.starts_on, trang.keo.ends_on)} · ${trang.keo.headcount} người`}
          />
          <Card style={styles.tongQuan}>
            <View style={styles.oTong}>
              <Text numberOfLines={1} style={[typography.money, { color: colors.ink }]}>
                {dinhDangTienVnd(trang.keo.budget_per_person_vnd)}
              </Text>
              <Text numberOfLines={1} style={[typography.caption, { color: colors.inkFaint }]}>
                một người
              </Text>
            </View>
            <View style={[styles.vach, { backgroundColor: colors.line }]} />
            <View style={styles.oTong}>
              <Text style={[typography.money, { color: colors.ink }]}>
                {dinhDangTienVnd(tongDuKien(trang.keo.budget_per_person_vnd, trang.keo.headcount))}
              </Text>
              <Text numberOfLines={1} style={[typography.caption, { color: colors.inkFaint }]}>
                cả kèo, tham chiếu
              </Text>
            </View>
            <View style={[styles.vach, { backgroundColor: colors.line }]} />
            <Pressable
              accessibilityLabel="Thành viên nhóm"
              accessibilityRole="button"
              onPress={() => router.push(`/groups/${trang.keo.context_id}/members` as never)}
              style={styles.oTong}
            >
              <Ionicons color={colors.accent} name="people-outline" size={22} />
              <Text style={[typography.caption, { color: colors.accent }]}>thành viên</Text>
            </Pressable>
          </Card>
          <SectionHeader
            action={moThem ? "Đóng" : "Thêm chặng"}
            onAction={() => {
              setMoThem((v) => !v);
              void napDanhMuc();
            }}
            title={cauSoChang(trang.keo.stops.length)}
          />
          {moThem ? (
            <Card style={styles.form}>
              <View style={styles.hang}>
                <View style={styles.oGio}>
                  <Field accessibilityLabel="Ô giờ chặng" icon="time-outline" keyboardType="numbers-and-punctuation" label="Giờ" onChangeText={setGio} value={gio} />
                </View>
                <View style={styles.flex}>
                  <Field accessibilityLabel="Ô tên chặng" icon="flag-outline" label="Chặng" onChangeText={setNhan} placeholder="Ví dụ: Ăn tối" value={nhan} />
                </View>
              </View>
              <Text style={[typography.caption, { color: colors.inkSoft }]}>Địa điểm trong danh mục (tuỳ chọn)</Text>
              <Inline gap={6} wrap>
                {danhMuc.map((p) => (
                  <Chip
                    key={p.id}
                    label={p.name}
                    onPress={() => setChoDiaDiem(choDiaDiem !== null && choDiaDiem.id === p.id ? null : p)}
                    selected={choDiaDiem !== null && choDiaDiem.id === p.id}
                  />
                ))}
              </Inline>
              <RudiButton disabled={dangGhi} label="Thêm chặng" loading={dangGhi} onPress={() => void themChangMoi(trang.keo)} />
            </Card>
          ) : null}
          {ganChoChang !== null ? (
            <Card style={styles.form}>
              <Text style={[typography.title, { color: colors.ink }]}>Gắn địa điểm cho «{ganChoChang.label}»</Text>
              <Inline gap={6} wrap>
                {danhMuc.map((p) => (
                  <Chip key={p.id} label={p.name} onPress={() => void ganChang(trang.keo, ganChoChang, p)} />
                ))}
              </Inline>
              <RudiButton label="Để sau" onPress={() => setGanChoChang(null)} variant="ghost" />
            </Card>
          ) : null}
          {thongBao !== null ? <Text style={[typography.caption, { color: colors.warn }]}>{thongBao}</Text> : null}
          {trang.keo.stops.length > 0 ? (
            <Card style={styles.danhSach}>
              {trang.keo.stops.map((stop, i) => {
                const daToi = theoChang[stop.id] ?? [];
                return (
                  <View key={stop.id} style={styles.hangChang}>
                    <View style={styles.cotGio}>
                      <Text style={[typography.label, { color: colors.ink }]}>{stop.at}</Text>
                      {i < trang.keo.stops.length - 1 ? <View style={[styles.duongGio, { backgroundColor: colors.line }]} /> : null}
                    </View>
                    <Pressable
                      accessibilityLabel={`Chặng ${stop.label}`}
                      accessibilityRole="button"
                      onPress={() => moHang(stop)}
                      style={styles.thanChang}
                    >
                      {stop.place_name === stop.label ? (
                        // A stop named after its place says the name once, as the place link.
                        <Text style={[typography.label, { color: colors.accent }]}>{stop.label}</Text>
                      ) : (
                        <>
                          <Text style={[typography.label, { color: colors.ink }]}>{stop.label}</Text>
                          <Text style={[typography.caption, { color: stop.place_id === null ? colors.inkFaint : colors.accent }]}>
                            {stop.place_name === null ? "Chưa gắn địa điểm · bấm để chọn" : stop.place_name}
                          </Text>
                        </>
                      )}
                      <Text style={[typography.caption, { color: colors.inkSoft }]}>{cauDaToi(daToi, phien.person_id)}</Text>
                    </Pressable>
                    {/* Both states sit in the same 48dp box so the row's right
                        edge does not jump between a badge and a button. */}
                    <View style={styles.oPhai}>
                      {daToi.some((c) => c.person_id === phien.person_id) ? (
                        // Arrived is a fact, not a control that went grey: a static badge.
                        <Chip icon="checkmark" label="Đã tới" selected />
                      ) : (
                        <RudiButton
                          compact
                          disabled={dangGhi}
                          full={false}
                          label="Tôi đã tới"
                          onPress={() => void daToiChang(trang.keo, stop)}
                          variant="outline"
                        />
                      )}
                    </View>
                  </View>
                );
              })}
            </Card>
          ) : (
            <Text style={[typography.caption, { color: colors.inkSoft }]}>
              Bấm «Thêm chặng», hoặc mở một địa điểm ở Khám phá rồi «Thêm vào kèo».
            </Text>
          )}
        </>
      ) : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  tongQuan: { flexDirection: "row", alignItems: "center", padding: 12 },
  oTong: { flex: 1, alignItems: "center", gap: 3, minHeight: 48, justifyContent: "center" },
  vach: { width: StyleSheet.hairlineWidth, alignSelf: "stretch" },
  form: { gap: 12 },
  hang: { flexDirection: "row", gap: 10 },
  oGio: { width: 118 },
  danhSach: { paddingVertical: 6, gap: 0 },
  hangChang: { flexDirection: "row", alignItems: "flex-start", gap: 10, paddingVertical: 8 },
  cotGio: { width: 52, alignItems: "center", gap: 6 },
  duongGio: { width: 2, flex: 1, minHeight: 18, borderRadius: 1 },
  thanChang: { flex: 1, gap: 2, minHeight: 48 },
  oPhai: { minHeight: 48, justifyContent: "center", flexShrink: 0 },
});
