/** Signing in, staying signed in, and signing out.
 *
 * Since ADR-0014 a production server does not believe `X-Actor-ID`. What it
 * believes is a bearer token it issued itself, and the only way to get one
 * without already having one is to exchange a **named** invitation: a row an
 * existing member wrote with somebody's `person_id` in it. The app therefore
 * never says who it is. It hands over a secret, and the server answers with
 * whose session that secret was.
 *
 * That asymmetry is the whole design and it is easy to undo by accident. A
 * body with a `person_id` in it, however well-meant, would put the client back
 * in charge of identity and reopen the hole the ADR closed. There is no such
 * field here and there must not be one.
 *
 * Three things live here rather than in `api.ts`:
 *
 * - **The native module.** `expo-secure-store` is imported dynamically, never
 *   at module scope. `api.ts` is loaded by the node test suite, which has no
 *   native modules at all, and a top-level import would make the entire API
 *   layer unloadable there.
 * - **The retry key.** A dropped response on `POST /sessions` is the worst
 *   failure this flow has: the invitation's secret is spent server-side, the
 *   token is lost in the network, and the person is locked out until somebody
 *   rotates the invitation for them. An `Idempotency-Key` turns that into a
 *   replay of the same answer.
 * - **The fallback store.** On web there is no SecureStore. The session is
 *   kept in memory for that session of the browser and nowhere else, which is
 *   the honest behaviour rather than quietly writing a credential to
 *   `localStorage`.
 */
import {
  datTokenPhien,
  newAttempt,
  tokenPhienHienTai,
  translatedAnonymous,
  translatedAsActor,
} from "./api";

/** What the server hands back once, and what we keep. */
export type TinCuoiTomTat = {
  id: string;
  kind: "text" | "image" | "ai_card";
  preview: string;
  author_id: string | null;
  author_display_name: string | null;
  created_at: string;
};

export type NhomTomTat = {
  id: string;
  display_name: string;
  my_state: "invited" | "active";
  my_role?: "member" | "admin";
  membership_id: string;
  member_count: number;
  unread_count: number;
  last_message?: TinCuoiTomTat | null;
};

export type Phien = {
  token: string;
  person_id: string;
  expires_at: string;
  /** `null` for a session minted by a door that is not an invitation (OTP,
   *  Google): the person may belong to no group yet. The invite door and
   *  `chonNhomMacDinh` fill it whenever a group is known. */
  context_id: string | null;
  membership_state: "invited" | "active" | "left" | null;
  membership_id: string | null;
  /** Which door minted this session (ADR-0016). Absent on rows stored before
   *  the field existed. */
  issued_via?: "invite" | "otp" | "google" | "genesis";
  is_new_person?: boolean;
  profile?: { display_name: string };
  /** Every group the person is in or invited to, as the server listed them. */
  contexts?: NhomTomTat[];
};

/** Where a secret is kept between launches. */
export type KhoAnToan = {
  doc(khoa: string): Promise<string | null>;
  ghi(khoa: string, giaTri: string): Promise<void>;
  xoa(khoa: string): Promise<void>;
};

const KHOA = "rudi.phien";

const LOI_DOI_LOI_MOI: Record<string, string> = {
  // 404 is every refusal this route makes: expired, revoked, already spent,
  // never existed. The server answers them identically on purpose, so the
  // sentence here must not pretend to know which one happened.
  http_404: "Lời mời này không dùng được nữa. Nhờ người trong nhóm mời lại.",
  http_422: "Mã lời mời không đúng định dạng.",
};

const LOI_DANG_XUAT: Record<string, string> = {
  http_401: "Phiên đã hết hiệu lực rồi.",
};

/** In memory only. The fallback, and what the web build always gets. */
export function khoTrongBoNho(): KhoAnToan {
  let giu: string | null = null;
  return {
    async doc() {
      return giu;
    },
    async ghi(_khoa, giaTri) {
      giu = giaTri;
    },
    async xoa() {
      giu = null;
    },
  };
}

let khoMacDinh: KhoAnToan | null = null;

/**
 * SecureStore when the platform has it, memory when it does not.
 *
 * Resolved once and remembered, because the answer cannot change inside one
 * run of the app, and because a failed dynamic import should not be retried on
 * every read.
 */
