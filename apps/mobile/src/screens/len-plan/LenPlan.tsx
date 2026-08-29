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
  docDanhSachBuoiDi,
  luuDongThoiGian,
  taoBuoiDi,
  thongDiepNguoiDoc,
  type Attempt,
} from "../../api";
import type { DemoPerson } from "../../navigation/nhom-demo";
import { khoiDongNhom, type NhomState } from "../chat/nhom";
import { space, type, usePalette } from "../../theme";
import { Button, Card, Screen } from "../../ui/Kit";
import { CoLoi, DangTai, TrongRong } from "../../ui/TrangThai";
import {
  nhanKhoangNgay,
  nhanNganSach,
  type BodyTaoBuoiDi,
  type BuoiDi,
  type ChangGui,
} from "./buoi-di";
import { DongThoiGian } from "./DongThoiGian";
import { TaoBuoiDi } from "./TaoBuoiDi";

type NhomMan = { kind: "dang-tai" } | { kind: "chua-chon" } | NhomState;
type DsMan =
  | { kind: "dang-tai" }
  | { kind: "xong"; outings: BuoiDi[] }
  | { kind: "loi"; loi: string };

type CuaSo = { pha: "ds" } | { pha: "tao" } | { pha: "tg"; buoi: BuoiDi };

export function LenPlan({ nguoi }: { nguoi: DemoPerson | null }) {
  const [nhom, setNhom] = useState<NhomMan>(nguoi ? { kind: "dang-tai" } : { kind: "chua-chon" });
  const [ds, setDs] = useState<DsMan>({ kind: "dang-tai" });
  const [cuaSo, setCuaSo] = useState<CuaSo>({ pha: "ds" });
  const [busy, setBusy] = useState(false);
  const [loiGhi, setLoiGhi] = useState<string | null>(null);
  const soLanThu = useRef<Record<string, Attempt>>({});

  const taiNhom = useCallback(() => {
    if (!nguoi) {
      setNhom({ kind: "chua-chon" });
      return;
    }
    let huy = false;
    setNhom({ kind: "dang-tai" });
    khoiDongNhom(nguoi.id).then((s) => {
      if (!huy) setNhom(s);
    });
    return () => {
      huy = true;
    };
  }, [nguoi]);

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

function TheBuoi({ buoi, onMo }: { buoi: BuoiDi; onMo: () => void }) {
  const c = usePalette();
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
      </Card>
    </Pressable>
  );
}
