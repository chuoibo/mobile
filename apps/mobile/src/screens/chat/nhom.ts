/** Why this screen cannot use the group id already sitting in `api.ts`.
 *
 * `CONTEXT_ID` there (`1aa00000-aaaa-…`) was minted so the expense flow had
 * *a* group to agree on across screens. It has never had a row in the
 * `contexts` table. Membership is not the actor header either: the server
 * computes `is_group_member` with `repository.is_member(context_id, actor.id)`,
 * a real query. Posting a chat message under that synthetic id is a 403
 * `permission_denied` with certainty, and the thread would then look empty
 * for a reason the empty-state copy could not name.
 *
 * So this file builds the group the way `scripts/seed_demo_data.py` does,
 * through the HTTP API, in four steps that are stable under retry:
 *
 *   1. `PUT /people/{id}` for the person signed in, and for `minh` (the
 *      creator). Without a people row, `POST /contexts` is a 500 on a
 *      foreign key, which is how this product used to greet every caller.
 *   2. `POST /contexts` as `minh`, idempotency key `uuid5(ns, "write:context")`.
 *      If the seed already ran, the middleware replays the original group.
 *      If it did not, this creates it and makes `minh` the admin. One call,
 *      two circumstances, one stable id.
 *   3. If the signed-in person is not `minh`: invite (as `minh`) then accept
 *      (as themselves). A 409 on accept is SUCCESS -- they are already in.
 *      Treating it as a fault would strand a seeded member behind a
 *      "could not join" banner on every launch.
 *   4. `GET /contexts/{id}/members` for the list the header prints. The
 *      number of members is this list's length, never a fixture.
 *
 * Every write carries a derived idempotency key, so pressing again replays
 * instead of doubling. Every failure names the step that died and the
 * address that was tried, because "không vào được nhóm" without either is
 * how an afternoon gets spent restarting a server that was fine.
 */

import { DEMO_GROUP_NAME, DEMO_PEOPLE, personById } from "../../navigation/nhom-demo";
import { KHONG_GIAN_DEMO, idNguoi, khoaGhi } from "./uuid5";

declare const process: { env: Record<string, string | undefined> };

export const NHOM_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

export type BuocNhom = "dat-ten" | "tao-nhom" | "moi" | "chap-nhan" | "doc-thanh-vien";

export type ThanhVien = {
  id: string;
  contextId: string;
  personId: string;
  state: "invited" | "active" | "left";
  role: "member" | "admin";
};

export type NhomState =
  | {
      kind: "xong";
      contextId: string;
      tenNhom: string;
      members: ThanhVien[];
    }
  | {
      kind: "hong";
      buoc: BuocNhom;
      url: string;
      status: number;
      detail: string;
    };

const MINH_SLUG = "minh";

function headers(actorId: string, contextId?: string, key?: string): Record<string, string> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Actor-ID": actorId,
    "X-Actor-Roles": "group_admin,member",
  };
  if (contextId) h["X-Actor-Contexts"] = contextId;
  if (key) h["Idempotency-Key"] = key;
  return h;
}

function goc(base: string): string {
  return base.replace(/\/$/, "");
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

function hong(buoc: BuocNhom, url: string, status: number, detail: string): NhomState {
  return { kind: "hong", buoc, url, status, detail };
}

type CallOk = { ok: true; status: number; body: unknown };
type CallFail = { ok: false; state: NhomState };

async function goi(
  buoc: BuocNhom,
  url: string,
  init: RequestInit,
  { choPhep409 = false }: { choPhep409?: boolean } = {},
): Promise<CallOk | CallFail> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    return { ok: false, state: hong(buoc, url, 0, (e as Error).message) };
  }
  if (choPhep409 && res.status === 409) {
    return { ok: true, status: 409, body: null };
  }
  if (!res.ok) {
    return { ok: false, state: hong(buoc, url, res.status, await docLoi(res)) };
  }
  if (res.status === 204) return { ok: true, status: 204, body: null };
  try {
    const text = await res.text();
    const body = text.trim() ? (JSON.parse(text) as unknown) : null;
    return { ok: true, status: res.status, body };
  } catch (e) {
    return { ok: false, state: hong(buoc, url, res.status, (e as Error).message) };
  }
}

