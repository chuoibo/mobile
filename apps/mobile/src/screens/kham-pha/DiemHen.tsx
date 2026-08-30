/** Điểm hẹn — F45, meet in the middle.
 *
 * ## What this screen refuses to collect
 *
 * The spec draws a table: "Kiệt → Thủ Đức, Nam → Quận 7". That table is the
 * private part, so it never leaves the phone. What goes to the server is an
 * unlabelled multiset -- two counts against two districts, with no names
 * attached and no field to put them in (`MeetingPointRequest` has exactly one
 * member, and `extra="forbid"` makes an attempt to add one a 422 rather than
 * something quietly dropped).
 *
 * That is why the picker counts travellers per district instead of listing
 * people. It is not a simplification of a nicer design; the counting *is* the
 * design, and a per-person row would be the thing this feature exists to
 * avoid sending.
 *
 * ## The warning fires before the collecting, not after
 *
 * With exactly two origins the answer is invertible: one origin plus the
 * meeting point yields the other. That discloses nothing to the *server* --
 * both origins came from this caller a moment ago -- but a phone that gathers
 * two areas and then shows the result to both people has told each of them
 * where the other one starts from.
 *
 * So the sentence appears while the second district is being added, before
 * the request is sent, and again on the result. `two_origin_inversion` from
 * the server backs the second one; the first is the same fact known locally,
 * because a warning that arrives with the answer arrives too late to change
 * whether you asked.
 *
 * ## Why the kilometres are printed next to the name
 *
 * "Cân bằng" is a claim, and a screen that just asserts it is asking to be
 * trusted. Ranking is by the longest single journey (`worst_km`), never by the
 * total: ranking on the total sends the group to whichever district most of
 * them already live in and hands the entire cost to the person furthest out,
 * which is the opposite of meeting in the middle. Both numbers are printed so
 * the ordering can be checked rather than believed.
 *
 * Lead tone `accent`, inherited from Khám phá. No teal: nobody owes anybody
 * anything on this screen.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card } from "../../ui/Kit";
import type { NguoiDung } from "../../navigation/nhom-demo";
import { KhongCoBanDo } from "./BanDoNhom";
import {
  fetchDiemHen,
  fetchKhuVuc,
  soKm,
  type DiemHenState,
  type KhuVuc,
  type KhuVucState,
  type UngVienDiemHen,
} from "./ban-do-nhom";

const CHAM = 44;

/** The most origins this screen will collect.
 *
 * Not a server limit -- the route takes any list. It is a screen limit,
 * because past a handful of districts the picker stops being readable and the
 * answer stops being actionable. Stated in copy where it bites, never as a
 * silent refusal. */
const TOI_DA_NGUOI = 12;

/** The sentence the two-origin case gets, in both places it is said. */
export const CAU_SUY_NGUOC =
  "Đang có đúng hai khu vực. Từ chỗ hẹn và một đầu là suy ra được đầu còn lại, nên nếu hai người này chưa nói cho nhau biết mình xuất phát từ đâu thì đừng đưa màn này cho người kia xem.";

/** Rows the picker draws: one district, and how many people start there. */
type Chon = { khu: KhuVuc; so: number };

/** The multiset the request carries: one entry per traveller, no names. */
export function thanhDanhSachKhuVuc(chon: Chon[]): string[] {
  const ids: string[] = [];
  for (const row of chon) {
    for (let i = 0; i < row.so; i += 1) ids.push(row.khu.id);
  }
  return ids;
}

export function tongNguoi(chon: Chon[]): number {
  return chon.reduce((acc, row) => acc + row.so, 0);
}

