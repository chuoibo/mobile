/** Thành tích — 07.03 of the mockup set, and the one screen of the twenty one
 *  that had no file at all.
 *
 * Mockup: `product/RuDi_Mobile_Product_Mockups/07_profile_finance/03_
 * achievements/07_03_achievements.png`. Layout follows it top to bottom:
 * profile row with a level chip, a stat row, a progress bar toward the next
 * level, the badge grid, this week's challenges, and one primary call to
 * action at the bottom.
 *
 * ## What is real on this screen
 *
 * Everything except one tile. `thanh-tich.ts` derives the level, all eight
 * badges and all three challenges from `GET /people/{id}/finance`, which is the
 * same self-only route the Cá nhân tab reads, and that file's header explains
 * each derivation. Four badges can actually open while somebody uses the demo;
 * the other four name the table this product would need first and say so on
 * their own face.
 *
 * The one tile with nothing behind it is `Chuyến đi`, and it is drawn the way
 * `CaNhan.tsx` draws its two empty tiles: the word "chưa có" at label size in
 * the faint ink, never a number. A screen reader hears the words, which an em
 * dash or a blank would not have given it.
 *
 * ## Why the CTA goes somewhere
 *
 * "Xem tất cả thành tích" opens a second view listing every badge with its
 * criterion, its progress and, where it is unmeasurable, the reason. A primary
 * button that does nothing is the specific defect the group screen was reported
 * for at 23:52 on 2026-08-30 -- a button that produced no request, no console
 * error and no movement -- so the last control on this screen leads somewhere
 * and the way back is always drawn.
 *
 * ## What this screen does not prove
 *
 * That anybody has looked at it. It carries a `vao=thanh-tich` address and a
 * row in `tools/tab-snapshots.mjs` so a cold URL can open it, which is
 * reachability, not measurement. See `lien-ket.ts` on why those are two claims.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card } from "../../ui/Kit";
import { CoLoi, DangTai, TrongRong } from "../../ui/TrangThai";
import { Anh, khungTron } from "../../ui/Anh";
import { BASE_URL, duongDanAnhDaiDien } from "../../api";
import type { DemoPerson } from "../../navigation/nhom-demo";
import { FinanceError, layTaiChinh, type Finance } from "../ca-nhan/tai-chinh";
import {
  DIEM_MOI_CAP,
  DIEM_MOI_KHOAN_CHI,
  DIEM_MOI_NHOM,
  huyHieuCuaNguoi,
  phanSo,
  thuThachTuan,
  tiLe,
  tienDoCapDo,
  type HuyHieu,
  type ThuThach,
} from "./thanh-tich";

type Trang =
  | { pha: "chua-chon" }
  | { pha: "dang-tai" }
  | { pha: "xong"; so: Finance }
  | { pha: "loi"; loi: string };

export function ThanhTich({
  nguoi,
  onDong,
  doc = layTaiChinh,
  bayGio = () => Date.now(),
}: {
  nguoi: DemoPerson | null;
  onDong: () => void;
  /** Injected so the screen can be exercised without a server, the same way
   *  `CaNhan` takes its reader. */
  doc?: typeof layTaiChinh;
  /** Injected for the same reason, and separately: the weekly challenges are a
   *  window over real timestamps, so a test that cannot move the clock would be
   *  measuring whichever rows happened to be recent on the day it ran. */
  bayGio?: () => number;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>(nguoi ? { pha: "dang-tai" } : { pha: "chua-chon" });
  const [xemTatCa, setXemTatCa] = useState(false);
  const [chon, setChon] = useState<string | null>(null);

  const tai = useCallback(async () => {
    if (!nguoi) {
      setTrang({ pha: "chua-chon" });
      return;
    }
    setTrang({ pha: "dang-tai" });
    try {
      setTrang({ pha: "xong", so: await doc(nguoi.personId) });
    } catch (error) {
      setTrang({
        pha: "loi",
        loi: error instanceof FinanceError ? error.message : "Chưa đọc được sổ.",
      });
    }
  }, [nguoi, doc]);

  useEffect(() => {
    void tai();
  }, [tai]);

  if (trang.pha === "xong" && xemTatCa) {
    return (
      <Khung
        tieuDe="Tất cả thành tích"
        phu="Mỗi huy hiệu kèm điều kiện mở, và huy hiệu nào chưa đo được thì nói rõ còn thiếu bảng nào."
        nhanDong="Quay lại"
        onDong={() => setXemTatCa(false)}
      >
        <TatCa so={trang.so} bayGio={bayGio()} />
      </Khung>
    );
  }

  return (
    <Khung
      tieuDe="Thành tích của bạn"
      phu="Lưu lại dấu ấn của bạn trong mỗi chuyến đi."
      nhanDong="Đóng"
      onDong={onDong}
      duoi={
        trang.pha === "xong" ? (
          <Button label="Xem tất cả thành tích" onPress={() => setXemTatCa(true)} />
        ) : null
      }
    >
      {trang.pha === "chua-chon" ? (
        <TrongRong
          tieuDe="Chưa chọn người"
          than="Màn này đọc sổ của một người cụ thể. Quay ra màn mở đầu và chọn một người trong nhóm."
        />
      ) : null}

      {trang.pha === "dang-tai" ? (
        <DangTai noiDung="Đang đọc sổ" phu="Huy hiệu và thử thách đều tính từ sổ, nên phải đọc xong mới vẽ." />
      ) : null}

      {trang.pha === "loi" ? (
        <CoLoi
          tieuDe="Chưa đọc được thành tích"
          than={trang.loi}
          viecTiepTheo="Bấm thử lại. Màn này chỉ đọc, chưa có gì bị ghi sai."
          diaChi={BASE_URL}
          onThuLai={() => void tai()}
        />
      ) : null}

      {trang.pha === "xong" ? (
        <>
          <TheNguoi nguoi={nguoi} so={trang.so} />
          <HangSoLieu so={trang.so} />
          <TienDo so={trang.so} />
          <LuoiHuyHieu so={trang.so} chon={chon} onChon={setChon} />
          <ThuThachTuan so={trang.so} bayGio={bayGio()} />
          <NguonSo />
        </>
      ) : null}
    </Khung>
  );
}