function docThanhVien(raw: unknown, field: string): ThanhVien {
  const m = raw as Record<string, unknown>;
  const state = m?.state;
  const role = m?.role;
  if (state !== "invited" && state !== "active" && state !== "left") {
    throw new Error(`${field}.state lạ: ${JSON.stringify(state)}`);
  }
  if (role !== "member" && role !== "admin") {
    throw new Error(`${field}.role lạ: ${JSON.stringify(role)}`);
  }
  if (typeof m.id !== "string" || typeof m.context_id !== "string" || typeof m.person_id !== "string") {
    throw new Error(`${field} thiếu id/context_id/person_id`);
  }
  return {
    id: m.id,
    contextId: m.context_id,
    personId: m.person_id,
    state,
    role,
  };
}

async function datTen(
  base: string,
  slug: string,
  personId: string,
  name: string,
): Promise<CallOk | CallFail> {
  const url = `${goc(base)}/people/${personId}`;
  return goi("dat-ten", url, {
    method: "PUT",
    headers: headers(personId, undefined, khoaGhi(slug)),
    body: JSON.stringify({ display_name: name }),
  });
}

/**
 * Open (or replay) the demo group under the signed-in slug, then return the
 * real members. Never throws.
 */
export async function khoiDongNhom(
  slug: string,
  opts: { base?: string } = {},
): Promise<NhomState> {
  const base = opts.base ?? NHOM_BASE_URL;
  const nguoi = personById(slug);
  if (!nguoi) {
    return hong(
      "dat-ten",
      `${goc(base)}/people`,
      0,
      `không có người "${slug}" trong nhóm demo, không bịa một người khác`,
    );
  }

  const minh = personById(MINH_SLUG)!;
  const minhDat = await datTen(base, MINH_SLUG, minh.personId, minh.name);
  if (!minhDat.ok) return minhDat.state;
  if (slug !== MINH_SLUG) {
    const minhNguoi = await datTen(base, slug, nguoi.personId, nguoi.name);
    if (!minhNguoi.ok) return minhNguoi.state;
  }

  const taoUrl = `${goc(base)}/contexts`;
  const tao = await goi("tao-nhom", taoUrl, {
    method: "POST",
    headers: headers(minh.personId, undefined, khoaGhi("context")),
    body: JSON.stringify({ display_name: DEMO_GROUP_NAME }),
  });
  if (!tao.ok) return tao.state;
  const taoBody = tao.body as { id?: unknown; display_name?: unknown } | null;
  if (!taoBody || typeof taoBody.id !== "string") {
    return hong("tao-nhom", taoUrl, tao.status, "máy chủ không trả id nhóm");
  }
  const contextId = taoBody.id;
  const tenNhom = typeof taoBody.display_name === "string" ? taoBody.display_name : DEMO_GROUP_NAME;

  if (slug !== MINH_SLUG) {
    const moiUrl = `${goc(base)}/contexts/${contextId}/members`;
    const moi = await goi(
      "moi",
      moiUrl,
      {
        method: "POST",
        headers: headers(minh.personId, contextId, khoaGhi(`invite:${slug}`)),
        body: JSON.stringify({ person_id: nguoi.personId }),
      },
      { choPhep409: true },
    );
    if (!moi.ok) return moi.state;
    if (moi.status !== 409) {
      const membershipId = (moi.body as { id?: unknown } | null)?.id;
      if (typeof membershipId !== "string") {
        return hong("moi", moiUrl, moi.status, "máy chủ không trả id lời mời");
      }
      const chapUrl = `${goc(base)}/memberships/${membershipId}/accept`;
      const chap = await goi(
        "chap-nhan",
        chapUrl,
        {
          method: "POST",
          headers: headers(nguoi.personId, contextId, khoaGhi(`accept:${slug}`)),
          body: JSON.stringify({}),
        },
        { choPhep409: true },
      );
      if (!chap.ok) return chap.state;
    }
  }

  const dsUrl = `${goc(base)}/contexts/${contextId}/members`;
  const ds = await goi("doc-thanh-vien", dsUrl, {
    method: "GET",
    headers: headers(nguoi.personId, contextId),
  });
  if (!ds.ok) return ds.state;
  try {
    const body = ds.body as { members?: unknown };
    if (!Array.isArray(body?.members)) throw new Error("thiếu mảng `members`");
    const members = body.members.map((m, i) => docThanhVien(m, `members[${i}]`));
    return { kind: "xong", contextId, tenNhom, members };
  } catch (e) {
    return hong("doc-thanh-vien", dsUrl, ds.status, (e as Error).message);
  }
}

export { DEMO_GROUP_NAME, DEMO_PEOPLE, KHONG_GIAN_DEMO, idNguoi, khoaGhi };
