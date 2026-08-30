/** Khám phá — the tab the app opens on, and the first place anyone sees AI.
 *
 * Mockup: `product/features/02-kham-pha-va-goi-y-dia-diem.png`, screen 1.
 *
 * Everything on this screen comes from the server. The catalogue is
 * `GET /places` (work item rd-be-05); the search box is `POST /places/search`
 * (rd-be-10), wired here by rd-fe-15. Nothing is bundled. When either route is
 * missing the screen says which address it tried and which work item owns it,
 * rather than quietly filling in -- see the header of `places.ts` for why that
 * rule is worth the empty tab it sometimes produces.
 *
 * ## The box asks a question; it does not filter
 *
 * It used to substring-match the loaded list, which `places.ts` called a stand
 * -in for the language problem the mockup's screen 2 actually poses. That
 * problem now has a real answer, so the stand-in is gone rather than sitting
 * beside it: one box that filtered while you typed *and* asked a model when you
 * pressed Enter would be two different meanings wearing one control, and the
 * "AI hiểu câu của bạn" panel would blink in and out with no rule a person
 * could learn. Typing composes a question, "Tìm bằng AI" asks it, and "Xoá tìm
 * kiếm" goes back to the catalogue.
 *
 * ## Deliberate differences from the mockup, and why
 *
 * | Mockup | Here | Why |
 * |---|---|---|
 * | Photo per card | Real `Anh` frame; drawn mark as stand-in | The frame is sized now, and `GET /places` sends no `photo_url` at all today -- only `photo_count`. The frame fills the day the field exists. See `AnhDiaDiem.tsx` |
 * | Name and rating over the photo | Under it | Over a drawn ramp that is white text on a gradient, and `tokens.json` bans small text on the brand layer. The mockup's photo is dark enough to carry it; a stand-in is not |
 * | Search box with placeholder only | Labelled field | The kit's own rule: a placeholder vanishes the moment you type |
 * | Chips immediately under the search box | Under the search box *and* its button | Splitting a field from its own submit to slot the filter between them separates a control from its action. The chips are still the first thing below the search unit |
 * | Avatar top-right | Not drawn | The Cá nhân tab is one tap away and already owns that |
 * | Real map strip | Relative-position strip, labelled | The coordinates are real; the basemap is not, and it says so |
 *
 * ## The grid is cut at four, and that is what makes "Xem tất cả" honest
 *
 * The mockup draws a 2x2 with a link beside the heading. Both halves of that
 * only work together: a link over an already-complete list does nothing, and a
 * grid of twelve pushes the map off the fold. `SO_THE_MAC_DINH` is the cut, the
 * link reveals the rest, and when a category holds four or fewer the link is
 * not drawn at all rather than drawn dead.
 *
 * ## Lead tone
 *
 * `accent` orange, same as the shell. `ai` purple appears only on the match
 * badge and the reason card, which is the palette's stated meaning for it.
 * DESIGN.md: một màn hình chỉ có MỘT tông dẫn.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Field, Screen } from "../../ui/Kit";
import { themChiTiet, thanLoiMayChu } from "../../ui/loi-may-chu";
import { AnhDiaDiem, Ruy, RuyDongCua } from "./AnhDiaDiem";
import { HangDanhMuc } from "./HangDanhMuc";
import { HuyHieuMatch } from "./NhanAi";
import { CauAiHieu, KhongCoKetQua, TimKhongDuoc } from "./CauAiHieu";
import { ChiTietDiaDiem } from "./ChiTietDiaDiem";
import type { NguoiDung } from "../../navigation/nhom-demo";
import type { Nhom as NhomWire } from "../vao-cua/cong-api";
import { DaiBanDo } from "./DaiBanDo";
import { BanDoNhom } from "./BanDoNhom";
import { MAX_QUERY_CHARS, askSearch, type TimKiemState } from "./tim-kiem";
import {
  PLACES_BASE_URL,
  byMatchThenRating,
  fetchPlaces,
  formatDistance,
  formatKinds,
  formatPricePerPerson,
  formatRating,
  type Category,
  type Place,
  type PlacesState,
} from "./places";

const TAT_CA = "tat-ca";

/** How many cards the grid shows before "Xem tất cả".
 *
 * Four, because the mockup draws a 2x2 and two columns times two rows is what
 * fits above the map strip on a 390pt phone without the map falling off the
 * fold entirely. The catalogue is twelve rows today, so this is a real cut and
 * the link below is a real action, not a decoration sized to never trigger. */
