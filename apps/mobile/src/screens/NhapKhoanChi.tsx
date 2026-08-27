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
import { Button, Card, Choice, Field, Screen } from "../ui/Kit";

export type Participant = { id: string; name: string };

export type Draft = {
  participants: Participant[];
  totalVnd: number;
  advancerId: string;
  occasion: string;
};

export function NhapKhoanChi({ onNext }: { onNext: (draft: Draft) => void }) {
  const c = usePalette();
  const [occasion, setOccasion] = useState("");
  const [names, setNames] = useState("");
  const [amount, setAmount] = useState("");
  const [advancerId, setAdvancerId] = useState<string | null>(null);

  // Position in the list is the identity, not the name. Two friends called Nam
  // are two people; keying anything by name collapses them into one and the
  // second person's share silently vanishes.
  const participants: Participant[] = names
    .split(",")
    .map((n) => n.trim())
    .filter(Boolean)
    .map((name, index) => ({ id: `p${index + 1}`, name }));
  const totalVnd = Number(amount.replace(/\D/g, "")) || 0;
  const chosen = participants.some((p) => p.id === advancerId);
  const ready = participants.length > 0 && totalVnd > 0 && chosen;

  const duplicated = [
    ...new Set(
      participants
        .map((p) => p.name)
        .filter((name, i, all) => all.indexOf(name) !== i)
    ),
  ];

  return (
    <Screen
      title="Khoản chi mới"
      hint="Ai có mặt, hết bao nhiêu, ai trả trước."
      footer={
        <>
          {duplicated.length > 0 ? (
            <Text style={{ ...type.label, color: c.warn }}>
              Có hai người tên {duplicated.join(", ")}. Chia tiền vẫn đúng, nhưng
              thêm gì đó để phân biệt sẽ dễ đọc hơn — ví dụ Nam A và Nam B.
            </Text>
          ) : null}
          <Button
            label="Chia tiền"
            disabled={!ready}
            onPress={() => onNext({ participants, totalVnd, advancerId: advancerId!, occasion: occasion.trim() || "khoản chi" })}
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
          <Choice
            label="Ai trả trước"
            options={participants.map((p) => ({ id: p.id, label: p.name }))}
            value={advancerId}
            onChange={setAdvancerId}
          />
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
