/** Why this file exists: there is no AI turn on the server, and the screen
 *  has to be able to say that without looking like an error and without
 *  lying that the model spoke.
 *
 * rd-be-04 is the work item that would add `POST /contexts/{id}/ai-turn`.
 * It is not on this server. Confirmed by `git ls-tree` and grep, not by a
 * 404 we once saw and might have misread. A client that then posted a
 * canned itinerary under `kind: "ai_card"` would put a sentence on screen
 * that is indistinguishable from one the model wrote, which is exactly
 * what the acceptance criteria forbid. So this file calls the route that
 * does not exist, and it classifies the answer into four states the
 * screen can tell apart:
 *
 *   * `im-lang`  -- 204, or `{ speak: false }`. The model read the thread
 *     and had nothing to add. That is a correct behaviour, not a fault.
 *     The screen shows nothing.
 *   * `da-noi`   -- a real `ai_card` came back. Draw it.
 *   * `chua-noi-duoc` -- 404 or 405. This build of the API does not have
 *     rd-be-04. The sentence names that work item and the URL that was
 *     tried, in the same calm voice `ChuaCoDuLieu` uses for a missing
 *     `GET /places`. It is not coloured as an error, because it is not
 *     one: the app is ahead of the server, not broken.
 *   * `hong`     -- any other failure. Status and the server's own words.
 *
 * Activation is "a new text just landed in the group", not "@AI". The
 * in-flight flag lives with the caller so two sends cannot stack two
 * turns; this file will not invent a second call to cover a missed first.
 */

import { parseMessage, type MessageWire } from "./tin-nhan";

declare const process: { env: Record<string, string | undefined> };

export const AI_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

/** Named in the UI so a 404 is attributable rather than mysterious. */
export const AI_WORK_ITEM = "rd-be-04";

export type AiTurnState =
  | { kind: "im-lang" }
  | { kind: "da-noi"; message: MessageWire }
  | { kind: "chua-noi-duoc"; url: string; cau: string }
  | { kind: "hong"; url: string; status: number; detail: string };

/**
 * The calm sentence a 404/405 turns into.
 *
 * Kept as a function so the screen and the test assert the same words, and
 * so those words cannot drift into an error tone without the test noticing.
 * Names the work item and the address; does not say "lỗi".
 */
export function cauAiChuaNoiDuoc(url: string): string {
  return `AI chưa nối vào máy chủ này. Việc còn nợ là ${AI_WORK_ITEM}. Địa chỉ đã thử: ${url}.`;
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

async function docLoi(res: { status: number; json: () => Promise<unknown>; text: () => Promise<string> }): Promise<string> {
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

function docThan(raw: unknown, url: string): AiTurnState {
  if (raw === null || raw === undefined) return { kind: "im-lang" };
  if (typeof raw !== "object") {
    return { kind: "hong", url, status: 200, detail: `máy chủ trả về ${JSON.stringify(raw)}` };
  }
  const body = raw as Record<string, unknown>;
  if (body.speak === false) return { kind: "im-lang" };
  if (body.kind === "ai_card") {
    try {
      return { kind: "da-noi", message: parseMessage(body, "ai-turn") };
    } catch (e) {
      return { kind: "hong", url, status: 200, detail: (e as Error).message };
    }
  }
  return {
    kind: "hong",
    url,
    status: 200,
    detail: "máy chủ trả lời nhưng không có thẻ AI và cũng không im lặng",
  };
}

/**
 * Call the AI turn once. Never throws.
 *
 * 204 is read as silence without touching the body: some stacks reject
 * `json()` on an empty response, and that rejection is not a server fault.
 */
export async function goiAiTurn(opts: {
  contextId: string;
  actorId: string;
  afterMessageId: string;
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
      body: JSON.stringify({ after_message_id: opts.afterMessageId }),
    });
  } catch (e) {
    return { kind: "hong", url, status: 0, detail: (e as Error).message };
  }

  if (res.status === 404 || res.status === 405) {
    return { kind: "chua-noi-duoc", url, cau: cauAiChuaNoiDuoc(url) };
  }
  if (res.status === 204) return { kind: "im-lang" };
  if (!res.ok) {
    return { kind: "hong", url, status: res.status, detail: await docLoi(res) };
  }

  let raw: unknown = null;
  try {
    const text = await res.text();
    if (!text.trim()) return { kind: "im-lang" };
    raw = JSON.parse(text) as unknown;
  } catch (e) {
    return { kind: "hong", url, status: res.status, detail: (e as Error).message };
  }
  return docThan(raw, url);
}