const SO_THE_MAC_DINH = 4;

export function KhamPha({ nguoi, nhom, diaDiemDau, moBanDoNgay, moDiemHenNgay }: {
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
  /** rd-fe-33. Open the group map as soon as the screen mounts, from
   *  `#ban-do=1`. Unlike `diaDiemDau` this waits for nothing: the map fetches
   *  its own three routes and does not need the catalogue to have arrived. */
  moBanDoNgay?: boolean;
  /** rd-fe-33. Open Điểm hẹn straight away, from `#ban-do=hen`. */
  moDiemHenNgay?: boolean;
} = {}) {
  const c = usePalette();
  const [state, setState] = useState<PlacesState>({ kind: "dang-tai" });
  const [danhMuc, setDanhMuc] = useState<string>(TAT_CA);
  const [cau, setCau] = useState("");
  const [tim, setTim] = useState<TimKiemState>({ kind: "chua-tim" });
  const [dangXem, setDangXem] = useState<Place | null>(null);
  // The group map (rd-fe-33). A full-screen sibling of the detail view rather
  // than a fifth tab: it answers a question about the places on *this* tab.
  const [moBanDo, setMoBanDo] = useState((moBanDoNgay ?? false) || (moDiemHenNgay ?? false));
  // Whether the grid is showing everything or just the first `SO_THE_MAC_DINH`.
  // Reset on every category change below, because "Xem tất cả" was a statement
  // about the list the person was looking at, not a standing preference.
  const [moRong, setMoRong] = useState(false);
  // Only the newest search may write state. Two taps on "Tìm" race, and the
  // slower reply landing second would overwrite the newer answer with an older
  // one -- results for a sentence the person has already replaced.
  const luot = useRef(0);

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

  // A new category is a new list. Carrying the expanded state across would open
  // the next category fully unrolled with a "Thu gọn" nobody pressed.
  useEffect(() => setMoRong(false), [danhMuc]);

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

  const timNgay = useCallback(() => {
    const q = cau.trim();
    if (!q) return;
    const cua = ++luot.current;
    setTim({ kind: "dang-tim", query: q });
    // The sentence, and only the sentence. No category, no group profile, no
    // template glued around it: this text reaches a model prompt, and every
    // string the client concatenated onto it would be a second place an
    // injected instruction could ride in that the server cannot see.
    //
    // The one thing that does ride along is who is asking. `POST /places/search`
    // spends model quota and is metered per actor (rd-be-13), so a search with
    // nobody signed in is a 401 -- `askSearch` says so without the round trip.
    askSearch(q, { actorId: nguoi?.personId }).then((s) => {
      if (luot.current === cua) setTim(s);
    });
  }, [cau, nguoi]);

  const xoaTim = useCallback(() => {
    luot.current += 1; // any reply still in flight is now stale
    setCau("");
    setTim({ kind: "chua-tim" });
  }, []);

  // The category filters the catalogue, and the catalogue is what the server
  // scored -- so re-scoring stays the server's job. Free text no longer filters
  // locally: it is a language question now, and `POST /places/search` answers
  // it for real. A substring stand-in beside the real thing would be two
  // different meanings for one box.
  const hienThi = useMemo(() => places.slice().sort(byMatchThenRating), [places]);

  // Gated on `nguoi`, and the button below is too. All three group-map routes
  // are member-gated, so opening this screen without an actor would produce a
  // 403 that says "bạn không còn trong nhóm này" to somebody who never
  // identified themselves in the first place -- true of the request, and
  // misleading about why.
  if (moBanDo && nguoi) {
    return (
      <BanDoNhom
        nguoi={nguoi}
        moDiemHenNgay={moDiemHenNgay ?? false}
        onQuayLai={() => setMoBanDo(false)}
      />
    );
  }

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

  const dangTim = tim.kind !== "chua-tim";

  return (
    <Screen title="Khám phá ✦" hint="AI chấm theo ngân sách, sở thích và khoảng cách của nhóm">
      <ScrollView
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }}
      >
        <Field
          label="Tìm bằng lời"
          value={cau}
          onChangeText={setCau}
          onSubmitEditing={timNgay}
          maxLength={MAX_QUERY_CHARS}
          placeholder="Quán nướng ngoài trời cho 6 người dưới 300k"
          hint="Cứ nói như nói với bạn bè. AI đọc cả câu, kể cả tiền và số người."
        />
        <View style={{ flexDirection: "row", gap: space.sm }}>
          <View style={{ flex: 1 }}>
            <Button
              label={tim.kind === "dang-tim" ? "Đang hỏi AI…" : "Tìm bằng AI"}
              onPress={timNgay}
              disabled={cau.trim() === "" || tim.kind === "dang-tim"}
            />
          </View>
          {dangTim ? (
            <View style={{ flex: 1 }}>
              <Button label="Xoá tìm kiếm" tone="quiet" onPress={xoaTim} />
            </View>
          ) : null}
        </View>

        {dangTim ? (
          <KetQuaTim state={tim} categories={categories} onChon={setDangXem} />
        ) : (
          <>
            <HangDanhMuc
              value={danhMuc}
              onChange={setDanhMuc}
              options={[{ id: TAT_CA, label: "Tất cả" }, ...categories.map((k) => ({ id: k.id, label: k.label }))]}
            />

            {state.kind === "dang-tai" ? <DangTai /> : null}
            {state.kind !== "dang-tai" && state.kind !== "co-du-lieu" ? <ChuaCoDuLieu state={state} /> : null}

            {state.kind === "co-du-lieu" ? (
              <>
                <TieuDeMuc
                  title="Gợi ý cho bạn"
                  // The link only exists when it has somewhere to go. With four
                  // or fewer places the grid already shows everything, and a
                  // "Xem tất cả" that reveals nothing is the kind of decoration
                  // that teaches people to stop trusting the other controls.
                  action={
                    hienThi.length > SO_THE_MAC_DINH
                      ? {
                          label: moRong ? "Thu gọn" : `Xem tất cả (${hienThi.length})`,
                          onPress: () => setMoRong((v) => !v),
                        }
                      : null
                  }
                />

                {hienThi.length === 0 ? (
                  <Card>
                    <Text style={{ ...type.body, color: c.ink }}>Chưa có chỗ nào trong danh mục này.</Text>
                    <Text style={{ ...type.label, color: c.inkSoft }}>
                      Thử đổi danh mục ở trên, hoặc tả chỗ bạn muốn đi vào ô tìm bằng lời.
                    </Text>
                  </Card>
                ) : (
                  <LuoiHaiCot
                    places={moRong ? hienThi : hienThi.slice(0, SO_THE_MAC_DINH)}
                    onChon={setDangXem}
                  />
                )}

                {/* The map keeps every place, collapsed grid or not. It is the
                    "where are these" answer, and answering it about four of
                    twelve pins would be a different and worse answer. */}
                <DaiBanDo places={hienThi} />

                {/* The strip above draws the catalogue; this opens the same
                    geography asked about *this group*. Kept as its own labelled
                    button rather than by making the strip pressable: the strip
                    is documented as one diagram with one name, and hanging a
                    navigation action on it would give that name two meanings. */}
                {nguoi ? (
                  <Button
                    label="Xem bản đồ của nhóm"
                    tone="ghost"
                    onPress={() => setMoBanDo(true)}
                  />
                ) : null}
              </>
            ) : null}
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

/**
 * The search half of the screen: the reading, then whatever it produced.
 *
 * The reading is drawn *above* the results and stays on screen even when there
 * are none, which is the whole design decision here. An empty result with the
 * misreading visible is a problem someone can fix in one edit; an empty result
 * on its own is a dead end that reads as "this feature does not work".
 *
 * Results are not re-sorted. `GET /places` is a catalogue and gets ordered by
 * open-now and score; this is an answer to a sentence, and relevance to that
 * sentence is the model's ordering, which sorting here would quietly discard.
 * The route makes the same choice for the same reason.
 */
function KetQuaTim({
  state,
  categories,
  onChon,
}: {
  state: TimKiemState;
  categories: Category[];
  onChon: (p: Place) => void;
}) {
  const c = usePalette();

  if (state.kind === "dang-tim") {
    return (
      <Card>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
          <ActivityIndicator color={c.ai} />
          <Text style={{ ...type.body, color: c.inkSoft }}>Đang đọc câu của bạn…</Text>
        </View>
      </Card>
    );
  }

  if (state.kind === "khong-tra-loi") {
    return <KhongCoKetQua coCachHieu={false} />;
  }

  if (state.kind !== "co-ket-qua") {
    return <TimKhongDuoc state={state} baseUrl={PLACES_BASE_URL} />;
  }

  return (
    <>
      <CauAiHieu understood={state.understood} categories={categories} />

      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
        <Text style={{ ...type.title, color: c.ink, flexShrink: 1 }}>Kết quả cho câu của bạn</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>{state.places.length} chỗ</Text>
      </View>

      {state.places.length === 0 ? (
        <KhongCoKetQua coCachHieu />
      ) : (
        <>
          <LuoiHaiCot places={state.places} onChon={onChon} />
          <DaiBanDo places={state.places} />
        </>
      )}
    </>
  );
}

/**
 * A section heading with an optional action on its right.
 *
 * Mockup: "Gợi ý cho bạn" with "Xem tất cả" opposite it.
 *
 * `action` is nullable rather than optional so a caller has to decide. The
 * heading appears on a list that can and cannot be expanded, and "I forgot to
 * pass it" and "there is nothing to expand" must not look the same at the call
 * site. The right-hand slot then holds either a control or nothing; it never
 * holds a disabled control, because a greyed "Xem tất cả" asks a person to work
 * out why it is grey when the honest answer is that the list is already whole.
 */
function TieuDeMuc({ title, action }: {
  title: string;
  action: { label: string; onPress: () => void } | null;
}) {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.sm }}>
      <Text style={{ ...type.title, color: c.ink, flexShrink: 1 }}>{title}</Text>
      {action ? (
        <Pressable
          onPress={action.onPress}
          accessibilityRole="button"
          // The label already reads as an action; the hint says what changes,
          // which the word "tất cả" alone does not for someone who cannot see
          // that the grid below is cut short.
          accessibilityLabel={action.label}
          hitSlop={space.sm}
          style={({ pressed }) => ({
            // Not a full 44 box: this is inline text beside a heading, and a
            // 44pt block here would push the heading off its own baseline.
            // `hitSlop` buys the target back without spending the layout.
            minHeight: 24,
            justifyContent: "center",
            opacity: pressed ? 0.6 : 1,
          })}
        >
          <Text style={{ ...type.label, color: c.accent, fontWeight: "600" }}>{action.label}</Text>
        </Pressable>
      ) : null}
    </View>
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
export function ChuaCoDuLieu({ state }: { state: PlacesState }) {
  const c = usePalette();
  let tieuDe = "Chưa có dữ liệu địa điểm";
  let than = "";
  let diaChi = "";

  if (state.kind === "chua-co-endpoint") {
    tieuDe = "Máy chủ này chưa có danh mục địa điểm";
    than = `Máy chủ đang chạy nhưng không có route GET /places. Route đó có trong ${state.work}, nên nhiều khả năng app đang trỏ vào một bản API cũ hơn, không phải app thiếu gì.`;
    diaChi = state.url;
  } else if (state.kind === "khong-noi-duoc") {
    tieuDe = "Không mở được máy chủ";
    than = themChiTiet("Không kết nối được tới API.", state.detail);
    diaChi = state.url;
  } else if (state.kind === "may-chu-loi") {
    tieuDe = `Máy chủ trả lỗi ${state.status}`;
    than = thanLoiMayChu(state.status, state.detail);
    diaChi = state.url;
  } else if (state.kind === "du-lieu-sai") {
    tieuDe = "Dữ liệu địa điểm không đúng dạng";
    than = themChiTiet("App từ chối hiển thị thay vì vẽ ra số sai.", state.detail);
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
        API app đang trỏ tới: {PLACES_BASE_URL}. Đổi trong .env rồi mở lại app.
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
      <AnhDiaDiem category={place.category} height={124} rounded={0} uri={place.photoUrl} name={place.name}>
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
        {/* Two lines, not one. At two columns on a 390pt phone a single line
            truncated "Tiệm Nướng Xóm Lào" to "Tiệm Nướng Xóm…" -- the mockup's
            own headline place, unreadable in the app that copies it. Two lines
            fit every name in the twelve-row catalogue; the cap stays so a
            pathological name cannot push the facts under it off the card. */}
        <Text numberOfLines={2} style={{ ...type.body, fontWeight: "700", color: c.ink }}>
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
