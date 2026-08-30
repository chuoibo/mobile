/** Bản đồ nhóm — F43 (social map) and F44 (group heatmap), one screen.
 *
 * Two routes, one surface, because they are the same question asked at two
 * resolutions: *which places* does this group keep going back to, and *which
 * districts*. Splitting them across two tabs would make a reader compare two
 * screens to notice that the district totals are the place totals added up.
 *
 * ## Why a list and not a scatter of dots
 *
 * `DaiBanDo` already draws the catalogue as relative-position pins, and its
 * header explains at length why the dots cannot be individually named: the
 * seed catalogue is two cities 200 km apart, so eight of twelve pins land
 * within a pixel or two of each other. Everything in that argument applies
 * harder here, because these pins carry *counts* -- the information really is
 * "Cà phê Vườn, 6 lần", and a mark a pointer cannot separately hit is a bad
 * way to say a number. So the layers are lists, the counts are text, and the
 * strip stays what it is: one diagram, named once, above them.
 *
 * ## The disclosure sentence is above the list, not under it
 *
 * `scanned_checkins` / `truncated` bound how much history produced the counts.
 * Printed underneath, a caveat is read after the reader has already believed
 * the list. Printed above, it is part of the claim. The heatmap carries a
 * second one for the check-ins that fell outside every district the product
 * knows -- silence there would present a fraction as the whole.
 *
 * ## The fourth layer is named, not drawn empty
 *
 * The server declares `saved` in `unavailable` instead of sending `[]`. An
 * empty list renders as "bạn chưa lưu chỗ nào", which is a claim about the
 * group; the truth is "chưa có chỗ để lưu", which is a claim about the
 * product. This screen keeps that distinction visible rather than flattening
 * it back out at the last step.
 *
 * ## Lead tone
 *
 * `accent` orange, same as Khám phá, which is the surface this extends. No
 * teal (money being split) and no purple (something a model produced): every
 * number here is a count of rows the group itself created.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card } from "../../ui/Kit";
import { themChiTiet, thanLoiMayChu } from "../../ui/loi-may-chu";
import type { NguoiDung } from "../../navigation/nhom-demo";
import { PLACES_BASE_URL } from "./places";
import {
  cauDaQuet,
  cauKhongRoKhu,
  fetchBanDoNhom,
  fetchNhietDo,
  soLan,
  type BanDoState,
  type ChoDaDi,
  type ChoTrenBanDo,
  type KhuNhietDo,
  type NhietDoState,
} from "./ban-do-nhom";
import { DiemHen } from "./DiemHen";

/** Minimum tap target. WCAG 2.5.8 asks 24, the platform guidance asks 44, and
 *  every other pressable in this app already uses 44. */
const CHAM = 44;

/**
 * Every way these screens can have nothing to show, each said differently.
 *
 * The important row is the first one. 403 on these three routes means the
 * reader is not in this group any more -- it is not a failure, so it gets a
 * sentence about membership and no status number, no address, and no retry
 * button. Telling somebody "lỗi 403" for a thing that is working exactly as
 * designed sends them to restart something that was never broken.
 */
export function KhongCoBanDo({
  state,
  onThuLai,
}: {
  state: Exclude<BanDoState | NhietDoState, { kind: "dang-tai" } | { kind: "co-du-lieu" } | { kind: "chua-hoi" }>;
  onThuLai?: () => void;
}) {
  const c = usePalette();

  if (state.kind === "khong-con-trong-nhom") {
    return (
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Bạn không còn trong nhóm này</Text>
        <Text style={{ ...type.body, color: c.inkSoft }}>
          Bản đồ và lịch sử của một nhóm chỉ người trong nhóm xem được. Nếu bạn nghĩ mình vẫn
          ở trong nhóm, nhờ một người trong đó mời lại giúp.
        </Text>
      </Card>
    );
  }

  let tieuDe = "Chưa có bản đồ nhóm";
  let than = "";
  let diaChi = "";

  if (state.kind === "chua-co-endpoint") {
    tieuDe = "Máy chủ này chưa có bản đồ nhóm";
    than = `Máy chủ đang chạy nhưng không có route này. Route đó có trong ${state.work}, nên nhiều khả năng app đang trỏ vào một bản API cũ hơn, không phải app thiếu gì.`;
    diaChi = state.url;
  } else if (state.kind === "khong-noi-duoc") {
    tieuDe = "Không mở được máy chủ";
    than = themChiTiet("Không kết nối được tới API.", state.detail);
    diaChi = state.url;
  } else if (state.kind === "may-chu-loi") {
    tieuDe = `Máy chủ trả lỗi ${state.status}`;
    than = thanLoiMayChu(state.status, state.detail);
    diaChi = state.url;
  } else {
    tieuDe = "Dữ liệu bản đồ không đúng dạng";
    than = themChiTiet("App từ chối hiển thị thay vì vẽ ra số sai.", state.detail);
    diaChi = state.url;
  }

  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
      <Text style={{ ...type.body, color: c.inkSoft }}>{than}</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>Đã thử: {diaChi}</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        API app đang trỏ tới: {PLACES_BASE_URL}. Đổi trong .env rồi mở lại app.
      </Text>
      {onThuLai ? <Button label="Thử lại" onPress={onThuLai} tone="ghost" /> : null}
    </Card>
  );
}

