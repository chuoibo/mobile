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
import { Anh } from "../../ui/Anh";
import { NutChonAnh } from "../../ui/NutChonAnh";
import {
  attemptFor,
  docKyNiem,
  taiAnhNhom,
  themKyNiemAnh,
  type Attempt,
  type KyNiemWire,
} from "../../api";
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
  docAnh = docKyNiem,
}: {
  nguoi: NguoiDung | null;
  /** Which group's wall, when the link named one. Null means "go and find it". */
  contextId?: string | null;
  /** Back out of the wall. Absent when it is rendered as a whole tab. */
  onDong?: () => void;
  /** Injected so the screen can be exercised without a server. */
  doc?: typeof layKyUc;
  timNhom?: typeof timNhomDemo;
  docAnh?: typeof docKyNiem;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-tai" });
  const [dangLamMoi, setDangLamMoi] = useState(false);
  // True when the group had to be created rather than found, which means this
  // wall is empty because nothing was ever seeded -- not because the group has
  // been nowhere. The two look identical on screen unless one of them says so.
  const [nhomVuaTao, setNhomVuaTao] = useState(false);
  // Which group this wall ended up reading. Held in state rather than recomputed
  // because the picker below has to upload into *the same* group the wall is
  // showing, and `timNhom` is a network call -- asking it a second time at
  // upload time could answer differently and hang the photo somewhere else.
  const [nhomDangXem, setNhomDangXem] = useState<string | null>(contextId ?? null);
  const [anh, setAnh] = useState<KyNiemWire[]>([]);
  // Photos load beside the ledger, not inside its state machine. A wall whose
  // recap failed should still be able to show and accept pictures, and a photo
  // route that is down must not blank out the money figures that did arrive.
  const [loiAnh, setLoiAnh] = useState<string | null>(null);

  const tai = useCallback(async () => {
    if (!nguoi) return;
    try {
      let nhom = contextId ?? null;
      if (nhom === null) {
        const tim = await timNhom(nguoi.personId);
        nhom = tim.contextId;
        setNhomVuaTao(!tim.daCoSan);
      }
      setNhomDangXem(nhom);
      setTrang({ pha: "xong", ky: await doc(nhom, nguoi.personId) });
    } catch (error) {
      const message =
        error instanceof KyUcError ? error.message : "Chưa đọc được sổ.";
      setTrang({ pha: "loi", loi: message });
    }
  }, [nguoi, contextId, doc, timNhom]);

  /** Re-read the wall. Called on mount, on pull-to-refresh, and after an upload.
   *
   * After an upload it is what makes the new photograph appear without the
   * person having to leave the screen and come back. Re-reading rather than
   * pushing the response onto the front of the list is deliberate: the server
   * decides the wall's order and its cursor, and a locally prepended row is a
   * second copy of that decision that disagrees the moment anybody else posts. */
  const taiAnh = useCallback(async () => {
    if (!nguoi || !nhomDangXem) return;
    try {
      setAnh(await docAnh(nhomDangXem, nguoi.personId));
      setLoiAnh(null);
    } catch (error) {
      setLoiAnh(
        error instanceof Error && error.message.trim() !== ""
          ? error.message
          : "Chưa đọc được ảnh của nhóm.",
      );
    }
  }, [nguoi, nhomDangXem, docAnh]);

  useEffect(() => {
    void taiAnh();
  }, [taiAnh]);

  useEffect(() => {
    void tai();
  }, [tai]);

  const lamMoi = useCallback(async () => {
    setDangLamMoi(true);
    await tai();
    await taiAnh();
    setDangLamMoi(false);
  }, [tai, taiAnh]);

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

        {san && nhomDangXem ? (
          <TuongAnh
            anh={anh}
            loi={loiAnh}
            contextId={nhomDangXem}
            personId={nguoi.personId}
            onThemXong={taiAnh}
          />
        ) : null}

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
            ? "Máy chủ chưa có nhóm demo nào nên app vừa lập một nhóm rỗng. Tường trống ở đây là vì chưa ai seed dữ liệu, không phải vì nhóm chưa đi đâu. Chạy `make demo` rồi mở lại."
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
 * The photo wall the mockup leads with, now that there is a store behind it.
 *
 * This screen used to say, at its foot, that photographs had nowhere to live.
 * That was true and is no longer: `POST /contexts/{id}/photos` writes into the
 * group's own private storage, and every byte is decoded, stripped of its
 * metadata and re-encoded on the way in. So the pictures here carry no GPS and
 * no camera serial, which is the condition under which drawing them at all is
 * defensible -- the objection was never that a wall is hard, it was that a photo
 * of real people is a location record with faces attached.
 *
 * Two rules this grid does not get to relax:
 *
 *  - **Nothing is fetched off our own API.** Every frame is an `Anh`, and `Anh`
 *    runs `nguonAnhAnToan` before it will build an `<Image>`. `image_url` is a
 *    string a *member* wrote, and the server only started refusing foreign
 *    addresses recently -- rows written before that are still in the database,
 *    so the client-side refusal is not redundancy, it is the layer that covers
 *    the rows the server's new check never saw.
 *  - **A missing picture is a frame, not a hole.** A load that fails falls back
 *    to the stand-in and stays there. It never shows a broken-image glyph and
 *    never shows the server's reason.
 *
 * The grid is two columns at every width this app is used at. A third column on
 * a phone puts a face at 110 pt, which is small enough that the wall stops being
 * something you look at and becomes something you scroll past.
 */
function TuongAnh({
  anh,
  loi,
  contextId,
  personId,
  onThemXong,
}: {
  anh: KyNiemWire[];
  loi: string | null;
  contextId: string;
  personId: string;
  onThemXong: () => void;
}) {
  const c = usePalette();
  // Keyed per photo url, so a retry after a failed "hang it on the wall" sends
  // the same key and replays rather than posting a second row -- and a genuinely
  // different picture gets its own key. Held in a ref because a re-render
  // between the press and the reply must not be able to lose it.
  const soKhoa = React.useRef<Record<string, Attempt>>({});

  const themAnh = useCallback(
    async (photo: { uri: string }) => {
      const daTai = await taiAnhNhom(contextId, photo, personId);
      await themKyNiemAnh(
        contextId,
        daTai.url,
        null,
        personId,
        attemptFor(soKhoa.current, `ky-niem:${daTai.url}`),
      );
    },
    [contextId, personId],
  );

  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Ảnh của nhóm</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Ảnh ở đây chỉ thành viên trong nhóm mở được. Máy chủ xoá sạch thông tin ẩn trong
        file trước khi lưu, nên tấm ảnh không mang theo toạ độ nơi chụp.
      </Text>

      <NutChonAnh
        nhan="Thêm ảnh"
        moTa="Chọn một tấm ảnh từ thư viện và thêm vào tường kỷ niệm của nhóm"
        taiLen={themAnh}
        onXong={onThemXong}
      />

      {loi ? (
        <Text style={{ ...type.label, color: c.ink }} accessibilityRole="alert">
          {loi}
        </Text>
      ) : null}

      {anh.length === 0 && !loi ? (
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Chưa có tấm ảnh nào. Tấm đầu tiên bạn thêm sẽ hiện ngay ở đây.
        </Text>
      ) : null}

      {anh.length > 0 ? (
        <View
          style={{
            flexDirection: "row",
            flexWrap: "wrap",
            gap: space.sm,
            marginTop: space.xs,
          }}
        >
          {anh.map((m) => (
            <Polaroid key={m.id} kyNiem={m} />
          ))}
        </View>
      ) : null}
    </Card>
  );
}

