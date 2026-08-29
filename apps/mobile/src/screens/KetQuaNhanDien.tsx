/** The reading, still a proposal: every number is an input, not a caption.
 *
 * Leading tone is `ai` (violet): the machine produced this, and a person can
 * still change it. The gap against the printed total is the reason this
 * screen exists; silently closing that gap would destroy the only signal
 * that a digit was misread.
 */
import React, { useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { MAX_AMOUNT_VND, formatVnd } from "../../../../packages/shared/money.mjs";
import {
  addLine,
  blockingProblem,
  editedCount,
  itemsTotalVnd,
  nameEdited,
  quantityEdited,
  totalEdited,
  removeLine,
  renameLine,
  setLineTotal,
  setQuantity,
  totalGapVnd,
  type BillLine,
  type BillReading,
  type EditRefusal,
} from "../receipt";
import { radius, space, type, usePalette } from "../theme";
import { Button, Card, ReadingNotice } from "../ui/Kit";

const HIT = 44;

/* Column widths, chosen against a 390pt phone rather than against a hunch.
 *
 * The card gives a row 336pt inside its padding. The first build spent
 * 44 on a delete button, 104 on money, 52 on quantity and 14 on a status dot,
 * which left the dish name 110pt and truncated six of eight dishes to
 * "Tokbokki phở". Names are how a person recognises the row they are
 * correcting, so the name takes the slack and everything else is cut to the
 * smallest size that still holds its content:
 *
 *   money 94  - "1.125.000" measures ~78pt at 16pt, plus 12 of padding
 *   qty    44 - two digits, and the minimum comfortable tap target
 *   delete 28 - visually small, but `hitSlop` restores the full 44 to the touch
 *   dot     0 - gone; an edited field now says so with its own border, which
 *               is more precise than a dot that only said "something in this
 *               row changed"
 */
const W_QTY = 44;
const W_MONEY = 94;
const W_DELETE = 28;
const DELETE_SLOP = { top: 8, bottom: 8, left: 8, right: 8 };

export function KetQuaNhanDien(props: {
  reading: BillReading;
  onChange: (next: BillReading) => void;
  onRetake: () => void;
  onContinue: () => void;
}): React.JSX.Element {
  const c = usePalette();
  const { reading, onChange } = props;
  const touched = editedCount(reading);
  const total = itemsTotalVnd(reading);
  const gap = totalGapVnd(reading);
  const blocked = blockingProblem(reading);

  const [qtyDraft, setQtyDraft] = useState<Record<string, string>>({});
  const [qtyReason, setQtyReason] = useState<Record<string, EditRefusal | undefined>>({});
  const [moneyDraft, setMoneyDraft] = useState<Record<string, string>>({});
  const [moneyReason, setMoneyReason] = useState<Record<string, EditRefusal | undefined>>({});
  const [moneyFocus, setMoneyFocus] = useState<Record<string, boolean>>({});

  function changeName(id: string, name: string) {
    onChange(renameLine(reading, id, name));
  }

  function changeQty(id: string, typed: string) {
    setQtyDraft((current) => ({ ...current, [id]: typed }));
    const result = setQuantity(reading, id, typed);
    if (result.ok) {
      setQtyReason((current) => ({ ...current, [id]: undefined }));
      onChange(result.reading);
    } else {
      setQtyReason((current) => ({ ...current, [id]: result.reason }));
    }
  }

  function blurQty(id: string) {
    if (qtyReason[id] === undefined) {
      setQtyDraft((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
    }
  }

  function changeMoney(id: string, typed: string) {
    setMoneyDraft((current) => ({ ...current, [id]: typed }));
    const result = setLineTotal(reading, id, typed);
    if (result.ok) {
      setMoneyReason((current) => ({ ...current, [id]: undefined }));
      onChange(result.reading);
    } else {
      setMoneyReason((current) => ({ ...current, [id]: result.reason }));
    }
  }

  function focusMoney(id: string, line: BillLine) {
    setMoneyFocus((current) => ({ ...current, [id]: true }));
    setMoneyDraft((current) =>
      current[id] === undefined ? { ...current, [id]: String(line.lineTotalVnd) } : current,
    );
  }

  function blurMoney(id: string) {
    setMoneyFocus((current) => ({ ...current, [id]: false }));
    if (moneyReason[id] === undefined) {
      setMoneyDraft((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
    }
  }

  function dropLine(id: string) {
    onChange(removeLine(reading, id));
  }

  function extraLine() {
    onChange(addLine(reading, `mon-them-${Date.now()}`));
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <Pressable
          onPress={props.onRetake}
          accessibilityRole="button"
          accessibilityLabel="Chụp lại"
          style={{ minWidth: HIT, minHeight: HIT, justifyContent: "center" }}
        >
          <Text style={{ ...type.title, color: c.ink, lineHeight: 28 }}>‹</Text>
        </Pressable>
        <Text style={{ ...type.title, color: c.ink, flex: 1 }}>Kết quả nhận diện</Text>
      </View>

      {/* The mockup's teal pill, in the mockup's slot, now branching.
          It used to count `reading.lines`, which includes rows a person typed
          in themselves -- so adding a missing dish raised a number labelled
          "nhận diện" for a line nothing recognised. `disclosure()` counts only
          what the reader transcribed, and hands back a different sentence
          entirely when the server asked for a second pair of eyes. */}
      <ReadingNotice reading={reading} />

      {/* Said out loud rather than left to the border colours. After four
          corrections a person needs to know how much of this is still the
          machine's reading and how much is theirs. */}
      {touched > 0 ? (
        <Text style={{ ...type.label, color: c.ai }}>
          Bạn đã sửa tay {touched} món. Ô nào viền tím là ô bạn đã đổi.
        </Text>
      ) : null}

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }}
        keyboardShouldPersistTaps="handled"
      >
        <Card style={{ paddingHorizontal: space.sm }}>
          <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.xs }}>
            <Text style={{ ...type.label, color: c.inkSoft, flex: 1, minWidth: 0 }}>Món ăn</Text>
            <Text
              style={{
                ...type.label, color: c.inkSoft,
                width: W_QTY, textAlign: "center", marginLeft: space.xs,
              }}
            >
              SL
            </Text>
            <Text
              style={{
                ...type.label, color: c.inkSoft,
                width: W_MONEY, textAlign: "right", marginLeft: space.xs,
              }}
            >
              Thành tiền
            </Text>
            <View style={{ width: W_DELETE }} />
          </View>

          {reading.lines.map((line) => {
            const qtyText = qtyDraft[line.id] ?? String(line.quantity);
            const moneyText = moneyFocus[line.id] || moneyDraft[line.id] !== undefined
              ? (moneyDraft[line.id] ?? String(line.lineTotalVnd))
              : formatVnd(line.lineTotalVnd);
            const dish = line.name.trim() === "" ? "món chưa có tên" : line.name;
            const qtyFail = qtyReason[line.id];
            const moneyFail = moneyReason[line.id];
            return (
              <View key={line.id} style={{ gap: 2 }}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <TextInput
                    value={line.name}
                    onChangeText={(name) => changeName(line.id, name)}
                    accessibilityLabel={
                      `Tên món, ${dish}${nameEdited(line) ? ", đã sửa tay" : ""}`
                    }
                    placeholder="Tên món"
                    placeholderTextColor={c.inkFaint}
                    style={{
                      ...type.body,
                      color: c.ink,
                      flex: 1,
                      // `minWidth: 0` is load-bearing, not tidying. On the web
                      // a TextInput is an <input>, and an <input> carries an
                      // intrinsic min-width of about twenty characters. A flex
                      // child will not shrink past its intrinsic minimum, so
                      // `flex: 1` alone could not give the row back any space:
                      // at 390px the name box stayed ~220px wide and pushed
                      // the Thành tiền column clean off the card. Measured in
                      // a real render before this line existed -- the money
                      // column, the one thing this screen is for, was not on
                      // screen at all.
                      minWidth: 0,
                      minHeight: HIT,
                      borderWidth: 1,
                      // The field says it was changed, not the row. A dot in
                      // the margin could only report "something here moved";
                      // this points at which of the three.
                      borderColor: nameEdited(line) ? c.ai : c.lineStrong,
                      borderRadius: radius.small,
                      paddingHorizontal: space.sm,
                    }}
                  />
                  <TextInput
                    value={qtyText}
                    onChangeText={(typed) => changeQty(line.id, typed)}
                    onBlur={() => blurQty(line.id)}
                    keyboardType="number-pad"
                    accessibilityLabel={
                      `Số lượng, ${dish}${quantityEdited(line) ? ", đã sửa tay" : ""}`
                    }
                    style={{
                      ...type.body,
                      color: c.ink,
                      width: W_QTY,
                      minHeight: HIT,
                      textAlign: "center",
                      borderWidth: 1,
                      borderColor:
                        qtyFail ? c.warn
                        : quantityEdited(line) ? c.ai
                        : c.lineStrong,
                      borderRadius: radius.small,
                      marginLeft: space.xs,
                    }}
                  />
                  <TextInput
                    value={moneyText}
                    onChangeText={(typed) => changeMoney(line.id, typed)}
                    onFocus={() => focusMoney(line.id, line)}
                    onBlur={() => blurMoney(line.id)}
                    keyboardType="number-pad"
                    accessibilityLabel={
                      `Thành tiền, ${dish}, ${formatVnd(line.lineTotalVnd)} đồng` +
                      (totalEdited(line) ? ", đã sửa tay" : "")
                    }
                    style={{
                      ...type.body,
                      color: c.ink,
                      width: W_MONEY,
                      minHeight: HIT,
                      textAlign: "right",
                      fontVariant: ["tabular-nums"],
                      borderWidth: 1,
                      borderColor:
                        moneyFail ? c.warn
                        : totalEdited(line) ? c.ai
                        : c.lineStrong,
                      borderRadius: radius.small,
                      paddingHorizontal: space.xs,
                      marginLeft: space.xs,
                    }}
                  />
                  <Pressable
                    onPress={() => dropLine(line.id)}
                    accessibilityRole="button"
                    accessibilityLabel={`Xoá món ${dish}`}
                    // Visually 28pt so the name column can have the space,
                    // but `hitSlop` keeps the touch target at 44.
                    hitSlop={DELETE_SLOP}
                    style={({ pressed }) => ({
                      width: W_DELETE,
                      height: HIT,
                      alignItems: "center",
                      justifyContent: "center",
                      opacity: pressed ? 0.7 : 1,
                    })}
                  >
                    <Text style={{ ...type.body, color: c.inkSoft }}>×</Text>
                  </Pressable>
                </View>
                {qtyFail !== undefined ? (
                  <Text style={{ ...type.label, color: c.warn, marginLeft: space.xs }}>
                    {refusalCopy(qtyFail)}
                  </Text>
                ) : null}
                {moneyFail !== undefined ? (
                  <Text style={{ ...type.label, color: c.warn, marginLeft: space.xs }}>
                    {refusalCopy(moneyFail)}
                  </Text>
                ) : null}
              </View>
            );
          })}
        </Card>

        <Button label="Thêm món" tone="quiet" onPress={extraLine} />

        {/* The mockup draws a second chip here, the one whose caption is an
            English endorsement of the reader followed by a percentage, and it
            is deliberately not rebuilt. Its only content was the percentage
            ADR-0009 decision 4 refuses; the sentence that legitimately replaces
            it is already at the top of this screen, above the fold, and a
            second pill repeating it word for word would read as a second,
            independent endorsement of the same reading. The invitation to
            correct things is the part of that block worth keeping. */}
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Bạn có thể chỉnh tay trước khi xác nhận
        </Text>

        {reading.warnings.map((warning, index) => (
          <Text key={`${index}-${warning}`} style={{ ...type.label, color: c.inkSoft }}>
            {warning}
          </Text>
        ))}
      </ScrollView>

      {/* Total and discrepancy sit OUTSIDE the scroll view, on purpose.
          They were the last children of it, and with eight rows on a 390pt
          screen that put both below the fold: the money and the "these lines
          do not add up to the paper" warning were only reachable by scrolling
          past the thing they describe. On a screen whose entire job is letting
          someone catch a misread digit, the running total has to be visible
          while they type, not after they go looking for it. */}
      <View style={{ gap: space.sm }}>
        <View
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "baseline",
            borderTopWidth: 1,
            borderTopColor: c.line,
            paddingTop: space.sm,
          }}
        >
          <Text style={{ ...type.title, color: c.ink }}>Tổng cộng</Text>
          {/* `type.amount` unmodified. It was `fontSize: 28` over the token,
              which is a size the system does not own -- tokens.json has a 28
              step (`h1`) but this map does not expose it, and reaching past a
              scale with a literal is how a scale stops being one. */}
          <Text style={{ ...type.amount, color: c.ink }}>
            {formatVnd(total)}
            <Text style={{ ...type.body, color: c.ink }}>đ</Text>
          </Text>
        </View>

        <GapNotice reading={reading} gap={gap} />

        {blocked !== null ? (
          <Text style={{ ...type.label, color: c.warn }}>{blocked}</Text>
        ) : null}
        <View style={{ flexDirection: "row", gap: space.sm }}>
          <View style={{ flex: 1 }}>
            <Button label="Chụp lại" tone="quiet" onPress={props.onRetake} />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              label="Tiếp tục"
              tone="split"
              disabled={blocked !== null}
              onPress={props.onContinue}
            />
          </View>
        </View>
      </View>
    </View>
  );
}

