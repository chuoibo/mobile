/** Counting the votes. The whole of F17's correctness lives in this file.
 *
 * WHERE THE STATE ACTUALLY IS, and why that is not a stub.
 *
 * There is no `/polls` route. rd-be-09 is queued and unwritten; at the time
 * this was built `main` had 16 route modules and none of them was a poll.
 * So a poll here is not held in app memory and it is not faked: it is a real
 * `ai_card` message in the real thread, written by
 * `POST /contexts/{id}/messages`, persisted in Postgres, read back by every
 * other member through `GET /contexts/{id}/messages`.
 *
 * That choice is only sound because of one server fact, checked in
 * `service.py` before a line of this was written: `post_context_message`
 * sets `author_id=actor.id` from the trusted actor header and gates the call
 * on `is_group_member`. A CLIENT CANNOT SAY WHO VOTED. It can only cast its
 * own ballot, and non-members get 403. If that ever stops being true, "one
 * person one vote" below stops being true with it, and this comment is the
 * place to come back to.
 *
 * THE SEAM. Everything under here is a fold over an array of messages. When
 * rd-be-09 lands, the server will return tallies directly and this file's
 * job shrinks to translating them: `tongHopBinhChon` is the only function
 * that needs a second implementation, and the screen never sees a message.
 * That is deliberate -- two live vote counters in one product is the same
 * failure as two splitters, and the way to not have that is to keep the
 * counting in one replaceable place rather than spread through the UI.
 *
 * FOUR THINGS THIS REFUSES TO DO, each of which would look like a feature:
 *
 *  1. NO BREAKING A TIE. A tie is a result and it is reported as one. There
 *     is no list-order fallback, no earliest-vote fallback. `dangHoa` is
 *     true and `dienDau` holds every option level at the top.
 *  2. NO BALLOT FOR THE MACHINE. A vote card with `author_id === null` is
 *     the companion speaking, and it is dropped. The AI proposes options; it
 *     does not get to choose among them.
 *  3. NO COUNTING A VOTE FOR AN OPTION THAT DOES NOT EXIST. A vote naming an
 *     unknown `option_id` is dropped, never re-homed onto a neighbour.
 *  4. NO REDEFINING A POLL THAT IS ALREADY OPEN. The first card for a
 *     `poll_id` wins. A later card reusing that id cannot swap the options
 *     out from under ballots already cast.
 *
 * Free of React and of `fetch` on purpose, so `tests/binh-chon.test.mjs`
 * checks the arithmetic without a renderer and without a server.
 */

import { docDiaDiem, theTuCard, type DiaDiem } from "./ke-hoach";
import type { MessageWire } from "./tin-nhan";

/** One choice on the ballot. `diaDiem` is present when the option came from
 *  a place the AI proposed, which is the case F17 is written around. */
export type LuaChon = {
  optionId: string;
  nhan: string;
  diaDiem: DiaDiem | null;
};

/** A poll as posted, before any ballot is counted. */
export type BinhChon = {
  pollId: string;
  cauHoi: string;
  luaChon: LuaChon[];
  /** Message id of the card that opened it. Stable, and useful as a key. */
  messageId: string;
  taoBoi: string | null;
};

/** One row of the result. `phieu` is the truth; `phanTram` is a label. */
export type KetQuaLuaChon = {
  optionId: string;
  nhan: string;
  diaDiem: DiaDiem | null;
  phieu: number;
  phanTram: number;
  /** Level with the highest count, and at least one vote exists. */
  dangDan: boolean;
};

export type KetQuaBinhChon = {
  pollId: string;
  cauHoi: string;
  messageId: string;
  ketQua: KetQuaLuaChon[];
  tongPhieu: number;
  /** Distinct people who cast a ballot. Never larger than `tongPhieu`, and
   *  equal to it, because a later ballot replaces an earlier one. */
  soNguoiDaBoPhieu: number;
  /** Every option tied at the top. One entry when there is a clear winner,
   *  more than one when it is a draw, none when nobody has voted. */
  dienDau: string[];
  dangHoa: boolean;
  /** The option this device's person chose, or null. */
  luaChonCuaToi: string | null;
};

const KIND_POLL = "poll";
const KIND_VOTE = "poll_vote";

function banGhi(value: unknown): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function chuoi(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const t = value.trim();
  return t === "" ? null : t;
}

/**
 * Read a poll card, or return null.
 *
 * Null for anything malformed, and null is the honest answer: the thread
 * then draws the "thẻ này không đọc được" row it already has for an
 * unreadable card, rather than a ballot with blank rows on it.
 *
 * Options are deduplicated by `option_id`. Two rows sharing an id would make
 * one ballot count twice on screen while the fold below counted it once.
 */
