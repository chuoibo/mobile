/** Kỷ niệm của nhóm — what a trip leaves behind once it is over.
 *
 * Pillar 5 of the spec (F30/F35) was empty until this screen. It deliberately
 * does not start at the photo grid the mockup leads with, and the reason is not
 * time: photographs of real people are private data this repository is not
 * allowed to hold, and the part of a trip a group can still recover months
 * later is not the pictures anyway. It is where they went and what it cost.
 * Both of those already existed in the database as side effects of other
 * features -- `outings` from F13/F15, `confirmed_allocations` from the split --
 * and neither was readable as one thing.
 *
 * Every number here is read from `GET /contexts/{id}/recap` on mount and
 * recomputed by the ledger on the request that asks. Nothing is cached, nothing
 * is added up in this file, and there is no arithmetic anywhere below: the
 * per-trip totals and the total across trips both arrive already summed,
 * because doing that addition here would be a second implementation of the one
 * thing this product cannot get wrong twice.
 *
 * The date rule is stated on screen rather than hidden in SQL. There is no
 * `expenses.outing_id`, so a trip claims the spending that happened on its
 * days -- a rule, not a fact, and one a person reading a total is entitled to
 * know. A dinner split three days after everyone got home belongs to no trip.
 *
 * Mockup: product/features/05-ky-niem-cua-nhom.png, screen 2 (the trip
 * overview). Screen 1's social wall -- reactions, comments, the photo collage
 * -- has nothing behind it: there is no reactions table, no comments table, and
 * no photo store. Those are named as missing at the foot of the screen rather
 * than drawn with plausible-looking counts. A shell is not a defect; a shell
 * wearing real data's clothes is.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Card } from "../../ui/Kit";
import { Gradient, HERO_SUNSET } from "../../navigation/Gradient";
import { DEMO_GROUP_NAME, type NguoiDung } from "../../navigation/nhom-demo";
import {
  KyUcError,
  khoangNgay,
  layKyUc,
  soNgay,
  tienVnd,
  timNhomDemo,
  tomTatChang,
  type BuoiDiChoi,
  type KyUc,
} from "./ky-uc";

type Trang =
  | { pha: "dang-tai" }
  | { pha: "xong"; ky: KyUc }
  | { pha: "loi"; loi: string };

export function KyNiem({
  nguoi,
  contextId,
  onDong,
  doc = layKyUc,
  timNhom = timNhomDemo,
}: {
  nguoi: NguoiDung | null;
  /** Which group's wall, when the link named one. Null means "go and find it". */
  contextId?: string | null;
  /** Back out of the wall. Absent when it is rendered as a whole tab. */
  onDong?: () => void;
  /** Injected so the screen can be exercised without a server. */
  doc?: typeof layKyUc;
  timNhom?: typeof timNhomDemo;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-tai" });
  const [dangLamMoi, setDangLamMoi] = useState(false);
  // True when the group had to be created rather than found, which means this
  // wall is empty because nothing was ever seeded -- not because the group has
  // been nowhere. The two look identical on screen unless one of them says so.
  const [nhomVuaTao, setNhomVuaTao] = useState(false);

  const tai = useCallback(async () => {
    if (!nguoi) return;
    try {
      let nhom = contextId ?? null;
      if (nhom === null) {
        const tim = await timNhom(nguoi.personId);
        nhom = tim.contextId;
        setNhomVuaTao(!tim.daCoSan);
      }
      setTrang({ pha: "xong", ky: await doc(nhom, nguoi.personId) });
    } catch (error) {
      const message =
        error instanceof KyUcError ? error.message : "Chưa đọc được sổ.";
      setTrang({ pha: "loi", loi: message });
    }
  }, [nguoi, contextId, doc, timNhom]);

  useEffect(() => {
    void tai();
  }, [tai]);

  const lamMoi = useCallback(async () => {
    setDangLamMoi(true);
    await tai();
    setDangLamMoi(false);
  }, [tai]);

  const san = nguoi !== null;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.ground }}
      contentContainerStyle={{ paddingBottom: space.xl }}
      // A keyboard tab-stop on the scroller itself. This screen is a column of
      // static cards with nothing pressable below the fold, so without it there
      // is no key that scrolls it and every trip past the first is unreachable
      // by keyboard. Measured as axe `scrollable-region-focusable` (serious) on
      // the Cá nhân screen, which has the same shape; fixing it there and not
      // here would have left the same hole one tab over.
      //
      // `tabIndex` rather than `focusable`: the latter is deprecated in
      // react-native-web 0.21 and warns. Native ignores it, which is correct --
      // a touch screen has no tab ring to join.
      tabIndex={0}
      refreshControl={
        <RefreshControl refreshing={dangLamMoi} onRefresh={lamMoi} tintColor={c.accent} />
      }
    >
      <Bia onDong={onDong} />

      <View style={{ padding: space.md, gap: space.md }}>
        {san ? null : <ChuaCoNhom />}

        {trang.pha === "dang-tai" && san ? (
          <Card>
            <View style={{ paddingVertical: space.md, alignItems: "flex-start" }}>
              <ActivityIndicator color={c.accent} />
            </View>
            <Text style={{ ...type.label, color: c.inkSoft }}>Đang đọc lại sổ của nhóm…</Text>
          </Card>
        ) : null}

        {trang.pha === "loi" ? <Loi loi={trang.loi} onThuLai={lamMoi} /> : null}

        {trang.pha === "xong" ? <Tuong ky={trang.ky} nhomVuaTao={nhomVuaTao} /> : null}
      </View>
    </ScrollView>
  );
}