function GapNotice({ reading, gap }: { reading: BillReading; gap: number | null }) {
  const c = usePalette();
  const printed = reading.printedTotalVnd;

  if (printed === null) {
    return (
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Bill này không có dòng tổng cộng để đối chiếu.
      </Text>
    );
  }

  if (gap === 0) {
    return (
      <Text style={{ ...type.label, color: c.split }}>
        Khớp với dòng Tổng cộng in trên bill.
      </Text>
    );
  }

  if (gap === null) return null;

  const copy = gap > 0
    ? `Dòng "Tổng cộng" in trên bill là ${formatVnd(printed)}đ, nhiều hơn tổng các món ${formatVnd(gap)}đ. Có thể máy đọc sót một món hoặc đọc nhầm một chữ số.`
    : `Tổng các món đang nhiều hơn dòng "Tổng cộng" in trên bill ${formatVnd(-gap)}đ. Kiểm tra lại các dòng vừa sửa.`;

  return (
    <View
      style={{
        borderLeftWidth: 3,
        borderLeftColor: c.warn,
        paddingLeft: space.sm,
        paddingVertical: space.xs,
      }}
    >
      <Text style={{ ...type.label, color: c.warn }}>{copy}</Text>
    </View>
  );
}

function refusalCopy(reason: EditRefusal): string {
  if (reason === "empty") return "Ô này không được để trống.";
  if (reason === "not-a-number") {
    return "Chỉ nhập chữ số. Dấu chấm, phẩy và khoảng trắng thì được.";
  }
  if (reason === "too-large") {
    return `Số này lớn hơn ${formatVnd(MAX_AMOUNT_VND)}đ. Ứng dụng từ chối thay vì làm tròn âm thầm.`;
  }
  return "Số lượng phải lớn hơn 0.";
}
