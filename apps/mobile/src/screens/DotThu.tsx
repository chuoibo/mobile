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
import { canPublish, type PublishGates } from "../api";
import { Button, Card, Screen } from "../ui/Kit";

export type Obligation = {
  id: string;
  senderId: string;
  senderName: string;
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

export function DotThu({
  obligations, published, gates, onPublish, onShare,
}: {
  obligations: Obligation[];
  published: boolean;
  gates: PublishGates;
  onPublish: () => void;
  onShare: () => void;
}) {
  const c = usePalette();
  const ready = canPublish(gates);
  const done = obligations.filter((o) => TRANSFERRED.has(o.status)).length;
  const senders = new Set(obligations.map((o) => o.senderId));
  const peopleDone = [...senders].filter((id) =>
    obligations.filter((o) => o.senderId === id).every((o) => NOTHING_LEFT.has(o.status))
  ).length;

  return (
    <Screen
      title="Đợt thu"
      hint={published ? "Đã phát. Ai cũng xem được phần của mình." : "Chưa phát. Chưa ai bị nhắn gì."}
      footer={
        published ? (
          <Button label="Chia sẻ cho từng người" onPress={onShare} />
        ) : (
          <>
            <Button label="Phát đợt thu" disabled={!ready} onPress={onPublish} />
            {!ready ? (
              <Text style={{ ...type.label, color: c.inkSoft }}>
                Người ứng tiền chưa xác nhận. Không ai bị nhắn gì cho tới lúc đó.
              </Text>
            ) : null}
          </>
        )
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

      {/* Spec section 8.3. Both are shown even once passed: "who agreed to
          this" is a thing an organiser should be able to check later, not a
          checkbox that disappears the moment it is ticked. */}
      {!published ? (
        <Card>
          <Text style={{ ...type.label, color: c.inkSoft }}>Trước khi phát</Text>

          <View style={{ gap: 2 }}>
            <Text style={{ ...type.body, color: gates.payerAcknowledged ? c.accent : c.ink }}>
              {gates.payerAcknowledged ? "✓" : "○"} Người ứng tiền đã xác nhận
            </Text>
            {!gates.payerAcknowledged ? (
              <Text style={{ ...type.label, color: c.inkSoft }}>
                App không gửi gì dưới tên một người trước khi họ đồng ý.
              </Text>
            ) : null}
          </View>

          {/* Gate 2 is not shown as a checkbox, because this screen cannot
              know its state -- no endpoint reports it. It used to be drawn
              unticked with a button that ticked it, which is a screen making
              a claim nobody had checked. The honest version says who decides
              and lets the refusal do the talking. */}
          <View style={{ gap: 2 }}>
            <Text style={{ ...type.body, color: c.ink }}>
              Có tài khoản nhận
            </Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Máy chủ kiểm cái này lúc phát. Chưa có tài khoản nhận đã xác nhận
              thì nó từ chối và nói rõ lý do.
            </Text>
          </View>
        </Card>
      ) : null}

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
                  {o.senderName} <Text style={{ color: c.inkSoft }}>gửi</Text> {o.recipient}
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
