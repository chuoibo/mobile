/** F15. The timeline the group built, in clock order, plus a form to add
 *  a stop. Lead tone is accent: a person typed these times, the machine
 *  did not invent them, and nobody is settling a bill.
 */
import React, { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Field, Screen } from "../../ui/Kit";
import {
  daCheckIn,
  kiemTraChang,
  nhanDaToi,
  nhanKhoangNgay,
  nhanNganSach,
  nhomCheckInTheoChang,
  sapXepChang,
  tongDuKien,
  type BuoiDi,
  type ChangGui,
  type CheckIn,
} from "./buoi-di";
import { formatVnd } from "../../../../../packages/shared/money.mjs";

const CHANG_TOI_DA = 50;
const NHAN_TOI_DA = 200;

export function DongThoiGian({
  buoi,
  busy,
  loi,
  checkins = [],
  toiId = null,
  onCheckIn,
  onMoi,
  onLuu,
  onQuayLai,
}: {
  buoi: BuoiDi;
  busy?: boolean;
  loi?: string;
  /** F46. Every arrival on this outing, ungrouped. */
  checkins?: readonly CheckIn[];
  /** Who is looking, so their own stops can say so instead of offering the
   *  button again. Null when the app has not identified anybody yet. */
  toiId?: string | null;
  /** Omitted when check-in is not available (no group handle, no identity),
   *  which is what hides the button rather than showing a dead one. */
  onCheckIn?: (stopId: string) => void;
  /** F14. Opens the invite screen for THIS trip. Omitted for the same reason
   *  `onCheckIn` is: inviting needs a group handle and an identity, and a
   *  button that cannot post is worse than no button. */
  onMoi?: () => void;
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
  const theoChang = nhomCheckInTheoChang(checkins);

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
        {/* No second "back" here. `Screen` pins the footer outside the
            scroller, so "Quay lại danh sách" is on screen the whole time; a
            link above the card as well put two back affordances in the tab
            order and made a screen reader announce the same destination
            twice. */}
        <Card>
          <TheChuyen buoi={buoi} tong={tong} />
          {/* F14. Inside the trip card rather than down beside "Thêm chặng":
              rủ thêm người is something you decide while looking at who is
              going and what it costs each of them, and those two numbers are
              the two lines directly above this button. */}
          {onMoi ? (
            <View style={{ alignSelf: "flex-start", marginTop: space.xs }}>
              <Button label="Mời thêm người vào chuyến" tone="quiet" onPress={onMoi} />
            </View>
          ) : null}
        </Card>

        {theoGio.length === 0 ? (
          <Text style={{ ...type.body, color: c.inkSoft }}>
            Chưa có chặng nào. Thêm giờ và việc làm ở dưới.
          </Text>
        ) : (
          <View style={{ gap: 0 }}>
            {theoGio.map((ch, i) => (
              <HangChang
                key={ch.id}
                at={ch.at}
                label={ch.label}
                placeName={ch.place_name}
                cuoi={i === theoGio.length - 1}
                checkins={theoChang[ch.id] ?? []}
                daToi={daCheckIn(theoChang[ch.id] ?? [], toiId)}
                busy={busy}
                onCheckIn={onCheckIn ? () => onCheckIn(ch.id) : undefined}
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
    // Neither the trip name nor the date range is repeated here: `Screen`
    // already prints both as the heading and its hint, and rendering them
    // again put the same two lines on screen twice, once inside a card that
    // is supposed to carry what the heading does NOT say.
    <View style={{ gap: space.xs }}>
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
  checkins,
  daToi,
  busy,
  onCheckIn,
}: {
  at: string;
  label: string;
  placeName: string | null;
  cuoi: boolean;
  checkins: readonly CheckIn[];
  daToi: boolean;
  busy?: boolean;
  onCheckIn?: () => void;
}) {
  const c = usePalette();
  const daToiText = nhanDaToi(checkins);
  // A reached stop fills its dot. The line already carries the words, so this
  // is redundancy for people scanning the shape of the plan rather than
  // reading it -- never the only way the state is announced.
  const coNguoiToi = checkins.length > 0;
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
            backgroundColor: coNguoiToi ? c.accent : "transparent",
            borderWidth: coNguoiToi ? 0 : 2,
            borderColor: c.accent,
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
        {daToiText ? (
          <Text style={{ ...type.label, color: c.accent }}>{daToiText}</Text>
        ) : null}
        {onCheckIn ? (
          <View style={{ alignSelf: "flex-start", marginTop: space.xs }}>
            <Button
              label={daToi ? "Bạn đã tới" : "Đã tới"}
              tone="quiet"
              disabled={daToi || busy}
              onPress={onCheckIn}
            />
          </View>
        ) : null}
      </View>
    </View>
  );
}
