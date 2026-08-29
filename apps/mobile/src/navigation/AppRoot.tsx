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
import { VoTab } from "./VoTab";
import { DEFAULT_TAB } from "./tabs";
import { diemDenHienTai } from "./lien-ket";
import type { DemoPerson } from "./nhom-demo";

export function AppRoot({ renderKhoanChi }: {
  renderKhoanChi: (onExit: () => void) => React.ReactNode;
}) {
  // Read once, at mount. Re-reading on every render would let a fragment
  // change yank somebody out of the screen they navigated to by hand.
  const [diemDen] = useState(diemDenHienTai);
  const [daVao, setDaVao] = useState(diemDen.boQuaMoDau);
  const [nguoi, setNguoi] = useState<DemoPerson | null>(diemDen.nguoi);

  if (!daVao) {
    return (
      <MoDau
        onVao={(p) => {
          setNguoi(p);
          setDaVao(true);
        }}
        onBoQua={() => setDaVao(true)}
      />
    );
  }

  return <VoTab nguoi={nguoi} tabDau={diemDen.tab ?? DEFAULT_TAB} renderKhoanChi={renderKhoanChi} />;
}
