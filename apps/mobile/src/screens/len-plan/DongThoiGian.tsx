/** F15. The timeline the group built, in clock order, plus a form to add
 *  a stop. Lead tone is accent: a person typed these times, the machine
 *  did not invent them, and nobody is settling a bill.
 */
import React, { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Field, Screen } from "../../ui/Kit";
import {
  kiemTraChang,
  nhanKhoangNgay,
  nhanNganSach,
  sapXepChang,
  tongDuKien,
  type BuoiDi,
  type ChangGui,
} from "./buoi-di";
import { formatVnd } from "../../../../../packages/shared/money.mjs";

const CHANG_TOI_DA = 50;
const NHAN_TOI_DA = 200;

export function DongThoiGian({
  buoi,
  busy,
  loi,
  onLuu,
  onQuayLai,
}: {
  buoi: BuoiDi;
  busy?: boolean;
  loi?: string;
  onLuu: (stops: ChangGui[]) => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const [gio, setGio] = useState("");
  const [nhan, setNhan] = useState("");
  const [quan, setQuan] = useState("");
  const [loiForm, setLoiForm] = useState<string | null>(null);

  const theoGio = sapXepChang(buoi.stops);
  const tong = tongDuKien(buoi.budget_per_person_vnd, buoi.headcount);
  const thongBao = loi ?? loiForm;

  function themChang() {
    const kq = kiemTraChang(gio, nhan);
    if (!kq.ok) {
      setLoiForm(kq.loi);
      return;
    }
    const place = quan.trim();
    if (place.length > NHAN_TOI_DA) {
      setLoiForm("Tên quán tối đa 200 ký tự.");
      return;
    }
    if (theoGio.length >= CHANG_TOI_DA) {
      setLoiForm("Một chuyến tối đa 50 chặng.");
      return;
    }
    const dangCo: ChangGui[] = theoGio.map((s) => ({
      at: s.at,
      label: s.label,
      place_name: s.place_name,
    }));
    onLuu(
      sapXepChang([
        ...dangCo,
        {
          at: gio.trim(),
          label: nhan.trim(),
          place_name: place === "" ? null : place,
        },
      ]),
    );
    setGio("");
    setNhan("");
    setQuan("");
    setLoiForm(null);
  }

  return (
    <Screen
      title={buoi.title}
      hint={nhanKhoangNgay(buoi.starts_on, buoi.ends_on)}
      footer={
        <Button label="Quay lại danh sách" tone="quiet" onPress={onQuayLai} />
      }
    >
      <ScrollView
        contentContainerStyle={{ gap: space.md, paddingBottom: space.sm }}
        keyboardShouldPersistTaps="handled"
      >
        <Pressable
          onPress={onQuayLai}
          accessibilityRole="button"
          accessibilityLabel="Quay lại danh sách chuyến"
          style={({ pressed }) => ({
            alignSelf: "flex-start",
            minHeight: 44,
            minWidth: 44,
            justifyContent: "center",
            opacity: pressed ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "600", color: c.accent }}>
            Quay lại
          </Text>
        </Pressable>

        <Card>
          <TheChuyen buoi={buoi} tong={tong} />
        </Card>

        {theoGio.length === 0 ? (
          <Text style={{ ...type.body, color: c.inkSoft }}>
            Chưa có chặng nào. Thêm giờ và việc làm ở dưới.
          </Text>
        ) : (
          <View style={{ gap: 0 }}>
            {theoGio.map((ch, i) => (
              <HangChang
                key={`${ch.position}-${ch.at}-${ch.label}`}
                at={ch.at}
                label={ch.label}
                placeName={ch.place_name}
                cuoi={i === theoGio.length - 1}
              />
            ))}
          </View>
        )}

        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Thêm chặng</Text>
          <Field
            label="Giờ"
            value={gio}
            onChangeText={setGio}
            placeholder="07:00"
          />
          <Field
            label="Nhãn chặng"
            value={nhan}
            onChangeText={setNhan}
            placeholder="Ăn sáng"
          />
          <Field
            label="Tên quán"
            value={quan}
            onChangeText={setQuan}
            placeholder="Lưng Chừng Cafe"
          />
          <Button
            label={busy ? "Đang lưu…" : "Thêm chặng"}
            disabled={busy || theoGio.length >= CHANG_TOI_DA}
            onPress={themChang}
          />
        </Card>

        {thongBao ? (
          <Text style={{ ...type.label, color: c.ink }}>{thongBao}</Text>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

function TheChuyen({ buoi, tong }: { buoi: BuoiDi; tong: number }) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
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
        }}
      >
        <Text style={{ ...type.body, color: c.ink, fontVariant: ["tabular-nums"] }}>
          {buoi.headcount} người
        </Text>
        <Text style={{ ...type.amountSmall, color: c.ink }}>
          {nhanNganSach(buoi.budget_per_person_vnd)}
        </Text>
      </View>
      <Text style={{ ...type.body, fontWeight: "700", color: c.ink, fontVariant: ["tabular-nums"] }}>
        Tổng dự kiến {formatVnd(tong)}đ
      </Text>
      <Text style={{ ...type.micro, color: c.inkSoft }}>
        Số tham chiếu, không phải giới hạn.
      </Text>
    </View>
  );
}

function HangChang({
  at,
  label,
  placeName,
  cuoi,
}: {
  at: string;
  label: string;
  placeName: string | null;
  cuoi: boolean;
}) {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", gap: space.sm, minHeight: 44 }}>
      <Text
        style={{
          ...type.amountSmall,
          color: c.ink,
          width: 52,
          marginTop: 2,
        }}
      >
        {at}
      </Text>
      <View style={{ width: 16, alignItems: "center" }}>
        <View
          style={{
            width: 10,
            height: 10,
            borderRadius: radius.pill,
            backgroundColor: c.accent,
            marginTop: 6,
          }}
        />
        {cuoi ? null : (
          <View style={{ flex: 1, width: 2, backgroundColor: c.line, marginTop: 2 }} />
        )}
      </View>
      <View style={{ flex: 1, gap: 2, paddingBottom: cuoi ? 0 : space.md }}>
        <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>{label}</Text>
        {placeName ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>{placeName}</Text>
        ) : null}
      </View>
    </View>
  );
}