export function binhChonTuCard(card: unknown, messageId: string, taoBoi: string | null): BinhChon | null {
  const root = banGhi(card);
  if (!root || root.kind !== KIND_POLL) return null;
  const payload = banGhi(root.payload);
  if (!payload) return null;

  const pollId = chuoi(payload.poll_id);
  const cauHoi = chuoi(payload.question);
  if (!pollId || !cauHoi) return null;
  if (!Array.isArray(payload.options)) return null;

  const daThay = new Set<string>();
  const luaChon: LuaChon[] = [];
  for (const raw of payload.options) {
    const o = banGhi(raw);
    if (!o) continue;
    const optionId = chuoi(o.option_id);
    if (!optionId || daThay.has(optionId)) continue;
    const diaDiem = o.place === undefined || o.place === null ? null : docDiaDiem(o.place);
    // A place-backed option is labelled by the place, so the label may be
    // absent on the wire. An option with neither is unrenderable, so drop it.
    const nhan = chuoi(o.label) ?? diaDiem?.ten ?? null;
    if (!nhan) continue;
    daThay.add(optionId);
    luaChon.push({ optionId, nhan, diaDiem });
  }

  // A ballot with nothing on it, or with one forced answer, is not a vote.
  if (luaChon.length < 2) return null;
  return { pollId, cauHoi, luaChon, messageId, taoBoi };
}

type PhieuBau = { pollId: string; optionId: string };

function phieuTuCard(card: unknown): PhieuBau | null {
  const root = banGhi(card);
  if (!root || root.kind !== KIND_VOTE) return null;
  const payload = banGhi(root.payload);
  if (!payload) return null;
  const pollId = chuoi(payload.poll_id);
  const optionId = chuoi(payload.option_id);
  if (!pollId || !optionId) return null;
  return { pollId, optionId };
}

/** Build the card body for opening a poll. Kept next to the parser so the
 *  two shapes cannot drift apart. */
export function cardMoBinhChon(opts: {
  pollId: string;
  cauHoi: string;
  luaChon: { optionId: string; nhan: string; diaDiem?: DiaDiem | null }[];
}): Record<string, unknown> {
  return {
    kind: KIND_POLL,
    payload: {
      poll_id: opts.pollId,
      question: opts.cauHoi,
      options: opts.luaChon.map((l) => ({
        option_id: l.optionId,
        label: l.nhan,
        ...(l.diaDiem ? { place: { id: l.diaDiem.id, name: l.diaDiem.ten } } : {}),
      })),
    },
  };
}

/** Build the card body for one ballot. */
export function cardBoPhieu(pollId: string, optionId: string): Record<string, unknown> {
  return { kind: KIND_VOTE, payload: { poll_id: pollId, option_id: optionId } };
}

/**
 * Integer percentages that sum to exactly 100, by largest remainder.
 *
 * Not a flourish. Rounding each share on its own puts "71% / 29% / 0%"
 * next to a bar row that adds to 99 or 101, and a person reading a vote
 * result notices that immediately and stops trusting the count. This is the
 * same discipline the money allocator holds -- the parts equal the whole --
 * applied to a label rather than to đồng.
 *
 * Remainder ties break by the option's position on the ballot, so two phones
 * looking at the same thread always print the same numbers.
 */
export function phanTramTronVen(counts: number[]): number[] {
  const total = counts.reduce((a, b) => a + b, 0);
  if (total <= 0) return counts.map(() => 0);

  const chinhXac = counts.map((c) => (c * 100) / total);
  const san = chinhXac.map((v) => Math.floor(v));
  let conLai = 100 - san.reduce((a, b) => a + b, 0);

  const thuTu = chinhXac
    .map((v, i) => ({ i, du: v - Math.floor(v) }))
    .sort((a, b) => (b.du === a.du ? a.i - b.i : b.du - a.du));

  const out = san.slice();
  for (const { i } of thuTu) {
    if (conLai <= 0) break;
    out[i] = out[i]! + 1;
    conLai -= 1;
  }
  return out;
}

/**
 * Fold the thread into results, one entry per poll, in the order the polls
 * were opened.
 *
 * `messages` must be in thread order, oldest first -- which is exactly what
 * the screen already holds, because `tinHienThiLanDau` reversed the server's
 * newest-first page before anything was drawn. Later position means later
 * ballot, so a person changing their mind is just their last vote card
 * overwriting their earlier one in the map. That is where "mỗi người một
 * phiếu" is actually enforced, and it is enforced against `author_id`, a
 * field the server writes and the client cannot forge.
 */
