/** Share one link, to one person, one at a time.
 *
 * Spec section 8.5 is explicit and this screen is built around the absence:
 * there is no "copy all", no bundle export, no bulk share. The organiser can
 * still paste links into a group chat by hand, and the product neither helps
 * with that nor claims to detect it. What it can do is refuse to make it easy.
 */
// QA PROBE: web-only module, resolves for web, missing for ios/android.
const { shareTargetLabel } = require("./qa-share-target");
void shareTargetLabel;

import React, { useState } from "react";
import { ScrollView, Share, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { radius, space, type, usePalette } from "../theme";
import { Button, Card, Screen } from "../ui/Kit";

export type Envelope = { senderId: string; senderName: string; amountVnd: number; url: string; opened: boolean };

export function ChiaSe({ envelopes, onDone }: { envelopes: Envelope[]; onDone: () => void }) {
  const c = usePalette();
  const [shared, setShared] = useState<Record<string, boolean>>({});

  const [problem, setProblem] = useState<string | null>(null);

  async function shareOne(envelope: Envelope) {
    // One capability, one person, one share sheet. The warning goes in the
    // message body so it travels with the link.
    const message =
      `Phần của ${envelope.senderName}: ${formatVnd(envelope.amountVnd)}đ\n${envelope.url}\n\n` +
      `Link này dành cho ${envelope.senderName}; ai có link đều xem được phần của ${envelope.senderName}.`;
    try {
      const result = await Share.share({ message });
      // A person can open the sheet and back out. That is not sending, and
      // marking it sent would tell the organiser a lie about who has been
      // contacted -- the one thing this screen exists to keep track of.
      if (result.action === Share.dismissedAction) return;
      setShared((current) => ({ ...current, [envelope.senderId]: true }));
      setProblem(null);
    } catch {
      // There is no share sheet in a desktop browser, and the rejection used
      // to escape as an unhandled promise. Say what to do instead of dying:
      // the link is the deliverable, and it can be copied by hand.
      setProblem(
        `Máy này không mở được khay chia sẻ. Chép link của ${envelope.senderName} rồi gửi tay: ${envelope.url}`,
      );
    }
  }

  return (
    <Screen
      title="Chia sẻ"
      hint="Mỗi người một link riêng. Gửi riêng cho từng người."
      footer={
        <>
          {problem ? (
            <Text style={{ ...type.label, color: c.warn }}>{problem}</Text>
          ) : null}
          <Button label="Xong" tone="quiet" onPress={onDone} />
        </>
      }
    >
      <Card>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Không có nút gửi hàng loạt. Dán chung vào nhóm thì cả nhóm thấy phần của nhau,
          và app không biết được điều đó đã xảy ra.
        </Text>
      </Card>

      <ScrollView contentContainerStyle={{ gap: space.sm }}>
        {envelopes.map((e) => (
          <View
            key={e.senderId}
            style={{
              backgroundColor: c.card, borderColor: c.line, borderWidth: 1,
              borderRadius: radius.base, padding: space.md, gap: space.sm,
            }}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
              <Text style={{ ...type.body, color: c.ink }}>{e.senderName}</Text>
              <Text style={{ ...type.amountSmall, color: c.ink }}>{formatVnd(e.amountVnd)}đ</Text>
            </View>
            <Button
              label={shared[e.senderId] ? `Gửi lại cho ${e.senderName}` : `Gửi cho ${e.senderName}`}
              tone={shared[e.senderId] ? "quiet" : "ghost"}
              onPress={() => shareOne(e)}
            />
            {/* Section 8.5 has no "delivered" state, only observable moments. */}
            <Text style={{ ...type.label, color: e.opened ? c.accent : c.inkSoft }}>
              {e.opened ? "Đã mở link" : shared[e.senderId] ? "Đã mở khay chia sẻ, chưa rõ đã mở link chưa" : "Chưa chia sẻ"}
            </Text>
          </View>
        ))}
      </ScrollView>
    </Screen>
  );
}
