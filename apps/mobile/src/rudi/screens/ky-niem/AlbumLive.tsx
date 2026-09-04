/**
 * Album chuyến đi on a real session (M6): three depths, all read-only.
 *
 *   kệ (every outing of the group, with the server's counts) → một album
 *   (its photos, the places it reached, the highlights) → thước phim (the
 *   reel: a model may compose it, and the screen says so; `reeled:false`
 *   is a normal answer with a reason, not an error).
 *
 * Every count here is the server's (`AlbumSummary` / `AlbumResponse`); the
 * money line is the trip's split total from the ledger. Photos are read with
 * the caller's headers, like the wall.
 */
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import type { Phien } from "../../../phien";
import { AlbumError } from "../../../screens/album/album-api";
import {
  cauThongKeAlbum,
  cauThuocPhim,
  layAlbum,
  layDanhSachAlbum,
  layThuocPhim,
  nguonAnh,
  tenDiaDiem,
  type Album,
  type ThuocPhim,
  type TomTatAlbum,
} from "../../ky-niem/ky-niem";
import { typography, useRudiTheme } from "../../theme";
import { AiNote, Card, Heading, ListRow, RudiButton, RudiScreen, SectionHeader, TopBar } from "../../ui";

function loiRaChu(error: unknown): string {
  if (error instanceof AlbumError) return error.message;
  if (error instanceof Error && error.message !== "") return error.message;
  return "Chưa đọc được album từ máy chủ.";
}

function cauKhoang(a: { period_label: string; in_progress: boolean; headcount: number }): string {
  return `${a.period_label}${a.in_progress ? " · đang đi" : ""} · ${a.headcount} người`;
}

/* ------------------------------------------------------------------ kệ */

type TrangKe = { pha: "dang-doc" } | { pha: "xong"; albums: TomTatAlbum[] } | { pha: "hong"; loi: string };

export function AlbumNhomLiveScreen({ phien, contextId }: { phien: Phien; contextId: string }) {
  const router = useRouter();
  const { colors } = useRudiTheme();
  const [trang, setTrang] = useState<TrangKe>({ pha: "dang-doc" });

  const doc = async () => {
    try {
      const ds = await layDanhSachAlbum(contextId, phien.person_id);
      setTrang({ pha: "xong", albums: ds.albums });
    } catch (error) {
      setTrang({ pha: "hong", loi: loiRaChu(error) });
    }
  };
  useEffect(() => {
    let song = true;
    void layDanhSachAlbum(contextId, phien.person_id)
      .then((ds) => {
        if (song) setTrang({ pha: "xong", albums: ds.albums });
      })
      .catch((error: unknown) => {
        if (song) setTrang({ pha: "hong", loi: loiRaChu(error) });
      });
    return () => {
      song = false;
    };
  }, [contextId, phien.person_id]);

  return (
    <RudiScreen testID="trip-album-screen">
      <TopBar subtitle="Mỗi kèo một album" title="Album chuyến đi" />
      {trang.pha === "dang-doc" ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc các album từ máy chủ…</Text> : null}
      {trang.pha === "hong" ? (
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
          <RudiButton label="Thử lại" onPress={() => void doc()} variant="outline" />
        </Card>
      ) : null}
      {trang.pha === "xong" && trang.albums.length === 0 ? (
        <Card>
          <Heading size="h2" title="Chưa có kèo nào" subtitle="Album mọc theo kèo: tạo một kèo ở Lên plan, ảnh và check-in trong những ngày đó sẽ gom về đây." />
        </Card>
      ) : null}
      {trang.pha === "xong"
        ? trang.albums.map((a) => (
            <ListRow
              icon={a.in_progress ? "walk-outline" : "albums-outline"}
              key={a.outing_id}
              onPress={() => router.push(`/trips/${a.outing_id}/album?ctx=${contextId}` as never)}
              subtitle={`${cauKhoang(a)} · ${cauThongKeAlbum(a)}`}
              title={a.title}
            />
          ))
        : null}
    </RudiScreen>
  );
}

/* --------------------------------------------------------------- một album */

type TrangAlbum =
  | { pha: "dang-doc" }
  | { pha: "xong"; album: Album; phim: ThuocPhim | null; dangDung: boolean; loiPhim: string | null }
  | { pha: "hong"; loi: string };

