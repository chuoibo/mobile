/** Cá nhân — where the money comes back as something a person recognises.
 *
 * This is the last stop on the demo path: split a bill, come back here, watch
 * the totals move. So every figure on it is read from `GET
 * /people/{id}/finance` on mount, and the ledger recomputes them on the
 * request that asks. There is no number typed into this file, no cached copy,
 * and no arithmetic -- `Đã thanh toán` and `Còn nợ` arrive already adding up
 * to the total above them, because doing that subtraction here would be a
 * second implementation of the one thing this product cannot get wrong twice.
 *
 * The screen remounts when the tab is selected (see `VoTab`), which is what
 * makes "come back and look" refetch rather than show what was true a
 * screen ago.
 *
 * Mockup: product/features/06-ho-so-va-hanh-trinh.png, screens 1 and 2. Parts
 * of screen 1 have nothing behind them -- there is no trips table, no photo
 * store, no ratings -- and those are drawn as the mockup draws them but
 * labelled, never filled with a plausible number. A shell is not a defect; a
 * shell wearing real data's clothes is.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Card } from "../../ui/Kit";
import { Gradient, HERO_SUNSET } from "../../navigation/Gradient";
import { DEMO_GROUP_NAME, type DemoPerson } from "../../navigation/nhom-demo";
import { MaCuaToi } from "./MaCuaToi";
import {
  FinanceError,
  layTaiChinh,
  moTaGiaoDich,
  ngayNgan,
  tienCoDau,
  tienVnd,
  type Finance,
  type Movement,
} from "./tai-chinh";

type Trang =
  | { pha: "dang-tai" }
  | { pha: "xong"; so: Finance }
  | { pha: "loi"; loi: string };

export function CaNhan({
  nguoi,
  doc = layTaiChinh,
}: {
  nguoi: DemoPerson | null;
  /** Injected so the screen can be exercised without a server. */
  doc?: typeof layTaiChinh;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-tai" });
  const [dangLamMoi, setDangLamMoi] = useState(false);

  const tai = useCallback(async () => {
    if (!nguoi) return;
    try {
      setTrang({ pha: "xong", so: await doc(nguoi.personId) });
    } catch (error) {
      const message =
        error instanceof FinanceError ? error.message : "Chưa đọc được sổ.";
      setTrang({ pha: "loi", loi: message });
    }
  }, [nguoi, doc]);

  useEffect(() => {
    void tai();
  }, [tai]);

  const lamMoi = useCallback(async () => {
    setDangLamMoi(true);
    await tai();
    setDangLamMoi(false);
  }, [tai]);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.ground }}
      contentContainerStyle={{ paddingBottom: space.xl }}
      // A keyboard tab-stop on the scroller itself, which this screen needs and
      // the other tabs do not. Every other tab holds buttons, and a scrollable
      // region containing a focusable child is already reachable by keyboard.
      // This screen is entirely static -- numbers, rows and labels, nothing
      // pressable -- so without a tab-stop there is no key that scrolls it, and
      // the transaction list and "Nhóm của bạn" below the fold cannot be read at
      // all. Measured: axe `scrollable-region-focusable` (serious) fired here
      // and on none of the other four tabs.
      //
      // `tabIndex` rather than `focusable`: the latter is deprecated in
      // react-native-web 0.21 and warns. Native ignores the prop, which is
      // correct -- a touch screen has no tab ring to join.
      tabIndex={0}
      refreshControl={
        <RefreshControl refreshing={dangLamMoi} onRefresh={lamMoi} tintColor={c.accent} />
      }
    >
      <BiaVaAnh nguoi={nguoi} ten={tenHienThi(nguoi, trang)} />

      <View style={{ padding: space.md, gap: space.md }}>
        {nguoi ? null : <ChuaChon />}
        <HangSoLieu trang={trang} />
        <TaiChinh trang={trang} onThuLai={lamMoi} coNguoi={Boolean(nguoi)} />
        <GiaoDich trang={trang} />
        <NhomCuaBan trang={trang} />
        <MaKetBan nguoi={nguoi} ten={tenHienThi(nguoi, trang)} />
      </View>
    </ScrollView>
  );
}

