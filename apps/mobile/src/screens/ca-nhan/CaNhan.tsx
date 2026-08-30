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
import { Button, Card } from "../../ui/Kit";
import { Gradient, HERO_SUNSET } from "../../navigation/Gradient";
import { DEMO_GROUP_NAME, type DemoPerson } from "../../navigation/nhom-demo";
import { Anh, khungTron } from "../../ui/Anh";
import { NutChonAnh } from "../../ui/NutChonAnh";
import { duongDanAnhDaiDien, taiAnhDaiDien } from "../../api";
import { MaCuaToi } from "./MaCuaToi";
import { Tuong } from "./Tuong";
import {
  FinanceError,
  ghiChuGioiHan,
  layTaiChinh,
  moTaGiaoDich,
  ngayNgan,
  tienCoDau,
  tienVnd,
  tinhTrangNo,
  type Finance,
  type Movement,
} from "./tai-chinh";

type Trang =
  | { pha: "dang-tai" }
  | { pha: "xong"; so: Finance }
  | { pha: "loi"; loi: string };

export function CaNhan({
  nguoi,
  onKetBan,
  onThanhTich,
  nhom = [],
  doc = layTaiChinh,
}: {
  nguoi: DemoPerson | null;
  /** Open the F03/F04 friend screen. Handed in by the shell rather than
   *  imported, because that screen takes over the whole viewport and only the
   *  shell knows how to give it back. Optional so the older callers -- and the
   *  screen's own tests -- keep compiling; a missing handler hides the row
   *  rather than rendering a button that does nothing. */
  onKetBan?: () => void;
  /** 07.03. Open the achievements screen. Handed in by the shell for the same
   *  reason `onKetBan` is, and optional in the same way: no handler hides the
   *  row rather than drawing a button that does nothing. */
  onThanhTich?: () => void;
  /** Groups this person can address a post to. Empty until the shell knows one. */
  nhom?: { id: string; name: string }[];
  /** Injected so the screen can be exercised without a server. */
  doc?: typeof layTaiChinh;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-tai" });
  const [dangLamMoi, setDangLamMoi] = useState(false);
  // Bumped after a successful upload. See `BiaVaAnh` for why a counter is the
  // thing that makes a new avatar appear at all.
  const [doiAnh, setDoiAnh] = useState(0);

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
      // A keyboard tab-stop on the scroller itself. Measured: axe
      // `scrollable-region-focusable` (serious) fired here and on none of the
      // other four tabs, because this was the one tab holding nothing
      // pressable, and a scrollable region containing a focusable child is
      // already reachable.
      //
      // rd-fe-25 added the avatar picker below, so that original reason has
      // expired -- and the stop stays anyway, for a reason the axe rule does not
      // cover. Satisfying the rule with a button means a keyboard reaches this
      // region only by tabbing *to that button*; the stop on the region is what
      // lets somebody scroll the transaction list and "Nhóm của bạn" with arrow
      // keys without first landing on a control that changes their photograph.
      // The rule is the floor here, not the requirement.
      //
      // `tabIndex` rather than `focusable`: the latter is deprecated in
      // react-native-web 0.21 and warns. Native ignores the prop, which is
      // correct -- a touch screen has no tab ring to join.
      tabIndex={0}
      refreshControl={
        <RefreshControl refreshing={dangLamMoi} onRefresh={lamMoi} tintColor={c.accent} />
      }
    >
      <BiaVaAnh nguoi={nguoi} ten={tenHienThi(nguoi, trang)} doiAnh={doiAnh} />

      <View style={{ padding: space.md, gap: space.md }}>
        {nguoi ? null : <ChuaChon />}
        {nguoi ? (
          <DoiAnhDaiDien
            personId={nguoi.personId}
            onXong={() => setDoiAnh((n) => n + 1)}
          />
        ) : null}
        <HangSoLieu trang={trang} />
        <CuaThanhTich nguoi={nguoi} onThanhTich={onThanhTich} />
        <TaiChinh trang={trang} onThuLai={lamMoi} coNguoi={Boolean(nguoi)} />
        <GiaoDich trang={trang} />
        {nguoi?.personId ? <Tuong nguoi={nguoi} nhom={nhom} /> : null}
        <NhomCuaBan trang={trang} />
        <CuaKetBan nguoi={nguoi} onKetBan={onKetBan} />
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

/** Cover band with the avatar sitting over its lower edge, as in the mockup.
 *
 * The avatar is a real photograph now, and the two things that took measuring
 * are both about the address it is read from.
 *
 * **The bytes are permission-checked, so the frame fetches them.** `GET
 * /people/{id}/avatar` answers 401 without `X-Actor-ID`, and an `<img>` cannot
 * send one. Pointing the frame at the address therefore never worked: the load
 * failed, `Anh` drew the initials, and the initials are also what somebody with
 * no photograph sees, so nothing on the screen or in the tests could tell the
 * two apart. `nguoiXem` is what makes the request carry the header; see `Anh`.
 *
 * **The address is stable, and that is a feature with one sharp edge.**
 * `/people/{id}/avatar` always names the current picture, so nothing has to be
 * stored, threaded through the finance response, or added to a roster for a new
 * face to appear -- the frame simply starts resolving. But the server sends
 * `Cache-Control: private, max-age=300` with it, which is right for a picture
 * every screen shows and wrong for the five minutes after you change yours: the
 * URL did not change, so the image layer has no reason to ask again, and a
 * person who just uploaded a photo would watch the old one stay put and
 * reasonably conclude the upload failed. `doiAnh` is bumped on success and rides
 * along as a query parameter, which makes the address different *only* for the
 * client that changed it. A timestamp would work too and would defeat the cache
 * on every mount, costing every other screen the caching this one needs beaten
 * exactly once.
 *
 * **A 404 is the ordinary answer.** Somebody with no avatar yet gets one, and
 * `Anh` draws the caller's stand-in for a frame whose load failed, so nothing
 * has to ask first. The stand-in is the person's initials, which is a better
 * answer than a grey silhouette: it is about them.
 */
function BiaVaAnh({
  nguoi,
  ten,
  anhBia,
  doiAnh = 0,
}: {
  nguoi: DemoPerson | null;
  ten: string;
  anhBia?: string | null;
  doiAnh?: number;
}) {
  const c = usePalette();
  const AVATAR = 84;
  const anhDaiDien = nguoi
    ? `${duongDanAnhDaiDien(nguoi.personId)}${doiAnh > 0 ? `?v=${doiAnh}` : ""}`
    : null;
  return (
    <View style={{ marginBottom: AVATAR / 2 + space.xs }}>
      {/* The cover band still holds no photograph: there is no cover-photo route
          and a stock landscape of somewhere this person has never been is a
          worse lie than a gradient. Same sunset the opening screen paints, so
          arriving here reads as the same product rather than a second one. No
          text sits on it: `tokens.brand` measures white on the coral stop at
          2.92:1 and forbids exactly that. */}
      <Anh
        uri={anhBia}
        alt=""
        // No cover-photo route exists, so no address reaching this frame is
        // permission-checked. Stated rather than defaulted; see `Anh`.
        nguoiXem={null}
        cho={<Gradient colors={HERO_SUNSET} style={{ flex: 1 }} />}
        style={{ height: 148 }}
      />
      <View
        style={{
          position: "absolute",
          left: space.md,
          bottom: -AVATAR / 2,
        }}
      >
        <Anh
          uri={anhDaiDien}
          alt={`Ảnh đại diện của ${ten}`}
          // `GET /people/{id}/avatar` is permission-checked, so the frame has to
          // fetch the bytes with this person's header rather than point an
          // <img> at the address and be told 401. See `Anh` and `taiAnhCoQuyen`.
          nguoiXem={nguoi?.personId ?? null}
          cho={
            <View
              style={{
                flex: 1,
                backgroundColor: c.accentSoft,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ ...type.amount, color: c.accent }}>{nguoi?.initials ?? "?"}</Text>
            </View>
          }
          style={{ ...khungTron(84), borderColor: c.card, borderWidth: 4 }}
        />
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

/**
 * Change your own picture. Yours, and only ever yours.
 *
 * `POST /people/{id}/avatar` checks `is_self` on the server, so the id in the
 * address is not a suggestion -- this screen could not set somebody else's face
 * even if it tried. Passing `nguoi.personId` as both the subject and the actor
 * is what makes that check pass, and it is written out rather than defaulted so
 * the day real sessions arrive, the place where the two stop being the same
 * value is visible.
 *
 * A card of its own rather than a control floating on the cover band. The
 * avatar overhangs the gradient by half its height and the name block fills the
 * space beside it; a button squeezed in there would either sit on a photograph
 * whose brightness nothing controls -- the contrast the rest of this screen is
 * measured against would stop meaning anything -- or push the name off the
 * band. It is the first card in the column, directly under the face it changes.
 */
function DoiAnhDaiDien({
  personId,
  onXong,
}: {
  personId: string;
  onXong: () => void;
}) {
  const c = usePalette();
  const tai = useCallback(
    async (photo: { uri: string }) => {
      await taiAnhDaiDien(personId, photo, personId);
    },
    [personId],
  );
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Ảnh đại diện</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Chỉ những người chung nhóm với bạn mới xem được tấm ảnh này. Máy chủ xoá sạch
        thông tin ẩn trong file trước khi lưu, nên ảnh không mang theo toạ độ nơi chụp.
      </Text>
      <NutChonAnh
        nhan="Đổi ảnh đại diện"
        moTa="Chọn một tấm ảnh từ thư viện để làm ảnh đại diện của bạn"
        kieu="nhe"
        taiLen={tai}
        onXong={onXong}
      />
    </Card>
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
 * rhythm is the design, and marked "chưa có" with one caption rather than
 * filled with a number that would look exactly as real as the two beside it.
 * That substitution is the failure this whole screen is built to avoid.
 *
 * The marker used to be an em dash, which read as nothing at all to a screen
 * reader: the tile announced "Kỷ niệm" and no value, so absence was indist-
 * inguishable from a figure that failed to load. Words say it outright. They
 * are set at `label` rather than `title` size because a 20px "chưa có" wraps
 * inside a quarter-width tile, and because a smaller, fainter value is the
 * honest signal that this is not a number. The shared `lineHeight` is what
 * keeps all four labels on one baseline across the mixed sizes.
 */
function HangSoLieu({ trang }: { trang: Trang }) {
  const c = usePalette();
  const so = trang.pha === "xong" ? trang.so : null;
  const o = (value: string) => (trang.pha === "dang-tai" ? "…" : value);
  const items: { label: string; value: string; that: boolean }[] = [
    { label: "Lần chia bill", value: o(`${so?.expense_count ?? 0}`), that: true },
    { label: "Nhóm", value: o(`${so?.group_count ?? 0}`), that: true },
    { label: "Kỷ niệm", value: "chưa có", that: false },
    { label: "Đánh giá", value: "chưa có", that: false },
  ];
  return (
    <Card>
      <View style={{ flexDirection: "row" }}>
        {items.map((item) => (
          <View key={item.label} style={{ flex: 1, alignItems: "center", gap: 2 }}>
            <Text
              style={{
                ...(item.that ? type.title : type.label),
                lineHeight: 26,
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

/** 07.03. The door to the achievements screen.
 *
 * Directly under the stat row because the two are the same subject read at two
 * depths: that row counts what the ledger knows, and the screen behind this
 * button turns those same counts into levels, badges and this week's
 * challenges. It reads the identical route, so nothing here can disagree with
 * the numbers above it.
 *
 * Renders nothing without a handler or without a person, the same rule
 * `CuaKetBan` follows: a screen that cannot say who is asking would send
 * `X-Actor-ID: undefined` and read as broken rather than as needing a sign-in.
 */
function CuaThanhTich({
  nguoi,
  onThanhTich,
}: {
  nguoi: DemoPerson | null;
  onThanhTich?: () => void;
}) {
  const c = usePalette();
  if (!nguoi || !onThanhTich) return null;
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Thành tích</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Level, huy hiệu và thử thách tuần này, tính từ chính cuốn sổ ở trên. Bốn huy
        hiệu mở được bằng hoạt động thật; bốn cái còn lại ghi rõ sản phẩm còn thiếu
        bảng nào mới đo được.
      </Text>
      <View style={{ marginTop: space.xs }}>
        <Button label="Xem thành tích của bạn" onPress={onThanhTich} tone="ghost" />
      </View>
    </Card>
  );
}

/** Tổng quan tài chính — the reason this screen is on the demo path.
 *
 * Mockup 07.02 puts three figures in a row: *Đã trả*, *Còn nhận*, *Còn phải
 * trả*. Only two of them existed here, and both were about money going out --
 * so the person who put the bill on their own card, which on the demo path is
 * the person running the demo, split a dinner, came back, and read `Còn nợ 0đ`
 * with nothing anywhere saying the money was coming back to them. `Còn nhận`
 * is the missing third, and it is read from the ledger like every other number
 * on this screen; see `receivable_vnd` in `repository.py`.
 *
 * The mockup's three tiles are laid out here as one total and a pair beneath
 * it, rather than three abreast. Three tiles across 390pt leaves about 90pt of
 * text width each, and `2.100.000đ` does not fit in it -- the same measurement
 * that put `minWidth: 0` on the transaction rows below. The information is the
 * mockup's; the row count is what the device allows.
 *
 * `Đã thanh toán` is kept although the mockup has no tile for it, because it
 * is the half of the total that `Còn phải trả` does not account for, and the
 * two are printed directly under the number they add up to.
 *
 * Exported for the renderer, not for other screens. `CaNhan` reaches its
 * loaded state through `useEffect`, which `renderToStaticMarkup` does not run
 * -- so rendering the whole screen only ever produces the spinner, and these
 * three figures could be missing from the markup with every test still green.
 * This is the seam that lets a test hand in a finished `Finance` and read what
 * a browser really gets. See `tests/tai-chinh-tren-man.test.mjs`.
 */
export function TaiChinh({
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
            <Text style={{ ...type.label, color: c.inkSoft }}>Đã trả</Text>
            <Text style={{ ...type.amount, color: c.ink }}>
              {tienVnd(trang.so.spend_vnd)}
            </Text>
            <Text style={{ ...type.micro, color: c.inkSoft }}>
              Tổng bạn đã chi. Đã thanh toán xong {tienVnd(trang.so.settled_vnd)}.
            </Text>
          </View>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <ONho
              label="Còn nhận"
              value={tienVnd(trang.so.receivable_vnd)}
              chu="Người khác nợ bạn"
              mau={c.split}
              nen={c.splitSoft}
            />
            <ONho
              label="Còn phải trả"
              value={tienVnd(trang.so.outstanding_vnd)}
              chu="Bạn còn nợ người khác"
              mau={c.accent}
              nen={c.accentSoft}
            />
          </View>
          {/* The five states of mockup 07.02, said in words. Two coloured
              numbers do not tell somebody in three seconds whether this is a
              good month, and colour is forbidden from carrying it alone. */}
          <Text style={{ ...type.body, color: c.ink }}>
            {tinhTrangNo(trang.so).cau}
          </Text>
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            Tính lại từ sổ mỗi lần mở màn này. Chia một khoản chi rồi quay lại, ba số
            trên đổi theo. Một khoản chỉ rời khỏi "còn nhận" khi bạn xác nhận đã nhận
            được tiền. Người kia báo đã chuyển thì chưa tính.
          </Text>
          {/* Stated, not drawn. The mockup breaks the month down into Ăn uống,
              Di chuyển, Cafe and Vui chơi, and no expense in this product
              carries a category -- there is no column, no field on the create
              request, and nothing that could fill those four bars except a
              guess. Four plausible bars would read exactly as real as the
              three figures above them, which is the substitution this screen
              is built to refuse. Saying so is the honest version of drawing
              it. */}
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            Chưa tách được theo nhóm chi (ăn uống, đi lại, cafe…): khoản chi trong sản
            phẩm này chưa mang danh mục nào.
          </Text>
        </View>
      ) : null}
    </Card>
  );
}

function ONho({
  label,
  value,
  chu,
  mau,
  nen,
}: {
  label: string;
  value: string;
  /** Which direction the money runs, spelled out. The mockup prints it under
   *  each tile, and it is the part that survives a greyscale screenshot: the
   *  two tiles are otherwise a green number and a coral number, and "còn
   *  nhận" versus "còn phải trả" is exactly the distinction somebody skims
   *  past. */
  chu?: string;
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
      {chu ? <Text style={{ ...type.micro, color: c.inkSoft }}>{chu}</Text> : null}
    </View>
  );
}

/** Giao dịch gần đây, newest first, sign carried by the word and the colour. */
function GiaoDich({ trang }: { trang: Trang }) {
  const c = usePalette();
  if (trang.pha !== "xong") return null;
  const list = trang.so.movements;
  const gioiHan = ghiChuGioiHan(list);
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Giao dịch gần đây</Text>
      {list.length === 0 ? (
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Chưa có giao dịch nào được xác nhận. Một khoản chỉ vào đây khi người nhận xác
          nhận đã nhận tiền. Người gửi báo đã chuyển thì chưa tính.
        </Text>
      ) : (
        list.map((m, i) => <DongGiaoDich key={m.obligation_id + i} m={m} />)
      )}
      {/* Only on a full page. A list of six rows is the whole history and
          saying otherwise would be its own small lie. */}
      {gioiHan ? (
        <Text style={{ ...type.micro, color: c.inkFaint }}>{gioiHan}</Text>
      ) : null}
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

/**
 * F03/F04. The door to the friend screen.
 *
 * It sits directly above "Mã kết bạn của bạn" because the two are the same
 * act from opposite ends: the code below is how somebody adds *you* with a
 * camera, this is how you add *them* with a number you already have. Before
 * this row existed, `POST /friends/lookup` and the four routes beside it had
 * shipped and no screen in the app called any of them -- which by this team's
 * way of counting means the feature was not there.
 *
 * Renders nothing without a handler or without a person. A button that opens
 * a screen which cannot say who is asking would send `X-Actor-ID: undefined`
 * and read as a broken feature rather than as one that needs signing in.
 */
function CuaKetBan({
  nguoi,
  onKetBan,
}: {
  nguoi: DemoPerson | null;
  onKetBan?: () => void;
}) {
  const c = usePalette();
  if (!nguoi || !onKetBan) return null;
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Bạn bè</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Tìm bạn bằng số điện thoại và gửi lời mời. Lời mời chỉ thành kết bạn khi người
        kia đồng ý, nên ở đây bạn xem được cả hai chiều: ai đang chờ bạn trả lời, và
        bạn đang chờ ai.
      </Text>
      <View style={{ marginTop: space.xs }}>
        <Button label="Mở màn kết bạn" onPress={onKetBan} tone="ghost" />
      </View>
    </Card>
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
          nhóm và ảnh thành viên chưa dựng, màn nhóm là việc của lane khác.
        </Text>
      )}
    </Card>
  );
}
