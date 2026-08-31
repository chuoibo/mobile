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
import { labelInGroup, type GroupMember } from "../participants";
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

export function DeXuat({ proposal, nhom, onConfirm, onBack, taiKhoanNhan }: {
  proposal: Proposal; onConfirm: () => void; onBack: () => void;
  /** The group's active membership, for ids this bill's roster cannot place.
   *
   *  Required rather than optional, and that is the point of the prop. An
   *  optional `nhom` with an `= []` default would let a caller drop the group
   *  and get the old behaviour back without the compiler saying anything --
   *  which is precisely how `?? id` survived four rounds of patching. Making
   *  it required means a new call site cannot forget. */
  nhom: GroupMember[];
  /** One masked line naming where the advancer's money will land, once it is
   *  known. Present only after the detour that stores it, and shown so that
   *  pressing the button that was just refused is an informed press rather than
   *  a hopeful one. Masked, never the full number: this screen is the one the
   *  organiser holds up to the table. */
  taiKhoanNhan?: string | null;
}) {
  const c = usePalette();
  // Iterate people, not allocation keys: the key is an id, and only the
  // participant list can turn it back into a name to show.
  const people = proposal.participants;
  /* Names come through `labelInGroup`, not through a `?? id` fallback.
   *
   * `roundingGainers` is `allocation.rounding_gainers` off `POST /expenses`:
   * the SERVER picks who carries the odd dong, keyed against the roster IT
   * holds. `advancerId` travels with the draft, so today both of them do
   * resolve against `proposal.participants` on the happy path -- this is the
   * shape of bug-050923 rather than a fifth live sighting of it, and it is
   * written down that way instead of being announced as a leak.
   *
   * It is still fixed, for two reasons. The fallback is a lie in the direction
   * that costs the most: it makes the screen where money enters the ledger
   * print a database key where a person's name goes, and it does it silently.
   * And the guarantee this screen wants does not depend on which call feeds
   * it -- `docChiaBill` already answers "against the roster IT has", so the
   * day anything routes that answer here the old code leaks and the new code
   * says "Thành viên". */
  const goiTen = (id: string) =>
    labelInGroup({ participants: people, advancerId: proposal.advancerId }, nhom, id);
  const advancerName = goiTen(proposal.advancerId);
  const gainerNames = proposal.roundingGainers.map(goiTen);
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

        {taiKhoanNhan ? (
          <Card style={{ backgroundColor: c.splitSoft, borderColor: c.split }}>
            <Text style={{ ...type.label, color: c.split, fontWeight: "600" }}>
              Đã ghi tài khoản nhận của {advancerName}
            </Text>
            <Text style={{ ...type.body, color: c.ink }}>{taiKhoanNhan}</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Chỉ bốn số cuối hiện ở đây. Số đầy đủ nằm trong mã QR mà người
              chuyển tiền quét.
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