/** A section heading plus its disclosure line, in that order. */
function TieuDeMuc({ chu, phu }: { chu: string; phu?: string | null }) {
  const c = usePalette();
  return (
    <View style={{ gap: 2 }}>
      <Text style={{ ...type.title, color: c.ink }}>{chu}</Text>
      {phu ? <Text style={{ ...type.micro, color: c.inkSoft }}>{phu}</Text> : null}
    </View>
  );
}

/** One place the group has been, with its count.
 *
 * The count sits in its own column at a fixed width so the numbers line up
 * down the list and can be compared without reading each name first. Tabular
 * figures come from `type.amountSmall`. */
function HangDaDi({ cho }: { cho: ChoDaDi }) {
  const c = usePalette();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        gap: space.sm,
        minHeight: CHAM,
      }}
    >
      <Text style={{ ...type.body, color: c.ink, flex: 1 }} numberOfLines={2}>
        {cho.placeName}
      </Text>
      <Text style={{ ...type.amountSmall, color: c.accent }}>{soLan(cho.visitCount)}</Text>
    </View>
  );
}

/** A place with a rating and no visit: trending and recommended both use it. */
function HangCho({ cho }: { cho: ChoTrenBanDo }) {
  const c = usePalette();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        gap: space.sm,
        minHeight: CHAM,
      }}
    >
      <Text style={{ ...type.body, color: c.ink, flex: 1 }} numberOfLines={2}>
        {cho.placeName}
      </Text>
      <Text style={{ ...type.micro, color: c.inkSoft }}>
        {cho.rating.toFixed(1)} ({cho.ratingCount})
      </Text>
    </View>
  );
}

/**
 * One district, as a count and as a bar.
 *
 * The count is the reading; the bar only echoes it. That ordering is not a
 * style preference, it is what the gate in `tests/receipt.test.mjs` decided:
 * ADR-0009 refused machine-derived percentages on screen, and the check is an
 * exact allow-list with an instruction attached -- open an ADR before adding
 * to it, do not widen the gate. `share_percent` therefore reaches the reader
 * only as the *width* of the bar (a CSS length, which that gate separates from
 * a percentage told to a person), and never as text.
 *
 * Nothing is lost by it. "6 lần" is the absolute fact and is already text, so
 * the row does not depend on comparing two lengths or on seeing colour; the
 * share is the derived number, and it was the derived number ADR-0009 was
 * about. The width still comes straight from the integer the server sent --
 * the app never recomputes a share, because two places computing one ratio is
 * how two screens end up disagreeing.
 */
function ThanhKhu({ khu }: { khu: KhuNhietDo }) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs, minHeight: CHAM, justifyContent: "center" }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
        <Text style={{ ...type.body, color: c.ink, flex: 1 }} numberOfLines={1}>
          {khu.label}
        </Text>
        <Text style={{ ...type.amountSmall, color: c.ink }}>{soLan(khu.visitCount)}</Text>
      </View>
      <View
        style={{
          height: 8,
          borderRadius: radius.pill,
          backgroundColor: c.accentSoft,
          overflow: "hidden",
        }}
      >
        <View
          style={{
            width: `${khu.sharePercent}%`,
            height: "100%",
            backgroundColor: c.accent,
            borderRadius: radius.pill,
          }}
        />
      </View>
    </View>
  );
}

/**
 * The group map screen.
 *
 * Loads both routes on mount. They are independent: the heatmap failing does
 * not blank the layers, because a reader who can see where the group has been
 * is better served than one who sees a single error card covering both.
 */