/** Chrome shared by both views, so the way out never depends on a request
 *  having succeeded. Same shape as `quan-tri/QuanTriNhom.tsx`. */
function Khung({
  tieuDe,
  phu,
  nhanDong,
  onDong,
  children,
  duoi,
}: {
  tieuDe: string;
  phu: string;
  nhanDong: string;
  onDong: () => void;
  children: React.ReactNode;
  duoi?: React.ReactNode;
}) {
  const c = usePalette();
  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.lg }}>
      <View style={{ gap: space.xs }}>
        <Text style={{ ...type.h1, color: c.ink }}>{tieuDe}</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>{phu}</Text>
      </View>
      <ScrollView contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }} tabIndex={0}>
        {children}
      </ScrollView>
      <View style={{ gap: space.sm }}>
        {duoi}
        <Button label={nhanDong} onPress={onDong} tone="quiet" />
      </View>
    </View>
  );
}

/** Profile row: face, name, and the level chip the mockup puts on the right. */
function TheNguoi({ nguoi, so }: { nguoi: DemoPerson | null; so: Finance }) {
  const c = usePalette();
  const tien = tienDoCapDo(so);
  const ten = so.display_name ?? nguoi?.name ?? "Khách";
  return (
    <Card>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <Anh
          uri={nguoi ? duongDanAnhDaiDien(nguoi.personId) : null}
          alt={`Ảnh đại diện của ${ten}`}
          // `GET /people/{id}/avatar` is permission checked and an <img> cannot
          // send a header, so the frame fetches the bytes as this person. Same
          // reason `CaNhan.tsx` passes it; without it the load 401s and the
          // initials draw, which looks identical to having no photograph.
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
              <Text style={{ ...type.title, color: c.accent }}>{nguoi?.initials ?? "?"}</Text>
            </View>
          }
          style={khungTron(56)}
        />
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <Text numberOfLines={1} style={{ ...type.title, color: c.ink }}>
            {ten}
          </Text>
          <Text numberOfLines={1} style={{ ...type.micro, color: c.inkSoft }}>
            {so.group_count > 0 ? `Đang đi cùng ${so.group_count} nhóm` : "Chưa vào nhóm nào"}
          </Text>
        </View>
        {/* The chip carries the word "Level" as well as the number, so it reads
            as a level and not as a count of something. */}
        <View
          style={{
            flexShrink: 0,
            paddingVertical: space.xs,
            paddingHorizontal: space.sm,
            borderRadius: radius.pill,
            backgroundColor: c.aiSoft,
          }}
        >
          <Text style={{ ...type.label, fontWeight: "700", color: c.aiInk }}>
            Level {tien.cap}
          </Text>
        </View>
      </View>
    </Card>
  );
}

