/** Who ate what: a matrix the server will split, not a split the app computed.
 *
 * Leading tone is `split` (teal). `ai` (violet) is reserved for what the
 * machine produced: here, the default "everyone shares every line" which
 * nobody has confirmed. Every dong under an avatar comes
 * from `allocation.allocations`. Showing a stale number as if it were current
 * is a money error, not a display one -- hence the "..." while a preview is
 * in flight for a different signature.
 */
import React, { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import {
  blockingProblem,
  countOn,
  isOn,
  signature,
  type Assignment,
} from "../assignment";
import { itemsTotalVnd, type BillLine, type BillReading } from "../receipt";
import { labelFor, type Roster } from "../participants";
import type { SplitPreview } from "../api";
import { radius, space, type, usePalette } from "../theme";
import { toggleState } from "../ui/a11y";
import { Button, Card, Field, ReadingNotice } from "../ui/Kit";

const HIT = 44;
const AVATAR = 56;
const CHECK = 24;
const W_NAME_MIN = 104;
const W_PRICE = 62;
const COL = 44;
/* On a 390pt phone the page gutter is space.md each side (32) and this
 * card's horizontal padding is space.xs each side (12), which leaves 346
 * inside. 104 for the name, 62 for the price, 44 per person: four people
 * fit, five collapse to the "k/N" chip. The mockup is four. */
const INNER_AT_390 = 346;

export function GoiYChia(props: {
  reading: BillReading;
  roster: Roster;
  assignment: Assignment;
  preview: { signature: string; split: SplitPreview } | null;
  onBack: () => void;
  onReset: () => void;
  onToggle: (lineId: string, personId: string) => void;
  onAddPerson: (name: string) => void;
  onRemovePerson: (id: string) => void;
  onSeeResults: () => void;
}): React.JSX.Element {
  const c = usePalette();
  const { reading, roster, assignment, preview } = props;
  const people = roster.participants;
  const ids = people.map((person) => person.id);
  const live = signature(reading, ids, assignment);
  const blocked = blockingProblem(reading, ids, assignment);
  const total = itemsTotalVnd(reading);
  // A preview computed for a different matrix is not this matrix. Painting
  // those dong under these ticks is how a person confirms a number they
  // never saw.
  const split = preview !== null && preview.signature === live ? preview.split : null;

  const [mode, setMode] = useState<"mon" | "phan-tram">("mon");
  const [adding, setAdding] = useState(false);
  const [pending, setPending] = useState("");
  const [removing, setRemoving] = useState<string | null>(null);
  const [openLine, setOpenLine] = useState<string | null>(null);
  const [tableWidth, setTableWidth] = useState(INNER_AT_390);

  const rest = tableWidth - W_NAME_MIN - W_PRICE;
  const colsFit = rest < COL ? 0 : Math.floor(rest / COL);
  const collapsed = people.length > colsFit;

  function addPending() {
    const name = pending.trim();
    if (!name) return;
    props.onAddPerson(name);
    setPending("");
    setAdding(false);
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <Pressable
          onPress={props.onBack}
          accessibilityRole="button"
          accessibilityLabel="Quay lại"
          style={{ minWidth: HIT, minHeight: HIT, justifyContent: "center" }}
        >
          <Text style={{ ...type.title, color: c.ink, lineHeight: 28 }}>‹</Text>
        </Pressable>
        {/* `title`, not `h1`, and the same step the previous screen's heading
            uses. At 28pt "Gợi ý chia theo người" wraps onto two lines on a
            390pt phone, which pushes "Làm lại" out of line with the back
            chevron and costs a row of the table underneath. */}
        <Text
          style={{ ...type.title, color: c.ink, flex: 1, minWidth: 0 }}
          numberOfLines={1}
        >
          Gợi ý chia theo người
        </Text>
        <Pressable
          onPress={props.onReset}
          accessibilityRole="button"
          accessibilityLabel="Làm lại"
          style={{ minWidth: HIT, minHeight: HIT, justifyContent: "center", alignItems: "flex-end" }}
        >
          <Text style={{ ...type.label, color: c.split, fontWeight: "600" }}>Làm lại</Text>
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        // `flexGrow: 0` is load-bearing. A ScrollView carries `flex: 1` in its
        // own base style, so a horizontal one dropped into a column stretches
        // down the page instead of hugging its row: measured at 390x844 it
        // took about 400pt of empty height and squeezed the matrix below it to
        // its header, so the screen rendered with the avatars, a hole, and a
        // table containing no dishes. The deterministic detector reported zero
        // findings on that render -- nothing was occluded or low contrast, the
        // content simply was not there.
        style={{ flexGrow: 0, flexShrink: 0 }}
        contentContainerStyle={{ gap: space.md, alignItems: "flex-start", paddingRight: space.sm }}
      >
        {people.map((person) => {
          const raw = split === null ? undefined : split.allocations[person.id];
          const amount = raw === undefined ? "..." : `${formatVnd(raw)}đ`;
          const selected = removing === person.id;
          return (
            <Pressable
              key={person.id}
              onPress={() => setRemoving(selected ? null : person.id)}
              accessibilityRole="button"
              accessibilityLabel={
                selected
                  ? `Đang chọn ${labelFor(roster, person.id)}, bấm lại để huỷ`
                  : labelFor(roster, person.id)
              }
              style={{ alignItems: "center", width: space.xxl + space.lg, gap: space.xs }}
            >
              <View
                style={{
                  width: AVATAR,
                  height: AVATAR,
                  borderRadius: radius.pill,
                  backgroundColor: selected ? c.split : c.splitSoft,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Text style={{ ...type.title, color: selected ? c.splitInk : c.split }}>
                  {initial(person.name)}
                </Text>
              </View>
              <Text
                style={{ ...type.label, color: c.ink, textAlign: "center" }}
                numberOfLines={1}
              >
                {labelFor(roster, person.id)}
              </Text>
              <Text style={{ ...type.amountSmall, color: c.ink, textAlign: "center" }}>
                {amount}
              </Text>
            </Pressable>
          );
        })}
        <Pressable
          onPress={() => { setAdding(true); setRemoving(null); }}
          accessibilityRole="button"
          accessibilityLabel="Thêm"
          style={{ alignItems: "center", width: space.xxl + space.lg, gap: space.xs }}
        >
          <View
            style={{
              width: AVATAR,
              height: AVATAR,
              borderRadius: radius.pill,
              borderWidth: 1,
              borderColor: c.lineStrong,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ ...type.h1, color: c.ink }}>+</Text>
          </View>
          <Text style={{ ...type.label, color: c.inkSoft }}>Thêm</Text>
        </Pressable>
      </ScrollView>

      {removing !== null ? (
        <Button
          label={`Xoá ${labelFor(roster, removing)} khỏi nhóm`}
          tone="quiet"
          onPress={() => {
            props.onRemovePerson(removing);
            setRemoving(null);
          }}
        />
      ) : null}

      {adding ? (
        <View style={{ gap: space.sm }}>
          <Field
            label="Tên người"
            value={pending}
            onChangeText={setPending}
            placeholder="Hà"
          />
          <Button label="Thêm" tone="split" disabled={!pending.trim()} onPress={addPending} />
        </View>
      ) : null}

      <View
        accessibilityRole="radiogroup"
        aria-label="Kiểu chia"
        style={{
          flexDirection: "row",
          alignSelf: "stretch",
          backgroundColor: c.splitSoft,
          borderRadius: radius.pill,
          padding: space.xs,
        }}
      >
        <ModeChip label="Theo món" on={mode === "mon"} onPress={() => setMode("mon")} />
        <ModeChip label="Theo %" on={mode === "phan-tram"} onPress={() => setMode("phan-tram")} />
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: space.md, paddingBottom: space.lg }}
        keyboardShouldPersistTaps="handled"
      >
        {mode === "phan-tram" ? (
          <Card>
            <Text style={{ ...type.body, color: c.ink }}>
              Chia theo phần trăm chưa làm. Hiện chỉ chia đều trong từng món.
            </Text>
            <Button label="Theo món" tone="quiet" onPress={() => setMode("mon")} />
          </Card>
        ) : (
          <>
            <Text style={{ ...type.label, color: c.inkSoft }}>Chọn người đã ăn món này</Text>
            {/* Said before the ticking starts, not after it. This sentence is
                the one that stops the disclosure pill below from being read as
                "the machine worked out who ate what": it did not, and cannot,
                because it only ever saw the paper. Left inside the scroll view
                on purpose -- it is an explanation, while the pill below is the
                disclosure that has to be on screen at all times. */}
            <Text style={{ ...type.label, color: c.inkSoft }}>
              AI đọc được các món trên bill. Ai đã ăn món nào thì AI không thấy,
              nên mặc định là cả nhóm ăn chung và bạn sửa lại cho đúng.
            </Text>
            <Card style={{ paddingHorizontal: space.xs }}>
              <View onLayout={(event) => setTableWidth(event.nativeEvent.layout.width)}>
                {collapsed ? (
                  <CollapsedTable
                    reading={reading}
                    roster={roster}
                    assignment={assignment}
                    onOpen={setOpenLine}
                  />
                ) : (
                  <MatrixTable
                    reading={reading}
                    roster={roster}
                    assignment={assignment}
                    onToggle={props.onToggle}
                  />
                )}
              </View>
            </Card>
          </>
        )}

      </ScrollView>

      {/* Pinned, like the total below it, and for a stronger reason. The
          disclosure about the reading has to be on screen rather than merely
          present, and this pill was the last child of the scroll view: with
          eight dishes on a 390pt phone it sat below the fold, and the rendered
          detector measured it 100% covered by the "Xem kết quả" button. A
          statement about what a machine produced, visible only to somebody who
          scrolls past the thing it describes, is not a disclosure. The mockup
          stacks it against Tổng cộng too.

          What it says changed as well. It used to interpolate a field the
          route has never sent, so what rendered was an English endorsement of
          the reader trailed by a bare percent sign. ADR-0009 decision 4 refuses
          the percentage: it would invite this screen to auto-accept above a
          threshold, and it measured how legible the print was, not whether the
          money was right. `ReadingNotice` keeps the pill and branches on the
          one field the route does send. */}
      <View style={{ gap: space.sm }}>
        <ReadingNotice reading={reading} stretch />
        <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
          Bạn có thể chỉnh tay trước khi xác nhận
        </Text>

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
          <Text style={{ ...type.amount, color: c.ink }}>
            {formatVnd(total)}
            <Text style={{ ...type.body, color: c.ink }}>đ</Text>
          </Text>
        </View>

        {split !== null && split.roundingGainers.length > 0 ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Chia không hết chẵn. Ai chịu 1đ lẻ sẽ do bước sau quyết, khi đã chọn người trả trước.
          </Text>
        ) : null}

        {blocked !== null ? (
          <Text style={{ ...type.label, color: c.warn }}>{blocked}</Text>
        ) : null}

        <Button
          label="Xem kết quả"
          tone="split"
          disabled={blocked !== null}
          onPress={props.onSeeResults}
        />
      </View>

      <LinePicker
        line={reading.lines.find((row) => row.id === openLine) ?? null}
        roster={roster}
        assignment={assignment}
        onToggle={props.onToggle}
        onClose={() => setOpenLine(null)}
      />
    </View>
  );
}

