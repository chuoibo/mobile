/** Enter one expense. The first thing an organiser does after a meal.
 *
 * Even split only, for now. Spec section 13.2 has not yet shown that typing
 * Vietnamese beats a structured form, so the form comes first and the natural
 * language path is added when there is evidence it earns its place.
 *
 * Two things here exist because of how the earlier version got identity and
 * amounts wrong, and both were bugs about money rather than about UI:
 *
 * 1. A participant's id used to be `p${index + 1}`, recomputed from the names
 *    string on every render. Pick "who paid" as `p2`, then insert a name above
 *    them, and `p2` is now a different person -- while the selection still
 *    looks valid, because a `p2` still exists. The advancer wins the rounding
 *    tie-break and receives every obligation, so a silent identity swap is a
 *    silent money error. Ids are now generated once, when a person is added,
 *    and never derived from position or display name.
 *
 * 2. The amount was `Number(amount.replace(/\D/g, ""))`, which accepts anything
 *    and rounds past 2^53 without saying so. Parsing now lives beside
 *    formatting in `packages/shared/money.mjs` -- one implementation, shared
 *    by every surface -- and refuses out-of-range input rather than quietly
 *    changing it.
 */
import React from "react";
import { ScrollView, Text, View } from "react-native";
import { FIXTURES } from "../api";
import {
  addParticipant,
  advancer,
  duplicateNames,
  makeIdFactory,
  removeParticipant,
  type DraftForm,
} from "../participants";
import {
  MAX_AMOUNT_VND,
  formatVnd,
  parseAmountVnd,
} from "../../../../packages/shared/money.mjs";
import { space, type, usePalette } from "../theme";
import { Button, Card, Choice, Field, Screen } from "../ui/Kit";

export type Participant = { id: string; name: string };

export type Draft = {
  participants: Participant[];
  totalVnd: number;
  advancerId: string;
  occasion: string;
};

/** Monotonic, never reused, never derived from anything the user can reorder.
 *  Module-level so ids stay unique across remounts of the screen. */
const nextParticipantId = makeIdFactory();

export function NhapKhoanChi({
  form,
  onForm,
  onNext,
}: {
  form: DraftForm;
  onForm: (next: DraftForm) => void;
  onNext: (draft: Draft) => void;
}) {
  const c = usePalette();
  const { occasion, pending, amount, roster } = form;
  const participants = roster.participants;
  const advancerId = roster.advancerId;

  const setOccasion = (value: string) => onForm({ ...form, occasion: value });
  const setPending = (value: string) => onForm({ ...form, pending: value });
  const setAmount = (value: string) => onForm({ ...form, amount: value });
  const setAdvancerId = (id: string | null) =>
    onForm({ ...form, roster: { ...roster, advancerId: id } });

  const parsed = parseAmountVnd(amount);
  const totalVnd = parsed.ok ? parsed.value : 0;
  const amountProblem = !parsed.ok && amount.trim() !== "" ? parsed.reason : null;

  const chosen = advancer(roster) !== null;
  const ready = participants.length > 0 && totalVnd > 0 && chosen;

  function addPending() {
    if (!pending.trim()) return;
    onForm({ ...form, pending: "", roster: addParticipant(roster, pending, nextParticipantId) });
  }

  function dropPerson(id: string) {
    // Removing anyone can only ever clear a selection, never move it: the id
    // stays attached to the person it was minted for.
    onForm({ ...form, roster: removeParticipant(roster, id) });
  }

  /** Load a situation the offline demo actually has a precomputed answer for. */
  function loadFixture(fixtureId: string) {
    const fixture = FIXTURES.find((f) => f.id === fixtureId);
    if (!fixture) return;
    onForm({
      occasion: fixture.occasion,
      pending: "",
      amount: String(fixture.totalVnd),
      roster: {
        participants: fixture.participants.map((p) => ({ id: p.id, name: p.name })),
        advancerId: fixture.advancerId,
      },
    });
  }

  const duplicated = duplicateNames(roster);

  return (
    <Screen
      title="Khoản chi mới"
      hint="Ai có mặt, hết bao nhiêu, ai trả trước."
      footer={
        <>
          {duplicated.length > 0 ? (
            <Text style={{ ...type.label, color: c.warn }}>
              Có hai người tên {duplicated.join(", ")}. Chia tiền vẫn đúng vì mỗi
              người có mã riêng, nhưng thêm gì đó để phân biệt sẽ dễ đọc hơn —
              ví dụ Nam A và Nam B.
            </Text>
          ) : null}
          <Button
            label="Chia tiền"
            disabled={!ready}
            onPress={() =>
              onNext({
                participants,
                totalVnd,
                advancerId: advancerId!,
                occasion: occasion.trim() || "khoản chi",
              })
            }
          />
        </>
      }
    >
      <ScrollView
        contentContainerStyle={{ gap: space.md }}
        keyboardShouldPersistTaps="handled"
      >
        <Card>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Bản chạy thử này không tự tính tiền — nó phát lại đáp án đã tính sẵn
            từ bộ vector kiểm thử. Chọn một tình huống để xem:
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
            {FIXTURES.map((fixture) => (
              <Button
                key={fixture.id}
                label={`${fixture.id} · ${formatVnd(fixture.totalVnd)}đ / ${fixture.participants.length}`}
                tone="quiet"
                onPress={() => loadFixture(fixture.id)}
              />
            ))}
          </View>
        </Card>

        <Card>
          <Field
            label="Đi đâu, ăn gì"
            value={occasion}
            onChangeText={setOccasion}
            placeholder="bữa lẩu tối thứ bảy"
          />
        </Card>

        <Card>
          <Field
            label="Thêm người"
            value={pending}
            onChangeText={setPending}
            placeholder="Hà"
          />
          <Button label="Thêm" tone="quiet" disabled={!pending.trim()} onPress={addPending} />
          {participants.length === 0 ? (
            <Text style={{ ...type.label, color: c.inkSoft }}>Chưa có ai.</Text>
          ) : (
            participants.map((person) => (
              <View
                key={person.id}
                style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}
              >
                <Text style={{ ...type.body, color: c.ink, flex: 1 }}>{person.name}</Text>
                <Button
                  label="Bỏ"
                  tone="quiet"
                  onPress={() => dropPerson(person.id)}
                />
              </View>
            ))
          )}
        </Card>

        <Card>
          <Field
            label="Tổng tiền"
            value={amount}
            onChangeText={setAmount}
            keyboardType="number-pad"
            placeholder="480000"
          />
          {amountProblem === "too-large" ? (
            <Text style={{ ...type.label, color: c.warn }}>
              Số này lớn hơn {formatVnd(MAX_AMOUNT_VND)}đ. Ứng dụng từ chối thay
              vì làm tròn âm thầm.
            </Text>
          ) : null}
          {amountProblem === "not-a-number" ? (
            <Text style={{ ...type.label, color: c.warn }}>
              Chỉ nhập chữ số. Dấu chấm, phẩy và khoảng trắng thì được.
            </Text>
          ) : null}
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