/** One picture on the wall, in the mockup's polaroid shape. */
function Polaroid({ kyNiem }: { kyNiem: KyNiemWire }) {
  const c = usePalette();
  const chuThich = kyNiem.caption?.trim() ?? "";
  return (
    // `flexBasis` with `flexGrow: 0` rather than a percentage width: two items
    // per row with the parent's gap between them, and a lone third item does not
    // stretch to fill the row it starts.
    <View
      style={{
        flexBasis: "47%",
        flexGrow: 0,
        borderRadius: radius.small,
        overflow: "hidden",
        backgroundColor: c.ground,
        borderWidth: 1,
        borderColor: c.line,
      }}
    >
      <Anh
        uri={kyNiem.image_url}
        alt={chuThich ? `Ảnh kỷ niệm: ${chuThich}` : "Ảnh kỷ niệm của nhóm"}
        // Square, because the wall reads as a wall only if the rows line up, and
        // a mixed-orientation set of real photographs does not.
        style={{ aspectRatio: 1, width: "100%" }}
        cho={
          // Not a grey rectangle. This is what a frame shows while its photo is
          // still arriving or after it refused to load, and the group's own
          // sunset says "a picture belongs here" rather than "something broke".
          <Gradient colors={HERO_SUNSET} style={{ flex: 1 }} />
        }
      />
      {chuThich ? (
        <Text
          numberOfLines={2}
          style={{ ...type.micro, color: c.inkSoft, padding: space.xs }}
        >
          {chuThich}
        </Text>
      ) : null}
    </View>
  );
}

/**
 * What the mockup draws that this screen cannot yet fill.
 *
 * Named here in one place rather than sprinkled as greyed-out buttons. A
 * disabled heart icon still says "reactions exist and yours did not register";
 * a sentence says the table was never built.
 *
 * Photographs left this list when `TuongAnh` above started working. Video,
 * reactions and comments are still here because they are still true: there is
 * no video store, no reactions table and no comments table. Check-ins have a
 * route and a table (F46) but no surface on this screen yet, which is a
 * different kind of missing and is said as one.
 */
function ConThieu() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.label, color: c.inkSoft }}>Chưa dựng trên màn này</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        Video chưa có kho lưu nào đứng sau. Thả tim và bình luận cũng chưa có bảng nào.
        Check-in đã có trong máy chủ nhưng chưa được vẽ lên tường này. Bốn thứ đó là việc
        còn lại của trụ cột 5, không phải thứ đang ẩn đi.
      </Text>
    </Card>
  );
}