function tenHienThi(nguoi: DemoPerson | null, trang: Trang): string {
  // The server's name wins when it has one: it is the row this screen is
  // actually reading, so a disagreement between it and the picker means the
  // picker is pointed at the wrong person, and hiding that would hide the bug.
  if (trang.pha === "xong" && trang.so.display_name) return trang.so.display_name;
  return nguoi?.name ?? "Khách";
}

/** Cover band with the avatar sitting over its lower edge, as in the mockup. */
function BiaVaAnh({ nguoi, ten }: { nguoi: DemoPerson | null; ten: string }) {
  const c = usePalette();
  const AVATAR = 84;
  return (
    <View style={{ marginBottom: AVATAR / 2 + space.xs }}>
      {/* No photograph. Real faces of real people do not go into Git, and a
          stock portrait of a stranger is a worse lie than a gradient. Same
          sunset the opening screen paints, so arriving here reads as the same
          product rather than a second one. No text sits on it: `tokens.brand`
          measures white on the coral stop at 2.92:1 and forbids exactly that. */}
      <Gradient colors={HERO_SUNSET} style={{ height: 148 }} />
      <View
        style={{
          position: "absolute",
          left: space.md,
          bottom: -AVATAR / 2,
          width: AVATAR,
          height: AVATAR,
          borderRadius: radius.pill,
          backgroundColor: c.accentSoft,
          borderColor: c.card,
          borderWidth: 4,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ ...type.amount, color: c.accent }}>{nguoi?.initials ?? "?"}</Text>
      </View>
      <View
        style={{
          position: "absolute",
          left: space.md + AVATAR + space.sm,
          right: space.md,
          bottom: -AVATAR / 2 + space.sm,
          gap: 2,
        }}
      >
        <Text numberOfLines={1} style={{ ...type.h1, color: c.ink }}>
          {ten}
        </Text>
        <Text numberOfLines={1} style={{ ...type.label, color: c.inkSoft }}>
          {DEMO_GROUP_NAME}
        </Text>
      </View>
    </View>
  );
}

function ChuaChon() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.body, color: c.ink }}>Bạn vào app bằng "Bỏ qua".</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Chưa có người nào được chọn nên chưa có sổ nào để đọc. Quay lại màn mở đầu và
        chọn một người trong nhóm để xem tài chính của họ.
      </Text>
    </Card>
  );
}

/**
 * The mockup's four-up stat row, carrying only what the ledger can answer.
 *
 * Two of the mockup's four -- kỷ niệm and đánh giá -- have no table behind
 * them anywhere in this product. They are kept in the row because the row's
 * rhythm is the design, and marked with `—` and one caption rather than filled
 * with a number that would look exactly as real as the two beside it. That
 * substitution is the failure this whole screen is built to avoid.
 */
function HangSoLieu({ trang }: { trang: Trang }) {
  const c = usePalette();
  const so = trang.pha === "xong" ? trang.so : null;
  const o = (value: string) => (trang.pha === "dang-tai" ? "…" : value);
  const items: { label: string; value: string; that: boolean }[] = [
    { label: "Lần chia bill", value: o(`${so?.expense_count ?? 0}`), that: true },
    { label: "Nhóm", value: o(`${so?.group_count ?? 0}`), that: true },
    { label: "Kỷ niệm", value: "—", that: false },
    { label: "Đánh giá", value: "—", that: false },
  ];
  return (
    <Card>
      <View style={{ flexDirection: "row" }}>
        {items.map((item) => (
          <View key={item.label} style={{ flex: 1, alignItems: "center", gap: 2 }}>
            <Text
              style={{
                ...type.title,
                fontVariant: ["tabular-nums"],
                color: item.that ? c.ink : c.inkFaint,
              }}
            >
              {item.value}
            </Text>
            <Text style={{ ...type.micro, color: c.inkSoft, textAlign: "center" }}>
              {item.label}
            </Text>
          </View>
        ))}
      </View>
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        Hai số đầu đọc từ sổ. Kỷ niệm và đánh giá chưa có trong sản phẩm nên để trống.
      </Text>
    </Card>
  );
}