function ModeChip({
  label, on, onPress,
}: {
  label: string; on: boolean; onPress: () => void;
}): React.JSX.Element {
  const c = usePalette();
  return (
    <Pressable
      onPress={onPress}
      // Two chips where exactly one is on is a radio group, not two buttons.
      // It was `role="button"` carrying `selected`, which is invalid on a
      // button on both platforms and was dropped before the DOM on this one,
      // so nothing ever announced which mode was active.
      {...toggleState("radio", on)}
      style={{
        flex: 1,
        minHeight: HIT,
        borderRadius: radius.pill,
        backgroundColor: on ? c.split : "transparent",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text style={{ ...type.body, fontWeight: "600", color: on ? c.splitInk : c.ink }}>
        {label}
      </Text>
    </Pressable>
  );
}

function MatrixTable({
  reading, roster, assignment, onToggle,
}: {
  reading: BillReading;
  roster: Roster;
  assignment: Assignment;
  onToggle: (lineId: string, personId: string) => void;
}): React.JSX.Element {
  const c = usePalette();
  const people = roster.participants;
  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "center", minHeight: HIT }}>
        <View style={{ flex: 1, minWidth: 0 }} />
        {people.map((person) => (
          <View
            key={person.id}
            style={{ width: COL, alignItems: "center", justifyContent: "center" }}
          >
            <View
              style={{
                width: CHECK,
                height: CHECK,
                borderRadius: radius.pill,
                backgroundColor: c.splitSoft,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ ...type.micro, color: c.split }}>{initial(person.name)}</Text>
            </View>
          </View>
        ))}
        <Text
          style={{
            ...type.label, color: c.inkSoft,
            width: W_PRICE, textAlign: "right",
          }}
        >
          Giá
        </Text>
      </View>
      {reading.lines.map((line) => (
        <MatrixRow
          key={line.id}
          line={line}
          roster={roster}
          assignment={assignment}
          onToggle={onToggle}
        />
      ))}
    </View>
  );
}

