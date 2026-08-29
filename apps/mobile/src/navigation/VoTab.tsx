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
import { KhamPha } from "../screens/kham-pha/KhamPha";
import { ManVo } from "./ManVo";
import { MenuTao } from "./MenuTao";
import { ThanhTab } from "./ThanhTab";
import { CREATE_ACTIONS, DEFAULT_TAB, type CreateActionId } from "./tabs";
import type { DemoPerson } from "./nhom-demo";

export function VoTab({ nguoi, renderKhoanChi }: {
  nguoi: DemoPerson | null;
  /** The organiser flow, handed in with the way back out of it. */
  renderKhoanChi: (onExit: () => void) => React.ReactNode;
}) {
  const c = usePalette();
  const scheme = useColorScheme();
  const [tab, setTab] = useState(DEFAULT_TAB);
  const [menuMo, setMenuMo] = useState(false);
  const [luongKhoanChi, setLuongKhoanChi] = useState(false);
  // What to say when someone opens a create action that is still a shell.
  const [thongBao, setThongBao] = useState<string | null>(null);

  function chonTao(id: CreateActionId) {
    setMenuMo(false);
    if (id === "tao-khoan-chi") {
      setLuongKhoanChi(true);
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

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />

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
        {tab === "tin-nhan" ? (
          <ManVo
            title="Tin nhắn"
            hint="Chat nhóm, AI gợi ý chỗ ăn ngay trong khung chat"
            screen="TinNhan"
            owner="frontend"
            work="rd-fe-03"
          />
        ) : null}
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
