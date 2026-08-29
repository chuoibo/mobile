/** Opening screen, then the shell. The whole of the app's routing.
 *
 * `nguoi` is the only piece of session state that exists. It is not auth and
 * is not treated as auth: nothing is gated on it, no request is signed with
 * it, and "Bỏ qua" enters the app with it null on purpose -- a real state that
 * the screens below have to render rather than a case to be prevented.
 */
import React, { useState } from "react";
import { MoDau } from "../screens/mo-dau/MoDau";
import { VoTab } from "./VoTab";
import type { DemoPerson } from "./nhom-demo";

export function AppRoot({ renderKhoanChi }: {
  renderKhoanChi: (onExit: () => void) => React.ReactNode;
}) {
  const [daVao, setDaVao] = useState(false);
  const [nguoi, setNguoi] = useState<DemoPerson | null>(null);

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

  return <VoTab nguoi={nguoi} renderKhoanChi={renderKhoanChi} />;
}
