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
 * Split an extraction into what a person can check and what they cannot.
 *
 * An expense citing a message id the thread does not contain is treated the
 * same as one citing nothing. A dangling id is worse than an absent one: it
 * looks like provenance while pointing nowhere.
 */
export function review(extraction: Extraction, thread: ThreadMessage[]): Reviewed {
  const byId = new Map(thread.map((message) => [message.id, message]));

  const grounded: Reviewed["grounded"] = [];
  const ungrounded: ExtractedExpense[] = [];

  for (const expense of extraction.expenses) {
    const sources = expense.sourceMessageIds
      .map((id) => byId.get(id))
      .filter((message): message is ThreadMessage => message !== undefined);
    if (sources.length === 0) {
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
