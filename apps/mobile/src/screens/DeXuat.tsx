/** The proposal. Nothing is in the ledger until someone confirms here.
 *
 * Spec section 3: AI and automation produce typed proposals; a deterministic
 * executor runs only after the right person confirms. This screen is that
 * moment, so it shows the whole allocation rather than a summary.
 */
import React from "react";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { space, type, usePalette } from "../theme";
import { Button, Card, Row, Screen } from "../ui/Kit";

export type Proposal = {
  allocations: Record<string, number>;
  roundingGainers: string[];
  totalVnd: number;
  advancer: string;
  occasion: string;
};

export function DeXuat({ proposal, onConfirm, onBack }: {
  proposal: Proposal; onConfirm: () => void; onBack: () => void;
}) {
  const c = usePalette();
  const names = Object.keys(proposal.allocations).sort();
  const owed = names.filter((n) => n !== proposal.advancer && proposal.allocations[n] > 0);

  return (
    <Screen
      title={`Chia ${proposal.occasion}`}
      hint={`${proposal.advancer} đã trả trước ${formatVnd(proposal.totalVnd)}đ.`}
      footer={
        <>
          <Button label="Đúng rồi, ghi vào sổ" onPress={onConfirm} />
          <Button label="Sửa lại" tone="quiet" onPress={onBack} />
        </>
      }
    >
      <ScrollView contentContainerStyle={{ gap: space.md }}>
        <Card>
          {names.map((name) => (
            <Row
              key={name}
              left={name === proposal.advancer ? `${name} (trả trước)` : name}
              right={`${formatVnd(proposal.allocations[name])}đ`}
              muted={name === proposal.advancer}
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
              Chia không hết chẵn. {proposal.roundingGainers.join(", ")} chịu thêm 1đ lẻ,
              vì {proposal.advancer === proposal.roundingGainers[0] ? "là người trả trước" : "theo thứ tự cố định"}.
            </Text>
          </Card>
        ) : null}

        <Card>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            {owed.length} người sẽ cần gửi tiền cho {proposal.advancer}.
            Chưa ai bị nhắn gì cho tới khi bạn phát đợt thu.
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
}