export async function khoAnToanMacDinh(): Promise<KhoAnToan> {
  if (khoMacDinh !== null) return khoMacDinh;
  try {
    const store = await import("expo-secure-store");
    // Touch the API before committing to it: the module resolves on web and
    // then throws from its methods, and finding that out on the first read
    // would lose a token that had already been issued.
    await store.getItemAsync(KHOA);
    khoMacDinh = {
      doc: (khoa) => store.getItemAsync(khoa),
      ghi: (khoa, giaTri) => store.setItemAsync(khoa, giaTri),
      xoa: (khoa) => store.deleteItemAsync(khoa),
    };
  } catch {
    khoMacDinh = khoTrongBoNho();
  }
  return khoMacDinh;
}

/** A non-empty string, or `null`. An empty id is an absent id, not a group named "". */
function chuoiHayNull(gia: unknown): string | null {
  return typeof gia === "string" && gia !== "" ? gia : null;
}

function docPhien(thoLuu: string | null): Phien | null {
  if (thoLuu === null) return null;
  try {
    const parsed = JSON.parse(thoLuu) as Partial<Phien>;
    if (typeof parsed.token !== "string" || parsed.token === "") return null;
    if (typeof parsed.person_id !== "string") return null;
    if (typeof parsed.expires_at !== "string") return null;
    // The group triple is nullable since ADR-0016: a session from the OTP or
    // Google door may belong to no group yet, and that is a person who should
    // land on "chưa có nhóm nào", not be signed out. A row written before the
    // fields existed still carries all three as strings and reads unchanged.
    const state =
      parsed.membership_state === "invited" ||
      parsed.membership_state === "active" ||
      parsed.membership_state === "left"
        ? parsed.membership_state
        : null;
    return {
      token: parsed.token,
      person_id: parsed.person_id,
      context_id: chuoiHayNull(parsed.context_id),
      expires_at: parsed.expires_at,
      membership_state: state,
      membership_id: chuoiHayNull(parsed.membership_id),
      issued_via: parsed.issued_via,
      is_new_person: parsed.is_new_person,
      profile: parsed.profile,
      contexts: Array.isArray(parsed.contexts) ? parsed.contexts : undefined,
    };
  } catch {
    // A corrupted record is a signed-out app, not a crashed one.
    return null;
  }
}

/**
 * Trade a named invitation for a session, and remember it.
 *
 * The body carries the secret and nothing else -- see the header of this file
 * for why there is no `person_id` in it.
 */
export async function doiLoiMoiLayPhien(
  maLoiMoi: string,
  kho?: KhoAnToan,
): Promise<Phien> {
  const phien = await translatedAnonymous<Phien>(LOI_DOI_LOI_MOI, "/sessions", {
    method: "POST",
    body: { invite_token: maLoiMoi },
    // Minted here, on the press. A retry of a dropped answer replays the same
    // session instead of spending a secret that is already gone.
    attempt: newAttempt(),
  });
  await ghiNho(phien, kho);
  return phien;
}

const LOI_VAO_NHOM: Record<string, string> = {
  // The row is gone, or was never this person's. Both read the same from here.
  http_404: "Lời mời này không còn hiệu lực. Nhờ người trong nhóm mời lại.",
  // Somebody already accepted, or the row moved on. Not an error worth a
  // scary sentence -- the next screen will show where they actually stand.
  http_409: "Trạng thái nhóm vừa đổi. Mở lại màn hình để xem hiện tại.",
};

/**
 * Consent to the membership this session was issued for, and remember it.
 *
 * Why the invitee presses this at all: a named invitation carries an existing
 * member's choice of a person, so the remaining question is that person's own
 * consent, not a second approval (ADR-0014 s8, `accept_context_membership`
 * requires `is_invitee`). A link invitation is the other shape and is not this
 * function's business -- there a member who is already in must approve.
 *
 * The stored record is rewritten from the SERVER's answer rather than being
 * patched to `"active"` locally. The two differ whenever the server declined
 * to move the row, and a local patch would leave the phone believing it is in
 * a group it is not -- which `nguon.ts` reads as permission to show group
 * money.
 */
