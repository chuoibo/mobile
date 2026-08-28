/** Reading the bot's output, and refusing the parts that cannot be checked.
 *
 * ADR-0008 let the bot read the whole thread. §5.1 had forbidden that, and the
 * thing put in its place was a rule: every extracted expense must cite the
 * message it was read from. This module is where that rule is enforced on the
 * client, so the screen renders a decision rather than making one.
 *
 * The validator on the server refuses ungrounded expenses too. Checking again
 * here is not redundancy for its own sake -- the screen is what a person acts
 * on, and "the server would have caught it" is no comfort if the number is
 * already on their screen looking like every other number.
 */

export type ThreadMessage = {
  id: string;
  author: string;
  text: string;
};

export type ExtractedExpense = {
  totalVnd: number;
  paidBy: string;
  label: string;
  sourceMessageIds: string[];
};

export type Extraction = {
  expenses: ExtractedExpense[];
  questions: string[];
};

export type Reviewed = {
  /** Expenses whose sources exist in the thread, with those messages attached. */
  grounded: { expense: ExtractedExpense; sources: ThreadMessage[] }[];
  /** Expenses citing nothing, or citing messages this thread does not contain. */
  ungrounded: ExtractedExpense[];
  /** Whether anything is still unresolved. */
  blocked: boolean;
};

/**
 * Does this message actually contain this amount?
 *
 * A display guard, not the contract. The server's validator is the authority
 * and normalises Vietnamese amounts properly; this is the cheap version that
 * stops the screen from asserting something the server would reject.
 *
 * It recognises the forms people write in chat:
 *
 *     800000   800.000   800,000   800 000    -> plain digits
 *     800k     800 k                          -> thousands
 *     1tr2     1 triệu 2   2tr350              -> millions, with a remainder
 *     85 nghìn   85 ngàn                       -> thousands, spelled
 *
 * When it cannot recognise anything it returns false, and false means the
 * expense is shown as unverifiable rather than shown as checked. Erring toward
 * "I could not confirm this" is the only safe direction here: the alternative
 * is a screen that says "read from this message" next to a message that says
 * nothing of the kind.
 */
export function messageMentionsAmount(text: string, amountVnd: number): boolean {
  const lower = text.toLowerCase();
  const bare = lower.replace(/[.,\s]/g, "");

  // Written out in full, with or without separators.
  if (bare.includes(String(amountVnd))) return true;

  // `800k`, `85 nghìn`, `85 ngàn` -- thousands.
  for (const match of lower.matchAll(/(\d+(?:[.,]\d+)?)\s*(k|nghìn|ngàn|nghin|ngan)\b/g)) {
    const value = Number(match[1].replace(",", "."));
    if (Number.isFinite(value) && Math.round(value * 1_000) === amountVnd) return true;
  }

  // `1tr2`, `2tr350`, `1 triệu 2` -- millions, where a trailing group is a
  // remainder in hundreds of thousands or in thousands depending on length.
  for (const match of lower.matchAll(/(\d+)\s*(?:tr|triệu|trieu)\s*(\d{1,3})?/g)) {
    const millions = Number(match[1]);
    const rest = match[2];
    if (!Number.isFinite(millions)) continue;
    if (!rest) {
      if (millions * 1_000_000 === amountVnd) return true;
      continue;
    }
    // "1tr2" is 1.200.000, "2tr350" is 2.350.000: the remainder is scaled to
    // whatever gets it to six digits.
    const scaled = Number(rest) * 10 ** (3 - rest.length);
    if (millions * 1_000_000 + scaled * 1_000 === amountVnd) return true;
  }

  return false;
}

/**
 * Split an extraction into what a person can check and what they cannot.
 *
 * Three ways an expense fails to be checkable, and QA found the last two by
 * reading this function:
 *
 * 1. **It cites nothing.** Obvious.
 * 2. **It cites a message the thread does not have.** A dangling id used to be
 *    dropped silently, leaving the surviving citations to carry the expense --
 *    so `["m1", "m_does_not_exist"]` displayed as fully sourced. If the missing
 *    one held the number, the person is told the opposite of the truth.
 * 3. **It cites a message that does not mention the amount.** This checked only
 *    that the id resolved, never that the message said anything relevant. A bot
 *    could return 500.000đ sourced to "Chào cả nhà" and the screen would print
 *    the greeting under the heading "Đọc từ tin nhắn này".
 *
 * The third is the one that matters. ADR-0008 let the bot read the whole thread
 * in exchange for citation, and a citation nobody checks is not a citation.
 */
export function review(extraction: Extraction, thread: ThreadMessage[]): Reviewed {
  const byId = new Map(thread.map((message) => [message.id, message]));

  const grounded: Reviewed["grounded"] = [];
  const ungrounded: ExtractedExpense[] = [];

  for (const expense of extraction.expenses) {
    const resolved = expense.sourceMessageIds.map((id) => byId.get(id));
    const dangling = resolved.some((message) => message === undefined);
    const sources = resolved.filter(
      (message): message is ThreadMessage => message !== undefined,
    );
    const mentionsAmount = sources.some((message) =>
      messageMentionsAmount(message.text, expense.totalVnd),
    );

    if (sources.length === 0 || dangling || !mentionsAmount) {
      ungrounded.push(expense);
    } else {
      grounded.push({ expense, sources });
    }
  }

  return {
    grounded,
    ungrounded,
    // Questions block acceptance. §8.3: nothing goes out in someone's name
    // until the facts are settled, and "I do not know who was there" is not
    // settled. Letting it through anyway would make the question decorative.
    blocked: extraction.questions.length > 0 || ungrounded.length > 0,
  };
}
