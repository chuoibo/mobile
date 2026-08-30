/** Album chuyến đi — F36's shelf, one album, and F37's AI reel over it.
 *
 * One screen with three states rather than three screens, because it is one
 * walk: the shelf of trips, the trip you opened, the reel the model built from
 * that trip's photographs. Back steps out one level at a time and the shelf is
 * not re-fetched on the way back, so a person who opened the wrong trip does
 * not pay a round-trip to correct themselves.
 *
 * What each state reads:
 *
 *   shelf   GET /contexts/{id}/albums
 *   album   GET /contexts/{id}/albums/{outing_id}
 *   reel    GET /contexts/{id}/albums/{outing_id}/reel
 *
 * The reel is the only place in this app where a sentence on screen was written
 * by a model, and it is labelled as one every time it appears. Everything beside
 * it -- the caption, the place, the hearts, the time, every figure in đồng --
 * is a row the server read out of the database. Mixing the two without saying
 * which is which is how a demo starts making claims nobody can stand behind.
 *
 * Money is printed, never computed. `split_total_vnd` arrives already summed
 * from the ledger; `tienVnd` groups its digits and changes nothing else.
 *
 * Mockup: product/RuDi_Mobile_Product_Mockups/06_memories (trip_album). The
 * shelf is drawn as cards rather than the mockup's masonry grid: this group's
 * albums come back with `photo_count: 0` on a live server, and a masonry grid
 * of nothing is a screen that looks broken while working correctly.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Card } from "../../ui/Kit";
import { Anh } from "../../ui/Anh";
import { Gradient, HERO_SUNSET } from "../../navigation/Gradient";
import { DEMO_GROUP_NAME, type NguoiDung } from "../../navigation/nhom-demo";
// Read from the memory wall's module, never edited here. The date range and the
// money formatter are already implemented once for the same rows; a second copy
// on this screen is a copy that drifts the day either rule changes.
import { khoangNgay, soNgay, tienVnd, timNhomDemo } from "../ky-niem/ky-uc";
import {
  AlbumError,
  layAlbum,
  layDanhSachAlbum,
  layThuocPhim,
  lyDoPhim,
  tenDiaDiem,
  type Album,
  type AnhAlbum,
  type CanhPhim,
  type DanhSachAlbum,
  type ThuocPhim,
  type TomTatAlbum,
} from "./album-api";

/** Which of the three the person is looking at. */
type Man =
  | { pha: "ke" }
  | { pha: "album"; outingId: string; ten: string }
  | { pha: "phim"; outingId: string; ten: string };

type Tai<T> =
  | { pha: "dang-tai" }
  | { pha: "xong"; du: T }
  | { pha: "loi"; loi: string };