export async function vaoNhom(phien: Phien, kho?: KhoAnToan): Promise<Phien> {
  if (phien.membership_id === null) {
    throw new Error("Phiên này không mang thẻ thành viên nào để đồng ý.");
  }
  const wire = await translatedAsActor<{ state: "invited" | "active" | "left" }>(
    LOI_VAO_NHOM,
    `/memberships/${phien.membership_id}/accept`,
    // No `contexts` claim. The route reads `membership_id` and asks only
    // `is_invitee`; claiming membership of a group this person has not joined
    // yet would be a false sentence on a `dev` host and ignored on a `prod`
    // one, so it is worth nothing and costs a lie.
    { method: "POST", actorId: phien.person_id },
  );
  const moi: Phien = { ...phien, membership_state: wire.state };
  await ghiNho(moi, kho);
  return moi;
}

/** Put a session into force for this process, and onto the device. */
export type OtpDaGui = {
  challenge_id: string;
  expires_in_seconds: number;
  resend_after_seconds: number;
};

// Keyed by the server's own codes (`viDich` looks the code up, not the
// status). `otp_code_invalid` is deliberately absent: its server sentence
// carries how many tries are left, and a fixed one here would hide that.
const LOI_OTP_GUI: Record<string, string> = {
  phone_required: "Nhập số điện thoại.",
  phone_not_mobile: "Chưa đúng dạng số di động Việt Nam.",
  otp_resend_too_soon: "Mã vừa được gửi. Đợi một chút rồi gửi lại.",
  otp_too_many_requests: "Số này vừa nhận nhiều mã. Thử lại sau ít phút.",
  rate_limited: "Thử lại sau một phút.",
  identity_key_missing: "Máy chủ chưa sẵn sàng cho đăng nhập.",
  sms_unavailable: "Chưa gửi được tin nhắn lúc này, thử lại sau.",
};

const LOI_OTP_XAC_MINH: Record<string, string> = {
  otp_challenge_not_found: "Mã không còn hiệu lực. Xin mã mới.",
  otp_too_many_attempts: "Sai quá nhiều lần. Xin mã mới.",
  challenge_id_invalid: "Lượt xin mã bị lỗi. Xin mã mới.",
  rate_limited: "Thử lại sau một phút.",
  identity_key_missing: "Máy chủ chưa sẵn sàng cho đăng nhập.",
};

/** Ask the server to send a code. The number goes in the body, never a path. */
export async function guiOtp(phone: string): Promise<OtpDaGui> {
  return translatedAnonymous<OtpDaGui>(LOI_OTP_GUI, "/auth/otp/request", {
    method: "POST",
    body: { phone },
    attempt: newAttempt(),
  });
}

/**
 * A session with a group to stand in, when the server knows one.
 *
 * The OTP door answers with `context_id: null` and the full `contexts` list;
 * the screens that already read live money (`nguon.ts`) need one group on the
 * session. The first ACTIVE membership is that group -- a person with several
 * picks another from the conversation list (M2). Pure, so it can be tested.
 */
export function chonNhomMacDinh(phien: Phien): Phien {
  if (phien.context_id !== null) return phien;
  const active = phien.contexts?.find((nhom) => nhom.my_state === "active");
  if (active === undefined) return phien;
  return {
    ...phien,
    context_id: active.id,
    membership_state: "active",
    membership_id: active.membership_id,
  };
}

/**
 * Every group this person is in or invited to, as the server lists them.
 *
 * `GET /people/me/contexts` (ADR-0016) is how a session minted by a door that
 * knows no group finds one. Read as the actor only for the `X-Actor-ID` header
 * a dev-mode server still looks at; in `prod` the bearer decides who "me" is.
 */
export async function docNhomCuaToi(personId: string): Promise<NhomTomTat[]> {
  const wire = await translatedAsActor<{ contexts: NhomTomTat[] }>({}, "/people/me/contexts", {
    method: "GET",
    actorId: personId,
  });
  return wire.contexts;
}

/**
 * A fresh group list on an existing session, written back to the disk.
 *
 * Used right after a group is created or accepted: the server already knows,
 * and the phone must not keep saying "chưa có nhóm nào" until the next launch.
 */
export async function ganDanhSachNhom(
  phien: Phien,
  contexts: NhomTomTat[],
  kho?: KhoAnToan,
): Promise<Phien> {
  const moi = chonNhomMacDinh({ ...phien, contexts });
  await ghiNho(moi, kho);
  return moi;
}

