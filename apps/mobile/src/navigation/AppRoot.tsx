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
import { DEFAULT_TAB, tabById } from "./tabs";
import type { DemoPerson } from "./nhom-demo";

/**
 * A tab named in the URL, on web only.
 *
 * Exists to be measured. The detector and the screenshot tools render a URL and
 * cannot press anything, so without this every scan of this app is a scan of
 * the opening screen -- which is how a tab ships unmeasured while the report
 * says the app was checked. `?man=kham-pha` opens straight onto that tab.
 *
 * Deliberately narrow: it reads one parameter, accepts only ids that
 * `tabs.ts` already declares, and does nothing at all on native, where
 * `location` is undefined. It signs nobody in -- the shell still renders the
 * nobody-selected state, which is a real state and the honest one to measure.
 */
function tabTuUrl(): string | null {
  const loc = (globalThis as { location?: { search?: string } }).location;
  if (!loc?.search) return null;
  const id = new URLSearchParams(loc.search).get("man");
  return id && tabById(id) ? id : null;
}

export function AppRoot({ renderKhoanChi }: {
  renderKhoanChi: (onExit: () => void) => React.ReactNode;
}) {
  const [tabDauTien] = useState(tabTuUrl);
  const [daVao, setDaVao] = useState(() => tabDauTien !== null);
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

  return <VoTab nguoi={nguoi} tabDau={tabDauTien ?? DEFAULT_TAB} renderKhoanChi={renderKhoanChi} />;
}
