/**
 * Tường nhóm on a real session (M6): the group's memories as the server
 * lists them, newest first, paged by its cursor. Hearts and comments are one
 * request each and the counts drawn are the server's; a check-in is a memory
 * without a photo, pinned to a catalogue place; a photo goes through «Thả
 * khoảnh khắc». Only members see any of it, which the subtitle says.
 */
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, attemptFor, thongDiepNguoiDoc, type Attempt } from "../../../api";
import type { Phien } from "../../../phien";
import { danhSachThanhVien } from "../../../screens/vao-cua/cong-api";
import { tenCua, type ThanhVien } from "../../chia-bill/hoa-don";
import { docDanhMuc } from "../../kham-pha/dia-diem";
import {
  cauKyNiem,
  cauTuongTac,
  checkInKyNiem,
  docBinhLuanCua,
  docTuongNhom,
  doiTim,
  guiBinhLuanCho,
  nguonAnh,
  type BinhLuan,
  type KyNiem,
} from "../../ky-niem/ky-niem";
import { typography, useRudiTheme } from "../../theme";
import { Card, Chip, Field, Heading, Inline, ListRow, RudiButton, RudiScreen, SearchField, SectionHeader, TopBar } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; kyNiem: KyNiem[]; conTro: string | null; conNua: boolean }
  | { pha: "hong"; loi: string };

type Cho = { id: string; name: string };

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

function tenHienThi(ten: string | null | undefined): string {
  if (typeof ten === "string" && ten.trim() !== "") return ten;
  return "Thành viên";
}

