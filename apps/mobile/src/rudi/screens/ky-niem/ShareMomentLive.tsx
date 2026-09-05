/**
 * Thả khoảnh khắc on a real session (M6): one photo, one caption, into the
 * group the session is in. The photo is shown before anything is sent; the
 * upload is App B's two requests (bytes, then the memory under its own
 * Attempt); a failure keeps the draft on screen instead of clearing it.
 */
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { ApiError, thongDiepNguoiDoc, type Attempt } from "../../../api";
import type { Phien } from "../../../phien";
import { boAnh, chonAnh, nenVaDung, type GiaiDoanTaiAnh, type TempPhoto } from "../../ky-niem/chon-anh";
import { CAPTION_DAI_NHAT, dangAnhLenTuong } from "../../ky-niem/ky-niem";
import { typography, useRudiTheme } from "../../theme";
import { Card, Field, Heading, RudiButton, RudiScreen, TopBar } from "../../ui";

function loiRaChu(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message !== "") return error.message;
  return thongDiepNguoiDoc(0, null);
}

function cauGiaiDoan(giaiDoan: GiaiDoanTaiAnh | null): string | null {
  if (giaiDoan === "chuan-bi-anh") return "Đang chuẩn bị ảnh…";
  if (giaiDoan === "dang-gui") return "Đang tải ảnh lên…";
  return null;
}

export function ShareMomentLiveScreen({ phien }: { phien: Phien }) {
  const router = useRouter();
  const params = useLocalSearchParams<{ place?: string; ten?: string }>();
  const { colors, radius } = useRudiTheme();
  const contextId = phien.context_id;
  // Mở từ màn một địa điểm thì ảnh được gắn vào chỗ ấy (M12, ADR-0017 §2.4).
  // Chỉ id đi lên máy chủ; TÊN chỗ ở đây thuần tuý để nói cho người đăng biết
  // họ đang gắn vào đâu, máy chủ tra tên của chính nó.
  const placeId = typeof params.place === "string" && params.place !== "" ? params.place : null;
  const tenCho = typeof params.ten === "string" && params.ten !== "" ? params.ten : null;
  const [anh, setAnh] = useState<TempPhoto | null>(null);
  const [caption, setCaption] = useState("");
  const [giaiDoan, setGiaiDoan] = useState<GiaiDoanTaiAnh | null>(null);
  const [ban, setBan] = useState(false);
  const [thongBao, setThongBao] = useState<string | null>(null);
  const attempts = useRef<Record<string, Attempt>>({});

  if (contextId === null) {
    return (
      <RudiScreen testID="share-moment-screen">
        <TopBar title="Thả khoảnh khắc" />
        <Heading title="Vào một nhóm trước" subtitle="Khoảnh khắc đăng vào tường của một nhóm; chưa có nhóm thì chưa có tường." />
        <RudiButton label="Tới Tin nhắn" onPress={() => router.push("/(tabs)/messages" as never)} variant="outline" />
      </RudiScreen>
    );
  }
  const ctx = contextId;

  const chon = async () => {
    setThongBao(null);
    try {
      const daChon = await chonAnh();
      if (daChon === null) return;
      if (anh !== null) await boAnh(anh);
      setAnh(daChon);
    } catch (error) {
      setThongBao(loiRaChu(error));
    }
  };

  const chiaSe = async () => {
    if (anh === null) return;
    setBan(true);
    setThongBao(null);
    try {
      await nenVaDung(anh, (nen) => dangAnhLenTuong(ctx, nen, caption.trim() === "" ? null : caption.trim(), phien.person_id, attempts.current, placeId), setGiaiDoan);
      router.replace(`/groups/${ctx}/wall` as never);
    } catch (error) {
      // The draft stays: the caption is still in the field, the photo is
      // still previewed (the compressed copy was discarded, the pick was not).
      setThongBao(loiRaChu(error));
    } finally {
      setGiaiDoan(null);
      setBan(false);
    }
  };

  const conLai = CAPTION_DAI_NHAT - caption.length;
  const cauTrangThai = cauGiaiDoan(giaiDoan);

  return (
    <RudiScreen testID="share-moment-screen">
      <TopBar title="Thả khoảnh khắc" />
      <Heading title="Một khoảnh khắc cho nhóm" subtitle="Ảnh và một câu, lên tường của nhóm bạn đang ở. Chỉ thành viên nhóm thấy." />
      {thongBao !== null ? <Text style={[typography.body, { color: colors.warn }]}>{thongBao}</Text> : null}
      <Card style={styles.polaroid}>
        {anh === null ? (
          <View accessibilityLabel="Chưa chọn ảnh" style={[styles.khungTrong, { backgroundColor: colors.accentSoft, borderRadius: radius.small }]}>
            <Ionicons color={colors.accent} name="camera-outline" size={40} />
            <Text style={[typography.caption, { color: colors.inkSoft }]}>Chưa có ảnh. Chọn một tấm từ thư viện.</Text>
          </View>
        ) : (
          <Image accessibilityLabel="Ảnh đã chọn" contentFit="cover" source={{ uri: anh.uri }} style={[styles.anh, { borderRadius: radius.small }]} />
        )}
        <Text numberOfLines={2} style={[typography.body, { color: colors.ink }]}>
          {caption.trim() === "" ? "Câu của bạn hiện ở đây" : caption.trim()}
        </Text>
      </Card>
      <RudiButton disabled={ban} icon="images-outline" label={anh === null ? "Chọn ảnh" : "Chọn ảnh khác"} onPress={() => void chon()} variant="outline" />
      <Field
        accessibilityLabel="Ô câu chú thích"
        label={`Một câu cho khoảnh khắc (${conLai} ký tự còn lại)`}
        maxLength={CAPTION_DAI_NHAT}
        multiline
        onChangeText={setCaption}
        placeholder="Ví dụ: Đà Lạt về đêm"
        value={caption}
      />
      {placeId === null ? null : (
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          {`Gắn vào ${tenCho ?? "địa điểm bạn vừa mở"}: ảnh sẽ hiện ở màn chỗ đó, cho người trong nhóm.`}
        </Text>
      )}
      <Text style={[typography.caption, { color: colors.inkSoft }]}>Đăng vào nhóm hiện tại. Máy chủ lột dữ liệu EXIF của ảnh trước khi lưu.</Text>
      <RudiButton disabled={ban || anh === null} icon="paper-plane-outline" label="Chia sẻ ngay vào nhóm" loading={ban} onPress={() => void chiaSe()} />
      {cauTrangThai !== null ? <Text style={[typography.caption, { color: colors.inkFaint }]}>{cauTrangThai}</Text> : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  polaroid: { gap: 10, padding: 12 },
  khungTrong: { alignItems: "center", justifyContent: "center", gap: 8, aspectRatio: 1 },
  anh: { width: "100%", aspectRatio: 1 },
});