/** Tổng quan tài chính — the reason this screen is on the demo path. */
function TaiChinh({
  trang,
  onThuLai,
  coNguoi,
}: {
  trang: Trang;
  onThuLai: () => void;
  coNguoi: boolean;
}) {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Tổng quan tài chính</Text>

      {trang.pha === "dang-tai" && coNguoi ? (
        <View style={{ paddingVertical: space.md, alignItems: "flex-start" }}>
          <ActivityIndicator color={c.accent} />
        </View>
      ) : null}

      {trang.pha === "loi" ? (
        <View style={{ gap: space.sm }} accessibilityRole="alert">
          <Text style={{ ...type.body, color: c.ink }}>{trang.loi}</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Màn này không có số dự phòng. Số cũ hiện lúc máy chủ im lặng sẽ nói rằng
            không có gì thay đổi, mà đó đúng là điều chưa biết.
          </Text>
          <Pressable
            onPress={onThuLai}
            accessibilityRole="button"
            style={({ pressed }) => ({
              alignSelf: "flex-start",
              borderWidth: 1,
              borderColor: c.lineStrong,
              borderRadius: radius.control,
              paddingVertical: 10,
              paddingHorizontal: space.md,
              opacity: pressed ? 0.85 : 1,
            })}
          >
            <Text style={{ ...type.body, fontWeight: "600", color: c.inkSoft }}>
              Thử lại
            </Text>
          </Pressable>
        </View>
      ) : null}

      {trang.pha === "xong" ? (
        <View style={{ gap: space.sm }}>
          <View style={{ gap: 2 }}>
            <Text style={{ ...type.label, color: c.inkSoft }}>Tổng chi tiêu</Text>
            <Text style={{ ...type.amount, color: c.ink }}>
              {tienVnd(trang.so.spend_vnd)}
            </Text>
          </View>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <ONho
              label="Đã thanh toán"
              value={tienVnd(trang.so.settled_vnd)}
              mau={c.split}
              nen={c.splitSoft}
            />
            <ONho
              label="Còn nợ"
              value={tienVnd(trang.so.outstanding_vnd)}
              mau={c.accent}
              nen={c.accentSoft}
            />
          </View>
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            Tính lại từ sổ mỗi lần mở màn này. Chia một khoản chi rồi quay lại, hai ô
            trên đổi theo.
          </Text>
        </View>
      ) : null}
    </Card>
  );
}

function ONho({
  label,
  value,
  mau,
  nen,
}: {
  label: string;
  value: string;
  mau: string;
  nen: string;
}) {
  const c = usePalette();
  return (
    // Colour is not the only carrier: the label above each number says which
    // is which, so the pair still reads with no colour vision at all.
    <View
      style={{
        flex: 1,
        gap: 2,
        padding: space.sm,
        borderRadius: radius.control,
        backgroundColor: nen,
      }}
    >
      <Text style={{ ...type.label, color: c.inkSoft }}>{label}</Text>
      <Text style={{ ...type.amountSmall, color: mau }}>{value}</Text>
    </View>
  );
}

/** Giao dịch gần đây, newest first, sign carried by the word and the colour. */
function GiaoDich({ trang }: { trang: Trang }) {
  const c = usePalette();
  if (trang.pha !== "xong") return null;
  const list = trang.so.movements;
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Giao dịch gần đây</Text>
      {list.length === 0 ? (
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Chưa có giao dịch nào được xác nhận. Một khoản chỉ vào đây khi người nhận xác
          nhận đã nhận tiền — người gửi báo đã chuyển thì chưa tính.
        </Text>
      ) : (
        list.map((m, i) => <DongGiaoDich key={m.obligation_id + i} m={m} />)
      )}
    </Card>
  );
}

