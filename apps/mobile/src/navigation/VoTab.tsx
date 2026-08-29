/** The tab shell: one screen showing, one bar underneath, one sheet over both.
 *
 * State lives here rather than in a router library. There are four
 * destinations, no URLs, no deep links and no back stack to speak of -- a
 * router would be a dependency, a navigation container and a set of types
 * standing in for a single string. When a second entry point exists (a link
 * into a group, a push notification) that trade changes, and this is the file
 * that changes with it.
 *
 * The expense flow arrives as a render prop instead of an import. It lives in
 * `App.tsx` and belongs to another lane's work; taking it as a prop keeps the
 * dependency pointing one way -- the shell knows a screen exists, not what it
 * does -- and means this file never has to be edited when that flow changes.
 */
import React, { useState } from "react";
import { SafeAreaView, Text, View, useColorScheme } from "react-native";
import { StatusBar } from "expo-status-bar";
import { radius, space, type, usePalette } from "../theme";
import { CaNhan } from "../screens/ca-nhan/CaNhan";
import { TinNhan } from "../screens/chat/TinNhan";
import { KhamPha } from "../screens/kham-pha/KhamPha";
import { Nhom } from "../screens/vao-cua/Nhom";
import { ManVo } from "./ManVo";
import { MenuTao } from "./MenuTao";
import { ThanhTab } from "./ThanhTab";
import { useInertBackground } from "./modal";
import { CREATE_ACTIONS, DEFAULT_TAB, type CreateActionId } from "./tabs";
import type { DemoPerson } from "./nhom-demo";

export function VoTab({ nguoi, tabDau, moNhomNgay, renderKhoanChi }: {
  nguoi: DemoPerson | null;
  /** Open the F03/F04 group screen immediately, from `#vao=nhom`. It sits
   *  behind the [+] menu, so nothing that loads a URL cold can otherwise
   *  reach it -- see `lien-ket.ts` for why that is treated as a defect. */
  moNhomNgay?: boolean;
  /** Which tab to open on, from the link that opened the app. Optional and
   *  null-tolerant so the shell keeps working for any caller that does not
   *  care; `AppRoot` passes the one named in the URL on web, so a screenshot
   *  tool can reach a tab it cannot tap. Null uses the default. */
  tabDau?: string | null;
  /** The organiser flow, handed in with the way back out of it. */
  renderKhoanChi: (onExit: () => void) => React.ReactNode;
}) {
  const c = usePalette();
  const scheme = useColorScheme();
  const [tab, setTab] = useState(tabDau ?? DEFAULT_TAB);
  const [menuMo, setMenuMo] = useState(false);
  const [luongKhoanChi, setLuongKhoanChi] = useState(false);
  // F03/F04. Takes the whole screen for the same reason the expense flow does:
  // it is a task with its own steps, and leaving the bar underneath would
  // offer an exit that drops the handle to a group this app cannot look up
  // again -- see `screens/vao-cua/Nhom.tsx` on why the group outlives the app's
  // memory of it.
  const [luongNhom, setLuongNhom] = useState(moNhomNgay ?? false);
  // What to say when someone opens a create action that is still a shell.
  const [thongBao, setThongBao] = useState<string | null>(null);
  // The screen and the bar go inert while the [+] sheet is open, so Tab cannot
  // walk onto controls the sheet is covering.
  const nenRef = useInertBackground(menuMo);

  function chonTao(id: CreateActionId) {
    setMenuMo(false);
    if (id === "tao-khoan-chi") {
      setLuongKhoanChi(true);
      return;
    }
    if (id === "tao-nhom") {
      setLuongNhom(true);
      return;
    }
    const action = CREATE_ACTIONS.find((a) => a.id === id);
    setThongBao(`"${action?.label}" chưa dựng — mới có chỗ trong menu.`);
  }

  // The expense flow takes the whole screen: it is a task with its own steps,
  // and leaving the tab bar under it would offer an exit that loses a
  // half-written expense without saying so.
  if (luongKhoanChi) {
    return <>{renderKhoanChi(() => setLuongKhoanChi(false))}</>;
  }

  if (luongNhom) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <Nhom nguoi={nguoi} onDong={() => setLuongNhom(false)} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />

      {/* Everything the sheet covers, in one container, so it can be taken out
          of the tab order as one thing while the sheet is open. The wrapper is
          a column of `flex: 1` inside a column of `flex: 1`, so it changes no
          layout -- it exists to give `useInertBackground` a single node to
          own. Splitting it into per-child refs would leave whichever child
          somebody adds next silently reachable behind the sheet. */}
      <View ref={nenRef} style={{ flex: 1 }}>
        <View style={{ flex: 1 }}>
          {tab === "kham-pha" ? <KhamPha /> : null}
          {tab === "len-plan" ? (
            <ManVo
              title="Lên plan"
              hint="Chuyến đi của nhóm, ngày giờ và ai đi"
              screen="LenPlan"
              owner="frontend"
              work="chưa xếp"
            />
          ) : null}
          {tab === "tin-nhan" ? <TinNhan nguoi={nguoi} /> : null}
          {tab === "ca-nhan" ? <CaNhan nguoi={nguoi} /> : null}
        </View>

        {thongBao ? <BangThongBao text={thongBao} onClose={() => setThongBao(null)} /> : null}

        <ThanhTab
          active={tab}
          menuOpen={menuMo}
          onSelect={(id) => {
            setThongBao(null);
            setTab(id);
          }}
          onCreate={() => {
            setThongBao(null);
            setMenuMo((open) => !open);
          }}
        />
      </View>

      {menuMo ? <MenuTao onPick={chonTao} onClose={() => setMenuMo(false)} /> : null}
    </SafeAreaView>
  );
}

/** Says why nothing happened, above the bar that was just pressed. */
function BangThongBao({ text, onClose }: { text: string; onClose: () => void }) {
  const c = usePalette();
  return (
    <View
      accessibilityRole="alert"
      style={{
        marginHorizontal: space.md,
        marginBottom: space.sm,
        padding: space.sm,
        borderRadius: radius.control,
        backgroundColor: c.card,
        borderColor: c.line,
        borderWidth: 1,
        flexDirection: "row",
        alignItems: "center",
        gap: space.sm,
      }}
    >
      <Text style={{ ...type.label, color: c.inkSoft, flex: 1 }}>{text}</Text>
      <Text
        accessibilityRole="button"
        onPress={onClose}
        style={{ ...type.label, fontWeight: "700", color: c.accent, paddingHorizontal: space.xs }}
      >
        Ẩn
      </Text>
    </View>
  );
}