export function AlbumChuyenDi({
  nguoi,
  contextId,
  chuyenDau,
  onDong,
  docKe = layDanhSachAlbum,
  docAlbum = layAlbum,
  docPhim = layThuocPhim,
  timNhom = timNhomDemo,
}: {
  nguoi: NguoiDung | null;
  /** Which group's shelf, when the link named one. Null means "go and find it". */
  contextId?: string | null;
  /** F36. Open straight on one trip's album, from `#chuyen=<uuid>`. Null starts
   *  at the shelf. Back still steps to the shelf rather than out, so a person
   *  who arrived by link is not trapped one level down. */
  chuyenDau?: string | null;
  /** Back out of the album. Absent when rendered as a whole tab. */
  onDong?: () => void;
  /** Injected so every state can be exercised without a server. */
  docKe?: typeof layDanhSachAlbum;
  docAlbum?: typeof layAlbum;
  docPhim?: typeof layThuocPhim;
  timNhom?: typeof timNhomDemo;
}) {
  const c = usePalette();
  // The link's trip, if it named one. `ten` is empty because a fragment carries
  // an id and not a title -- the header falls back to the screen's own name
  // until the album arrives with the real one, rather than printing a guess.
  const [man, setMan] = useState<Man>(
    chuyenDau ? { pha: "album", outingId: chuyenDau, ten: "" } : { pha: "ke" },
  );
  const [nhom, setNhom] = useState<string | null>(contextId ?? null);
  const [ke, setKe] = useState<Tai<DanhSachAlbum>>({ pha: "dang-tai" });
  const [album, setAlbum] = useState<Tai<Album>>({ pha: "dang-tai" });
  const [phim, setPhim] = useState<Tai<ThuocPhim>>({ pha: "dang-tai" });
  const [dangLamMoi, setDangLamMoi] = useState(false);

  const taiKe = useCallback(async () => {
    if (!nguoi) return;
    try {
      let id = contextId ?? null;
      if (id === null) id = (await timNhom(nguoi.personId)).contextId;
      setNhom(id);
      setKe({ pha: "xong", du: await docKe(id, nguoi.personId) });
    } catch (error) {
      setKe({ pha: "loi", loi: loiCua(error) });
    }
  }, [nguoi, contextId, docKe, timNhom]);

  useEffect(() => {
    void taiKe();
  }, [taiKe]);

  /** The link's album, once the group id it needs has resolved.
   *
   * Separate from `taiKe` rather than folded into it: the shelf is still
   * fetched, because back has to land somewhere, and a person who arrived by
   * link should not pay for the shelf twice when they step up to it. Both ids
   * are stable, so this runs once.
   */
  useEffect(() => {
    if (!chuyenDau || !nhom || !nguoi) return;
    let huy = false;
    void (async () => {
      try {
        const du = await docAlbum(nhom, chuyenDau, nguoi.personId);
        if (!huy) setAlbum({ pha: "xong", du });
      } catch (error) {
        if (!huy) setAlbum({ pha: "loi", loi: loiCua(error) });
      }
    })();
    return () => {
      huy = true;
    };
  }, [chuyenDau, nhom, nguoi, docAlbum]);

  /** Open one trip. The album is fetched fresh rather than assembled from the
   *  shelf row: the shelf carries counts and a cover, the album carries the
   *  photographs and the places, and faking the second from the first would put
   *  a trip's real `photo_count` above an empty grid. */
  const moAlbum = useCallback(
    async (row: TomTatAlbum) => {
      if (!nguoi || !nhom) return;
      setMan({ pha: "album", outingId: row.outing_id, ten: row.title });
      setAlbum({ pha: "dang-tai" });
      try {
        setAlbum({ pha: "xong", du: await docAlbum(nhom, row.outing_id, nguoi.personId) });
      } catch (error) {
        setAlbum({ pha: "loi", loi: loiCua(error) });
      }
    },
    [nguoi, nhom, docAlbum],
  );

  const moPhim = useCallback(
    async (outingId: string, ten: string) => {
      if (!nguoi || !nhom) return;
      setMan({ pha: "phim", outingId, ten });
      setPhim({ pha: "dang-tai" });
      try {
        setPhim({ pha: "xong", du: await docPhim(nhom, outingId, nguoi.personId) });
      } catch (error) {
        setPhim({ pha: "loi", loi: loiCua(error) });
      }
    },
    [nguoi, nhom, docPhim],
  );

  const lamMoi = useCallback(async () => {
    setDangLamMoi(true);
    if (man.pha === "ke") await taiKe();
    else if (man.pha === "album") {
      if (nguoi && nhom) {
        try {
          setAlbum({ pha: "xong", du: await docAlbum(nhom, man.outingId, nguoi.personId) });
        } catch (error) {
          setAlbum({ pha: "loi", loi: loiCua(error) });
        }
      }
    } else await moPhim(man.outingId, man.ten);
    setDangLamMoi(false);
  }, [man, taiKe, moPhim, docAlbum, nguoi, nhom]);

  /** One step back, never straight out. The reel belongs to an album and the
   *  album belongs to the shelf; collapsing all of it to `onDong` would make the
   *  back arrow mean two different things depending on how deep you are. */
  const lui = useCallback(() => {
    if (man.pha === "phim") setMan({ pha: "album", outingId: man.outingId, ten: man.ten });
    else if (man.pha === "album") setMan({ pha: "ke" });
    else onDong?.();
  }, [man, onDong]);

  // A trip opened by link has no title until its album lands, so the header
  // falls back to the screen's own name rather than rendering an empty heading.
  const tenAlbum =
    man.pha === "ke" ? "" : man.ten || (album.pha === "xong" ? album.du.title : "");
  const tieuDe =
    man.pha === "ke"
      ? "Album chuyến đi"
      : man.pha === "album"
        ? tenAlbum || "Album chuyến đi"
        : "Thước phim AI";
  const phu =
    man.pha === "ke"
      ? `${DEMO_GROUP_NAME} · mỗi chuyến một album`
      : man.pha === "album"
        ? "Ảnh, chỗ đã tới và tiền của chuyến này"
        : tenAlbum || DEMO_GROUP_NAME;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.ground }}
      contentContainerStyle={{ paddingBottom: space.xl }}
      // A keyboard tab-stop on the scroller itself, for the same reason the
      // memory wall has one: this is a column of cards with nothing pressable
      // below the fold on the reel, so without it every pick past the first is
      // unreachable by keyboard. Measured elsewhere in this app as axe
      // `scrollable-region-focusable` (serious).
      tabIndex={0}
      refreshControl={
        <RefreshControl refreshing={dangLamMoi} onRefresh={lamMoi} tintColor={c.accent} />
      }
    >
      <Bia tieuDe={tieuDe} phu={phu} onLui={man.pha === "ke" && !onDong ? undefined : lui} />

      <View style={{ padding: space.md, gap: space.md }}>
        {nguoi === null ? <ChuaCoNhom /> : null}

        {nguoi && man.pha === "ke" ? (
          <TrangThai
            tai={ke}
            onThuLai={lamMoi}
            render={(du) => <Ke danhSach={du} onMo={moAlbum} />}
          />
        ) : null}

        {nguoi && man.pha === "album" ? (
          <TrangThai
            tai={album}
            onThuLai={lamMoi}
            render={(du) => (
              <MotAlbum
                album={du}
                nguoiXem={nguoi.personId}
                onXemPhim={() => moPhim(du.outing_id, du.title)}
              />
            )}
          />
        ) : null}

        {nguoi && man.pha === "phim" ? (
          <TrangThai
            tai={phim}
            onThuLai={lamMoi}
            render={(du) => <Phim phim={du} nguoiXem={nguoi.personId} />}
          />
        ) : null}
      </View>
    </ScrollView>
  );
}

