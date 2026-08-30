/** Lên plan: the group's outings, and the door into creating one.
 *
 * Group membership is a real row. `CONTEXT_ID` in api.ts has never had one,
 * so this screen opens the group the same way chat does, through
 * `khoiDongNhom`, then lists and writes against that id.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import {
  ApiError,
  attemptFor,
  BASE_URL,
  checkInChang,
  docCheckIn,
  docDanhSachBuoiDi,
  luuDongThoiGian,
  taoBuoiDi,
  thongDiepNguoiDoc,
  type Attempt,
} from "../../api";
import type { DemoPerson } from "../../navigation/nhom-demo";
import { moNhomChoMan, type NhomPhien, type NhomState } from "../chat/nhom";
// The recap read, imported rather than re-implemented. `ky-uc.ts` sets the
// precedent by importing `khoaGhi` out of the chat lane for the same reason: a
// second copy of a route call is a copy that drifts the day the route changes.
// What is deliberately NOT imported is that file's money formatter, which the
// two screens keep separately on purpose (see its header).
import { layKyUc } from "../ky-niem/ky-uc";
import { space, type, usePalette } from "../../theme";
import { Button, Card, Screen } from "../../ui/Kit";
import { CoLoi, DangTai, TrongRong } from "../../ui/TrangThai";
import {
  nhanKhoangNgay,
  nhanNganSach,
  type BodyTaoBuoiDi,
  type BuoiDi,
  type ChangGui,
  type CheckIn,
} from "./buoi-di";
import {
  doNganSach,
  nguonDaTieu,
  nhanDaTieu,
  nhanKetLuan,
  type NguonDaTieu,
} from "./ngan-sach";
import { DongThoiGian } from "./DongThoiGian";
import { TaoBuoiDi } from "./TaoBuoiDi";

type NhomMan = { kind: "dang-tai" } | { kind: "chua-chon" } | NhomState;
type DsMan =
  | { kind: "dang-tai" }
  | { kind: "xong"; outings: BuoiDi[] }
  | { kind: "loi"; loi: string };

type CuaSo = { pha: "ds" } | { pha: "tao" } | { pha: "tg"; buoi: BuoiDi };
/** F34. How the recap read went. A failed read is its own case rather than an
 *  empty map, because an empty map means "no trip has finished" and that is a
 *  sentence this screen prints. */
type SoDaTieu = { kind: "xong"; theo: ReadonlyMap<string, number> } | { kind: "loi" };