export function tongHopBinhChon(messages: MessageWire[], toiLaAi: string | null): KetQuaBinhChon[] {
  const polls = new Map<string, BinhChon>();
  // poll_id -> (person_id -> option_id). Last write wins.
  const phieu = new Map<string, Map<string, string>>();

  for (const m of messages) {
    if (m.kind !== "ai_card" || m.card === null) continue;

    const poll = binhChonTuCard(m.card, m.id, m.author_id);
    if (poll) {
      // First card for an id owns it: options cannot be swapped under votes
      // that were already cast against them.
      if (!polls.has(poll.pollId)) polls.set(poll.pollId, poll);
      continue;
    }

    const bau = phieuTuCard(m.card);
    if (!bau) continue;
    // The companion has no ballot. Without an author there is no person to
    // hold the "one each" rule against, so this is dropped rather than
    // counted under some placeholder.
    if (!m.author_id) continue;
    let hop = phieu.get(bau.pollId);
    if (!hop) {
      hop = new Map<string, string>();
      phieu.set(bau.pollId, hop);
    }
    hop.set(m.author_id, bau.optionId);
  }

  const ra: KetQuaBinhChon[] = [];
  for (const poll of polls.values()) {
    const hop = phieu.get(poll.pollId) ?? new Map<string, string>();
    const hopLe = new Set(poll.luaChon.map((l) => l.optionId));

    const dem = new Map<string, number>(poll.luaChon.map((l) => [l.optionId, 0]));
    let tongPhieu = 0;
    let luaChonCuaToi: string | null = null;
    for (const [personId, optionId] of hop) {
      // A ballot naming an option this poll does not have is dropped. It is
      // never re-homed onto a neighbour, which would invent a preference.
      if (!hopLe.has(optionId)) continue;
      dem.set(optionId, dem.get(optionId)! + 1);
      tongPhieu += 1;
      if (toiLaAi && personId === toiLaAi) luaChonCuaToi = optionId;
    }

    const counts = poll.luaChon.map((l) => dem.get(l.optionId)!);
    const phanTram = phanTramTronVen(counts);
    const cao = counts.length ? Math.max(...counts) : 0;
    const dienDau = cao > 0 ? poll.luaChon.filter((l, i) => counts[i] === cao).map((l) => l.optionId) : [];

    ra.push({
      pollId: poll.pollId,
      cauHoi: poll.cauHoi,
      messageId: poll.messageId,
      ketQua: poll.luaChon.map((l, i) => ({
        optionId: l.optionId,
        nhan: l.nhan,
        diaDiem: l.diaDiem,
        phieu: counts[i]!,
        phanTram: phanTram[i]!,
        dangDan: cao > 0 && counts[i] === cao,
      })),
      tongPhieu,
      soNguoiDaBoPhieu: tongPhieu,
      dienDau,
      dangHoa: dienDau.length > 1,
      luaChonCuaToi,
    });
  }
  return ra;
}

/**
 * Every place the companion has put on the table in this thread, oldest
 * first, deduplicated by id.
 *
 * This is the ballot's supply of options, and the reason the compose screen
 * has no free-text field. A typed option would be a place the server never
 * asserted, and the group would then vote on -- and later go to -- somewhere
 * that exists only in a chat message. Every row here came from a `places` or
 * `itinerary` card, which the server grounds against its own catalogue, so
 * `optionId` is a real place id that a later ballot and a later plan both
 * resolve to the same row.
 *
 * Ordered by first mention rather than by name: the thread's order is the
 * order the group already discussed them in, and re-sorting would quietly
 * promote whichever place happens to start with an early letter.
 */
export function diaDiemDaGoiY(messages: MessageWire[]): DiaDiem[] {
  const daThay = new Set<string>();
  const ra: DiaDiem[] = [];
  for (const m of messages) {
    if (m.kind !== "ai_card" || m.card === null) continue;
    const the = theTuCard(m.card);
    if (!the) continue;
    const trong =
      the.kind === "places" ? the.diaDiem : the.kind === "itinerary" ? the.chang.map((ch) => ch.diaDiem) : [];
    for (const d of trong) {
      if (daThay.has(d.id)) continue;
      daThay.add(d.id);
      ra.push(d);
    }
  }
  return ra;
}

/** The most recently opened poll in the thread, which is the one the chat
 *  tab surfaces. Null when the thread has none. */
export function binhChonGanNhat(
  messages: MessageWire[],
  toiLaAi: string | null,
): KetQuaBinhChon | null {
  const tatCa = tongHopBinhChon(messages, toiLaAi);
  return tatCa.length === 0 ? null : tatCa[tatCa.length - 1]!;
}

/**
 * One line saying where the vote stands, for the screen and for the screen
 * reader. The tie is stated in words here, not left to a chip a screen
 * reader might not reach.
 */
export function cauKetQua(kq: KetQuaBinhChon): string {
  if (kq.tongPhieu === 0) return "Chưa có phiếu nào";
  if (kq.dangHoa) {
    const ten = kq.ketQua.filter((r) => r.dangDan).map((r) => r.nhan);
    return `Đang hoà giữa ${ten.join(" và ")}`;
  }
  const dan = kq.ketQua.find((r) => r.dangDan)!;
  return `${dan.nhan} đang dẫn với ${dan.phieu} phiếu`;
}
