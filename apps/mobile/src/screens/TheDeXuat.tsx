/** What the bot proposes after reading the thread, and where each number came from.
 *
 * ADR-0008 let the bot read the whole conversation, which was a real loosening:
 * §5.1 had required an explicit context snapshot per invocation. The thing put
 * in its place is this screen. Every extracted expense must show the message it
 * was read from, in the author's own words, next to the number.
 *
 * That is not decoration. Reading "who paid what" out of Vietnamese small talk
 * is guesswork, and it will be wrong sometimes. A wrong reading that shows its
 * source is a question a person can answer in two seconds. A wrong reading that
 * shows only a number is a number somebody accepts.
 *
 * Three things this screen deliberately does not do:
 *
 * - **No confidence score.** ADR-0009 decision 5. A percentage invites a rule
 *   like "auto-accept above 90%", and that rule hollows out the §8.3
 *   confirmation gate while looking like rigour.
 * - **No total.** The split belongs to the server's allocator. Adding the
 *   extracted amounts here would be a second implementation of money, which is
 *   what `api.ts` was carrying until it got removed.
 * - **No silent skipping.** Questions the skill could not answer are shown at
 *   the same level as the expenses, not tucked below them. "I need to ask
 *   something" is an outcome, not a footnote.
 */
import React from "react";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs";
import { radius, space, type, usePalette } from "../theme";
import {
  review,
  type Extraction,
  type ExtractedExpense,
  type ThreadMessage,
} from "../extraction";
import { Button, Card, Screen } from "../ui/Kit";

// The grounding decision lives in `extraction.ts` so it can be tested without
// a React renderer. This screen renders that decision; it does not make one.
export type { Extraction, ExtractedExpense, ThreadMessage } from "../extraction";

/**
 * An expense whose sources are missing or unknown to the thread.
 *
 * The validator refuses these server-side, so reaching the screen means
 * something upstream is broken. Rendering it loudly beats rendering it as a
 * normal row: an unsourced number that looks like every other number is
 * exactly the failure ADR-0008 traded §5.1 away to avoid.
 */
function Ungrounded({ expense }: { expense: ExtractedExpense }) {
  const c = usePalette();
  return (
    <View
      style={{
        borderColor: c.warn,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: 4,
      }}
    >
      <Text style={{ ...type.body, color: c.warn }}>
        {formatVnd(expense.totalVnd)}đ · {expense.label}
      </Text>
      <Text style={{ ...type.label, color: c.warn }}>
        Không tìm được tin nhắn nào cho khoản này, nên nó chưa dùng được. Nhập
        tay sẽ nhanh hơn là sửa nó.
      </Text>
    </View>
  );
}

function Quote({ message }: { message: ThreadMessage }) {
  const c = usePalette();
  return (
    <View
      style={{
        borderLeftColor: c.line,
        borderLeftWidth: 2,
        paddingLeft: space.sm,
        gap: 2,
      }}
    >
      <Text style={{ ...type.label, color: c.inkSoft }}>{message.author}</Text>
      {/* The author's words, not a summary. A paraphrase would be the bot
          checking its own reading. */}
      <Text style={{ ...type.body, color: c.ink }}>{message.text}</Text>
    </View>
  );
}

export function TheDeXuat({
  extraction,
  thread,
  onAccept,
  onEdit,
  onDismiss,
}: {
  extraction: Extraction;
  thread: ThreadMessage[];
  onAccept: (expenses: ExtractedExpense[]) => void;
  onEdit: () => void;
  onDismiss: () => void;
}) {
  const c = usePalette();
  const { grounded, ungrounded, blocked } = review(extraction, thread);

  return (
    <Screen
      title="Tôi đọc được thế này"
      hint="Mỗi số đều kèm tin nhắn tôi đọc ra nó. Xem lại rồi hãy xác nhận."
      footer={
        <>
          {blocked ? (
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Còn chỗ chưa chắc. Trả lời xong mới ghi vào sổ được.
            </Text>
          ) : null}
          <Button
            label="Đúng rồi, ghi vào sổ"
            disabled={blocked}
            onPress={() => onAccept(grounded.map((item) => item.expense))}
          />
          <Button label="Để tôi nhập tay" tone="quiet" onPress={onEdit} />
          <Button label="Bỏ qua" tone="quiet" onPress={onDismiss} />
        </>
      }
    >
      <ScrollView contentContainerStyle={{ gap: space.md }}>
        {extraction.questions.length > 0 ? (
          <Card>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Tôi cần hỏi trước
            </Text>
            {extraction.questions.map((question) => (
              <Text key={question} style={{ ...type.body, color: c.ink }}>
                {question}
              </Text>
            ))}
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Tôi không đoán những chỗ này. Đoán sai một lần là cả nhóm mất tin.
            </Text>
          </Card>
        ) : null}

        {grounded.length === 0 && ungrounded.length === 0 ? (
          <Card>
            <Text style={{ ...type.body, color: c.ink }}>
              Tôi không thấy khoản chi nào trong đoạn này.
            </Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Có thể mọi người chưa nói số tiền, hoặc đang nói đùa về tiền. Nhập
              tay thì chắc hơn.
            </Text>
          </Card>
        ) : null}

        {grounded.map(({ expense, sources }, index) => {
          return (
            <Card key={`${expense.label}-${index}`}>
              <Text style={{ ...type.amount, color: c.ink }}>
                {formatVnd(expense.totalVnd)}
                <Text style={{ ...type.body, color: c.inkSoft }}> đ</Text>
              </Text>
              <Text style={{ ...type.body, color: c.ink }}>
                {expense.label}
              </Text>
              <Text style={{ ...type.label, color: c.inkSoft }}>
                {expense.paidBy} trả trước
              </Text>

              <Text style={{ ...type.label, color: c.inkSoft, marginTop: space.sm }}>
                {sources.length === 1 ? "Đọc từ tin nhắn này" : "Đọc từ các tin nhắn này"}
              </Text>
              <View style={{ gap: space.sm }}>
                {sources.map((message) => (
                  <Quote key={message.id} message={message} />
                ))}
              </View>
            </Card>
          );
        })}

        {ungrounded.map((expense, index) => (
          <Ungrounded key={`ungrounded-${index}`} expense={expense} />
        ))}

        {/* Deliberately last and deliberately plain. The split is the server's
            job; this screen only says what it read. */}
        <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
          Chia tiền tính ở máy chủ, không tính ở đây.
        </Text>
      </ScrollView>
    </Screen>
  );
}