/**
 * The mockup's three-up stat row.
 *
 * Two are read from the ledger. `Chuyến đi` has no table behind it anywhere in
 * this product, so it carries the words "chưa có" at label size in the faint
 * ink rather than a number -- the same substitution `CaNhan.tsx` refuses, for
 * the same reason, and written the same way so the two screens agree.
 */
function HangSoLieu({ so }: { so: Finance }) {
  const c = usePalette();
  const items: { label: string; value: string; that: boolean }[] = [
    { label: "bill đã chia", value: `${so.expense_count}`, that: true },
    { label: "nhóm", value: `${so.group_count}`, that: true },
    { label: "chuyến đi", value: "chưa có", that: false },
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
        Hai số đầu đọc từ sổ. Sản phẩm chưa có bảng chuyến đi nên ô thứ ba để trống.
      </Text>
    </Card>
  );
}

/** "Tiến độ khám phá": the bar, and the rule that produced it. */
function TienDo({ so }: { so: Finance }) {
  const c = usePalette();
  const t = tienDoCapDo(so);
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Tiến độ khám phá</Text>
      <Text style={{ ...type.body, color: c.ink }}>
        <Text style={{ fontWeight: "700", color: c.accent }}>{t.diemTrongCap}</Text>
        <Text style={{ color: c.inkSoft }}>
          {` / ${t.diemMoiCap} điểm để lên Level ${t.capSau}`}
        </Text>
      </Text>
      <Thanh phan={tiLe(t.diemTrongCap, t.diemMoiCap)} mau={c.accent} />
      <Text style={{ ...type.micro, color: c.inkSoft }}>
        {`Cách tính: ${DIEM_MOI_KHOAN_CHI} điểm mỗi khoản chi bạn có mặt, ${DIEM_MOI_NHOM} điểm mỗi nhóm, ${DIEM_MOI_CAP} điểm một level. Tổng của bạn: ${t.diem} điểm.`}
      </Text>
    </Card>
  );
}

/** One progress bar. Track and fill, with the fill never below a visible sliver
 *  once there is any progress at all: a bar showing 1 of 100 as literally zero
 *  pixels reads as "nothing counted", which is a different claim. */
function Thanh({ phan, mau }: { phan: number; mau: string }) {
  const c = usePalette();
  const rong = phan > 0 ? Math.max(4, Math.round(phan * 100)) : 0;
  return (
    <View
      style={{
        height: 8,
        borderRadius: radius.pill,
        backgroundColor: c.line,
        overflow: "hidden",
      }}
    >
      <View style={{ width: `${rong}%`, height: "100%", backgroundColor: mau }} />
    </View>
  );
}

/** The badge grid, four across on the mockup and wrapped here so it survives a
 *  narrow phone without a horizontal scroll. */
function LuoiHuyHieu({
  so,
  chon,
  onChon,
}: {
  so: Finance;
  chon: string | null;
  onChon: (id: string | null) => void;
}) {
  const c = usePalette();
  const ds = huyHieuCuaNguoi(so);
  const daMo = ds.filter((h) => h.trangThai === "mo").length;
  const dangChon = ds.find((h) => h.id === chon) ?? null;
  return (
    <Card>
      <View style={{ gap: space.xs }}>
        <Text style={{ ...type.title, color: c.ink }}>Huy hiệu ({daMo}/{ds.length})</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Chạm một huy hiệu để xem điều kiện mở của nó.
        </Text>
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
        {ds.map((h) => (
          <OHuyHieu
            key={h.id}
            huy={h}
            dangChon={h.id === chon}
            onPress={() => onChon(chon === h.id ? null : h.id)}
          />
        ))}
      </View>
      {dangChon ? <ChiTietHuyHieu huy={dangChon} /> : null}
    </Card>
  );
}