export function BanDoNhom({
  nguoi,
  contextId,
  onQuayLai,
  fetchImpl,
}: {
  /** Who the app is acting as. All three routes are gated on membership, so
   *  without this there is nobody to check and the answer is 403. */
  nguoi: NguoiDung;
  contextId?: string;
  onQuayLai: () => void;
  /** Injected by the tests. Production passes nothing and gets `fetch`. */
  fetchImpl?: typeof fetch;
}) {
  const c = usePalette();
  const [banDo, setBanDo] = useState<BanDoState>({ kind: "dang-tai" });
  const [nhietDo, setNhietDo] = useState<NhietDoState>({ kind: "dang-tai" });
  const [moDiemHen, setMoDiemHen] = useState(false);

  const tai = useCallback(() => {
    const opts = { personId: nguoi.personId, contextId, fetchImpl };
    setBanDo({ kind: "dang-tai" });
    setNhietDo({ kind: "dang-tai" });
    void fetchBanDoNhom(opts).then(setBanDo);
    void fetchNhietDo(opts).then(setNhietDo);
  }, [nguoi.personId, contextId, fetchImpl]);

  useEffect(() => {
    tai();
  }, [tai]);

  if (moDiemHen) {
    return (
      <DiemHen
        nguoi={nguoi}
        contextId={contextId}
        fetchImpl={fetchImpl}
        onQuayLai={() => setMoDiemHen(false)}
      />
    );
  }

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
            accessibilityLabel="Quay lại Khám phá"
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
          <Text style={{ ...type.h1, color: c.ink, flex: 1 }}>Bản đồ nhóm</Text>
        </View>

        <Text style={{ ...type.body, color: c.inkSoft }}>
          Nhóm này hay lui tới đâu, tính từ chính những lần cả nhóm check-in. Không có ai đi
          với ai và không có lúc nào: chỉ có chỗ và số lần.
        </Text>

        {banDo.kind === "dang-tai" ? (
          <Card>
            <ActivityIndicator color={c.accent} />
            <Text style={{ ...type.micro, color: c.inkSoft }}>Đang đọc lịch sử của nhóm…</Text>
          </Card>
        ) : banDo.kind !== "co-du-lieu" ? (
          <KhongCoBanDo state={banDo} onThuLai={tai} />
        ) : (
          <>
            <Card>
              <TieuDeMuc chu="Đã đi" phu={cauDaQuet(banDo.data.daQuet, banDo.data.batHet)} />
              {banDo.data.daDi.length === 0 ? (
                <Text style={{ ...type.body, color: c.inkSoft }}>
                  Chưa có lần check-in nào để đếm. Lần đầu cả nhóm check-in ở đâu đó, chỗ đó
                  hiện ở đây.
                </Text>
              ) : (
                banDo.data.daDi.map((cho) => <HangDaDi key={cho.placeId} cho={cho} />)
              )}
            </Card>

            {banDo.data.dangHot.length > 0 ? (
              <Card>
                <TieuDeMuc
                  chu="Đang hot"
                  phu="Xếp theo điểm đánh giá của cả nền tảng, không phải theo nhóm bạn."
                />
                {banDo.data.dangHot.map((cho) => <HangCho key={cho.placeId} cho={cho} />)}
              </Card>
            ) : null}

            {banDo.data.nenThu.length > 0 ? (
              <Card>
                <TieuDeMuc chu="Nên thử" phu="Những chỗ nhóm chưa từng tới." />
                {banDo.data.nenThu.map((cho) => <HangCho key={cho.placeId} cho={cho} />)}
              </Card>
            ) : null}

            {/* Named, not drawn empty. See the header. */}
            {banDo.data.chuaCo.map((lop) => (
              <Card key={lop.layer}>
                <Text style={{ ...type.title, color: c.inkSoft }}>
                  Lớp &quot;{lop.layer}&quot; chưa có
                </Text>
                <Text style={{ ...type.body, color: c.inkSoft }}>{lop.reason}</Text>
              </Card>
            ))}
          </>
        )}

        {nhietDo.kind === "dang-tai" ? null : nhietDo.kind !== "co-du-lieu" ? (
          <KhongCoBanDo state={nhietDo} onThuLai={tai} />
        ) : nhietDo.data.khu.length > 0 ? (
          <Card>
            <TieuDeMuc
              chu="Nhóm hay tụ ở đâu"
              phu={cauDaQuet(nhietDo.data.daQuet, nhietDo.data.batHet)}
            />
            {nhietDo.data.khu.map((khu) => <ThanhKhu key={khu.id} khu={khu} />)}
            {cauKhongRoKhu(nhietDo.data.khongRoKhu) ? (
              <Text style={{ ...type.micro, color: c.inkSoft }}>
                {cauKhongRoKhu(nhietDo.data.khongRoKhu)}
              </Text>
            ) : null}
          </Card>
        ) : null}

        <Card>
          <TieuDeMuc
            chu="Hẹn nhau ở đâu cho tiện"
            phu="Chọn khu vực từng người xuất phát, máy tính chỗ gặp cân bằng nhất."
          />
          <Button label="Tìm điểm hẹn" onPress={() => setMoDiemHen(true)} />
        </Card>
      </ScrollView>
    </View>
  );
}