/** Cover band, as the mockup's trip header draws it. */
function Bia({ onDong }: { onDong?: () => void }) {
  const c = usePalette();
  return (
    <View>
      {/* The same sunset the opening screen and Cá nhân paint, so arriving
          here reads as one product. No text sits on the gradient itself:
          `tokens.brand` measures white on the coral stop at 2.92:1 and
          forbids exactly that. */}
      <Gradient colors={HERO_SUNSET} style={{ height: 104 }} />
      {onDong ? (
        <Pressable
          onPress={onDong}
          accessibilityRole="button"
          accessibilityLabel="Đóng kỷ niệm, quay lại màn trước"
          style={({ pressed }) => ({
            position: "absolute",
            top: space.sm,
            left: space.sm,
            // 44pt: the touch target floor, and the reason this is padding
            // rather than a smaller box with a bigger glyph.
            minWidth: 44,
            minHeight: 44,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: radius.pill,
            backgroundColor: c.card,
            opacity: pressed ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>←</Text>
        </Pressable>
      ) : null}
      <View style={{ paddingHorizontal: space.md, paddingTop: space.md, gap: space.xs }}>
        <Text style={{ ...type.h1, color: c.ink }}>Kỷ niệm của nhóm</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {DEMO_GROUP_NAME} · những chuyến đã đi qua
        </Text>
      </View>
    </View>
  );
}

function ChuaCoNhom() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.body, color: c.ink }}>Bạn vào app bằng "Bỏ qua".</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Kỷ niệm là của riêng một nhóm, và nhóm chỉ mở ra cho thành viên. Quay lại màn mở
        đầu và chọn một người trong nhóm để xem tường của họ.
      </Text>
    </Card>
  );
}

function Loi({ loi, onThuLai }: { loi: string; onThuLai: () => void }) {
  const c = usePalette();
  return (
    <Card>
      <View style={{ gap: space.sm }} accessibilityRole="alert">
        <Text style={{ ...type.body, color: c.ink }}>{loi}</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Màn này không giữ bản sao nào. Một tường kỷ niệm cũ hiện lúc máy chủ im lặng sẽ
          nói rằng nhóm chưa đi đâu thêm, mà đó đúng là điều chưa biết.
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
          <Text style={{ ...type.body, fontWeight: "600", color: c.inkSoft }}>Thử lại</Text>
        </Pressable>
      </View>
    </Card>
  );
}

function Tuong({ ky, nhomVuaTao }: { ky: KyUc; nhomVuaTao: boolean }) {
  const c = usePalette();
  if (ky.outings.length === 0) {
    return (
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>
          {nhomVuaTao ? "Nhóm này vừa được tạo" : "Chưa có chuyến nào đã xong"}
        </Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {nhomVuaTao
            ? "Máy chủ chưa có nhóm demo nào nên app vừa lập một nhóm rỗng. Tường trống ở đây là vì chưa ai seed dữ liệu, không phải vì nhóm chưa đi đâu — chạy `make demo` rồi mở lại."
            : "Tường kỷ niệm gom lại những buổi đi chơi đã kết thúc. Một chuyến còn ở phía trước nằm ở tab Lên plan, và nó chuyển sang đây sau ngày cuối cùng của chuyến."}
        </Text>
      </Card>
    );
  }
  return (
    <>
      <TongKet ky={ky} />
      {ky.outings.map((o) => (
        <TheChuyen key={o.outing_id} chuyen={o} />
      ))}
      <ConThieu />
    </>
  );
}

