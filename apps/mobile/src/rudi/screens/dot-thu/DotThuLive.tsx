/**
 * One collection round (đợt thu) on a real session (M5, slice v-b).
 *
 * What the screen draws is the server's board: who transfers to whom, how
 * much, and whether it arrived -- status derived on the server from confirmed
 * receipts, never from a button here. The three things a person can do:
 *
 *   - publish the round (the organiser): obligations become real and every
 *     sender gets a private guest link, returned exactly once;
 *   - send a link (the organiser): one share sheet per person, never a bulk
 *     send, and a dismissed sheet is not counted as sent;
 *   - say the money arrived (the recipient of that obligation, nobody else).
 *
 * A phone that did not publish the round has no links to send: the server
 * keeps only a digest of each token, and this screen says so.
 */
import { useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Share, StyleSheet, Text, View } from "react-native";

import { ApiError, attemptFor, thongDiepNguoiDoc, type Attempt } from "../../../api";
import type { Phien } from "../../../phien";
import { dinhDangTienVnd } from "../../../screens/chat/ke-hoach";
import { danhSachThanhVien } from "../../../screens/vao-cua/cong-api";
import { tenCua, type ThanhVien } from "../../chia-bill/hoa-don";
import {
  TU_NGHIA_VU,
  cauHangNghiaVu,
  cauTrangThaiDot,
  daPhat,
  docBangThu,
  docDotThuCuaNhom,
  loiNhanChiaSe,
  nghiaVuToiNhan,
  phatDotThu,
  tomTatBang,
  xacNhanDaNhan,
  type Envelope,
  type NghiaVu,
  type TrangThaiDot,
} from "../../dot-thu/dot-thu";
import { docLinkDot, luuLinkDot } from "../../dot-thu/kho-link";
import { typography, useRudiTheme } from "../../theme";
import { Card, Heading, RudiButton, RudiScreen, SectionHeader, TopBar } from "../../ui";

type Trang =
  | { pha: "dang-doc" }
  | { pha: "xong"; nghiaVu: NghiaVu[]; soTranhCai: number; trangThai: TrangThaiDot | null; links: Envelope[] | null }
  | { pha: "hong"; loi: string };

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

function tenHienThi(ten: string | null | undefined): string {
  if (typeof ten === "string" && ten.trim() !== "") return ten;
  return "Thành viên";
}