/** One district row: label, a count, and two 44pt buttons. */
function HangChon({
  row,
  onThem,
  onBot,
  conChoThem,
}: {
  row: Chon;
  onThem: () => void;
  onBot: () => void;
  conChoThem: boolean;
}) {
  const c = usePalette();
  const chon = row.so > 0;
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: space.sm,
        minHeight: CHAM,
      }}
    >
      <Text style={{ ...type.body, color: chon ? c.ink : c.inkSoft, flex: 1 }} numberOfLines={1}>
        {row.khu.label}
      </Text>
      <Pressable
        onPress={onBot}
        disabled={row.so === 0}
        accessibilityRole="button"
        accessibilityLabel={`Bớt một người xuất phát từ ${row.khu.label}`}
        style={{
          width: CHAM,
          height: CHAM,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: radius.pill,
          backgroundColor: row.so === 0 ? c.ground : c.card,
          borderWidth: 1,
          borderColor: c.line,
          opacity: row.so === 0 ? 0.5 : 1,
        }}
      >
        <Text style={{ ...type.title, color: c.ink }}>−</Text>
      </Pressable>
      {/* The count is text, not just a highlight: a row's meaning is "hai
          người ở đây", and that cannot be carried by a colour alone. */}
      <Text
        style={{ ...type.amountSmall, color: chon ? c.accent : c.inkFaint, minWidth: 24, textAlign: "center" }}
      >
        {row.so}
      </Text>
      <Pressable
        onPress={onThem}
        disabled={!conChoThem}
        accessibilityRole="button"
        accessibilityLabel={`Thêm một người xuất phát từ ${row.khu.label}`}
        style={{
          width: CHAM,
          height: CHAM,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: radius.pill,
          backgroundColor: conChoThem ? c.accentSoft : c.ground,
          borderWidth: 1,
          borderColor: conChoThem ? c.accentSoft : c.line,
          opacity: conChoThem ? 1 : 0.5,
        }}
      >
        <Text style={{ ...type.title, color: c.ink }}>+</Text>
      </Pressable>
    </View>
  );
}

/** One candidate, with the arithmetic that ranked it. */
function TheUngVien({ ung, dau }: { ung: UngVienDiemHen; dau: boolean }) {
  const c = usePalette();
  return (
    <Card>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
        <Text style={{ ...type.title, color: c.ink, flex: 1 }}>{ung.placeName}</Text>
        {dau ? (
          <View
            style={{
              backgroundColor: c.accentSoft,
              borderRadius: radius.small,
              paddingHorizontal: space.xs,
              paddingVertical: 2,
              alignSelf: "flex-start",
            }}
          >
            <Text style={{ ...type.micro, color: c.ink }}>Cân bằng nhất</Text>
          </View>
        ) : null}
      </View>
      <Text style={{ ...type.micro, color: c.inkSoft }}>{ung.address}</Text>
      <Text style={{ ...type.body, color: c.ink }}>
        Người đi xa nhất: {soKm(ung.canBang.worstKm)}
      </Text>
      <Text style={{ ...type.micro, color: c.inkSoft }}>
        Tổng quãng đường cả nhóm {soKm(ung.canBang.totalKm)} · chênh lệch giữa người gần nhất
        và xa nhất {soKm(ung.canBang.spreadKm)}
      </Text>
      <View style={{ gap: 2 }}>
        {ung.chang.map((chang, i) => (
          // Keyed by index: the same district legitimately appears twice when
          // two people start from it, so the id is not unique here.
          <View
            key={`${chang.id}-${i}`}
            style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}
          >
            <Text style={{ ...type.micro, color: c.inkSoft, flex: 1 }} numberOfLines={1}>
              Từ {chang.label}
            </Text>
            <Text style={{ ...type.micro, color: c.inkSoft }}>{soKm(chang.km)}</Text>
          </View>
        ))}
      </View>
    </Card>
  );
}

/** The warning card, drawn identically wherever the two-origin case is true. */
function CanhBaoSuyNguoc() {
  const c = usePalette();
  return (
    <Card style={{ borderColor: c.warn, borderWidth: 1 }}>
      <Text style={{ ...type.title, color: c.ink }}>Hai người thì suy ngược được</Text>
      <Text style={{ ...type.body, color: c.inkSoft }}>{CAU_SUY_NGUOC}</Text>
    </Card>
  );
}