function loiCua(error: unknown): string {
  return error instanceof AlbumError ? error.message : "Chưa đọc được album.";
}

/** Loading, refused, or loaded — in one place, so all three states of all three
 *  fetches read the same and none of them can quietly render nothing. */
function TrangThai<T>({
  tai,
  onThuLai,
  render,
}: {
  tai: Tai<T>;
  onThuLai: () => void;
  render: (du: T) => React.ReactNode;
}) {
  const c = usePalette();
  if (tai.pha === "dang-tai") {
    return (
      <Card>
        <View style={{ paddingVertical: space.md, alignItems: "flex-start" }}>
          <ActivityIndicator color={c.accent} />
        </View>
        <Text style={{ ...type.label, color: c.inkSoft }}>Đang hỏi máy chủ…</Text>
      </Card>
    );
  }
  if (tai.pha === "loi") {
    return (
      <Card>
        <View style={{ gap: space.sm }} accessibilityRole="alert">
          <Text style={{ ...type.body, color: c.ink }}>{tai.loi}</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Màn này không giữ bản sao nào. Một album cũ hiện lúc máy chủ im lặng sẽ nói
            rằng chuyến đi chỉ có bấy nhiêu, mà đó đúng là điều chưa biết.
          </Text>
          <NutVien nhan="Thử lại" onPress={onThuLai} />
        </View>
      </Card>
    );
  }
  return <>{render(tai.du)}</>;
}