/**
 * Make one of the listed groups the current one, and remember it.
 *
 * The conversation list is where a person with several groups picks which one
 * the money screens read. Only a group the server listed can be chosen -- an
 * id typed from nowhere would send `nguon.ts` live on a group the server may
 * refuse -- and an `invited` row is not a choice yet: accepting is `vaoNhom`.
 */
export async function chonNhom(phien: Phien, contextId: string, kho?: KhoAnToan): Promise<Phien> {
  const nhom = phien.contexts?.find((ung) => ung.id === contextId);
  if (nhom === undefined) {
    throw new Error("Nhóm này không có trong danh sách máy chủ vừa trả.");
  }
  if (nhom.my_state !== "active") {
    throw new Error("Bạn chưa đồng ý vào nhóm này.");
  }
  const moi: Phien = {
    ...phien,
    context_id: nhom.id,
    membership_state: "active",
    membership_id: nhom.membership_id,
  };
  await ghiNho(moi, kho);
  return moi;
}

/** The caller's own profile as `GET /people/me` returns it (M2). */
export type HoSoToi = {
  id: string;
  display_name: string;
  bio: string | null;
  city: string | null;
  created_at: string;
  counts: {
    friends: number;
    contexts: number;
    outings: number;
    places_checked_in: number;
    memories: number;
  };
  login_methods: string[];
};

const LOI_HO_SO: Record<string, string> = {
  person_not_found: "Máy chủ chưa có hồ sơ cho tài khoản này.",
  http_422: "Hồ sơ chưa hợp lệ: tên không được rỗng, giới thiệu tối đa 500 chữ.",
};

export async function docHoSoToi(personId: string): Promise<HoSoToi> {
  return translatedAsActor<HoSoToi>(LOI_HO_SO, "/people/me", { method: "GET", actorId: personId });
}

/** Partial update; `bio`/`city` = "" clears the field. */
export async function suaHoSoToi(
  personId: string,
  thayDoi: { display_name?: string; bio?: string; city?: string },
): Promise<HoSoToi> {
  return translatedAsActor<HoSoToi>(LOI_HO_SO, "/people/me", {
    method: "PATCH",
    body: thayDoi,
    actorId: personId,
    attempt: newAttempt(),
  });
}

/** Spend the code for a session, remember it, and hand the bearer to `api.ts`. */
export async function xacMinhOtp(
  challengeId: string,
  phone: string,
  code: string,
  kho?: KhoAnToan,
): Promise<Phien> {
  const wire = await translatedAnonymous<Phien>(LOI_OTP_XAC_MINH, "/auth/otp/verify", {
    method: "POST",
    body: { challenge_id: challengeId, phone, code },
    attempt: newAttempt(),
  });
  const phien = chonNhomMacDinh(wire);
  await ghiNho(phien, kho);
  return phien;
}

export async function ghiNho(phien: Phien, kho?: KhoAnToan): Promise<void> {
  datTokenPhien(phien.token);
  const store = kho ?? (await khoAnToanMacDinh());
  await store.ghi(KHOA, JSON.stringify(phien));
}

/**
 * Read the stored session at launch, if there is one.
 *
 * An expired record is dropped here rather than sent: the server would answer
 * 401 and the app would show a person a failure for something it already knew.
 */
export async function khoiPhucPhien(kho?: KhoAnToan): Promise<Phien | null> {
  const store = kho ?? (await khoAnToanMacDinh());
  const phien = docPhien(await store.doc(KHOA));
  if (phien === null) return null;
  if (Date.parse(phien.expires_at) <= Date.now()) {
    await store.xoa(KHOA);
    datTokenPhien(null);
    return null;
  }
  datTokenPhien(phien.token);
  return phien;
}

/**
 * Sign out on the server first, then forget locally.
 *
 * That order is the point. A session only the phone forgets is still a live
 * credential on the server, and a phone somebody else is holding is exactly
 * when that matters. The local record is cleared even when the call fails,
 * because a person who pressed sign-out has said what they want and the
 * server-side row will expire on its own.
 */
export async function dangXuat(personId: string, kho?: KhoAnToan): Promise<void> {
  const token = tokenPhienHienTai();
  try {
    if (token !== null) {
      await translatedAsActor<void>(LOI_DANG_XUAT, "/sessions/current", {
        method: "DELETE",
        actorId: personId,
      });
    }
  } finally {
    datTokenPhien(null);
    const store = kho ?? (await khoAnToanMacDinh());
    await store.xoa(KHOA);
  }
}
