/** Enter one expense. The first thing an organiser does after a meal.
 *
 * Even split only, for now. Spec section 13.2 has not yet shown that typing
 * Vietnamese beats a structured form, so the form comes first and the natural
 * language path is added when there is evidence it earns its place.
 */
import React, { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { space, type, usePalette } from "../theme";
import { Button, Card, Field, Screen } from "../ui/Kit";

export type Draft = {
  participants: string[];
  totalVnd: number;
  advancer: string;
  occasion: string;
};

export function NhapKhoanChi({ onNext }: { onNext: (draft: Draft) => void }) {
  const c = usePalette();
  const [occasion, setOccasion] = useState("");
  const [names, setNames] = useState("");
  const [amount, setAmount] = useState("");
  const [advancer, setAdvancer] = useState("");

  const participants = names.split(",").map((n) => n.trim()).filter(Boolean);
  const totalVnd = Number(amount.replace(/\D/g, "")) || 0;
  const ready = participants.length > 0 && totalVnd > 0 && participants.includes(advancer.trim());

  return (
    <Screen
      title="Khoản chi mới"
      hint="Ai có mặt, hết bao nhiêu, ai trả trước."
      footer={
        <>
          {!ready && participants.length > 0 && !participants.includes(advancer.trim()) ? (
            <Text style={{ ...type.label, color: c.warn }}>
              Người trả trước phải nằm trong danh sách có mặt.
            </Text>
          ) : null}
          <Button
            label="Chia tiền"
            disabled={!ready}
            onPress={() => onNext({ participants, totalVnd, advancer: advancer.trim(), occasion: occasion.trim() || "khoản chi" })}
          />
        </>
      }
    >
      <ScrollView contentContainerStyle={{ gap: space.md }} keyboardShouldPersistTaps="handled">
        <Card>
          <Field label="Đi đâu, ăn gì" value={occasion} onChangeText={setOccasion} placeholder="bữa lẩu tối thứ bảy" />
          <Field label="Ai có mặt" value={names} onChangeText={setNames} placeholder="Hà, Nam, Quyên" />
          <Text style={{ ...type.label, color: c.inkSoft }}>Ngăn cách bằng dấu phẩy.</Text>
        </Card>

        <Card>
          <Field label="Tổng tiền" value={amount} onChangeText={setAmount} keyboardType="number-pad" placeholder="480000" />
          {totalVnd > 0 ? (
            <Text style={{ ...type.amount, color: c.ink }}>
              {formatVnd(totalVnd)}
              <Text style={{ ...type.body, color: c.inkSoft }}> đ</Text>
            </Text>
          ) : null}
        </Card>

        <Card>
          <Field label="Ai trả trước" value={advancer} onChangeText={setAdvancer} placeholder="Nam" />
          {/* Section 8.3 gate 2: nothing goes out in someone's name until they
              acknowledge it. Saying so here sets the expectation early. */}
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Người này sẽ phải xác nhận trước khi app gửi lời nhắc dưới tên họ.
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
}
