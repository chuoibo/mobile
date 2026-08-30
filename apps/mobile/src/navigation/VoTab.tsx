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
import { KetBan } from "../screens/ca-nhan/KetBan";
import { TinNhan } from "../screens/chat/TinNhan";
import { KhamPha } from "../screens/kham-pha/KhamPha";
import { KyNiem } from "../screens/ky-niem/KyNiem";
import { LenPlan } from "../screens/len-plan/LenPlan";
import { NhanLoiMoi } from "../screens/len-plan/NhanLoiMoi";
import { Nhom } from "../screens/vao-cua/Nhom";
import { MenuTao } from "./MenuTao";
import { ThanhTab } from "./ThanhTab";
import { useInertBackground } from "./modal";
import { CREATE_ACTIONS, DEFAULT_TAB, type CreateActionId, type CreateFlowId } from "./tabs";
import { DEMO_GROUP_NAME, type DemoPerson } from "./nhom-demo";
import type { Nhom as NhomWire } from "../screens/vao-cua/cong-api";
import type { TheBan } from "../screens/vao-cua/ma-ban";

export function VoTab({
  nguoi,
  tabDau,
  moNhomNgay,
  moKyNiemNgay,
  moBanBeNgay,
  nhomId,
  banQuetDuoc,
  diaDiemDau,
  moBanDoNgay,
  moDiemHenNgay,
  moiBuoiDi,
  renderKhoanChi,
}: {
  nguoi: DemoPerson | null;
  /** Open the F03/F04 group screen immediately, from `#vao=nhom`. It sits
   *  behind the [+] menu, so nothing that loads a URL cold can otherwise
   *  reach it -- see `lien-ket.ts` for why that is treated as a defect. */
  moNhomNgay?: boolean;
  /** Open the F30 memory wall immediately, from `#vao=ky-niem`. Same reason:
   *  it lives behind the [+] menu, so a detector run, a screenshot pass or an
   *  accessibility sweep could not reach it at all without this. */
  moKyNiemNgay?: boolean;
  /** Open the F03/F04 friend screen immediately, from `#vao=ban-be`. It sits
   *  behind a button on the Cá nhân tab, so the same rule applies. */
  moBanBeNgay?: boolean;
  /** Which group the wall should read, from `#nhom=<uuid>`. Null lets the
   *  screen find the demo group itself. */
  nhomId?: string | null;
  /** Which tab to open on, from the link that opened the app. Optional and
   *  null-tolerant so the shell keeps working for any caller that does not
   *  care; `AppRoot` passes the one named in the URL on web, so a screenshot
   *  tool can reach a tab it cannot tap. Null uses the default. */
  tabDau?: string | null;
  /** F05. A friend read off a scanned code, passed through to the group
   *  screen so the card is already filled when it opens. */
  banQuetDuoc?: TheBan | null;
  /** F46. A place id from the link, opened as a detail card so the check-in
   *  on it is reachable without a tap. Passed straight through to Khám phá. */
  diaDiemDau?: string | null;
  /** rd-fe-33. Open the group map immediately, from `#ban-do=1`. Same shape
   *  and same reason as `diaDiemDau`: it sits behind a button on Khám phá. */
  moBanDoNgay?: boolean;
  /** rd-fe-33. Open Điểm hẹn straight away, from `#ban-do=hen`. */
  moDiemHenNgay?: boolean;
  /** F14. An outing-invite token from `#moi=`. Opens the accept screen
   *  full-screen, the same way a group or a memory wall does. */
  moiBuoiDi?: string | null;
  /** The organiser flow, handed in with the way back out of it and with whoever
   *  is signed in. The person is not a decoration: the expense flow opens the
   *  group under their id (`khoiDongNhom`), and a bill has to be written into a
   *  group that exists -- filing it under a synthetic id is how every confirm
   *  in this app came back `422 participant_not_in_context`. */
  renderKhoanChi: (onExit: () => void, nguoi: DemoPerson | null) => React.ReactNode;
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
  // F30. Full screen like the two flows above, and for the same reason: it is
  // a place you go and come back from, not a tab you switch between.
  const [luongKyNiem, setLuongKyNiem] = useState(moKyNiemNgay ?? false);
  // F03/F04. Full screen for the same reason as the two above: it is a task
  // with its own steps, and it is entered from a button on Cá nhân rather than
  // from the bar, so leaving the bar underneath would offer two ways out of
  // one task.
  const [luongBanBe, setLuongBanBe] = useState(moBanBeNgay ?? false);
  const [luongLoiMoi, setLuongLoiMoi] = useState(Boolean(moiBuoiDi));
  // The group handle, lifted out of the group screen.
  //
  // It used to live inside `Nhom.tsx` and die when that screen closed, which
  // made every other tab unable to name the group the person had just opened.
  // F46 is what forced the issue: a check-in is posted to a context, and Khám
  // phá had no way to learn one. Holding it here does not make it survive a
  // reload -- there is still no storage, and `Nhom.tsx`'s header still says so
  // -- but it does make it survive closing the screen, which is the difference
  // between "the app forgot" and "the app never knew".
  const [nhom, setNhom] = useState<NhomWire | null>(null);
  // What to say when someone opens a create action that is still a shell.
  const [thongBao, setThongBao] = useState<string | null>(null);
  // The screen and the bar go inert while the [+] sheet is open, so Tab cannot
  // walk onto controls the sheet is covering.
  const nenRef = useInertBackground(menuMo);

  /** Opening a whole-screen task, one entry per flow the table can name.
   *
   *  A `Record` rather than an if-chain: `CreateFlowId` is a closed union, so
   *  adding a flow to `tabs.ts` and forgetting it here does not compile. The
   *  old chain answered a missing case with the "chưa dựng" notice, which is
   *  the same thing an unwired row shows -- a wiring mistake was
   *  indistinguishable from honest work in progress.
   */
  const moLuong: Record<CreateFlowId, () => void> = {
    "khoan-chi": () => setLuongKhoanChi(true),
    nhom: () => setLuongNhom(true),
    "ky-niem": () => setLuongKyNiem(true),
  };

  function chonTao(id: CreateActionId) {
    setMenuMo(false);
    const action = CREATE_ACTIONS.find((a) => a.id === id);
    const route = action?.route ?? null;
    if (route?.kind === "tab") {
      setTab(route.tab);
      return;
    }
    if (route?.kind === "flow") {
      moLuong[route.flow]();
      return;
    }
    setThongBao(`"${action?.label}" chưa dựng, mới có chỗ trong menu.`);
  }

  // The expense flow takes the whole screen: it is a task with its own steps,
  // and leaving the tab bar under it would offer an exit that loses a
  // half-written expense without saying so.
  if (luongLoiMoi && moiBuoiDi) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <NhanLoiMoi
          token={moiBuoiDi}
          nguoi={nguoi}
          onDong={() => setLuongLoiMoi(false)}
        />
      </SafeAreaView>
    );
  }

  if (luongKhoanChi) {
    return <>{renderKhoanChi(() => setLuongKhoanChi(false), nguoi)}</>;
  }

  if (luongNhom) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <Nhom
          nguoi={nguoi}
          nhomDangCo={nhom}
          onNhom={setNhom}
          banQuetDuoc={banQuetDuoc ?? null}
          onDong={() => setLuongNhom(false)}
        />
      </SafeAreaView>
    );
  }

  if (luongBanBe) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <KetBan nguoi={nguoi} onDong={() => setLuongBanBe(false)} />
      </SafeAreaView>
    );
  }

  if (luongKyNiem) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <KyNiem
          nguoi={nguoi}
          contextId={nhomId ?? null}
          onDong={() => setLuongKyNiem(false)}
        />
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
          {tab === "kham-pha" ? (
            <KhamPha
              nguoi={nguoi}
              nhom={nhom}
              diaDiemDau={diaDiemDau ?? null}
              moBanDoNgay={moBanDoNgay ?? false}
              moDiemHenNgay={moDiemHenNgay ?? false}
            />
          ) : null}
          {tab === "len-plan" ? <LenPlan nguoi={nguoi} /> : null}
          {tab === "tin-nhan" ? <TinNhan nguoi={nguoi} /> : null}
          {tab === "ca-nhan" ? (
            <CaNhan
              nguoi={nguoi}
              onKetBan={() => setLuongBanBe(true)}
              nhom={
                nhom
                  ? [{ id: nhom.id, name: nhom.display_name }]
                  : nhomId
                    ? [{ id: nhomId, name: DEMO_GROUP_NAME }]
                    : []
              }
            />
          ) : null}
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