export function LenPlan({ nguoi, nhomPhien }: {
  nguoi: DemoPerson | null;
  /** The group this session opened, from `VoTab`. Same prop, same reason and
   *  same required-not-optional argument as `TinNhan` -- an outing planned in
   *  one group and a conversation held in another is not a plan. */
  nhomPhien: NhomPhien | null;
}) {
  const [nhom, setNhom] = useState<NhomMan>(nguoi ? { kind: "dang-tai" } : { kind: "chua-chon" });
  const [ds, setDs] = useState<DsMan>({ kind: "dang-tai" });
  const [cuaSo, setCuaSo] = useState<CuaSo>({ pha: "ds" });
  const [busy, setBusy] = useState(false);
  const [loiGhi, setLoiGhi] = useState<string | null>(null);
  // F46. Arrivals for the outing currently open, refetched when it opens and
  // after each check-in. Kept beside the outing rather than inside it because
  // the server returns them from a separate route -- folding them into `BuoiDi`
  // would make every list read look like it carried arrivals when it does not.
  const [checkins, setCheckins] = useState<CheckIn[]>([]);
  // F34. Spend per outing, read from the ledger through the recap route and
  // keyed by outing id. Never merged into `BuoiDi`: the outings list route does
  // not carry a spend figure, and folding one in would make every read look
  // like it had money in it when only the recap does.
  const [daTieu, setDaTieu] = useState<SoDaTieu>({ kind: "xong", theo: new Map() });
  const soLanThu = useRef<Record<string, Attempt>>({});

  const taiNhom = useCallback(() => {
    if (!nguoi) {
      setNhom({ kind: "chua-chon" });
      return;
    }
    let huy = false;
    setNhom({ kind: "dang-tai" });
    moNhomChoMan(nguoi, nhomPhien).then((s) => {
      if (!huy) setNhom(s);
    });
    return () => {
      huy = true;
    };
  }, [nguoi, nhomPhien]);

  useEffect(() => taiNhom(), [taiNhom]);

  const taiDs = useCallback(() => {
    if (!nguoi || nhom.kind !== "xong") return;
    let huy = false;
    setDs({ kind: "dang-tai" });
    docDanhSachBuoiDi(nhom.contextId, nguoi.personId)
      .then((page) => {
        if (!huy) setDs({ kind: "xong", outings: page.outings });
      })
      .catch((err) => {
        if (huy) return;
        setDs({
          kind: "loi",
          loi: err instanceof ApiError ? err.message : thongDiepNguoiDoc(0, null),
        });
      });
    return () => {
      huy = true;
    };
  }, [nguoi, nhom]);

  useEffect(() => taiDs(), [taiDs]);

  // F34. The spend side of "đã tiêu X / ngân sách Y". Read separately from the
  // outings list because it comes from a separate route, and read at all only
  // because money law 2 forbids the alternative: the phone could add the
  // group's expenses up itself, and then this screen and Cá nhân would be two
  // implementations of one sum, disagreeing about one dinner.
  //
  // A failure here does not take the list down. A trip you can still open and
  // plan is worth more than a blank screen, and the card says in words that the
  // spend figure is the part that is missing.
  useEffect(() => {
    if (!nguoi || nhom.kind !== "xong") return;
    let huy = false;
    const contextId = nhom.contextId;
    layKyUc(contextId, nguoi.personId)
      .then((ky) => {
        if (huy) return;
        const theo = new Map<string, number>();
        for (const chuyen of ky.outings) theo.set(chuyen.outing_id, chuyen.split_total_vnd);
        setDaTieu({ kind: "xong", theo });
      })
      .catch(() => {
        if (!huy) setDaTieu({ kind: "loi" });
      });
    return () => {
      huy = true;
    };
  }, [nguoi, nhom]);

  // F46. Read arrivals when a timeline opens, and clear them when it closes so
  // the next outing cannot briefly render the previous one's check-ins.
  const buoiDangMo = cuaSo.pha === "tg" ? cuaSo.buoi.id : null;
  const contextId = nhom.kind === "xong" ? nhom.contextId : null;
  useEffect(() => {
    if (!buoiDangMo || !contextId || !nguoi) {
      setCheckins([]);
      return;
    }
    let huy = false;
    docCheckIn(buoiDangMo, nguoi.personId, contextId)
      .then((r) => {
        if (!huy) setCheckins(r.checkins);
      })
      // A timeline that cannot show arrivals is still a usable timeline, so
      // this failure does not take the screen down with it.
      .catch(() => {
        if (!huy) setCheckins([]);
      });
    return () => {
      huy = true;
    };
  }, [buoiDangMo, contextId, nguoi]);

  async function tao(body: BodyTaoBuoiDi) {
    if (!nguoi || nhom.kind !== "xong") return;
    setBusy(true);
    setLoiGhi(null);
    try {
      const moi = await taoBuoiDi(
        nhom.contextId,
        body,
        nguoi.personId,
        attemptFor(soLanThu.current, `tao-buoi:${body.title}:${body.starts_on}:${body.ends_on}`),
      );
      setCuaSo({ pha: "tg", buoi: moi });
      setDs((truoc) =>
        truoc.kind === "xong"
          ? { kind: "xong", outings: [moi, ...truoc.outings] }
          : { kind: "xong", outings: [moi] },
      );
    } catch (err) {
      setLoiGhi(err instanceof ApiError ? err.message : "Chưa tạo được chuyến. Thử lại sau một chút.");
    } finally {
      setBusy(false);
    }
  }

  async function luu(stops: ChangGui[]) {
    if (!nguoi || nhom.kind !== "xong" || cuaSo.pha !== "tg") return;
    setBusy(true);
    setLoiGhi(null);
    try {
      const capNhat = await luuDongThoiGian(
        cuaSo.buoi.id,
        stops,
        nguoi.personId,
        attemptFor(soLanThu.current, `timeline:${cuaSo.buoi.id}:${JSON.stringify(stops)}`),
        nhom.contextId,
      );
      setCuaSo({ pha: "tg", buoi: capNhat });
      setDs((truoc) =>
        truoc.kind === "xong"
          ? {
              kind: "xong",
              outings: truoc.outings.map((o) => (o.id === capNhat.id ? capNhat : o)),
            }
          : truoc,
      );
    } catch (err) {
      setLoiGhi(
        err instanceof ApiError ? err.message : "Chưa lưu được dòng thời gian. Thử lại sau một chút.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function checkIn(stopId: string) {
    if (!nguoi || nhom.kind !== "xong" || cuaSo.pha !== "tg") return;
    setBusy(true);
    setLoiGhi(null);
    try {
      await checkInChang(
        stopId,
        nguoi.personId,
        attemptFor(soLanThu.current, `checkin:${stopId}:${nguoi.personId}`),
        nhom.contextId,
      );
      // Re-read rather than appending the created row: the list is what other
      // members have done too, and this is the moment we are already talking
      // to the server about this outing.
      const lai = await docCheckIn(cuaSo.buoi.id, nguoi.personId, nhom.contextId);
      setCheckins(lai.checkins);
    } catch (err) {
      setLoiGhi(
        err instanceof ApiError ? err.message : "Chưa ghi được check-in. Thử lại sau một chút.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (cuaSo.pha === "tao") {
    return (
      <TaoBuoiDi
        busy={busy}
        loiMayChu={loiGhi ?? undefined}
        onTao={tao}
        onHuy={() => {
          setLoiGhi(null);
          setCuaSo({ pha: "ds" });
        }}
      />
    );
  }

  if (cuaSo.pha === "tg") {
    return (
      <DongThoiGian
        buoi={cuaSo.buoi}
        busy={busy}
        loi={loiGhi ?? undefined}
        checkins={checkins}
        toiId={nguoi?.personId ?? null}
        // No group handle or no identity means no context to post into, so the
        // button is absent rather than present and failing.
        onCheckIn={nguoi && nhom.kind === "xong" ? checkIn : undefined}
        onLuu={luu}
        onQuayLai={() => {
          setLoiGhi(null);
          setCuaSo({ pha: "ds" });
        }}
      />
    );
  }

  return (
    <Screen title="Lên plan" hint="Chuyến đi của nhóm, ngày giờ và ai đi.">
      <ScrollView
        contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }}
        keyboardShouldPersistTaps="handled"
      >
        {nhom.kind === "chua-chon" ? (
          <TrongRong
            tieuDe="Chưa chọn người"
            than="Quay lại màn mở đầu và chọn một người trong nhóm. Không có người thì không biết nhóm nào để hỏi chuyến."
          />
        ) : null}

        {nhom.kind === "dang-tai" ? (
          <DangTai noiDung="Đang mở nhóm" phu="Hỏi máy chủ nhóm demo, rồi đọc danh sách chuyến." />
        ) : null}

        {nhom.kind === "hong" ? (
          <CoLoi
            tieuDe="Chưa vào được nhóm"
            than={thongDiepNguoiDoc(nhom.status, nhom.detail)}
            viecTiepTheo="Kiểm tra máy chủ đang chạy, rồi bấm thử lại."
            diaChi={nhom.url}
            onThuLai={taiNhom}
          />
        ) : null}

        {nhom.kind === "xong" && ds.kind === "dang-tai" ? (
          <DangTai noiDung="Đang đọc chuyến của nhóm" />
        ) : null}

        {nhom.kind === "xong" && ds.kind === "loi" ? (
          <CoLoi
            tieuDe="Chưa đọc được danh sách chuyến"
            than={ds.loi}
            viecTiepTheo="Bấm thử lại. Chưa có gì bị ghi sai."
            diaChi={BASE_URL}
            onThuLai={taiDs}
          />
        ) : null}

        {nhom.kind === "xong" && ds.kind === "xong" && ds.outings.length === 0 ? (
          <TrongRong
            tieuDe="Chưa có chuyến nào"
            than="Tạo chuyến đầu: đặt tên, chọn ngày, ghi số người và ngân sách tham chiếu."
            hanhDong={{ nhan: "Tạo chuyến mới", onPress: () => setCuaSo({ pha: "tao" }) }}
          />
        ) : null}

        {nhom.kind === "xong" && ds.kind === "xong"
          ? ds.outings.map((o) => (
              <TheBuoi
                key={o.id}
                buoi={o}
                nguon={nguonDaTieu(daTieu, o.id)}
                onMo={() => {
                  setLoiGhi(null);
                  setCuaSo({ pha: "tg", buoi: o });
                }}
              />
            ))
          : null}

        {nhom.kind === "xong" && ds.kind === "xong" && ds.outings.length > 0 ? (
          <Button
            label="Tạo chuyến mới"
            onPress={() => {
              setLoiGhi(null);
              setCuaSo({ pha: "tao" });
            }}
          />
        ) : null}
      </ScrollView>
    </Screen>
  );
}

export function TheBuoi({
  buoi,
  nguon,
  onMo,
}: {
  buoi: BuoiDi;
  nguon: NguonDaTieu;
  onMo: () => void;
}) {
  const c = usePalette();
  const y = doNganSach(buoi, nguon);
  return (
    <Pressable
      onPress={onMo}
      accessibilityRole="button"
      accessibilityLabel={`Mở dòng thời gian ${buoi.title}`}
      style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}
    >
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>{buoi.title}</Text>
        <Text style={{ ...type.label, color: c.inkSoft, fontVariant: ["tabular-nums"] }}>
          {nhanKhoangNgay(buoi.starts_on, buoi.ends_on)}
        </Text>
        <View
          style={{
            flexDirection: "row",
            flexWrap: "wrap",
            justifyContent: "space-between",
            gap: space.sm,
            minHeight: 44,
            alignItems: "center",
          }}
        >
          <Text style={{ ...type.body, color: c.ink, fontVariant: ["tabular-nums"] }}>
            {buoi.headcount} người
          </Text>
          <Text style={{ ...type.amountSmall, color: c.ink }}>
            {nhanNganSach(buoi.budget_per_person_vnd)}
          </Text>
        </View>

        {/* F34. Spend against budget. Sits under the per-person reference
            rather than replacing it: the reference is what the group agreed,
            and it stays legible after the trip is over and the total lands. */}
        <View
          style={{
            borderTopWidth: 1,
            borderTopColor: c.line,
            paddingTop: space.sm,
            gap: space.xs,
          }}
        >
          <Text
            style={{
              ...type.amountSmall,
              color: y.kind === "vuot" ? c.warn : c.ink,
            }}
          >
            {nhanDaTieu(y)}
          </Text>
          <Text
            style={{
              ...type.label,
              color: y.kind === "vuot" ? c.warn : c.inkSoft,
              fontWeight: y.kind === "vuot" ? "700" : "400",
            }}
          >
            {y.kind === "vuot" ? `Vượt ngân sách. ${nhanKetLuan(y)}` : nhanKetLuan(y)}
          </Text>
          {y.kind !== "chua-co-so" ? (
            // The rule the number obeys, said out loud. There is no
            // `expenses.outing_id`, so the server counts what was spent on the
            // trip's days. A dinner split three days after everyone got home
            // belongs to no trip, and somebody comparing this against their own
            // memory deserves to know that before they call it a bug.
            <Text style={{ ...type.micro, color: c.inkFaint }}>
              Tính theo các khoản chi rơi vào ngày của chuyến.
            </Text>
          ) : null}
        </View>
      </Card>
    </Pressable>
  );
}