function MatrixRow({
  line, roster, assignment, onToggle,
}: {
  line: BillLine;
  roster: Roster;
  assignment: Assignment;
  onToggle: (lineId: string, personId: string) => void;
}): React.JSX.Element {
  const c = usePalette();
  const dish = line.name.trim() === "" ? "món chưa có tên" : line.name;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", minHeight: HIT }}>
      <Text
        style={{ ...type.body, color: c.ink, flex: 1, minWidth: 0 }}
        numberOfLines={1}
      >
        {line.name}
      </Text>
      {roster.participants.map((person) => {
        const checked = isOn(assignment, line.id, person.id);
        return (
          <Pressable
            key={person.id}
            onPress={() => onToggle(line.id, person.id)}
            // `aria-checked`, via the kit helper. `accessibilityState` reached
            // the browser as nothing at all, so this cell rendered
            // byte-identical ticked and unticked and a screen reader could not
            // tell which dishes were on somebody's bill. See `ui/a11y.ts`.
            {...toggleState("checkbox", checked)}
            accessibilityLabel={`${labelFor(roster, person.id)}, ${dish}`}
            // The cell is 44 wide and 44 tall, so neighbouring columns abut
            // and never overlap. Horizontal hitSlop stays 0: half the gap
            // between columns is 0, and any slop past that would assign a
            // dish to the wrong person.
            style={{
              width: COL,
              height: HIT,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <CheckDot on={checked} />
          </Pressable>
        );
      })}
      <Text
        style={{
          ...type.label, color: c.ink,
          width: W_PRICE, textAlign: "right",
          fontVariant: ["tabular-nums"],
        }}
      >
        {formatVnd(line.lineTotalVnd)}
      </Text>
    </View>
  );
}

function CollapsedTable({
  reading, roster, assignment, onOpen,
}: {
  reading: BillReading;
  roster: Roster;
  assignment: Assignment;
  onOpen: (lineId: string) => void;
}): React.JSX.Element {
  const c = usePalette();
  const n = roster.participants.length;
  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "center", minHeight: HIT }}>
        <View style={{ flex: 1, minWidth: 0 }} />
        <Text
          style={{
            ...type.label, color: c.inkSoft,
            width: W_PRICE, textAlign: "right",
          }}
        >
          Giá
        </Text>
      </View>
      {reading.lines.map((line) => {
        const k = countOn(assignment, line.id);
        const dish = line.name.trim() === "" ? "món chưa có tên" : line.name;
        return (
          <View
            key={line.id}
            style={{ flexDirection: "row", alignItems: "center", minHeight: HIT, gap: space.xs }}
          >
            <Text
              style={{ ...type.body, color: c.ink, flex: 1, minWidth: 0 }}
              numberOfLines={1}
            >
              {line.name}
            </Text>
            <Pressable
              onPress={() => onOpen(line.id)}
              accessibilityRole="button"
              accessibilityLabel={`${k} trên ${n} người đã ăn ${dish}`}
              style={{
                minHeight: HIT,
                minWidth: HIT,
                paddingHorizontal: space.sm,
                borderRadius: radius.pill,
                borderWidth: 1,
                borderColor: c.lineStrong,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ ...type.label, color: c.ink, fontWeight: "600" }}>
                {k}/{n}
              </Text>
            </Pressable>
            <Text
              style={{
                ...type.label, color: c.ink,
                width: W_PRICE, textAlign: "right",
                fontVariant: ["tabular-nums"],
              }}
            >
              {formatVnd(line.lineTotalVnd)}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

function LinePicker({
  line, roster, assignment, onToggle, onClose,
}: {
  line: BillLine | null;
  roster: Roster;
  assignment: Assignment;
  onToggle: (lineId: string, personId: string) => void;
  onClose: () => void;
}): React.JSX.Element | null {
  const c = usePalette();
  if (line === null) return null;
  const dish = line.name.trim() === "" ? "món chưa có tên" : line.name;
  return (
    <Modal visible animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
        <Text style={{ ...type.h1, color: c.ink }}>{dish}</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>Chọn người đã ăn món này</Text>
        <ScrollView contentContainerStyle={{ gap: space.xs }}>
          {roster.participants.map((person) => {
            const checked = isOn(assignment, line.id, person.id);
            return (
              <Pressable
                key={person.id}
                onPress={() => onToggle(line.id, person.id)}
                // Same substitution as the matrix cell, same reason.
                {...toggleState("checkbox", checked)}
                accessibilityLabel={`${labelFor(roster, person.id)}, ${dish}`}
                style={{
                  minHeight: HIT,
                  flexDirection: "row",
                  alignItems: "center",
                  gap: space.sm,
                }}
              >
                <CheckDot on={checked} />
                <Text style={{ ...type.body, color: c.ink, flex: 1 }}>
                  {labelFor(roster, person.id)}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
        <Button label="Xong" tone="split" onPress={onClose} />
      </View>
    </Modal>
  );
}

function CheckDot({ on }: { on: boolean }): React.JSX.Element {
  const c = usePalette();
  return (
    <View
      style={{
        width: CHECK,
        height: CHECK,
        borderRadius: radius.pill,
        backgroundColor: on ? c.split : "transparent",
        borderWidth: on ? 0 : 1,
        borderColor: c.lineStrong,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {on ? (
        <Text style={{ ...type.micro, color: c.splitInk, fontWeight: "700" }}>✓</Text>
      ) : null}
    </View>
  );
}

function initial(name: string): string {
  const trimmed = name.trim();
  if (trimmed === "") return "?";
  return trimmed.charAt(0).toUpperCase();
}
