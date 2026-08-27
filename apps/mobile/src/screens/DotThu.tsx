/** The collection board. This is the centre of the product, not the split.
 *
 * Spec section 8.1: splitting is arithmetic, collecting is the part that
 * actually costs people something. So this screen counts transfers, not money,
 * and it counts them the way section 8.7 says: transfers first, people second,
 * because one person paying two different recipients breaks a per-person count.
 */
import React from "react";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { radius, space, type, usePalette } from "../theme";
import { Button, Card, Screen } from "../ui/Kit";

export type Obligation = {
  id: string;
  sender: string;
  recipient: string;
  amountVnd: number;
  status: "outstanding" | "partially_confirmed" | "confirmed" | "over_confirmed" | "waived" | "disputed";
};

const TRANSFERRED = new Set(["confirmed", "over_confirmed"]);
const NOTHING_LEFT = new Set([...TRANSFERRED, "waived"]);

const WORDING: Record<Obligation["status"], string> = {
  outstanding: "chưa gửi",
  partially_confirmed: "gửi một phần",
  confirmed: "đã nhận",
  over_confirmed: "nhận dư",
  waived: "được bỏ qua",
  disputed: "đang thắc mắc",
};

export function DotThu({ obligations, published, onPublish, onShare }: {
  obligations: Obligation[]; published: boolean;
  onPublish: () => void; onShare: () => void;
}) {
  const c = usePalette();
  const done = obligations.filter((o) => TRANSFERRED.has(o.status)).length;
  const senders = new Set(obligations.map((o) => o.sender));
  const peopleDone = [...senders].filter((s) =>
    obligations.filter((o) => o.sender === s).every((o) => NOTHING_LEFT.has(o.status))
  ).length;

  return (
    <Screen
      title="Đợt thu"
      hint={published ? "Đã phát. Ai cũng xem được phần của mình." : "Chưa phát. Chưa ai bị nhắn gì."}
      footer={
        published
          ? <Button label="Chia sẻ cho từng người" onPress={onShare} />
          : <Button label="Phát đợt thu" onPress={onPublish} />
      }
    >
      <Card>
        {/* Transfers is the headline number; people is the secondary read. */}
        <Text style={{ ...type.amount, color: c.ink }}>
          {done}/{obligations.length}
          <Text style={{ ...type.body, color: c.inkSoft }}>  lượt chuyển xong</Text>
        </Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {peopleDone}/{senders.size} người đã xong toàn bộ
        </Text>
      </Card>

      <ScrollView contentContainerStyle={{ gap: space.sm }}>
        {obligations.map((o) => {
          const settled = TRANSFERRED.has(o.status);
          const flagged = o.status === "disputed";
          return (
            <View
              key={o.id}
              style={{
                backgroundColor: c.card, borderColor: flagged ? c.warn : c.line,
                borderWidth: 1, borderRadius: radius.base,
                padding: space.md, flexDirection: "row",
                justifyContent: "space-between", alignItems: "center", gap: space.sm,
              }}
            >
              <View style={{ flexShrink: 1, gap: 2 }}>
                <Text style={{ ...type.body, color: c.ink }}>
                  {o.sender} <Text style={{ color: c.inkSoft }}>gửi</Text> {o.recipient}
                </Text>
                <Text style={{ ...type.label, color: flagged ? c.warn : settled ? c.accent : c.inkSoft }}>
                  {WORDING[o.status]}
                </Text>
              </View>
              <Text style={{ ...type.amountSmall, color: settled ? c.accent : c.ink }}>
                {formatVnd(o.amountVnd)}đ
              </Text>
            </View>
          );
        })}
      </ScrollView>
    </Screen>
  );
}
