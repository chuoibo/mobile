/** Opening screen, then the shell. The whole of the app's routing.
 *
 * `nguoi` is the only piece of session state that exists. It is not auth and
 * is not treated as auth: nothing is gated on it, no request is signed with
 * it, and "Bỏ qua" enters the app with it null on purpose -- a real state that
 * the screens below have to render rather than a case to be prevented.
 *
 * A `#tab=...&nguoi=...` fragment may name where to open. See `lien-ket.ts`
 * for why that exists and why it is not a way past anything.
 */
import React, { useState } from "react";
import { MoDau } from "../screens/mo-dau/MoDau";
import { DangKy } from "../screens/vao-cua/DangKy";
import { VoTab } from "./VoTab";
import { DEFAULT_TAB } from "./tabs";
import { diemDenHienTai } from "./lien-ket";
import type { NguoiDung } from "./nhom-demo";
import type { NhomPhien } from "../screens/chat/nhom";

export function AppRoot({ renderKhoanChi }: {
  /** The third argument is the group this session opened, and it is not
   *  optional: a bill written into a different group from the one the chat
   *  above it belongs to is the same defect as bug-223337 wearing a different
   *  screen. `VoTab` holds the handle and hands it to all three surfaces. */
  renderKhoanChi: (
    onExit: () => void,
    nguoi: NguoiDung | null,
    nhomPhien: NhomPhien | null,
  ) => React.ReactNode;
}) {
  // Read once, at mount. Re-reading on every render would let a fragment
  // change yank somebody out of the screen they navigated to by hand.
  const [diemDen] = useState(diemDenHienTai);
  const [daVao, setDaVao] = useState(diemDen.boQuaMoDau);
  const [nguoi, setNguoi] = useState<NguoiDung | null>(diemDen.nguoi);
  // F01 sits between the opening screen and the shell rather than inside
  // either. It is its own destination -- somebody can back out of it to the
  // sunset without having registered, which a sheet over `MoDau` would have
  // made awkward and which entering the shell first would have made a lie.
  const [dangDangKy, setDangDangKy] = useState(diemDen.vao === "dang-ky");

  if (!daVao) {
    if (dangDangKy) {
      return (
        <DangKy
          onXong={(p) => {
            setNguoi(p);
            setDangDangKy(false);
            setDaVao(true);
          }}
          onQuayLai={() => setDangDangKy(false)}
        />
      );
    }
    return (
      <MoDau
        onVao={(p) => {
          setNguoi(p);
          setDaVao(true);
        }}
        onBoQua={() => setDaVao(true)}
        onSoDienThoai={() => setDangDangKy(true)}
      />
    );
  }

  return (
    <VoTab
      nguoi={nguoi}
      tabDau={diemDen.tab ?? DEFAULT_TAB}
      moNhomNgay={diemDen.vao === "nhom"}
      moKyNiemNgay={diemDen.vao === "ky-niem"}
      moBanBeNgay={diemDen.vao === "ban-be"}
      moWidgetNgay={diemDen.vao === "widget"}
      moQuanTriNgay={diemDen.vao === "quan-tri"}
      moThanhTichNgay={diemDen.vao === "thanh-tich"}
      moAlbumNgay={diemDen.vao === "album"}
      albumChuyen={diemDen.albumChuyen}
      nhomId={diemDen.nhomId}
      banQuetDuoc={diemDen.ban}
      diaDiemDau={diemDen.diaDiem}
      moBanDoNgay={diemDen.banDo}
      moDiemHenNgay={diemDen.diemHen}
      moiBuoiDi={diemDen.moiBuoiDi}
      renderKhoanChi={renderKhoanChi}
    />
  );
}