/** The band over the list: how much this group has been through, in total. */
function TongKet({ ky }: { ky: KyUc }) {
  const c = usePalette();
  const soChuyen = ky.outings.length;
  return (
    <Card>
      <Text style={{ ...type.label, color: c.inkSoft }}>Đã đi cùng nhau</Text>
      <View style={{ flexDirection: "row", alignItems: "baseline", gap: space.sm }}>
        <Text style={{ ...type.amount, color: c.ink }}>{soChuyen}</Text>
        <Text style={{ ...type.body, color: c.inkSoft }}>
          {soChuyen === 1 ? "chuyến đã xong" : "chuyến đã xong"}
        </Text>
      </View>
      <View
        style={{
          gap: 2,
          padding: space.sm,
          borderRadius: radius.control,
          backgroundColor: c.splitSoft,
        }}
      >
        <Text style={{ ...type.label, color: c.inkSoft }}>Tổng tiền đã chia trong các chuyến</Text>
        <Text style={{ ...type.amountSmall, color: c.split }}>{tienVnd(ky.split_total_vnd)}</Text>
      </View>
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        Tính lại từ sổ mỗi lần mở màn này, không đọc con số nào đã lưu sẵn.
      </Text>
    </Card>
  );
}

/** One trip: where it went, what it cost, how long it ran. */
function TheChuyen({ chuyen }: { chuyen: BuoiDiChoi }) {
  const c = usePalette();
  const ngay = soNgay(chuyen.starts_on, chuyen.ends_on);
  const chang = tomTatChang(chuyen.stops);
  return (
    <Card style={{ padding: 0, overflow: "hidden", gap: 0 }}>
      {/* The mockup's hero photo, without a photo. A stock picture of a place
          the group never went is a worse lie than a gradient, and real photos
          of real people are exactly what this repository must not hold. */}
      <Gradient colors={HERO_SUNSET} style={{ height: 76 }} />

      <View style={{ padding: space.md, gap: space.sm }}>
        <View style={{ gap: 2 }}>
          <Text style={{ ...type.title, color: c.ink }}>{chuyen.title}</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            {khoangNgay(chuyen.starts_on, chuyen.ends_on)} · {ngay} ngày ·{" "}
            {chuyen.headcount} người
          </Text>
        </View>

        {chang ? (
          <View style={{ gap: 2 }}>
            <Text style={{ ...type.micro, color: c.inkFaint }}>Đã tới</Text>
            <Text style={{ ...type.body, color: c.ink }}>{chang}</Text>
          </View>
        ) : null}

        {chuyen.stops.length > 0 ? <DongThoiGian stops={chuyen.stops} /> : null}

        <View style={{ flexDirection: "row", gap: space.sm }}>
          <O
            label="Đã chia"
            value={tienVnd(chuyen.split_total_vnd)}
            mau={c.split}
            nen={c.splitSoft}
          />
          <O
            label={chuyen.expense_count === 1 ? "Khoản chi" : "Khoản chi"}
            value={`${chuyen.expense_count}`}
            mau={c.accent}
            nen={c.accentSoft}
          />
        </View>

        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Tiền của một chuyến là các khoản chi đã chốt rơi vào đúng những ngày đó. Một bữa
          chia sau khi cả nhóm đã về thì không tính vào chuyến này.
        </Text>
      </View>
    </Card>
  );
}

/** The timeline F15 keeps in builder order, not clock order. */
function DongThoiGian({ stops }: { stops: BuoiDiChoi["stops"] }) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      {stops.map((stop) => (
        <View
          key={`${stop.position}-${stop.at}`}
          style={{ flexDirection: "row", alignItems: "baseline", gap: space.sm }}
        >
          {/* Fixed width so the labels line up into a column. A wall-clock
              `HH:MM` is always five characters, so nothing is being clipped
              into fitting. */}
          <Text
            style={{
              ...type.micro,
              color: c.inkSoft,
              fontVariant: ["tabular-nums"],
              width: 42,
            }}
          >
            {stop.at}
          </Text>
          {/* `minWidth: 0` is load-bearing: a flex item defaults to
              `min-width: auto` and refuses to shrink below its content, so a
              long stop name pushes past the card edge instead of wrapping. */}
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={{ ...type.label, color: c.ink }}>
              {stop.place_name ?? stop.label}
            </Text>
            {stop.place_name ? (
              <Text style={{ ...type.micro, color: c.inkFaint }}>{stop.label}</Text>
            ) : null}
          </View>
        </View>
      ))}
    </View>
  );
}

function O({ label, value, mau, nen }: { label: string; value: string; mau: string; nen: string }) {
  const c = usePalette();
  return (
    // Colour is not the only carrier: the label above each number says which is
    // which, so the pair still reads with no colour vision at all.
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

/**
 * What the mockup draws that this screen cannot yet fill.
 *
 * Named here in one place rather than sprinkled as greyed-out buttons. A
 * disabled heart icon still says "reactions exist and yours did not register";
 * a sentence says the table was never built.
 */
function ConThieu() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.label, color: c.inkSoft }}>Chưa dựng trên màn này</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        Ảnh, video và check-in của mockup chưa có kho lưu nào đứng sau, nên không được vẽ
        ra ở đây. Thả tim, bình luận và lưu khoảnh khắc cũng chưa có bảng nào — bốn thứ đó
        là việc còn lại của trụ cột 5, không phải thứ đang ẩn đi.
      </Text>
    </Card>
  );
}