export function DiemHen({
  nguoi,
  contextId,
  onQuayLai,
  fetchImpl,
}: {
  nguoi: NguoiDung;
  contextId?: string;
  onQuayLai: () => void;
  fetchImpl?: typeof fetch;
}) {
  const c = usePalette();
  const [khuVuc, setKhuVuc] = useState<KhuVucState>({ kind: "dang-tai" });
  const [so, setSo] = useState<Record<string, number>>({});
  const [ketQua, setKetQua] = useState<DiemHenState>({ kind: "chua-hoi" });

  const opts = useMemo(
    () => ({ personId: nguoi.personId, contextId, fetchImpl }),
    [nguoi.personId, contextId, fetchImpl],
  );

  useEffect(() => {
    void fetchKhuVuc(opts).then(setKhuVuc);
  }, [opts]);

  const chon: Chon[] =
    khuVuc.kind === "co-du-lieu"
      ? khuVuc.data.map((khu) => ({ khu, so: so[khu.id] ?? 0 }))
      : [];
  const tong = tongNguoi(chon);
  const haiDau = tong === 2;

  const doi = useCallback((id: string, delta: number) => {
    setSo((truoc) => {
      const moi = Math.max(0, (truoc[id] ?? 0) + delta);
      return { ...truoc, [id]: moi };
    });
    // A selection change invalidates the answer on screen. Leaving the old
    // result under a new selection is how a person reads a meeting point for
    // origins they no longer entered.
    setKetQua({ kind: "chua-hoi" });
  }, []);

  const hoi = useCallback(() => {
    setKetQua({ kind: "dang-tai" });
    void fetchDiemHen(thanhDanhSachKhuVuc(chon), opts).then(setKetQua);
  }, [chon, opts]);

  return (
    <View style={{ flex: 1, backgroundColor: c.ground }}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ padding: space.md, paddingBottom: space.xl, gap: space.md }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
          <Pressable
            onPress={onQuayLai}
            accessibilityRole="button"
            accessibilityLabel="Quay lại bản đồ nhóm"
            style={{
              minWidth: CHAM,
              minHeight: CHAM,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: radius.pill,
              backgroundColor: c.card,
            }}
          >
            <Text style={{ ...type.title, color: c.ink }}>‹</Text>
          </Pressable>
          <Text style={{ ...type.h1, color: c.ink, flex: 1 }}>Điểm hẹn</Text>
        </View>

        <Text style={{ ...type.body, color: c.inkSoft }}>
          Đếm xem mấy người xuất phát từ mỗi khu, không cần ghi ai là ai. Máy chủ chỉ nhận
          danh sách khu vực, không nhận tên người, nên nó không biết ai đi từ đâu.
        </Text>

        {khuVuc.kind === "dang-tai" ? (
          <Card>
            <ActivityIndicator color={c.accent} />
            <Text style={{ ...type.micro, color: c.inkSoft }}>Đang lấy danh sách khu vực…</Text>
          </Card>
        ) : khuVuc.kind !== "co-du-lieu" ? (
          <KhongCoBanDo state={khuVuc} onThuLai={() => void fetchKhuVuc(opts).then(setKhuVuc)} />
        ) : (
          <Card>
            <Text style={{ ...type.title, color: c.ink }}>Ai xuất phát từ đâu</Text>
            {chon.map((row) => (
              <HangChon
                key={row.khu.id}
                row={row}
                conChoThem={tong < TOI_DA_NGUOI}
                onThem={() => doi(row.khu.id, 1)}
                onBot={() => doi(row.khu.id, -1)}
              />
            ))}
            <Text style={{ ...type.micro, color: c.inkSoft }}>
              {tong === 0
                ? "Chọn ít nhất hai người thì mới có chỗ giữa để tính."
                : tong >= TOI_DA_NGUOI
                  ? `Đang là ${tong} người, mức tối đa màn này nhận.`
                  : `Đang là ${tong} người.`}
            </Text>
          </Card>
        )}

        {/* Before the request, not with the answer. */}
        {haiDau && ketQua.kind === "chua-hoi" ? <CanhBaoSuyNguoc /> : null}

        <Button label="Tìm chỗ gặp" onPress={hoi} disabled={tong < 2 || ketQua.kind === "dang-tai"} />

        {ketQua.kind === "dang-tai" ? (
          <Card>
            <ActivityIndicator color={c.accent} />
            <Text style={{ ...type.micro, color: c.inkSoft }}>Đang tính quãng đường…</Text>
          </Card>
        ) : ketQua.kind === "chua-hoi" ? null : ketQua.kind !== "co-du-lieu" ? (
          <KhongCoBanDo state={ketQua} onThuLai={hoi} />
        ) : (
          <>
            {ketQua.data.suyNguocDuoc ? <CanhBaoSuyNguoc /> : null}
            <Text style={{ ...type.micro, color: c.inkSoft }}>
              Đo từ tâm mỗi khu vực:{" "}
              {ketQua.data.diemXuatPhat.map((k) => k.label).join(" · ")}
            </Text>
            {ketQua.data.ungVien.length === 0 ? (
              <Card>
                <Text style={{ ...type.title, color: c.ink }}>Chưa tìm được chỗ nào ở giữa</Text>
                <Text style={{ ...type.body, color: c.inkSoft }}>
                  Danh mục địa điểm hiện chưa có quán nào nằm giữa những khu vực này. Thử bớt
                  một khu ở xa rồi tính lại.
                </Text>
              </Card>
            ) : (
              ketQua.data.ungVien.map((ung, i) => (
                <TheUngVien key={ung.placeId} ung={ung} dau={i === 0} />
              ))
            )}
          </>
        )}
      </ScrollView>
    </View>
  );
}