/** Cover band, matching the memory wall so arriving here reads as one product. */
function Bia({ tieuDe, phu, onLui }: { tieuDe: string; phu: string; onLui?: () => void }) {
  const c = usePalette();
  return (
    <View>
      {/* No text sits on the gradient itself: `tokens.brand` measures white on
          the coral stop at 2.92:1 and forbids exactly that. */}
      <Gradient colors={HERO_SUNSET} style={{ height: 104 }} />
      {onLui ? (
        <Pressable
          onPress={onLui}
          accessibilityRole="button"
          accessibilityLabel="Quay lại màn trước"
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
        <Text style={{ ...type.h1, color: c.ink }}>{tieuDe}</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>{phu}</Text>
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
        Album là của riêng nhóm và chỉ mở ra cho thành viên. Quay lại màn mở đầu, chọn một
        người trong nhóm rồi mở lại màn này.
      </Text>
    </Card>
  );
}

/* ------------------------------------------------------------------ shelf --- */

function Ke({
  danhSach,
  onMo,
}: {
  danhSach: DanhSachAlbum;
  onMo: (row: TomTatAlbum) => void;
}) {
  const c = usePalette();
  if (danhSach.albums.length === 0) {
    return (
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Chưa có chuyến nào</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Một album được lập từ một chuyến đi. Tạo chuyến ở tab Lên plan, đi xong rồi quay
          lại đây.
        </Text>
      </Card>
    );
  }
  return (
    <>
      <Card>
        <Text style={{ ...type.label, color: c.inkSoft }}>Nhóm đã có</Text>
        <View style={{ flexDirection: "row", alignItems: "baseline", gap: space.sm }}>
          <Text style={{ ...type.amount, color: c.ink }}>{danhSach.albums.length}</Text>
          <Text style={{ ...type.body, color: c.inkSoft }}>album</Text>
        </View>
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Mỗi album là một chuyến. Số ảnh, số chỗ và số tiền đều đọc lại từ máy chủ mỗi lần
          mở màn này, không có con số nào lưu sẵn ở đây.
        </Text>
      </Card>

      {danhSach.albums.map((row) => (
        <TheAlbum key={row.outing_id} row={row} onMo={() => onMo(row)} />
      ))}
    </>
  );
}

/** One trip on the shelf. The whole card is the button, so the target is the
 *  card rather than a chevron nobody can hit on a moving bus. */
function TheAlbum({ row, onMo }: { row: TomTatAlbum; onMo: () => void }) {
  const c = usePalette();
  return (
    <Pressable
      onPress={onMo}
      accessibilityRole="button"
      accessibilityLabel={`Mở album ${row.title}, ${khoangNgay(row.starts_on, row.ends_on)}, ${row.photo_count} ảnh`}
      style={({ pressed }) => ({ opacity: pressed ? 0.9 : 1 })}
    >
      <Card style={{ padding: 0, overflow: "hidden", gap: 0 }}>
        {/* The album's own newest photograph when it has one. Never a stock
            picture of a place the group never went: the fallback is the
            group's sunset, which says "a picture belongs here" rather than
            inventing one. */}
        <Gradient colors={HERO_SUNSET} style={{ height: 76 }} />

        <View style={{ padding: space.md, gap: space.sm }}>
          <View style={{ gap: 2 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
              <Text style={{ ...type.title, color: c.ink, flex: 1 }}>{row.title}</Text>
              {row.in_progress ? <Chip nhan="Đang đi" /> : null}
            </View>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              {khoangNgay(row.starts_on, row.ends_on)} ·{" "}
              {soNgay(row.starts_on, row.ends_on)} ngày · {row.headcount} người
            </Text>
          </View>

          <View style={{ flexDirection: "row", gap: space.sm }}>
            <O label="Ảnh" value={`${row.photo_count}`} mau={c.accent} nen={c.accentSoft} />
            <O label="Chỗ đã tới" value={`${row.place_count}`} mau={c.ink} nen={c.ground} />
            <O
              label="Đã chia"
              value={tienVnd(row.split_total_vnd)}
              mau={c.split}
              nen={c.splitSoft}
            />
          </View>
        </View>
      </Card>
    </Pressable>
  );
}

/* ------------------------------------------------------------------ album --- */

/* Exported so a test can render the album card on its own. The screen around
 * it loads over three async readers, and `renderToStaticMarkup` is synchronous,
 * so reaching this subtree through `AlbumChuyenDi` would only ever capture the
 * spinner. Same shape as `ChuaCoDuLieu` in `KhamPha.tsx`. */
export function MotAlbum({
  album,
  nguoiXem,
  onXemPhim,
}: {
  album: Album;
  nguoiXem: string;
  onXemPhim: () => void;
}) {
  const c = usePalette();
  return (
    <>
      <Card>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
          <Text style={{ ...type.title, color: c.ink, flex: 1 }}>{album.title}</Text>
          {album.in_progress ? <Chip nhan="Đang đi" /> : null}
        </View>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {khoangNgay(album.starts_on, album.ends_on)} · {album.period_label} ·{" "}
          {album.headcount} người
        </Text>
        {/* The server keeps `title` and `period_label` in separate fields so a
            client never has to guess which half a machine wrote. Neither is
            AI-composed today, and this line says so rather than letting the
            heading imply it. */}
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Tên album là tên chuyến do nhóm tự đặt. Chưa có tên nào do AI đặt ở màn này.
        </Text>

        <View style={{ flexDirection: "row", gap: space.sm }}>
          <O label="Ảnh" value={`${album.photo_count}`} mau={c.accent} nen={c.accentSoft} />
          <O label="Check-in" value={`${album.checkin_count}`} mau={c.ink} nen={c.ground} />
          <O
            label="Đã chia"
            value={tienVnd(album.split_total_vnd)}
            mau={c.split}
            nen={c.splitSoft}
          />
        </View>
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          {album.expense_count} khoản chi đã chốt rơi vào đúng những ngày của chuyến. Một
          bữa chia sau khi cả nhóm đã về thì không tính vào đây.
        </Text>
      </Card>

      {album.places.length > 0 ? (
        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Đã tới</Text>
          {/* `tenDiaDiem` rather than `place_name ?? place_id`: the fallback
              used to be the id, so a check-in the server could not name read as
              `· 4f1e2d3c-9a8b-...` -- an opaque identifier printed where a
              place name goes. The reel below already refuses that (`Canh`
              drops the place when it is null); this is the same refusal, said
              in words so the row still carries the visit. */}
          {album.places.map((p) => (
            <Text key={p.place_id} style={{ ...type.body, color: c.ink }}>
              · {tenDiaDiem(p)}
            </Text>
          ))}
        </Card>
      ) : null}

      {album.highlights.length > 0 ? (
        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Nhóm thích nhất</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Xếp theo số tim chính nhóm đã thả. Đây là lựa chọn của người, không phải của AI.
          </Text>
          <Luoi anh={album.highlights} nguoiXem={nguoiXem} nhom={album.context_id} />
        </Card>
      ) : null}

      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Ảnh trong chuyến</Text>
        {album.photos.length === 0 ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Chuyến này chưa có tấm ảnh nào. Ảnh vào album qua tường kỷ niệm của nhóm: tấm
            nào chụp trong những ngày của chuyến thì hiện ở đây.
          </Text>
        ) : (
          <Luoi anh={album.photos} nguoiXem={nguoiXem} nhom={album.context_id} />
        )}
      </Card>

      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Thước phim AI</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          AI đọc ảnh của chuyến này rồi chọn ra vài khoảnh khắc và viết một câu cho mỗi
          cái. Nó chỉ được chọn trong số ảnh có thật của nhóm.
        </Text>
        <NutVien nhan="Dựng thước phim" onPress={onXemPhim} chinh />
      </Card>
    </>
  );
}

/** Two columns at every width this app is used at. A third column on a phone
 *  puts a face at 110pt, which is small enough that the grid stops being
 *  something you look at and becomes something you scroll past. */
function Luoi({
  anh,
  nguoiXem,
  nhom,
}: {
  anh: AnhAlbum[];
  nguoiXem: string;
  nhom: string;
}) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm, marginTop: space.xs }}>
      {anh.map((a) => (
        <Khung key={a.memory_id} anh={a} nguoiXem={nguoiXem} nhom={nhom} />
      ))}
    </View>
  );
}

