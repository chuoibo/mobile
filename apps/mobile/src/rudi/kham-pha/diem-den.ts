/**
 * Điểm đến: which city the catalogue is showing (M10, ADR-0018).
 *
 * The catalogue spans fifteen destinations, so «places» is not a list until
 * somebody says where. The server always answers with one destination and says
 * which one it picked; this module is how the screen reads the choices, keeps
 * the person's own choice on the phone, and words the two states that are easy
 * to get wrong: «chưa bật vị trí» and «bạn đang ở ngoài vùng RuDi biết».
 *
 * The choice lives in AsyncStorage rather than on the server on purpose. It is
 * browsing state, like a filter -- not a fact about the person, and not
 * something their friends should see change.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

import { translatedAnonymous } from "../../api";

export type DiemDen = {
  id: string;
  name: string;
  province: string | null;
  blurb: string | null;
  lat: number;
  lng: number;
  /** Straight-line kilometres from coordinates the caller sent, else null. */
  distanceKm: number | null;
};

export type DanhSachDiemDen = {
  diemDen: DiemDen[];
  /** The one the caller is standing in, or null: either no coordinates were
   *  sent, or the nearest destination is too far to claim them. */
  ganNhat: DiemDen | null;
};

const LOI_DIEM_DEN: Record<string, string> = {
  coordinates_incomplete: "Thiếu một nửa toạ độ, nên chưa hỏi được chỗ gần bạn.",
  destination_not_found: "Điểm đến này không còn trong danh mục.",
};

function doc(wire: unknown): DiemDen {
  const o = wire as Record<string, unknown>;
  return {
    id: String(o.id),
    name: String(o.name),
    province: o.province === null || o.province === undefined ? null : String(o.province),
    blurb: o.blurb === null || o.blurb === undefined ? null : String(o.blurb),
    lat: Number(o.lat),
    lng: Number(o.lng),
    distanceKm:
      o.distance_km === null || o.distance_km === undefined ? null : Number(o.distance_km),
  };
}

/**
 * Every destination, and optionally which one the caller is in.
 *
 * Coordinates are sent only when the person asked for «gần tôi». They are used
 * inside that one request and nothing keeps them -- not this module, not the
 * server (ADR-0018).
 */
export async function docDiemDen(viTri?: { lat: number; lng: number }): Promise<DanhSachDiemDen> {
  const params = new URLSearchParams();
  if (viTri !== undefined) {
    params.set("lat", String(viTri.lat));
    params.set("lng", String(viTri.lng));
  }
  const duoi = params.toString();
  // The path is written so the contract gate can read it: a template that
  // swallows the «?» leaves the gate unable to say which route is being called.
  const wire = await translatedAnonymous<{ destinations: unknown[]; nearest: unknown }>(
    LOI_DIEM_DEN,
    duoi ? `/destinations?${duoi}` : "/destinations",
    { method: "GET" },
  );
  return {
    diemDen: (wire.destinations ?? []).map(doc),
    ganNhat: wire.nearest === null || wire.nearest === undefined ? null : doc(wire.nearest),
  };
}

const KHOA = "rudi.diem-den.v1";

/** Remember the choice on this phone. Failure is not worth a screen. */
export async function luuDiemDen(id: string): Promise<void> {
  try {
    await AsyncStorage.setItem(KHOA, id);
  } catch {
    // A filter that did not persist costs one tap next time.
  }
}

export async function docDiemDenDaChon(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(KHOA);
  } catch {
    return null;
  }
}

/** «Cách bạn 4.2 km», or nothing when nobody measured. */
export function cauKhoangCach(diemDen: Pick<DiemDen, "distanceKm">): string | null {
  if (diemDen.distanceKm === null) return null;
  return `Cách bạn ${diemDen.distanceKm} km`;
}

/** The subtitle under a destination name: province, and distance if known. */
export function dongPhuDiemDen(diemDen: DiemDen): string {
  const phan = [diemDen.province, cauKhoangCach(diemDen)].filter(
    (x): x is string => typeof x === "string" && x !== "",
  );
  return phan.join(" · ");
}

/**
 * What the «gần tôi» row says, in each of the four states it really has.
 *
 * The fourth one is the one an app usually gets wrong: coordinates arrived,
 * and no destination is close enough. Saying «Đà Nẵng» to somebody standing in
 * Kon Tum because Đà Nẵng is the nearest row we happen to have is worse than
 * saying we do not know.
 */
export function cauGanToi(
  trang:
    | { kind: "chua-hoi" }
    | { kind: "dang-hoi" }
    | { kind: "tu-choi" }
    | { kind: "xong"; ganNhat: DiemDen | null },
): string {
  switch (trang.kind) {
    case "chua-hoi":
      return "Dùng vị trí để tìm điểm đến gần bạn";
    case "dang-hoi":
      return "Đang hỏi vị trí…";
    case "tu-choi":
      return "Chưa bật vị trí. Chọn tay ở danh sách dưới cũng được.";
    case "xong":
      return trang.ganNhat === null
        ? "Chỗ bạn đang đứng chưa nằm trong vùng RuDi biết. Chọn tay ở dưới nhé."
        : `Gần bạn: ${trang.ganNhat.name}`;
  }
}
