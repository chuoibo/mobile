/** Khám phá — the tab the app opens on, and the first place anyone sees AI.
 *
 * Mockup: `product/features/02-kham-pha-va-goi-y-dia-diem.png`, screen 1.
 *
 * Everything on this screen comes from `GET /places` (work item rd-be-05,
 * lane backend). Nothing is bundled. When that route is missing the screen
 * says which address it tried and which work item owns it, rather than
 * quietly filling in -- see the header of `places.ts` for why that rule is
 * worth the empty tab it sometimes produces.
 *
 * ## Deliberate differences from the mockup, and why
 *
 * | Mockup | Here | Why |
 * |---|---|---|
 * | Photo per card | Drawn mark on a token ramp | No place imagery in Git; see `AnhDiaDiem.tsx` |
 * | Search box with placeholder only | Labelled field | The kit's own rule: a placeholder vanishes the moment you type |
 * | Avatar top-right | Not drawn | The Cá nhân tab is one tap away and already owns that |
 * | Real map strip | Relative-position strip, labelled | The coordinates are real; the basemap is not, and it says so |
 *
 * ## Lead tone
 *
 * `accent` orange, same as the shell. `ai` purple appears only on the match
 * badge and the reason card, which is the palette's stated meaning for it.
 * DESIGN.md: một màn hình chỉ có MỘT tông dẫn.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Card, Choice, Field, Screen } from "../../ui/Kit";
import { AnhDiaDiem, Ruy, RuyDongCua } from "./AnhDiaDiem";
import { HuyHieuMatch } from "./NhanAi";
import { ChiTietDiaDiem } from "./ChiTietDiaDiem";
import type { NguoiDung } from "../../navigation/nhom-demo";
import type { Nhom as NhomWire } from "../vao-cua/cong-api";
import { DaiBanDo } from "./DaiBanDo";
import {
  PLACES_BASE_URL,
  byMatchThenRating,
  fetchPlaces,
  formatDistance,
  formatKinds,
  formatPricePerPerson,
  formatRating,
  locNoiBo,
  type Category,
  type Place,
  type PlacesState,
} from "./places";

const TAT_CA = "tat-ca";

export function KhamPha({ nguoi, nhom, diaDiemDau }: {
  /** Who the app is acting as, passed down to the check-in card. Optional so
   *  the screen still renders for any caller that does not care -- including
   *  the detector runs, which load it cold. */
  nguoi?: NguoiDung | null;
  /** The group a check-in would belong to. `VoTab` holds it. */
  nhom?: NhomWire | null;
  /** F46. A place id from the opening link, opened as a detail card as soon as
   *  the list it names has arrived. Null opens the list, and so does an id no
   *  loaded place matches. */
  diaDiemDau?: string | null;
} = {}) {
  const c = usePalette();
  const [state, setState] = useState<PlacesState>({ kind: "dang-tai" });
  const [danhMuc, setDanhMuc] = useState<string>(TAT_CA);
  const [tim, setTim] = useState("");
  const [dangXem, setDangXem] = useState<Place | null>(null);

  const tai = useCallback((cat: string) => {
    let huy = false;
    setState({ kind: "dang-tai" });
    fetchPlaces({ category: cat === TAT_CA ? null : cat }).then((s) => {
      if (!huy) setState(s);
    });
    return () => {
      huy = true;
    };
  }, []);

  useEffect(() => tai(danhMuc), [tai, danhMuc]);

  const places = state.kind === "co-du-lieu" ? state.places : [];

  // The link's place, opened once and only once.
  //
  // `daMoTuLink` is what stops this from being a cage: without it, pressing
  // back out of the card would re-satisfy the condition on the next render and
  // reopen it, and the list would be unreachable for as long as the fragment
  // stayed in the address bar.
  const [daMoTuLink, setDaMoTuLink] = useState(false);
  useEffect(() => {
    if (daMoTuLink || !diaDiemDau || places.length === 0) return;
    setDaMoTuLink(true);
    const thay = places.find((p) => p.id === diaDiemDau);
    // An unknown id leaves the list up. It is a link to a place this build
    // cannot show -- a stale share, or another environment's catalogue -- and
    // an empty card would say "this place has nothing" instead of the truth.
    if (thay) setDangXem(thay);
  }, [daMoTuLink, diaDiemDau, places]);
  const categories: Category[] = state.kind === "co-du-lieu" ? state.categories : [];

  // Text filters what is already on screen; the category goes back to the
  // server. Two mechanisms, on purpose: the category is part of the query the
  // server scored against, and re-scoring is the server's job. Filtering by
  // mood in natural language is screen 2 of the mockup and is not built.
  const hienThi = useMemo(
    () => locNoiBo(places, tim).slice().sort(byMatchThenRating),
    [places, tim],
  );

  if (dangXem) {
    return (
      <ChiTietDiaDiem
        place={dangXem}
        nguoi={nguoi ?? null}
        nhom={nhom ?? null}
        onQuayLai={() => setDangXem(null)}
      />
    );
  }

  return (
    <Screen title="Khám phá ✦" hint="AI chấm theo ngân sách, sở thích và khoảng cách của nhóm">
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }}
      >
        <Field
          label="Tìm địa điểm"
          value={tim}
          onChangeText={setTim}
          placeholder="Tên quán, món ăn, hoạt động…"
        />

        {categories.length > 0 ? (
          <Choice
            label="Danh mục"
            value={danhMuc}
            onChange={setDanhMuc}
            options={[{ id: TAT_CA, label: "Tất cả" }, ...categories.map((k) => ({ id: k.id, label: k.label }))]}
          />
        ) : null}

        {state.kind === "dang-tai" ? <DangTai /> : null}
        {state.kind !== "dang-tai" && state.kind !== "co-du-lieu" ? <ChuaCoDuLieu state={state} /> : null}

        {state.kind === "co-du-lieu" ? (
          <>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
              <Text style={{ ...type.title, color: c.ink }}>Gợi ý cho bạn</Text>
              <Text style={{ ...type.label, color: c.inkSoft }}>
                {hienThi.length}/{places.length} chỗ
              </Text>
            </View>

            {hienThi.length === 0 ? (
              <Card>
                <Text style={{ ...type.body, color: c.ink }}>Không có chỗ nào khớp “{tim}”.</Text>
                <Text style={{ ...type.label, color: c.inkSoft }}>
                  Thử bỏ bớt chữ, hoặc đổi danh mục ở trên.
                </Text>
              </Card>
            ) : (
              <LuoiHaiCot places={hienThi} onChon={setDangXem} />
            )}

            <DaiBanDo places={hienThi} />
          </>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

function DangTai() {
  const c = usePalette();
  return (
    <Card>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <ActivityIndicator color={c.accent} />
        <Text style={{ ...type.body, color: c.inkSoft }}>Đang hỏi máy chủ chỗ nào hợp với nhóm…</Text>
      </View>
    </Card>
  );
}

/**
 * The four ways this screen can have nothing to show, each said differently.
 *
 * "Máy chủ không mở" and "máy chủ mở nhưng chưa có route này" send a person to
 * two different places. Collapsing them into one "Lỗi" is how an afternoon
 * gets spent restarting a server that was fine the whole time -- so the
 * address, the status, and the work item that owns the gap are all on screen.
 */
function ChuaCoDuLieu({ state }: { state: PlacesState }) {
  const c = usePalette();
  let tieuDe = "Chưa có dữ liệu địa điểm";
  let than = "";
  let diaChi = "";

  if (state.kind === "chua-co-endpoint") {
    tieuDe = "Máy chủ này chưa có danh mục địa điểm";
    than = `Máy chủ đang chạy nhưng không có route GET /places. Route đó có trong ${state.work}, nên nhiều khả năng app đang trỏ vào một bản API cũ hơn — không phải app thiếu gì.`;
    diaChi = state.url;
  } else if (state.kind === "khong-noi-duoc") {
    tieuDe = "Không mở được máy chủ";
    than = `Không kết nối được tới API. Chi tiết: ${state.detail}`;
    diaChi = state.url;
  } else if (state.kind === "may-chu-loi") {
    tieuDe = `Máy chủ trả lỗi ${state.status}`;
    than = state.detail;
    diaChi = state.url;
  } else if (state.kind === "du-lieu-sai") {
    tieuDe = "Dữ liệu địa điểm không đúng dạng";
    than = `App từ chối hiển thị thay vì vẽ ra số sai. Chi tiết: ${state.detail}`;
    diaChi = state.url;
  }

  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
      <Text style={{ ...type.body, color: c.inkSoft }}>{than}</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>Đã thử: {diaChi}</Text>
      {/* The env var's name is deliberately NOT spelled out here. The gate in
          `tests/base-url.test.mjs` greps the built bundle for that token to
          prove Expo substituted the read rather than leaving it to resolve on
          a device -- and it is a blunt substring check, as a gate guarding
          something that silently falls back to localhost should be. Printing
          the name in copy would put the token in the bundle and cost the gate
          its meaning. The address below is the part a person can act on. */}
      <Text style={{ ...type.micro, color: c.inkFaint }}>
        API app đang trỏ tới: {PLACES_BASE_URL} — đổi trong .env rồi mở lại app.
      </Text>
    </Card>
  );
}

/**
 * Two columns, built explicitly rather than by wrapping.
 *
 * `flexWrap` with percentage widths gives a different result on web and on
 * native the moment a gap is involved, and the mockup's grid is staggered
 * anyway -- cards are not the same height. Two `flex: 1` columns filled
 * alternately give exact gutters on both platforms and stagger for free.
 */
function LuoiHaiCot({ places, onChon }: { places: Place[]; onChon: (p: Place) => void }) {
  const trai = places.filter((_, i) => i % 2 === 0);
  const phai = places.filter((_, i) => i % 2 === 1);
  return (
    <View style={{ flexDirection: "row", gap: space.sm }}>
      <View style={{ flex: 1, gap: space.sm }}>
        {trai.map((p) => <TheDiaDiem key={p.id} place={p} onChon={onChon} />)}
      </View>
      <View style={{ flex: 1, gap: space.sm }}>
        {phai.map((p) => <TheDiaDiem key={p.id} place={p} onChon={onChon} />)}
      </View>
    </View>
  );
}

/**
 * One place card: image block with the badge over it, then the facts.
 *
 * The name sits *under* the image rather than over it, unlike the mockup. Over
 * the scrim it would be white on a ramp, and `tokens.json` bans small text on
 * the brand layer outright -- the mockup's own photo is dark enough to carry
 * it and a drawn ramp is not. The badge can live up there because it brings
 * its own measured ground.
 */
function TheDiaDiem({ place, onChon }: { place: Place; onChon: (p: Place) => void }) {
  const c = usePalette();
  return (
    <Pressable
      onPress={() => onChon(place)}
      accessibilityRole="button"
      accessibilityLabel={
        `${place.name}, ${formatKinds(place.kinds)}, ${formatDistance(place.distanceKm)}` +
        // Said aloud, not just coloured. The ribbon is the sighted half of this
        // signal; without it here a screen reader user gets a card that reads
        // like every other card and only finds the shut door on the detail page.
        (place.openNow ? "" : ", đang đóng cửa")
      }
      style={({ pressed }) => ({
        backgroundColor: c.card,
        borderColor: c.line,
        borderWidth: 1,
        borderRadius: radius.base,
        overflow: "hidden",
        opacity: pressed ? 0.9 : 1,
      })}
    >
      <AnhDiaDiem category={place.category} height={124} rounded={0}>
        <View style={{ flex: 1, padding: space.xs, justifyContent: "space-between" }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
            <HuyHieuMatch match={place.match} />
            {/* A shut door outranks "HOT" as news. One ribbon slot, and when
                the two compete the closed state wins it. */}
            {place.openNow ? (
              place.flag ? <Ruy flag={place.flag} /> : null
            ) : (
              <RuyDongCua />
            )}
          </View>
        </View>
      </AnhDiaDiem>

      <View style={{ padding: space.sm, gap: 2 }}>
        <Text numberOfLines={1} style={{ ...type.body, fontWeight: "700", color: c.ink }}>
          {place.name}
        </Text>
        <Text numberOfLines={1} style={{ ...type.micro, color: c.inkFaint }}>
          {formatKinds(place.kinds)}
        </Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs, marginTop: 2 }}>
          <Text style={{ ...type.micro, color: c.accent }}>★</Text>
          <Text style={{ ...type.micro, color: c.inkSoft }}>
            {formatRating(place.rating, place.ratingCount)}
          </Text>
          <Text style={{ ...type.micro, color: c.inkFaint }}>·</Text>
          <Text style={{ ...type.micro, color: c.inkSoft }}>{formatDistance(place.distanceKm)}</Text>
        </View>
        <Text style={{ ...type.micro, color: c.split, marginTop: 2 }}>
          {formatPricePerPerson(place.priceMinVnd, place.priceMaxVnd)}
        </Text>
      </View>
    </Pressable>
  );
}