function gioViet(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function GroupWallLiveScreen({ phien, contextId }: { phien: Phien; contextId: string }) {
  const router = useRouter();
  const { colors, radius } = useRudiTheme();
  const me = phien.person_id;
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [roster, setRoster] = useState<ThanhVien[]>([]);
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [ban, setBan] = useState(false);
  const [moBinhLuan, setMoBinhLuan] = useState<string | null>(null);
  const [binhLuan, setBinhLuan] = useState<Record<string, BinhLuan[]>>({});
  const [nhap, setNhap] = useState("");
  const [moCheckIn, setMoCheckIn] = useState(false);
  const [danhMuc, setDanhMuc] = useState<Cho[] | null>(null);
  const [timCho, setTimCho] = useState("");
  const [choChon, setChoChon] = useState<Cho | null>(null);
  const [cauCheckIn, setCauCheckIn] = useState("");
  const attempts = useRef<Record<string, Attempt>>({});

  const docTrangDau = useCallback(async () => {
    const t = await docTuongNhom(contextId, me);
    setTrang({ pha: "xong", kyNiem: t.kyNiem, conTro: t.conTro, conNua: t.conNua });
  }, [contextId, me]);

  useFocusEffect(
    useCallback(() => {
      let song = true;
      docTrangDau().catch((error: unknown) => {
        if (song) setTrang({ pha: "hong", loi: loiRaChu(error) });
      });
      return () => {
        song = false;
      };
    }, [docTrangDau]),
  );

  useEffect(() => {
    let song = true;
    void danhSachThanhVien(contextId, me)
      .then((ds) => {
        if (song) setRoster(ds.map((tv) => ({ id: tv.person_id, name: tenHienThi(tv.display_name) })));
      })
      .catch(() => undefined);
    return () => {
      song = false;
    };
  }, [contextId, me]);

  const chay = async (viec: () => Promise<void>) => {
    setBan(true);
    setThongBao(null);
    try {
      await viec();
    } catch (error) {
      setThongBao(loiRaChu(error));
    } finally {
      setBan(false);
    }
  };

  const thayKyNiem = (moi: KyNiem) =>
    setTrang((t) => (t.pha === "xong" ? { ...t, kyNiem: t.kyNiem.map((k) => (k.id === moi.id ? moi : k)) } : t));

  const tim = (k: KyNiem) => chay(async () => thayKyNiem(await doiTim(k, contextId, me)));

  const moHoacDongBinhLuan = (k: KyNiem) =>
    chay(async () => {
      if (moBinhLuan === k.id) {
        setMoBinhLuan(null);
        return;
      }
      setMoBinhLuan(k.id);
      setNhap("");
      if (binhLuan[k.id] === undefined) {
        const ds = await docBinhLuanCua(contextId, k.id, me);
        setBinhLuan((b) => ({ ...b, [k.id]: ds }));
      }
    });

  const guiBinhLuan = (k: KyNiem) =>
    chay(async () => {
      if (nhap.trim() === "") return;
      const bl = await guiBinhLuanCho(contextId, k.id, nhap, me, attempts.current);
      setBinhLuan((b) => ({ ...b, [k.id]: [...(b[k.id] === undefined ? [] : b[k.id]), bl] }));
      thayKyNiem({ ...k, commentCount: k.commentCount + 1 });
      setNhap("");
    });

  const taiThem = () =>
    chay(async () => {
      if (trang.pha !== "xong" || trang.conTro === null) return;
      const t = await docTuongNhom(contextId, me, { before: trang.conTro });
      setTrang({ pha: "xong", kyNiem: [...trang.kyNiem, ...t.kyNiem], conTro: t.conTro, conNua: t.conNua });
    });

  const moCheckInForm = () =>
    chay(async () => {
      setMoCheckIn(true);
      if (danhMuc === null) {
        const dm = await docDanhMuc();
        setDanhMuc(dm.places.map((p) => ({ id: p.id, name: p.name })));
      }
    });

  const dangCheckIn = () =>
    chay(async () => {
      if (choChon === null) return;
      const k = await checkInKyNiem(contextId, choChon.id, cauCheckIn, me, attemptFor(attempts.current, `check-in:${choChon.id}:${cauCheckIn.trim()}`));
      setTrang((t) => (t.pha === "xong" ? { ...t, kyNiem: [k, ...t.kyNiem] } : t));
      setMoCheckIn(false);
      setChoChon(null);
      setCauCheckIn("");
    });

  // At most a dozen chips: a hundred is a haystack. Diacritic-insensitive, so
  // «di be» finds «Dì Bé» the way the Explore filter does.
  const choHienRa = (danhMuc ?? [])
    .filter((cho) => {
      const q = timCho.trim();
      if (q === "") return true;
      const gap = (x: string) =>
        x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/gi, "d").toLowerCase();
      return gap(cho.name).includes(gap(q));
    })
    .slice(0, 12);

  return (
    <RudiScreen testID="group-wall-screen">
      <TopBar subtitle="Chỉ thành viên nhóm thấy" title="Tường nhóm" />
      {thongBao !== null ? <Text style={[typography.body, { color: colors.warn }]}>{thongBao}</Text> : null}
      <View style={styles.haiNut}>
        <View style={styles.flex}>
          <RudiButton icon="camera-outline" label="Thả khoảnh khắc" onPress={() => router.push("/moments/new" as never)} />
        </View>
        <View style={styles.flex}>
          <RudiButton disabled={ban} icon="location-outline" label="Check-in" onPress={() => void moCheckInForm()} variant="soft" />
        </View>
      </View>

      {moCheckIn ? (
        <Card style={styles.form}>
          <SectionHeader title="Check-in ở đâu?" />
          {danhMuc === null ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc danh mục…</Text> : null}
          {/* A destination holds a hundred places since the catalogue became
              real (M9), so this stopped being a chip row and became a search:
              a hundred chips is a haystack, not a choice. The box narrows;
              what stays is the first dozen matches. */}
          {danhMuc === null ? null : (
            <SearchField
              accessibilityLabel="Ô tìm chỗ check-in"
              onChangeText={setTimCho}
              placeholder="Tìm chỗ bạn đang ở"
              value={timCho}
            />
          )}
          <Inline gap={6} wrap>
            {choHienRa.map((cho) => (
              <Chip accessibilityLabel={`Chọn ${cho.name}`} key={cho.id} label={cho.name} onPress={() => setChoChon(cho)} selected={choChon !== null && choChon.id === cho.id} />
            ))}
          </Inline>
          {danhMuc !== null && choHienRa.length === 0 ? (
            <Text style={[typography.caption, { color: colors.inkFaint }]}>
              Không có chỗ nào khớp «{timCho}». Thử tên ngắn hơn nhé.
            </Text>
          ) : null}
          <Field accessibilityLabel="Ô câu check-in" label="Một câu (không bắt buộc)" onChangeText={setCauCheckIn} placeholder="Ví dụ: Ốc ở đây ngon" value={cauCheckIn} />
          <RudiButton disabled={ban || choChon === null} icon="checkmark" label="Đăng check-in" loading={ban} onPress={() => void dangCheckIn()} />
          <RudiButton label="Thôi" onPress={() => setMoCheckIn(false)} variant="ghost" />
        </Card>
      ) : null}

      {trang.pha === "dang-doc" ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc tường từ máy chủ…</Text> : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void chay(docTrangDau)} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" && trang.kyNiem.length === 0 ? (
        <Card>
          <Heading size="h2" title="Chưa có kỷ niệm nào" subtitle="Thả khoảnh khắc đầu tiên của nhóm, hoặc check-in ở chỗ đang ngồi." />
        </Card>
      ) : null}
      {trang.pha === "xong"
        ? trang.kyNiem.map((k) => {
            const anh = nguonAnh(k.imageUrl, me, contextId);
            const dsBl = binhLuan[k.id];
            return (
              <Card key={k.id} style={styles.bai}>
                <View style={styles.dong}>
                  <Text style={[typography.label, styles.flex, { color: colors.ink }]}>{tenCua(roster, k.authorId)}</Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>{gioViet(k.createdAt)}</Text>
                </View>
                {anh !== null ? (
                  <Image accessibilityLabel={cauKyNiem(k)} contentFit="cover" source={anh} style={[styles.anh, { borderRadius: radius.small }]} />
                ) : null}
                {k.kind === "checkin" ? (
                  <ListRow icon="location" title={cauKyNiem(k)} subtitle={k.caption === null || k.caption.trim() === "" ? undefined : k.caption} />
                ) : k.caption !== null && k.caption.trim() !== "" ? (
                  <Text style={[typography.body, { color: colors.ink }]}>{k.caption}</Text>
                ) : null}
                <Text style={[typography.caption, { color: colors.inkFaint }]}>{cauTuongTac(k)}</Text>
                <View style={styles.hanhDong}>
                  <Pressable
                    accessibilityLabel={`${k.toiDaTim ? "Bỏ tim" : "Thả tim"} ${cauKyNiem(k)}`}
                    accessibilityRole="button"
                    aria-pressed={k.toiDaTim}
                    disabled={ban}
                    onPress={() => void tim(k)}
                    style={({ pressed }) => [styles.nutHanhDong, pressed && styles.pressed]}
                  >
                    <Ionicons color={k.toiDaTim ? colors.accent : colors.inkSoft} name={k.toiDaTim ? "heart" : "heart-outline"} size={22} />
                    <Text style={[typography.label, { color: k.toiDaTim ? colors.accent : colors.inkSoft }]}>{k.toiDaTim ? "Đã tim" : "Thích"}</Text>
                  </Pressable>
                  <Pressable
                    accessibilityLabel={`${moBinhLuan === k.id ? "Ẩn bình luận" : "Bình luận"} ${cauKyNiem(k)}`}
                    accessibilityRole="button"
                    aria-expanded={moBinhLuan === k.id}
                    disabled={ban}
                    onPress={() => void moHoacDongBinhLuan(k)}
                    style={({ pressed }) => [styles.nutHanhDong, pressed && styles.pressed]}
                  >
                    <Ionicons color={moBinhLuan === k.id ? colors.accent : colors.inkSoft} name={moBinhLuan === k.id ? "chatbubble" : "chatbubble-outline"} size={21} />
                    <Text style={[typography.label, { color: moBinhLuan === k.id ? colors.accent : colors.inkSoft }]}>{moBinhLuan === k.id ? "Ẩn bình luận" : "Bình luận"}</Text>
                  </Pressable>
                </View>
                {moBinhLuan === k.id ? (
                  <View style={styles.khungBl}>
                    {dsBl === undefined ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc bình luận…</Text> : null}
                    {dsBl !== undefined && dsBl.length === 0 ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Chưa có bình luận. Viết câu đầu tiên.</Text> : null}
                    {(dsBl === undefined ? [] : dsBl).map((bl) => (
                      <Text key={bl.id} style={[typography.body, { color: colors.ink }]}>
                        <Text style={typography.label}>{bl.tenTacGia}: </Text>
                        {bl.noiDung}
                      </Text>
                    ))}
                    <Field accessibilityLabel="Ô viết bình luận" onChangeText={setNhap} placeholder="Viết bình luận…" value={nhap} />
                    <RudiButton compact disabled={ban || nhap.trim() === ""} full={false} label="Gửi bình luận" loading={ban} onPress={() => void guiBinhLuan(k)} variant="soft" />
                  </View>
                ) : null}
              </Card>
            );
          })
        : null}
      {trang.pha === "xong" && trang.conNua ? <RudiButton disabled={ban} label="Tải thêm kỷ niệm cũ hơn" onPress={() => void taiThem()} variant="outline" /> : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  form: { gap: 10 },
  bai: { gap: 10 },
  dong: { flexDirection: "row", alignItems: "center", gap: 10 },
  anh: { width: "100%", aspectRatio: 4 / 3 },
  hanhDong: { flexDirection: "row", gap: 8 },
  haiNut: { flexDirection: "row", gap: 8 },
  nutHanhDong: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12 },
  pressed: { opacity: 0.7 },
  khungBl: { gap: 8 },
});