/** One frame. Fetched through `Anh`, which runs `nguonAnhAnToan` before it will
 *  build an `<Image>` and sends the viewer's header — `/contexts/{c}/photos/{p}`
 *  is members-only, and without a header the server answers 401 and the whole
 *  grid falls back to its stand-in, which looks exactly like a trip with no
 *  photographs. */
function Khung({ anh, nguoiXem, nhom }: { anh: AnhAlbum; nguoiXem: string; nhom: string }) {
  const c = usePalette();
  const chuThich = anh.caption?.trim() ?? "";
  return (
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
        uri={anh.image_url}
        alt={chuThich ? `Ảnh trong album: ${chuThich}` : "Ảnh trong album của nhóm"}
        nguoiXem={nguoiXem}
        nhom={nhom}
        style={{ aspectRatio: 1, width: "100%" }}
        cho={<Gradient colors={HERO_SUNSET} style={{ flex: 1 }} />}
      />
      {chuThich ? (
        <Text numberOfLines={2} style={{ ...type.micro, color: c.inkSoft, padding: space.xs }}>
          {chuThich}
        </Text>
      ) : null}
      <Text style={{ ...type.micro, color: c.inkFaint, paddingHorizontal: space.xs, paddingBottom: space.xs }}>
        {anh.reaction_count} tim · {anh.comment_count} bình luận
      </Text>
    </View>
  );
}