/** One badge tile.
 *
 * State is never carried by colour alone. Each tile prints its own status word
 * under the name, so the grid reads on a greyscale screenshot and to somebody
 * with no colour vision, which is the rule the rest of this app follows.
 *
 * `minHeight` is the 44pt tap-target floor, and the tile is a real button
 * rather than a `Text` with an `onPress`, so a keyboard reaches it and a screen
 * reader announces it as pressable.
 */
function OHuyHieu({
  huy,
  dangChon,
  onPress,
}: {
  huy: HuyHieu;
  dangChon: boolean;
  onPress: () => void;
}) {
  const c = usePalette();
  const mo = huy.trangThai === "mo";
  const nen = mo ? c.accentSoft : "transparent";
  const vien = dangChon ? c.accent : mo ? c.accent : c.line;
  const chuTrangThai =
    huy.trangThai === "mo"
      ? "đã mở"
      : huy.trangThai === "chua-dat"
        ? phanSo(huy.daDat ?? 0, huy.can ?? 1)
        : "chưa đo được";
  return (
    <View style={{ width: "25%", padding: space.xs / 2 }}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        aria-expanded={dangChon}
        accessibilityLabel={`${huy.ten}, ${chuTrangThai}. ${huy.dieuKien}`}
        style={({ pressed }) => ({
          minHeight: 44,
          alignItems: "center",
          gap: 2,
          paddingVertical: space.xs,
          paddingHorizontal: 2,
          borderRadius: radius.control,
          borderWidth: 1,
          borderColor: vien,
          backgroundColor: nen,
          opacity: pressed ? 0.85 : 1,
        })}
      >
        {/* A shape, not a photograph. There is no badge artwork in this repo and
            a stock icon set is not worth a dependency for a demo; the ring
            plus the state word carries earned versus not. */}
        <View
          style={{
            width: 30,
            height: 30,
            borderRadius: radius.pill,
            borderWidth: 2,
            borderColor: mo ? c.accent : c.lineStrong,
            backgroundColor: mo ? c.accent : "transparent",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Text style={{ ...type.micro, fontWeight: "700", color: mo ? c.accentInk : c.inkFaint }}>
            {mo ? "✓" : huy.trangThai === "chua-dat" ? "•" : "?"}
          </Text>
        </View>
        <Text numberOfLines={2} style={{ ...type.micro, color: c.ink, textAlign: "center" }}>
          {huy.ten}
        </Text>
        <Text numberOfLines={1} style={{ ...type.micro, color: c.inkFaint, textAlign: "center" }}>
          {chuTrangThai}
        </Text>
      </Pressable>
    </View>
  );
}

/** The criterion behind whichever badge was tapped, announced when it opens. */
function ChiTietHuyHieu({ huy }: { huy: HuyHieu }) {
  const c = usePalette();
  return (
    <View
      role="status"
      accessibilityLiveRegion="polite"
      style={{
        gap: 2,
        padding: space.sm,
        borderRadius: radius.control,
        backgroundColor: c.ground,
        borderWidth: 1,
        borderColor: c.line,
      }}
    >
      <Text style={{ ...type.body, fontWeight: "600", color: c.ink }}>{huy.ten}</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>{huy.dieuKien}</Text>
      {huy.trangThai === "chua-do-duoc" ? (
        <Text style={{ ...type.micro, color: c.warn }}>
          {`Chưa đo được: ${huy.thieuGi}. Huy hiệu này là phần vỏ, không phải điều kiện bạn chưa đạt.`}
        </Text>
      ) : (
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          {`Đang ở ${phanSo(huy.daDat ?? 0, huy.can ?? 1)}, tính từ sổ.`}
        </Text>
      )}
    </View>
  );
}

/** "Thử thách tuần này". Every row is a window over real timestamps. */
function ThuThachTuan({ so, bayGio }: { so: Finance; bayGio: number }) {
  const c = usePalette();
  const ds = thuThachTuan(so, bayGio);
  return (
    <Card>
      <View style={{ gap: space.xs }}>
        <Text style={{ ...type.title, color: c.ink }}>Thử thách tuần này</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Đếm trong 7 ngày gần nhất, từ các giao dịch người nhận đã xác nhận.
        </Text>
      </View>
      {ds.map((t) => (
        <HangThuThach key={t.id} t={t} />
      ))}
    </Card>
  );
}

function HangThuThach({ t }: { t: ThuThach }) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      <View style={{ flexDirection: "row", alignItems: "baseline", gap: space.sm }}>
        <Text style={{ ...type.body, color: c.ink, flex: 1, minWidth: 0 }}>{t.ten}</Text>
        {/* The word "xong" beside the fraction, so completion is not a green
            bar and nothing else. */}
        <Text
          style={{
            ...type.label,
            fontWeight: "600",
            fontVariant: ["tabular-nums"],
            color: t.xong ? c.split : c.inkSoft,
          }}
        >
          {t.xong ? `${phanSo(t.daDat, t.can)} xong` : phanSo(t.daDat, t.can)}
        </Text>
      </View>
      <Thanh phan={tiLe(t.daDat, t.can)} mau={t.xong ? c.split : c.accent} />
    </View>
  );
}