export function TripAlbumLiveScreen({ phien, contextId, outingId }: { phien: Phien; contextId: string; outingId: string }) {
  const { colors, radius } = useRudiTheme();
  const [trang, setTrang] = useState<TrangAlbum>({ pha: "dang-doc" });
  const me = phien.person_id;

  useEffect(() => {
    let song = true;
    void layAlbum(contextId, outingId, me)
      .then((album) => {
        if (song) setTrang({ pha: "xong", album, phim: null, dangDung: false, loiPhim: null });
      })
      .catch((error: unknown) => {
        if (song) setTrang({ pha: "hong", loi: loiRaChu(error) });
      });
    return () => {
      song = false;
    };
  }, [contextId, outingId, me]);

  const dungPhim = async () => {
    if (trang.pha !== "xong") return;
    setTrang({ ...trang, dangDung: true, loiPhim: null });
    try {
      const phim = await layThuocPhim(contextId, outingId, me);
      setTrang((t) => (t.pha === "xong" ? { ...t, phim, dangDung: false } : t));
    } catch (error) {
      setTrang((t) => (t.pha === "xong" ? { ...t, dangDung: false, loiPhim: loiRaChu(error) } : t));
    }
  };

  if (trang.pha === "dang-doc") {
    return (
      <RudiScreen testID="trip-album-screen">
        <TopBar title="Album" />
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Đang đọc album từ máy chủ…</Text>
      </RudiScreen>
    );
  }
  if (trang.pha === "hong") {
    return (
      <RudiScreen testID="trip-album-screen">
        <TopBar title="Album" />
        <Card>
          <Text style={[typography.body, { color: colors.warn }]}>{trang.loi}</Text>
        </Card>
      </RudiScreen>
    );
  }
  const a = trang.album;
  return (
    <RudiScreen testID="trip-album-screen">
      <TopBar subtitle={cauKhoang(a)} title={a.title} />
      <Heading title={a.title} subtitle={cauThongKeAlbum(a)} />

      <SectionHeader title="Khoảnh khắc nổi bật" />
      {a.highlights.length === 0 ? (
        <Text style={[typography.caption, { color: colors.inkFaint }]}>Chưa có ảnh nào trong những ngày của kèo. Thả khoảnh khắc lên tường nhóm là ảnh về đây.</Text>
      ) : null}
      <View style={styles.luoi}>
        {a.highlights.map((anh) => {
          const nguon = nguonAnh(anh.image_url, me, contextId);
          return nguon === null ? null : (
            <Image accessibilityLabel={anh.caption === null || anh.caption === "" ? "Ảnh nổi bật" : anh.caption} contentFit="cover" key={anh.memory_id} source={nguon} style={[styles.oAnh, { borderRadius: radius.small }]} />
          );
        })}
      </View>

      <SectionHeader title="Chỗ đã tới" />
      {a.places.length === 0 ? <Text style={[typography.caption, { color: colors.inkFaint }]}>Chưa check-in ở đâu trong kèo này.</Text> : null}
      {a.places.map((p) => (
        <ListRow icon="location-outline" key={p.place_id} title={tenDiaDiem(p)} />
      ))}

      <SectionHeader title="Thước phim" />
      {trang.phim === null ? (
        <>
          <RudiButton disabled={trang.dangDung} icon="film-outline" label="Dựng thước phim" loading={trang.dangDung} onPress={() => void dungPhim()} tone="ai" variant="soft" />
          <Text style={[typography.caption, { color: colors.inkSoft }]}>Máy chủ chọn vài cảnh từ kỷ niệm của kèo; có mô hình thì mô hình dựng, không thì nói rõ vì sao chưa có.</Text>
        </>
      ) : (
        <>
          {trang.phim.source === "ai" ? <AiNote>{cauThuocPhim(trang.phim)}</AiNote> : <Text style={[typography.body, { color: colors.ink }]}>{cauThuocPhim(trang.phim)}</Text>}
          {trang.phim.title !== null ? <Heading size="h2" title={trang.phim.title} /> : null}
          {trang.phim.picks.map((canh) => {
            const nguon = nguonAnh(canh.image_url, me, contextId);
            return (
              <Card key={canh.memory_id} style={styles.canh}>
                {nguon !== null ? <Image contentFit="cover" source={nguon} style={[styles.anhCanh, { borderRadius: radius.small }]} /> : null}
                <Text style={[typography.body, { color: colors.ink }]}>{canh.note}</Text>
                {canh.place_name !== null ? <Text style={[typography.caption, { color: colors.inkFaint }]}>{canh.place_name}</Text> : null}
              </Card>
            );
          })}
        </>
      )}
      {trang.loiPhim !== null ? <Text style={[typography.body, { color: colors.warn }]}>{trang.loiPhim}</Text> : null}
    </RudiScreen>
  );
}

const styles = StyleSheet.create({
  luoi: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  oAnh: { width: "31%", aspectRatio: 1 },
  canh: { gap: 8 },
  anhCanh: { width: "100%", aspectRatio: 4 / 3 },
});
