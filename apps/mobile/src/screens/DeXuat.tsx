/** The proposal. Nothing is in the ledger until someone confirms here.
 *
 * Spec section 3: AI and automation produce typed proposals; a deterministic
 * executor runs only after the right person confirms. This screen is that
 * moment, so it shows the whole allocation rather than a summary.
 */
import type { Participant } from "./NhapKhoanChi";
import React from "react";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { space, type, usePalette } from "../theme";
import { Button, Card, Row, Screen } from "../ui/Kit";

export type Proposal = {
  participants: Participant[];
  allocations: Record<string, number>;
  roundingGainers: string[];
  totalVnd: number;
  advancerId: string;
  occasion: string;
};

export function DeXuat({ proposal, onConfirm, onBack }: {
  proposal: Proposal; onConfirm: () => void; onBack: () => void;
}) {
  const c = usePalette();
  // Iterate people, not allocation keys: the key is an id, and only the
  // participant list can turn it back into a name to show.
  const people = proposal.participants;
  const advancerName =
    people.find((p) => p.id === proposal.advancerId)?.name ?? proposal.advancerId;
  // roundingGainers holds ids; ids are never shown to anyone.
  const gainerNames = proposal.roundingGainers.map(
    (id) => people.find((p) => p.id === id)?.name ?? id
  );
  const owed = people.filter(
    (p) => p.id !== proposal.advancerId && proposal.allocations[p.id] > 0
  );

  return (
    <Screen
      title={`Chia ${proposal.occasion}`}
      hint={`${advancerName} đã trả trước ${formatVnd(proposal.totalVnd)}đ.`}
      footer={
        <>
          <Button label="Đúng rồi, ghi vào sổ" onPress={onConfirm} />
          <Button label="Sửa lại" tone="quiet" onPress={onBack} />
        </>
      }
    >
      <ScrollView contentContainerStyle={{ gap: space.md }}>
        <Card>
          {people.map((person) => (
            <Row
              key={person.id}
              left={person.id === proposal.advancerId ? `${person.name} (trả trước)` : person.name}
              right={`${formatVnd(proposal.allocations[person.id])}đ`}
              muted={person.id === proposal.advancerId}
            />
          ))}
          <View style={{ height: 1, backgroundColor: c.line, marginVertical: space.xs }} />
          <Row left="Tổng" right={`${formatVnd(proposal.totalVnd)}đ`} />
        </Card>

        {/* Spec section 4 requires the rounding rule be visible, not hidden in
            a helper. A dong is trivial; an unexplained dong is not. */}
        {proposal.roundingGainers.length > 0 ? (
          <Card>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Chia không hết chẵn. {gainerNames.join(", ")} chịu thêm 1đ lẻ,
              vì {proposal.advancerId === proposal.roundingGainers[0] ? "là người trả trước" : "theo thứ tự cố định"}.
            </Text>
          </Card>
        ) : null}

        <Card>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            {owed.length} người sẽ cần gửi tiền cho {advancerName}.
            Chưa ai bị nhắn gì cho tới khi bạn phát đợt thu.
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
}
