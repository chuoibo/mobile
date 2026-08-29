/** Why the AI turn has five outcomes and not two.
 *
 * THIS FILE WAS REWRITTEN AGAINST THE REAL CONTRACT. The first version was
 * written while rd-be-04 was unmerged and guessed the wire: it POSTed
 * `{after_message_id}`, read `{speak: false}`, and looked for `kind:
 * "ai_card"` at the top level of the body. rd-be-04 landed (main @ 7e1db9a)
 * and the route takes NO body and answers `CompanionTurnResponse`:
 * `{context_id, spoke, reason, message}`. Every field the guess read is
 * absent, so the guessed client would have classified every real answer as
 * `hong` while its tests stayed green against the guessed shape.
 *
 * The interesting part is `spoke: false`, which arrives for six different
 * reasons that are NOT the same event:
 *
 *   no_conversation · already_spoke_last · rate_limited · cooldown
 *       -- `plan_turn` decided not to speak. This is the ceiling working.
 *          An AI that answers every message is annoying, not clever. Show
 *          nothing at all; there is no news here.
 *
 *   unavailable
 *       -- the model call itself failed: no key, a network fault, a
 *          malformed answer. Folding this into silence is the tempting bug,
 *          and it is the dishonest one. A deployment with no GEMINI_API_KEY
 *          would then look exactly like an AI that read the thread and had
 *          nothing to add, forever, and nobody would ever find out.
 *
 *   ungrounded
 *       -- the model named a place that is not in the server catalogue, so
 *          `ground_card` threw away the WHOLE card (rd-be-04 QĐ-2: rejecting
 *          the card is observable, quietly dropping one stop is not). This is
 *          the anti-fabrication guard firing. It is the system behaving
 *          correctly, but it is still a reason the user saw no answer, so it
 *          gets its own calm sentence rather than being hidden.
 *
 * `chua-noi-duoc` survives from the first version for one honest reason: a
 * 404 still means this build of the API predates rd-be-04, and the app can be
 * pointed at an older server than the one on main today.
 *
 * Activation is "a new text just landed in the group", not "@AI". The
 * in-flight flag lives with the caller so two sends cannot stack two turns;
 * this file will not invent a second call to cover a missed first.
 *
 * Nothing here ever renders a sentence this client wrote as though the model
 * wrote it. The only text that reaches a bubble comes from `message.card`.
 */

import { parseMessage, type MessageWire } from "./tin-nhan";

declare const process: { env: Record<string, string | undefined> };

export const AI_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

/** Named in the UI so a 404 is attributable rather than mysterious. */
export const AI_WORK_ITEM = "rd-be-04";

/** The reasons `plan_turn` gives for staying quiet on purpose. Anything else
 *  with `spoke: false` is a failure to answer, not a decision not to. */
export const LY_DO_IM_LANG = [
  "no_conversation",
  "already_spoke_last",
  "rate_limited",
  "cooldown",
] as const;

export type AiTurnState =
  /** The companion read the thread and chose not to speak. Draw nothing. */
  | { kind: "im-lang"; reason: string }
  /** A grounded card came back. Draw it. */
  | { kind: "da-noi"; message: MessageWire }
  /** Asked, but no usable answer: the model failed, or it tried to invent a
   *  place and the server refused the card. Say which, calmly. */
  | { kind: "khong-tra-loi-duoc"; reason: string; cau: string }
  /** This API build predates rd-be-04. Not an error; the app is ahead. */
  | { kind: "chua-noi-duoc"; url: string; cau: string }
  /** Anything else. Status and the server's own words. */
  | { kind: "hong"; url: string; status: number; detail: string };

/**
 * The calm sentence a 404/405 turns into.
 *
 * Kept as a function so the screen and the test assert the same words, and so
 * those words cannot drift into an error tone without the test noticing.
 * Names the work item and the address; does not say "lỗi".
 */
export function cauAiChuaNoiDuoc(url: string): string {
  return `AI chưa nối vào máy chủ này. Việc còn nợ là ${AI_WORK_ITEM}. Địa chỉ đã thử: ${url}.`;
}

/**
 * The sentence for `unavailable` and `ungrounded`.
 *
 * Both are honest about what happened without leaking anything: the server
 * never sends the exception text (it would risk carrying the API key or the
 * chat content), so neither does this.
 */
