/** The personal wall: who may read a post, and what a refusal means.
 *
 * Split out of the component so the parts worth testing can be tested without
 * rendering anything: the four audience sentences, the publish gate, the
 * request body, and the failure text. Nothing here talks to React.
 *
 * The four audiences are a vocabulary, not a ladder. `friends` and `group`
 * reach two disjoint sets of people; neither contains the other. This file
 * does not compare two of them by position, and the screen must not draw
 * them as a slider, a chip row ordered narrow-to-wide, or a lock that opens
 * in steps. See `app/domain/post_audience.py`.
 */
import { ApiError, BASE_URL, dangBai, docTuongNguoi, type Attempt, type PostWire } from "../../api";
import { cauMayChuLoi } from "../../ui/loi-may-chu";

export const AUDIENCES = ["only_me", "friends", "group", "public"] as const;
export type Audience = (typeof AUDIENCES)[number];

/** What a client that says nothing gets. The server's DEFAULT_AUDIENCE. */
export const MAC_DINH_NGUOI_DOC: Audience = "only_me";

export type MucNguoiDoc = {
  nhan: string;
  /** Who can read this, and who cannot. Said before the person presses Đăng. */
  giaiThich: string;
};

/**
 * One sentence per audience, naming the set of people it reaches.
 *
 * Written to be read on the screen, so they are Vietnamese and they do not
 * use an em dash. The words are the rule: a chip labelled only with the
 * level's name would let somebody press "Bạn bè" thinking it included their
 * groupmates.
 */
export const MUC_NGUOI_DOC: Record<Audience, MucNguoiDoc> = {
  only_me: {
    nhan: "Chỉ mình tôi",
    giaiThich: "Không ai khác đọc được. Kể cả bạn bè và người trong nhóm.",
  },
  friends: {
    nhan: "Bạn bè",
    giaiThich:
      "Người đã kết bạn với bạn. Người trong nhóm chưa kết bạn thì không đọc được.",
  },
  group: {
    nhan: "Một nhóm",
    giaiThich: "Chỉ thành viên nhóm bạn chọn. Bạn bè ngoài nhóm không đọc được.",
  },
  public: {
    nhan: "Công khai",
    giaiThich: "Ai mở app cũng đọc được.",
  },
};

export type FormDang = {
  body: string;
  audience: Audience;
  contextId: string | null;
};

/** Whether Đăng may fire. Empty body or a group post with no group cannot. */
export function coTheDang(form: FormDang): boolean {
  if (!form.body.trim()) return false;
  if (form.audience === "group" && !form.contextId) return false;
  return true;
}

/**
 * The POST /posts body. No `author_id`. `context_id` only when `group`.
 *
 * A second copy of the same omit-rule lives in `api.ts` (`thanDangBaiApi`),
 * which is what actually goes on the wire. This one is what the screen and
 * the tests read; the two are pinned against each other by `tests/tuong.test.mjs`.
 */
export function thanDangBai(form: FormDang & { imageUrl?: string | null }): {
  body: string;
  audience: Audience;
  context_id?: string;
  image_url?: string;
} {
  const than: {
    body: string;
    audience: Audience;
    context_id?: string;
    image_url?: string;
  } = { body: form.body.trim(), audience: form.audience };
  if (form.audience === "group" && form.contextId) {
    than.context_id = form.contextId;
  }
  if (form.imageUrl) than.image_url = form.imageUrl;
  return than;
}

export class TuongError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "TuongError";
  }
}

/**
 * Refusals in words the person reading them can act on.
 *
 * Known codes become a next move. Everything else, including every 5xx body,
 * goes through `cauMayChuLoi` so neither an English code nor a raw 5xx page
 * reaches the screen. `thanLoiMayChu` is deliberately not used: its excerpt
 * would put `Internal Server Error` after "Chi tiết:".
 */
export function loiTuong(status: number, code: string, _detail = ""): string {
  const known = LOI_TUONG[code.toLowerCase()];
  if (known) return known;
  if (status === 0) return `Không gọi được ${BASE_URL}`;
  if (status === 401) return "Chưa đăng nhập nên chưa hỏi được máy chủ.";
  return cauMayChuLoi(status);
}

const LOI_TUONG: Record<string, string> = {
  unknown_audience:
    "Mức người đọc này app không gửi được. Chọn lại một trong bốn lựa chọn trên màn.",
  group_audience_needs_context:
    "Chọn nhóm đã, rồi mới đăng được bài cho nhóm đó.",
  context_not_addressable:
    "Chỉ bài cho một nhóm mới được gắn nhóm. Chọn lại mức người đọc.",
  post_not_found: "Bài này không còn hoặc không phải dành cho bạn.",
  permission_denied: "Tài khoản đang dùng chưa được phép đăng bài này.",
};

export type Bai = PostWire;

/** Read this person's wall, as themselves. Self-only at the server. */
export async function layTuong(personId: string): Promise<Bai[]> {
  try {
    return await docTuongNguoi(personId, personId);
  } catch (error) {
    throw bocLoi(error);
  }
}

/** Write one post as this person. The actor is `personId`, never a body field. */
export async function guiBai(
  personId: string,
  form: FormDang,
  attempt: Attempt,
): Promise<Bai> {
  try {
    return await dangBai(
      { body: form.body.trim(), audience: form.audience, contextId: form.contextId },
      personId,
      attempt,
    );
  } catch (error) {
    throw bocLoi(error);
  }
}

function bocLoi(error: unknown): TuongError {
  if (error instanceof TuongError) return error;
  if (error instanceof ApiError) {
    return new TuongError(error.status, loiTuong(error.status, error.code, error.message));
  }
  return new TuongError(0, loiTuong(0, "", ""));
}