/* ------------------------------------------------------------------- reel --- */

function Phim({ phim, nguoiXem }: { phim: ThuocPhim; nguoiXem: string }) {
  const c = usePalette();
  if (!phim.reeled) {
    return (
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Chưa dựng được thước phim</Text>
        <Text style={{ ...type.body, color: c.ink }}>{lyDoPhim(phim.reason)}</Text>
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Máy chủ trả lời bình thường, chỉ là không có bản dựng nào. Màn này không thay
          bằng một thước phim cũ hay một thước phim viết sẵn.
        </Text>
      </Card>
    );
  }
  return (
    <>
      <Card>
        {/* The provenance line comes first, above the model's own title. A
            reader has to know who wrote a sentence before they read it, not
            after. */}
        <NhanAi source={phim.source} />
        {phim.title ? (
          <Text style={{ ...type.title, color: c.ink }}>{phim.title}</Text>
        ) : null}
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {phim.picks.length} khoảnh khắc, chọn từ ảnh có thật của chuyến. Máy chủ bỏ mọi
          lựa chọn không khớp với một tấm ảnh trong nhóm.
        </Text>
      </Card>

      {phim.picks.map((canh, i) => (
        <Canh
          key={canh.memory_id}
          canh={canh}
          thuTu={i + 1}
          tong={phim.picks.length}
          nguoiXem={nguoiXem}
          nhom={phim.context_id}
        />
      ))}
    </>
  );
}

/** One picked moment. The model's sentence is boxed and labelled; the row's own
 *  facts sit outside the box. */