export function DotThuLiveScreen({ phien, batchId }: { phien: Phien; batchId: string }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const contextId = phien.context_id;
  const [trang, setTrang] = useState<Trang>({ pha: "dang-doc" });
  const [roster, setRoster] = useState<ThanhVien[]>([]);
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [ban, setBan] = useState(false);
  // Per sender: the sheet was opened and not dismissed. Not "delivered" -- the
  // phone cannot know that -- and the caption says as much.
  const [daMoKhay, setDaMoKhay] = useState<Record<string, boolean>>({});
  const attempts = useRef<Record<string, Attempt>>({});

  const doc = useCallback(async () => {
    if (contextId === null) return;
    const [bang, danhSach, links] = await Promise.all([
      docBangThu(contextId, batchId, phien.person_id),
      docDotThuCuaNhom(contextId, phien.person_id),
      docLinkDot(batchId),
    ]);
    const dot = danhSach.find((d) => d.id === batchId);
    setTrang({ pha: "xong", nghiaVu: bang.nghiaVu, soTranhCai: bang.soTranhCai, trangThai: dot === undefined ? null : dot.trangThai, links });
  }, [batchId, contextId, phien.person_id]);

  useEffect(() => {
    if (contextId === null) return;
    let song = true;
    void danhSachThanhVien(contextId, phien.person_id)
      .then((ds) => {
        if (song) setRoster(ds.map((tv) => ({ id: tv.person_id, name: tenHienThi(tv.display_name) })));
      })
      .catch(() => undefined);
    doc().catch((error: unknown) => {
      if (song) setTrang({ pha: "hong", loi: loiRaChu(error) });
    });
    return () => {
      song = false;
    };
  }, [contextId, doc, phien.person_id]);

  if (contextId === null) {
    return (
      <RudiScreen tone="split" testID="collection-batch-screen">
        <TopBar title="Đợt thu" />
        <Heading title="Vào một nhóm trước" subtitle="Đợt thu là của nhóm; chưa có nhóm thì chưa có ai để thu." />
        <RudiButton label="Tới Tin nhắn" onPress={() => router.push("/(tabs)/messages" as never)} tone="split" variant="outline" />
      </RudiScreen>
    );
  }

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

  const phat = () =>
    chay(async () => {
      const links = await phatDotThu(batchId, phien.person_id, attemptFor(attempts.current, `phat:${batchId}`), roster);
      await luuLinkDot(batchId, links);
      await doc();
    });

  const guiLink = (envelope: Envelope) =>
    chay(async () => {
      const ketQua = await Share.share({ message: loiNhanChiaSe(envelope) });
      if (ketQua.action === Share.dismissedAction) return;
      setDaMoKhay((hienTai) => ({ ...hienTai, [envelope.senderId]: true }));
    });

  const daNhan = (n: NghiaVu) =>
    chay(async () => {
      await xacNhanDaNhan(n.id, n.amountVnd, phien.person_id, attemptFor(attempts.current, `nhan:${n.id}:${n.amountVnd}`));
      await doc();
    });

  const docLai = () => chay(doc);

  if (trang.pha === "dang-doc") {
    return (
      <RudiScreen tone="split" testID="collection-batch-screen">
        <TopBar title="Đợt thu" />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc bảng thu…</Text>
      </RudiScreen>
    );
  }
  if (trang.pha === "hong") {
    return (
      <RudiScreen tone="split" testID="collection-batch-screen">
        <TopBar title="Đợt thu" />
        <Card>
          <Text style={[typography.title, { color: colors.warn }]}>Chưa đọc được bảng thu</Text>
          <Text style={[typography.caption, { color: colors.inkSoft }]}>{trang.loi}</Text>
        </Card>
        <RudiButton label="Thử lại" onPress={docLai} tone="split" variant="soft" />
      </RudiScreen>
    );
  }

  const tom = tomTatBang(trang.nghiaVu);
  const daPhatRoi = trang.trangThai !== null && daPhat(trang.trangThai);
  const toiNhan = new Set(nghiaVuToiNhan(trang.nghiaVu, phien.person_id).map((n) => n.id));

  return (
    <RudiScreen tone="split" testID="collection-batch-screen">
      <TopBar subtitle={trang.trangThai === null ? undefined : cauTrangThaiDot(trang.trangThai)} title="Đợt thu" />
      {thongBao !== null ? <Text style={[typography.body, { color: colors.warn }]}>{thongBao}</Text> : null}
      <Card style={styles.hero} tone="split">
        <Text style={[styles.soLon, { color: colors.ink }]}>
          {tom.daVe}/{tom.tong} lượt chuyển đã về
        </Text>
        <Text style={[typography.caption, { color: colors.inkSoft }]}>
          {tom.nguoiXong}/{tom.nguoiGui} người đã xong phần mình.{" "}
          {daPhatRoi ? "Đã phát: ai cũng xem được phần của mình." : "Chưa phát: chưa ai bị nhắn gì."}
        </Text>
      </Card>

      <SectionHeader title="Ai chuyển cho ai" />
      {trang.nghiaVu.length === 0 ? (
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Đợt này không ai phải chuyển tiền.</Text>
      ) : null}
      {trang.nghiaVu.map((n) => (
        <Card key={n.id} style={styles.hang}>
          <View style={styles.dong}>
            <View style={styles.flex}>
              <Text style={[typography.label, { color: colors.ink }]}>{cauHangNghiaVu(n, roster)}</Text>
              <Text style={[typography.caption, { color: n.tranhCai ? colors.warn : colors.inkFaint }]}>
                {TU_NGHIA_VU[n.trangThai]}
                {n.tranhCai && n.trangThai !== "disputed" ? " · đang thắc mắc" : ""}
              </Text>
            </View>
            <Text style={[typography.money, { color: colors.ink }]}>{dinhDangTienVnd(n.amountVnd)}</Text>
          </View>
          {daPhatRoi && toiNhan.has(n.id) ? (
            <RudiButton
              compact
              disabled={ban}
              full={false}
              icon="checkmark-done-outline"
              label={`Tiền đã về từ ${tenCua(roster, n.senderId)}`}
              onPress={() => void daNhan(n)}
              tone="split"
              variant="soft"
            />
          ) : null}
        </Card>
      ))}

      {!daPhatRoi ? (
        <>
          <RudiButton disabled={ban} icon="paper-plane-outline" label="Phát đợt thu" loading={ban} onPress={() => void phat()} tone="split" />
          <Text style={[typography.caption, { color: colors.inkSoft }]}>
            Phát xong thì mỗi người nhận một link riêng để xem phần của mình; nghĩa vụ chỉ tồn tại từ lúc đó. Máy chủ chỉ phát khi người ứng tiền đã xác nhận.
          </Text>
        </>
      ) : null}

      {daPhatRoi ? (
        <>
          <SectionHeader title="Gửi link riêng" />
          {trang.links === null ? (
            <Card>
              <Text style={[typography.caption, { color: colors.inkSoft }]}>
                Link của đợt này được phát ở máy khác. Máy chủ chỉ giữ dấu vân của link, nên máy này không lấy lại được; bảng thu ở trên vẫn là thật.
              </Text>
            </Card>
          ) : null}
          {trang.links !== null && trang.links.length === 0 ? (
            <Text style={[typography.caption, { color: colors.inkFaint }]}>Không có link nào: đợt này không ai phải chuyển.</Text>
          ) : null}
          {(trang.links === null ? [] : trang.links).map((env) => (
            <Card key={env.senderId} style={styles.hang}>
              <View style={styles.dong}>
                <View style={styles.flex}>
                  <Text style={[typography.label, { color: colors.ink }]}>{env.senderName}</Text>
                  <Text style={[typography.caption, { color: colors.inkFaint }]}>
                    {daMoKhay[env.senderId] === true ? "Đã mở khay chia sẻ, chưa rõ đã gửi chưa" : "Chưa gửi. Mỗi người một link riêng."}
                  </Text>
                </View>
                <Text style={[typography.money, { color: colors.ink }]}>{dinhDangTienVnd(env.amountVnd)}</Text>
              </View>
              <RudiButton
                compact
                disabled={ban}
                full={false}
                icon="share-social-outline"
                label={daMoKhay[env.senderId] === true ? `Gửi lại cho ${env.senderName}` : `Gửi cho ${env.senderName}`}
                onPress={() => void guiLink(env)}
                tone="split"
                variant="outline"
              />
            </Card>
          ))}
        </>
      ) : null}

      <RudiButton disabled={ban} icon="refresh-outline" label="Đọc lại từ máy chủ" onPress={docLai} tone="split" variant="ghost" />
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  hero: { gap: 6 },
  soLon: { fontSize: 24, lineHeight: 30, fontWeight: "800", letterSpacing: -0.4, fontVariant: ["tabular-nums"] },
  hang: { gap: 10 },
  dong: { flexDirection: "row", alignItems: "center", gap: 10 },
});
