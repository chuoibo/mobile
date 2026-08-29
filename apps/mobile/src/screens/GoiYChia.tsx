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
import { moTaTrangThaiGan, type BillWire, type SoDu } from "../bill";
import { itemsTotalVnd, type BillLine, type BillReading } from "../receipt";
import { availableMembers, labelFor, type GroupMember, type Roster } from "../participants";
import type { SplitPreview } from "../api";
import { radius, space, type, usePalette } from "../theme";
import { toggleState } from "../ui/a11y";
import { Button, Card, ReadingNotice } from "../ui/Kit";

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

/** The scrolling region holding the matrix. Exported so the test that asserts
 *  it carries a keyboard tab-stop names the same element the screen does. */
export const VUNG_CUON_MA_TRAN = "vung-cuon-ma-tran";

export function GoiYChia(props: {
  reading: BillReading;
  roster: Roster;
  /** The group this bill belongs to. Adding somebody picks from here.
   *
   * It used to be a text box, and that was bug-125301: typing "Hải" minted a
   * fresh UUID instead of finding Hải, so the split was recorded to the dong
   * against a stranger who shared his name and the real Hải's screen never
   * moved. A name is not an identity. Nobody reaches this screen without a
   * group, so there is nothing for a text box to be good for. */
  nhom: GroupMember[];
  assignment: Assignment;
  preview: { signature: string; split: SplitPreview } | null;
  /** The stored bill, or `null` while the write has not landed.
   *
   * Read for two things and nothing else: whether these ticks exist anywhere
   * but this phone, and which lines the server still counts as the reader's
   * guess. The matrix itself stays local -- a screen that waited on a bill id
   * before letting somebody tick a box would be down whenever the network is.
   */
  bill: BillWire | null;
  /** The group's net position before this bill. `null` when not loaded. */
  soDu: SoDu | null;
  onBack: () => void;
  onReset: () => void;
  onToggle: (lineId: string, personId: string) => void;
  onAddMember: (member: GroupMember) => void;
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
  const [removing, setRemoving] = useState<string | null>(null);
  const [openLine, setOpenLine] = useState<string | null>(null);
  const [tableWidth, setTableWidth] = useState(INNER_AT_390);

  const rest = tableWidth - W_NAME_MIN - W_PRICE;
  const colsFit = rest < COL ? 0 : Math.floor(rest / COL);
  const collapsed = people.length > colsFit;

  const conLai = availableMembers(roster, props.nhom);
  // Open by default when nobody is on the bill yet. The reported dead end was
  // an empty matrix reading "Chưa có ai trong nhóm. Thêm người bằng nút + ở
  // trên." above a table with no columns -- a screen whose only useful action
  // was hidden behind a press. With nobody added there is nothing else this
  // screen can be for, so the group is already on it.
  const moiThem = adding || people.length === 0;

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
        {/* Only when it has something to reveal. With nobody on the bill the
            list below is already open, and with the whole group added there is
            nobody left to offer -- a "+" that opens an empty panel reads as a
            broken button. */}
        {people.length > 0 && conLai.length > 0 ? (
          <Pressable
            onPress={() => { setAdding(!adding); setRemoving(null); }}
            accessibilityRole="button"
            accessibilityLabel={adding ? "Đóng danh sách nhóm" : "Thêm người từ nhóm"}
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
              <Text style={{ ...type.h1, color: c.ink }}>{adding ? "−" : "+"}</Text>
            </View>
            <Text style={{ ...type.label, color: c.inkSoft }}>Thêm</Text>
          </Pressable>
        ) : null}
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

      {moiThem ? (
        <View style={{ gap: space.sm }}>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            {people.length === 0
              ? "Ai đã ăn bữa này? Chọn trong nhóm."
              : "Còn lại trong nhóm"}
          </Text>
          {conLai.length === 0 ? (
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Cả nhóm đã có mặt trong bữa này.
            </Text>
          ) : (
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>
              {conLai.map((member) => (
                <Pressable
                  key={member.id}
                  onPress={() => {
                    props.onAddMember(member);
                    // Stay open. Adding the first person makes the roster
                    // non-empty, which is the condition that was holding this
                    // list open -- so without this, picking one person closed
                    // the list and the next one cost a trip back through "+".
                    // A group eats together; picking three in a row is the
                    // normal case, not the exception.
                    setAdding(true);
                    setRemoving(null);
                  }}
                  accessibilityRole="button"
                  // Named with the person, not with the slot. The label is what
                  // a screen reader reads and what the test asserts on, and it
                  // has to say which of seven this is.
                  accessibilityLabel={`Thêm ${member.name} vào nhóm`}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: space.xs,
                    minHeight: HIT,
                    paddingHorizontal: space.sm,
                    borderRadius: radius.pill,
                    borderWidth: 1,
                    borderColor: c.lineStrong,
                  }}
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
                    <Text style={{ ...type.micro, color: c.split }}>{initial(member.name)}</Text>
                  </View>
                  <Text style={{ ...type.body, color: c.ink }}>{member.name}</Text>
                </Pressable>
              ))}
            </View>
          )}
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
        // A keyboard tab-stop on the scroller itself. axe reported
        // `scrollable-region-focusable` (serious, WCAG 2.1.1) here and on none
        // of the other four screens, and the reason is the state this screen
        // opens in: with nobody on the bill the matrix renders no checkboxes at
        // all, so the region holds nothing focusable and no key scrolls it --
        // the dishes below the fold cannot be reached without a pointer. Same
        // fix and same reasoning as the Cá nhân tab; `tabIndex` rather than
        // `focusable`, which react-native-web 0.21 deprecates and warns on.
        // Native ignores it, correctly: a touch screen has no tab ring.
        tabIndex={0}
        // A handle for the test that guards the line above. Without it the
        // assertion would have to find this div by class name, which is a
        // hash react-native-web is free to change.
        nativeID={VUNG_CUON_MA_TRAN}
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

        <SoDuNhom soDu={props.soDu} roster={roster} />

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
        {/* Two different facts, deliberately not merged into one reassuring
            line. `ReadingNotice` above is about the reading -- whether the
            machine trusts what it transcribed off the paper. This one is about
            the ticks: whether they exist anywhere but this phone, and how many
            lines are still the reader's guess rather than somebody's decision.
            A bill can be read perfectly and stored nowhere. */}
        <Text
          style={{
            ...type.label,
            color: props.bill == null ? c.warn : c.inkSoft,
            textAlign: "center",
          }}
        >
          {moTaTrangThaiGan(props.bill)}
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

/** Where the group stood before this dinner, in plain sentences.
 *
 * Renders nothing at all when there is nothing to say -- no panel, no empty
 * card, no spinner. A settled group is the normal case, and a box announcing
 * "0đ" on every clean bill is noise sitting where a person is trying to read a
 * table.
 *
 * Every number here is `net_vnd` off the ledger, printed. Nothing on this
 * screen adds them up or nets them against the bill above: the money in this
 * panel and the money in that matrix answer different questions, and a total
 * spanning both would be a third number the server never computed.
 */
function SoDuNhom({
  soDu,
  roster,
}: {
  soDu: SoDu | null;
  roster: Roster;
}): React.JSX.Element | null {
  const c = usePalette();
  if (soDu == null || soDu.transfers.length === 0) return null;
  return (
    <Card>
      <View style={{ gap: space.xs }}>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Trước bữa này, nhóm còn nợ nhau
        </Text>
        {soDu.transfers.map((row) => (
          <Text
            key={`${row.fromId}-${row.toId}`}
            style={{ ...type.body, color: c.ink }}
          >
            {labelFor(roster, row.fromId)} trả {labelFor(roster, row.toId)}{" "}
            {formatVnd(row.amountVnd)}đ
          </Text>
        ))}
        {/* Said only when the server proved it, and never upgraded to a claim
            when it did not. "Ít nhất có thể" over a list nobody proved minimal
            is a small lie that costs trust on a money screen for nothing. */}
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {soDu.provenMinimal
            ? "Đây là số lần chuyển ít nhất có thể."
            : "Có thể còn cách chuyển gọn hơn."}
        </Text>
      </View>
    </Card>
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