export function cauKhongTraLoiDuoc(reason: string): string {
  if (reason === "ungrounded") {
    return "AI có trả lời nhưng nhắc tới một địa điểm không có trong danh mục của máy chủ, nên cả thẻ đã bị bỏ. Không có gợi ý nào được đăng.";
  }
  return "AI chưa trả lời được lúc này. Máy chủ nhận yêu cầu nhưng phần trả lời không dùng được. Thử gửi thêm một tin nữa.";
}

export function aiTurnUrl(base: string, contextId: string): string {
  return `${base.replace(/\/$/, "")}/contexts/${contextId}/ai-turn`;
}

function headers(actorId: string, contextId: string, key?: string): Record<string, string> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Actor-ID": actorId,
    "X-Actor-Roles": "group_admin,member",
    "X-Actor-Contexts": contextId,
  };
  if (key) h["Idempotency-Key"] = key;
  return h;
}

async function docLoi(res: {
  status: number;
  json: () => Promise<unknown>;
  text: () => Promise<string>;
}): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown; code?: unknown };
    if (typeof body?.detail === "string" && body.detail.trim()) return body.detail;
    if (typeof body?.code === "string" && body.code.trim()) return body.code;
  } catch {
    /* not JSON */
  }
  try {
    const text = (await res.text()).slice(0, 200);
    if (text) return text;
  } catch {
    /* already consumed */
  }
  return `HTTP ${res.status}`;
}

/** Classify one 200 body. Exported so the test can drive it without a fetch. */
export function docThanAiTurn(raw: unknown, url: string): AiTurnState {
  const body = raw !== null && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : null;
  if (!body) {
    return {
      kind: "hong",
      url,
      status: 200,
      detail: "máy chủ trả về một thân không phải đối tượng",
    };
  }

  const reason = typeof body.reason === "string" ? body.reason : "";

  if (body.spoke === true) {
    try {
      return { kind: "da-noi", message: parseMessage(body.message, "ai-turn.message") };
    } catch (e) {
      return { kind: "hong", url, status: 200, detail: (e as Error).message };
    }
  }

  if (body.spoke === false) {
    if ((LY_DO_IM_LANG as readonly string[]).includes(reason)) {
      return { kind: "im-lang", reason };
    }
    // `unavailable`, `ungrounded`, and any reason a later server adds. An
    // unknown reason is treated as a failure to answer rather than as
    // silence, because silence is the state that hides things.
    return { kind: "khong-tra-loi-duoc", reason, cau: cauKhongTraLoiDuoc(reason) };
  }

  return {
    kind: "hong",
    url,
    status: 200,
    detail: "máy chủ trả lời nhưng không nói là đã nói hay chưa",
  };
}

/**
 * Call the AI turn once. Never throws.
 *
 * The route takes no body: the server reads the last 40 messages itself and
 * `plan_turn` decides from metadata alone. There is nothing for the client to
 * point at, and passing a message id would suggest the client picks the
 * window when it does not.
 */
export async function goiAiTurn(opts: {
  contextId: string;
  actorId: string;
  idempotencyKey?: string;
  base?: string;
}): Promise<AiTurnState> {
  const base = opts.base ?? AI_BASE_URL;
  const url = aiTurnUrl(base, opts.contextId);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: headers(opts.actorId, opts.contextId, opts.idempotencyKey),
    });
  } catch (e) {
    return { kind: "hong", url, status: 0, detail: (e as Error).message };
  }

  if (res.status === 404 || res.status === 405) {
    return { kind: "chua-noi-duoc", url, cau: cauAiChuaNoiDuoc(url) };
  }
  // 204 is read as silence without touching the body: some stacks reject
  // `json()` on an empty response, and that rejection is not a server fault.
  if (res.status === 204) return { kind: "im-lang", reason: "no_content" };
  if (!res.ok) {
    return { kind: "hong", url, status: res.status, detail: await docLoi(res) };
  }

  let raw: unknown = null;
  try {
    const text = await res.text();
    if (!text.trim()) return { kind: "im-lang", reason: "no_content" };
    raw = JSON.parse(text) as unknown;
  } catch (e) {
    return { kind: "hong", url, status: res.status, detail: (e as Error).message };
  }
  return docThanAiTurn(raw, url);
}