function DongGiaoDich({ m }: { m: Movement }) {
  const c = usePalette();
  const vao = m.direction === "in";
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: space.sm,
        paddingVertical: space.xs,
      }}
    >
      <View
        style={{
          width: 38,
          height: 38,
          borderRadius: radius.small,
          backgroundColor: vao ? c.splitSoft : c.accentSoft,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* An arrow, not only a colour: the direction has to survive a
            greyscale screenshot and a red-green blind reader. */}
        <Text style={{ ...type.body, fontWeight: "700", color: vao ? c.split : c.accent }}>
          {vao ? "↓" : "↑"}
        </Text>
      </View>
      {/* `minWidth: 0` is load-bearing, not tidying. A flex item defaults to
          `min-width: auto`, which refuses to shrink below its content -- so a
          long expense name ("Homestay Đà Lạt · 2 đêm") pushed this column
          wider than the row and ran underneath the amount on its right.
          `numberOfLines` does not save it: that clips the paint, while the box
          keeps its full width. Caught by the detector at 390pt, where the
          label was measured 40% under the number. */}
      <View style={{ flex: 1, minWidth: 0, gap: 1 }}>
        <Text numberOfLines={1} style={{ ...type.body, color: c.ink }}>
          {m.occasion ?? m.context_name ?? "Khoản chi"}
        </Text>
        <Text numberOfLines={1} style={{ ...type.micro, color: c.inkSoft }}>
          {moTaGiaoDich(m)}
        </Text>
      </View>
      {/* The money never gives up room to the label beside it. */}
      <View style={{ alignItems: "flex-end", flexShrink: 0, gap: 1 }}>
        <Text style={{ ...type.amountSmall, color: vao ? c.split : c.accent }}>
          {tienCoDau(m)}
        </Text>
        <Text style={{ ...type.micro, color: c.inkFaint }}>{ngayNgan(m.occurred_at)}</Text>
      </View>
    </View>
  );
}

/** F05. This person's own code, on the screen that is about who they are.
 *
 * Placed under "Nhóm của bạn" because the two are the same act read from
 * opposite ends: that card counts the groups somebody is already in, this one
 * is how they get into the next. The mockup's profile screen carries the
 * identity block, and a code is identity in a form a camera can read.
 *
 * Renders nothing when nobody is signed in. A QR built for "Khách" would be a
 * working square that adds a person who does not exist, which is worse than an
 * absent card -- and `ChuaChon` above already says why the screen is empty.
 */
function MaKetBan({ nguoi, ten }: { nguoi: DemoPerson | null; ten: string }) {
  const c = usePalette();
  if (!nguoi) return null;
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Mã kết bạn của bạn</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Đưa mã này cho người bạn muốn thêm. Họ quét xong là mở màn nhóm với tên
        bạn đã điền sẵn, chỉ việc mời vào nhóm.
      </Text>
      <View style={{ marginTop: space.sm }}>
        <MaCuaToi personId={nguoi.personId} ten={ten} />
      </View>
    </Card>
  );
}

/** "Nhóm của bạn" — the count is read from the ledger, the tiles are not. */
function NhomCuaBan({ trang }: { trang: Trang }) {
  const c = usePalette();
  if (trang.pha !== "xong") return null;
  const count = trang.so.group_count;
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Nhóm của bạn ({count})</Text>
      {count === 0 ? (
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Chưa vào nhóm nào. Số này đếm các nhóm bạn đã nhận lời mời.
        </Text>
      ) : (
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {count === 1 ? "Một nhóm" : `${count} nhóm`} đang hoạt động. Danh sách tên
          nhóm và ảnh thành viên chưa dựng — màn nhóm là việc của lane khác.
        </Text>
      )}
    </Card>
  );
}
