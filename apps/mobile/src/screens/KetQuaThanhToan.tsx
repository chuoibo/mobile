/** Settlement: who owes how much, who pays whom, and whose code is showing.
 *
 * Every dong on this screen arrived from the server. The only arithmetic
 * here is adding the allocation map to print the bill total -- the same
 * integers the server already sent, read down the column, never split and
 * never rounded. A stale or locally recomputed figure would be a money
 * error, not a display one. The QR payload is not this file's either:
 * `renderMaQr` is injected so the parent can place a code without this
 * screen knowing a bank account exists.
 */
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { labelFor, labelInGroup, type GroupMember, type Roster } from "../participants";
import { radius, space, type, usePalette } from "../theme";
import { toggleState } from "../ui/a11y";
import { Button, Card, Row } from "../ui/Kit";
import type { Envelope } from "./ChiaSe";
import type { Obligation } from "./DotThu";

const HIT = 44;
const INITIAL = space.lg;

export function KetQuaThanhToan(props: {
  roster: Roster;
  /** The group's active membership, for the senders the bill does not hold.
   *  An envelope is answered by the server in ids, so labelling one against
   *  the bill alone prints a UUID at a person -- bug-050923, one screen over. */
  nhom: GroupMember[];
  allocations: Record<string, number>;
  obligations: Obligation[];
  envelopes: Envelope[];
  advancerId: string;
  itemCount: number;
  nguoiDangChon: string | null;
  onChonNguoi: (senderId: string) => void;
  renderMaQr: (senderId: string) => React.ReactNode;
  onShare: () => void;
  onDone: () => void;
  onBack: () => void;
}): React.JSX.Element {
  const c = usePalette();
  const {
    roster, nhom, allocations, obligations, envelopes, itemCount, nguoiDangChon, advancerId,
  } = props;

  // Integer add of the server's own figures. Not a split: the split already
  // happened on the server; this is the same numbers, summed.
  let tong = 0;
  for (const amount of Object.values(allocations)) tong += amount;

  const people = roster.participants.filter((person) => allocations[person.id] !== undefined);
  // Counted from the rows actually drawn, not from the roster. If the server
  // allocated to fewer people than the roster holds, "4 người" over three rows
  // is the screen disagreeing with itself about whose dinner this was.
  const soNguoi = people.length;

  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        <Pressable
          onPress={props.onBack}
          accessibilityRole="button"
          accessibilityLabel="Quay lại gợi ý chia"
          style={{ minWidth: HIT, minHeight: HIT, justifyContent: "center" }}
        >
          <Text style={{ ...type.title, color: c.ink }}>←</Text>
        </Pressable>
        <Text
          style={{ ...type.title, color: c.ink, flex: 1, textAlign: "center" }}
          numberOfLines={1}
        >
          Kết quả thanh toán
        </Text>
        {/* Same width as the back control so the title sits on the real centre,
            not the leftover after the arrow. */}
        <View style={{ minWidth: HIT }} />
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }}
      >
        <View style={{ alignItems: "center", gap: space.xs }}>
          <Text style={{ ...type.label, color: c.inkSoft }}>Tổng hoá đơn</Text>
          <Text style={{ ...type.amount, color: c.ink }}>{formatVnd(tong)}đ</Text>
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            {itemCount} món · {soNguoi} người
          </Text>
        </View>

        {/* The code comes before the two detail cards, and the mockup draws it
            after them. The mockup is not wrong; it is drawn at a size where all
            four blocks fit at once, and this screen is not. Measured on the web
            export at 390x844: 893pt of content in a 609pt scroller, with the
            code block landing at y=728 and 116 of its 196pt inside the
            viewport. A person arriving here saw 59% of a QR code and had to
            scroll before a banking app could see the rest of it.
            Something has to be below the fold on this screen. The choice is
            which, and the answer is the two cards that can be read a line at a
            time rather than the one block that is useless when cropped. The
            cards keep their own relative order, and enough of the first one
            shows under the code to say the screen continues. */}
        <View style={{ gap: space.sm, alignItems: "stretch" }}>
          <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
            Quét để thanh toán
          </Text>
          {envelopes.length > 1 ? (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              // `flexGrow: 0` is load-bearing: a horizontal ScrollView carries
              // `flex: 1` in its own base style and would otherwise stretch
              // down the page instead of hugging this chip row.
              style={{ flexGrow: 0, flexShrink: 0 }}
              contentContainerStyle={{ gap: space.xs, alignItems: "center" }}
            >
              <View
                accessibilityRole="radiogroup"
                aria-label="Người chuyển"
                style={{ flexDirection: "row", gap: space.xs }}
              >
                {envelopes.map((envelope) => {
                  const on = envelope.senderId === nguoiDangChon;
                  // `labelInGroup`, not `labelFor`: this id was chosen by the
                  // server, not by walking the roster above, so the bill is
                  // the wrong list to be sure it is in. `labelFor` hands the
                  // id straight back when it cannot place one, which put a
                  // UUID on the chip a person taps to find their own code.
                  const name = labelInGroup(roster, nhom, envelope.senderId);
                  return (
                    <Pressable
                      key={envelope.senderId}
                      onPress={() => props.onChonNguoi(envelope.senderId)}
                      // A chip row where exactly one is on is a radio group.
                      // `role="button"` with `selected` is invalid on both
                      // platforms and is dropped before the DOM on this one;
                      // `toggleState` is the pairing that actually arrives.
                      {...toggleState("radio", on)}
                      accessibilityLabel={name}
                      style={{
                        minHeight: HIT,
                        paddingHorizontal: space.md,
                        borderRadius: radius.pill,
                        borderWidth: 1,
                        borderColor: on ? c.split : c.line,
                        backgroundColor: on ? c.split : c.card,
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Text
                        style={{
                          ...type.body,
                          fontWeight: on ? "600" : "400",
                          color: on ? c.splitInk : c.ink,
                        }}
                      >
                        {name}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </ScrollView>
          ) : null}
          {nguoiDangChon !== null ? (
            props.renderMaQr(nguoiDangChon)
          ) : (
            <Text style={{ ...type.body, color: c.inkSoft, textAlign: "center" }}>
              Chưa phát đợt thu nên chưa có mã.
            </Text>
          )}
        </View>

        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Số tiền mỗi người phải trả</Text>
          <View>
            {people.map((person, index) => {
              const amount = allocations[person.id];
              return (
                <View
                  key={person.id}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: space.sm,
                    paddingVertical: space.sm,
                    borderBottomWidth: index < people.length - 1 ? 1 : 0,
                    borderBottomColor: c.line,
                  }}
                >
                  <View
                    style={{
                      width: INITIAL,
                      height: INITIAL,
                      borderRadius: radius.pill,
                      backgroundColor: c.splitSoft,
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Text style={{ ...type.micro, color: c.split }}>{initial(person.name)}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ ...type.body, color: c.ink }} numberOfLines={1}>
                      {labelFor(roster, person.id)}
                    </Text>
                    {/* The person who fronted the money is in this list for
                        their share, which is not money they transfer to
                        anybody. Saying so here stops the row being read as a
                        fifth debt sitting under four real ones. */}
                    {person.id === advancerId ? (
                      <Text style={{ ...type.micro, color: c.inkFaint }}>đã ứng tiền</Text>
                    ) : null}
                  </View>
                  <Text style={{ ...type.amountSmall, color: c.split, textAlign: "right" }}>
                    {formatVnd(amount)}đ
                  </Text>
                </View>
              );
            })}
          </View>
        </Card>

        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Chuyển khoản</Text>
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            Ai chuyển cho ai, theo sổ của máy chủ
          </Text>
          {obligations.length === 0 ? (
            <Text style={{ ...type.body, color: c.inkSoft }}>Không ai phải chuyển cho ai.</Text>
          ) : (
            obligations.map((row) => (
              <Row
                key={row.id}
                left={`${row.senderName} trả cho ${row.recipient}`}
                right={`${formatVnd(row.amountVnd)}đ`}
              />
            ))
          )}
        </Card>
      </ScrollView>

      <View style={{ flexDirection: "row", gap: space.sm }}>
        <View style={{ flex: 1 }}>
          <Button label="Chia sẻ kết quả" tone="ghost" onPress={props.onShare} />
        </View>
        <View style={{ flex: 1 }}>
          <Button label="Hoàn tất" tone="split" onPress={props.onDone} />
        </View>
      </View>
    </View>
  );
}

function initial(name: string): string {
  const trimmed = name.trim();
  if (trimmed === "") return "?";
  return trimmed.charAt(0).toUpperCase();
}
