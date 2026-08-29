/** F13. Name the trip, pick the days, say how many people, write a
 *  reference budget. Nothing here is a cap and nothing here is teal:
 *  nobody owes this number, a person typed it.
 */
import React, { useState } from "react";
import { ScrollView, Text } from "react-native";
import { space, type, usePalette } from "../../theme";
import { Button, Card, Field, Screen } from "../../ui/Kit";
import {
  kiemTraTaoBuoiDi,
  nhanNganSach,
  type BodyTaoBuoiDi,
  type FormTaoBuoiDi,
} from "./buoi-di";

const FORM_TRONG: FormTaoBuoiDi = {
  title: "",
  starts_on: "",
  ends_on: "",
  headcount: "",
  nganSach: "",
};

export function TaoBuoiDi({
  banDau,
  busy,
  loiMayChu,
  onTao,
  onHuy,
}: {
  banDau?: Partial<FormTaoBuoiDi>;
  busy?: boolean;
  loiMayChu?: string;
  onTao: (body: BodyTaoBuoiDi) => void;
  onHuy: () => void;
}) {
  const c = usePalette();
  const [form, setForm] = useState<FormTaoBuoiDi>({ ...FORM_TRONG, ...banDau });
  const [loi, setLoi] = useState<string | null>(null);

  const set = <K extends keyof FormTaoBuoiDi>(key: K, value: FormTaoBuoiDi[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const nganSachXem = kiemTraTaoBuoiDi(form);
  const nganSachChu =
    nganSachXem.ok ? nhanNganSach(nganSachXem.body.budget_per_person_vnd) : null;

  function gui() {
    const kq = kiemTraTaoBuoiDi(form);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    onTao(kq.body);
  }

  const thongBao = loiMayChu ?? loi;

  return (
    <Screen
      title="Tạo chuyến"
      hint="Tên, khoảng ngày, số người, và ngân sách tham chiếu."
      footer={
        <>
          <Button
            label={busy ? "Đang tạo…" : "Tạo chuyến"}
            disabled={busy}
            onPress={gui}
          />
          <Button label="Huỷ" tone="quiet" disabled={busy} onPress={onHuy} />
        </>
      }
    >
      <ScrollView
        contentContainerStyle={{ gap: space.md, paddingBottom: space.sm }}
        keyboardShouldPersistTaps="handled"
      >
        <Card>
          <Field
            label="Tên chuyến"
            value={form.title}
            onChangeText={(t) => set("title", t)}
            placeholder="Đà Lạt cuối tuần"
            onSubmitEditing={gui}
          />
          <Field
            label="Ngày bắt đầu"
            value={form.starts_on}
            onChangeText={(t) => set("starts_on", t)}
            placeholder="2026-09-07"
          />
          <Field
            label="Ngày kết thúc"
            value={form.ends_on}
            onChangeText={(t) => set("ends_on", t)}
            placeholder="2026-09-08"
          />
        </Card>

        <Card>
          <Field
            label="Số người"
            value={form.headcount}
            onChangeText={(t) => set("headcount", t)}
            keyboardType="number-pad"
            placeholder="7"
          />
          <Field
            label="Ngân sách mỗi người"
            value={form.nganSach}
            onChangeText={(t) => set("nganSach", t)}
            keyboardType="number-pad"
            placeholder="2500000"
          />
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Số tham chiếu, không phải giới hạn. Vượt cũng không sao.
          </Text>
          {nganSachChu ? (
            <Text style={{ ...type.amountSmall, color: c.ink }}>{nganSachChu}</Text>
          ) : null}
        </Card>

        {thongBao ? (
          <Text style={{ ...type.label, color: c.ink }}>{thongBao}</Text>
        ) : null}
      </ScrollView>
    </Screen>
  );
}