/** Where every number above came from, said once at the bottom of the screen.
 *
 * The scoring rule is this app's, not the server's. Saying so is the difference
 * between a demo feature and a claim that a backend nobody has written is
 * keeping score.
 */
function NguonSo() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Mọi con số trên màn này tính từ sổ của chính bạn, đọc qua một đường duy nhất
        (tài chính cá nhân) mỗi lần mở màn. Máy chủ chưa có bảng thành tích: cách quy
        điểm và điều kiện huy hiệu là quy tắc của bản demo này, in ngay trên màn để bạn
        đối chiếu được.
      </Text>
    </Card>
  );
}

/** The CTA's destination: every badge and every challenge, with criteria. */
function TatCa({ so, bayGio }: { so: Finance; bayGio: number }) {
  const c = usePalette();
  const ds = huyHieuCuaNguoi(so);
  const doDuoc = ds.filter((h) => h.trangThai !== "chua-do-duoc");
  const chuaDo = ds.filter((h) => h.trangThai === "chua-do-duoc");
  return (
    <>
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Đo được từ sổ ({doDuoc.length})</Text>
        {doDuoc.map((h) => (
          <DongThanhTich
            key={h.id}
            ten={h.ten}
            than={h.dieuKien}
            phai={h.trangThai === "mo" ? "đã mở" : phanSo(h.daDat ?? 0, h.can ?? 1)}
            manh={h.trangThai === "mo"}
          />
        ))}
      </Card>
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Chưa đo được ({chuaDo.length})</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Bốn huy hiệu này là phần vỏ. Sản phẩm chưa có bảng nào đếm được điều kiện của
          chúng, nên chúng không mở ra được dù bạn làm gì.
        </Text>
        {chuaDo.map((h) => (
          <DongThanhTich key={h.id} ten={h.ten} than={`${h.dieuKien}. Thiếu: ${h.thieuGi}.`} phai="chưa đo" />
        ))}
      </Card>
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Thử thách tuần này</Text>
        {thuThachTuan(so, bayGio).map((t) => (
          <DongThanhTich
            key={t.id}
            ten={t.ten}
            than="Đếm trong 7 ngày gần nhất."
            phai={phanSo(t.daDat, t.can)}
            manh={t.xong}
          />
        ))}
      </Card>
    </>
  );
}

function DongThanhTich({
  ten,
  than,
  phai,
  manh,
}: {
  ten: string;
  than: string;
  phai: string;
  manh?: boolean;
}) {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-start", gap: space.sm }}>
      <View style={{ flex: 1, minWidth: 0, gap: 1 }}>
        <Text style={{ ...type.body, color: c.ink }}>{ten}</Text>
        <Text style={{ ...type.micro, color: c.inkSoft }}>{than}</Text>
      </View>
      <Text
        style={{
          ...type.label,
          fontWeight: "600",
          flexShrink: 0,
          color: manh ? c.split : c.inkFaint,
        }}
      >
        {phai}
      </Text>
    </View>
  );
}
