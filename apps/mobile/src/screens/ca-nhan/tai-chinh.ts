/** Reading one person's money off the API, and shaping it for the screen.
 *
 * Nothing here computes money. `settled + outstanding == spend` is guaranteed
 * by the ledger query that answers this route, and the screen renders the
 * three numbers it is given -- deriving even one of them here would be a
 * second implementation of the same arithmetic, which is exactly how two
 * screens end up showing two different totals for one dinner.
 *
 * Formatting is not computing. Grouping digits and naming a direction change
 * how a number reads, never what it is.
 *
 * Split out of the component so the parts worth testing can be tested without
 * rendering anything: the money formatter, the sign, and the failure text.
 */
import { BASE_URL } from "../../api";

/** One confirmed arrival, as the server describes it. */
export type Movement = {
  obligation_id: string;
  /** `out` when this person sent it, `in` when they collected it. */
  direction: "in" | "out";
  /** Always positive. The sign lives in `direction`. */
  amount_vnd: number;
  counterparty_id: string;
  counterparty_name: string | null;
  context_id: string;
  context_name: string | null;
  occasion: string | null;
  occurred_at: string;
};

export type Finance = {
  person_id: string;
  display_name: string | null;
  spend_vnd: number;
  settled_vnd: number;
  outstanding_vnd: number;
  expense_count: number;
  group_count: number;
  movements: Movement[];
};

/**
 * Money as Vietnamese writes it: `860.000đ`.
 *
 * `Intl` is not used. Hermes ships without full ICU unless the app opts into a
 * larger binary, and `toLocaleString` there silently falls back to the C
 * locale -- which groups with commas. A demo in front of Vietnamese viewers
 * showing `860,000đ` is a small thing that reads as a foreign product, and the
 * failure is invisible on the web build, where Intl works fine.
 */
export function tienVnd(amount: number): string {
  const negative = amount < 0;
  const digits = Math.abs(Math.trunc(amount)).toString();
  let grouped = "";
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) grouped += ".";
    grouped += digits[i];
  }
  return `${negative ? "-" : ""}${grouped}đ`;
}

/** A movement with its sign shown, the way the mockup prints it. */
export function tienCoDau(movement: Movement): string {
  return `${movement.direction === "in" ? "+" : "-"}${tienVnd(movement.amount_vnd)}`;
}

/** `20/05`, from the ISO instant the server sent. */
export function ngayNgan(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  const dd = `${at.getDate()}`.padStart(2, "0");
  const mm = `${at.getMonth() + 1}`.padStart(2, "0");
  return `${dd}/${mm}`;
}

/** What a movement was for, without ever printing a bare id. */
export function moTaGiaoDich(movement: Movement): string {
  const who = movement.counterparty_name;
  if (movement.direction === "in") {
    return who ? `${who} đã chuyển cho bạn` : "Bạn nhận được";
  }
  return who ? `Bạn đã trả ${who}` : "Bạn đã thanh toán";
}

export class FinanceError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "FinanceError";
  }
}

/**
 * Ask the server what this person's money looks like right now.
 *
 * Self-only at the server, so the actor header and the path id are the same
 * person by construction rather than by the caller remembering. Passing a
 * different pair is a 403, which is the rule working.
 *
 * No caching and no fallback data. This screen exists to show that the numbers
 * moved; a stale copy served while the network is down would show that they
 * did not.
 */
export async function layTaiChinh(
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Finance> {
  let response: Response;
  try {
    response = await fetchImpl(`${BASE_URL}/people/${personId}/finance`, {
      headers: {
        "X-Actor-ID": personId,
        "X-Actor-Roles": "member",
        Accept: "application/json",
      },
    });
  } catch {
    // Names the address it tried. "Không kết nối được" on its own sends
    // somebody to check their wifi when the real answer is that the phone is
    // pointed at the laptop's localhost.
    throw new FinanceError(0, `Không gọi được ${BASE_URL}`);
  }
  if (!response.ok) {
    let code = "";
    try {
      code = ((await response.json()) as { code?: string }).code ?? "";
    } catch {
      code = "";
    }
    throw new FinanceError(response.status, loiTaiChinh(response.status, code));
  }
  return (await response.json()) as Finance;
}

/** Refusals in words the person reading them can act on. */
export function loiTaiChinh(status: number, code: string): string {
  if (code === "not_your_finances") return "Chỉ chính chủ xem được phần tài chính này.";
  if (status === 401) return "Chưa đăng nhập nên chưa hỏi được máy chủ.";
  if (status >= 500) return "Máy chủ đang lỗi, chưa đọc được sổ.";
  return `Máy chủ trả lỗi ${status}.`;
}
