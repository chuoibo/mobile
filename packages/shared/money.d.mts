export declare function formatVnd(amountVnd: number): string;
export declare const MAX_AMOUNT_VND: number;
export type ParsedAmount =
  | { ok: true; value: number }
  | { ok: false; reason: "empty" | "not-a-number" | "too-large" };
export declare function parseAmountVnd(typed: string): ParsedAmount;