function Canh({
  canh,
  thuTu,
  tong,
  nguoiXem,
  nhom,
}: {
  canh: CanhPhim;
  thuTu: number;
  tong: number;
  nguoiXem: string;
  nhom: string;
}) {
  const c = usePalette();
  const chuThich = canh.caption?.trim() ?? "";
  return (
    <Card style={{ padding: 0, overflow: "hidden", gap: 0 }}>
      {canh.image_url ? (
        <Anh
          uri={canh.image_url}
          alt={chuThich ? `Khoảnh khắc ${thuTu}: ${chuThich}` : `Khoảnh khắc ${thuTu} của chuyến`}
          nguoiXem={nguoiXem}
          nhom={nhom}
          style={{ aspectRatio: 4 / 3, width: "100%" }}
          cho={<Gradient colors={HERO_SUNSET} style={{ flex: 1 }} />}
        />
      ) : (
        <Gradient colors={HERO_SUNSET} style={{ height: 96 }} />
      )}

      <View style={{ padding: space.md, gap: space.sm }}>
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Khoảnh khắc {thuTu}/{tong}
        </Text>

        {chuThich ? <Text style={{ ...type.body, color: c.ink }}>{chuThich}</Text> : null}

        {/* The one sentence on this screen a machine wrote, inside a box that
            says so. Colour is not the only carrier: the label above it is
            words, so the boundary still reads with no colour vision at all. */}
        <View
          style={{
            gap: 2,
            padding: space.sm,
            borderRadius: radius.control,
            backgroundColor: c.accentSoft,
          }}
        >
          <Text style={{ ...type.micro, color: c.inkSoft }}>AI viết câu này</Text>
          <Text style={{ ...type.label, color: c.ink }}>{canh.note}</Text>
        </View>

        <Text style={{ ...type.micro, color: c.inkFaint }}>
          {canh.place_name ? `${canh.place_name} · ` : ""}
          {canh.reaction_count} tim · {canh.comment_count} bình luận
        </Text>
      </View>
    </Card>
  );
}

/** Says who composed the reel, in words rather than a sparkle icon.
 *
 * `source` is the server's own field and is read rather than assumed: a reel
 * marked `none` reaching this branch would mean the server built something
 * without a model, and printing "AI dựng" over it would be this screen making
 * the claim on its own. */
function NhanAi({ source }: { source: "ai" | "none" }) {
  const c = usePalette();
  return (
    <View
      style={{
        alignSelf: "flex-start",
        paddingHorizontal: space.xs,
        paddingVertical: 2,
        borderRadius: radius.small,
        backgroundColor: c.accentSoft,
      }}
    >
      <Text style={{ ...type.micro, color: c.inkSoft }}>
        {source === "ai" ? "AI dựng thước phim này" : "Không phải AI dựng"}
      </Text>
    </View>
  );
}

/* ------------------------------------------------------------------ bits --- */

function O({ label, value, mau, nen }: { label: string; value: string; mau: string; nen: string }) {
  const c = usePalette();
  return (
    // Colour is not the only carrier: the label above each number says which is
    // which, so the row still reads with no colour vision at all.
    <View style={{ flex: 1, gap: 2, padding: space.sm, borderRadius: radius.control, backgroundColor: nen }}>
      <Text style={{ ...type.label, color: c.inkSoft }}>{label}</Text>
      <Text style={{ ...type.amountSmall, color: mau }}>{value}</Text>
    </View>
  );
}

function Chip({ nhan }: { nhan: string }) {
  const c = usePalette();
  return (
    <View
      style={{
        paddingHorizontal: space.xs,
        paddingVertical: 2,
        borderRadius: radius.small,
        backgroundColor: c.ground,
        borderColor: c.line,
        borderWidth: 1,
      }}
    >
      <Text style={{ ...type.micro, color: c.inkSoft }}>{nhan}</Text>
    </View>
  );
}

function NutVien({
  nhan,
  onPress,
  chinh,
}: {
  nhan: string;
  onPress: () => void;
  chinh?: boolean;
}) {
  const c = usePalette();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => ({
        alignSelf: "flex-start",
        // 44pt floor again: this is the button that starts a model call, and it
        // is the one people press on a phone in a car.
        minHeight: 44,
        justifyContent: "center",
        borderWidth: 1,
        borderColor: chinh ? c.accent : c.lineStrong,
        borderRadius: radius.control,
        paddingVertical: 10,
        paddingHorizontal: space.md,
        backgroundColor: chinh ? c.accentSoft : "transparent",
        opacity: pressed ? 0.85 : 1,
      })}
    >
      <Text style={{ ...type.body, fontWeight: "600", color: chinh ? c.ink : c.inkSoft }}>
        {nhan}
      </Text>
    </Pressable>
  );
}
