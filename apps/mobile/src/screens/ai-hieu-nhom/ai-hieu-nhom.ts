/** Wire contract for the four group-understanding reads. */
import { tienVnd } from "../len-plan/ngan-sach";
import { chiTietLoi } from "../../ui/loi-tren-man";

declare const process: { env: Record<string, string | undefined> };

export const AI_HIEU_NHOM_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

export type PreferenceTaste = {
  label: string;
  checkin_count: number;
  score: number;
};

export type PreferenceSection = {
  section: "food" | "activity";
  taste_count: number;
  tastes: PreferenceTaste[];
};

export type PreferenceProfileResponse = {
  context_id: string;
  has_profile: boolean;
  reason: string;
  sections: PreferenceSection[];
  checkin_count: number;
  outing_count: number;
  split_total_vnd: number;
  avg_per_person_vnd: number | null;
};

export type SuggestionPlace = {
  id: string;
  name: string;
  category: string;
  address: string;
  price_min_vnd: number;
  price_max_vnd: number;
  rating: number;
  distance_km: number;
  open_hours: string;
};

export type SuggestionStop = {
  time_text: string;
  note: string;
  reason: string | null;
  verdict: "hop" | "tam" | "khong-hop" | null;
  place: SuggestionPlace;
};

export type SuggestionBasis = {
  outing_count: number;
  split_total_vnd: number;
  avg_per_person_vnd: number | null;
  top_categories: string[];
  recent_titles: string[];
};

export type GroupSuggestionResponse = {
  context_id: string;
  suggested: boolean;
  reason: string;
  title: string | null;
  when_text: string | null;
  stops: SuggestionStop[];
  basis: SuggestionBasis;
  source: "ai" | "none";
};

export type ConversationBasis = {
  message_count: number;
  speaker_count: number;
  member_count: number;
};

export type ContextualSuggestionResponse = {
  context_id: string;
  suggested: boolean;
  reason: string;
  title: string | null;
  when_text: string | null;
  stops: SuggestionStop[];
  basis: ConversationBasis;
  source: "ai" | "none";
};

export type BudgetOutingView = {
  outing_id: string;
  title: string;
  headcount: number;
  budget_per_person_vnd: number;
  spent_per_person_vnd: number;
  remaining_per_person_vnd: number;
  over_budget: boolean;
};

export type BudgetComparison = {
  candidate_per_person_vnd: number;
  delta_vnd: number;
  verdict: "re-hon" | "nhu-thuong" | "cao-hon";
};

export type GroupBudgetResponse = {
  context_id: string;
  outing_count: number;
  active_member_count: number;
  avg_per_person_vnd: number | null;
  in_progress: BudgetOutingView[];
  comparison: BudgetComparison | null;
};

export type AiHieuNhomState =
  | { kind: "dang-tai" }
  | { kind: "chua-biet-la-ai" }
  | { kind: "bi-tu-choi"; url: string }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; detail: string }
  | {
      kind: "xong";
      hoSo: PreferenceProfileResponse;
      goiY: GroupSuggestionResponse;
      theoChat: ContextualSuggestionResponse;
      nganSach: GroupBudgetResponse;
    };

type RouteResult<T> =
  | { kind: "xong"; url: string; body: T }
  | { kind: "bi-tu-choi"; url: string }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; detail: string };

type RouteFailure = Exclude<RouteResult<unknown>, { kind: "xong" }>;

async function docLoi(response: Response): Promise<string> {
  const fallback = `HTTP ${response.status}`;
  try {
    const detail = (await response.text()).replace(/\s+/g, " ").trim();
    return detail ? detail.slice(0, 200) : fallback;
  } catch {
    return fallback;
  }
}

async function goiRoute<T>(
  url: string,
  actorId: string,
  fetchImpl: typeof fetch,
): Promise<RouteResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: {
        "X-Actor-ID": actorId,
        // All four permissions in `app/domain/permissions.py` --
        // view_group_preference_profile, view_group_suggestion,
        // view_contextual_suggestion, view_group_budget -- read
        // `"roles": {"group_admin", "member"}`, so the id alone is refused:
        // measured against the live stack, X-Actor-ID on its own returns 403
        // `role_not_permitted` on every one of them. The same pair the
        // neighbouring group screens send (`chat/nhom.ts`, `chat/tin-nhan.ts`),
        // and no wider: these are reads, and membership is still checked
        // server-side against the rows, so a claimed role buys a non-member
        // nothing.
        "X-Actor-Roles": "group_admin,member",
        Accept: "application/json",
      },
    });
  } catch (problem) {
    return {
      kind: "khong-noi-duoc",
      url,
      detail: chiTietLoi(problem) || "Không kết nối được tới máy chủ.",
    };
  }

  if (response.status === 401 || response.status === 403) {
    return { kind: "bi-tu-choi", url };
  }
  if (!response.ok) {
    return { kind: "may-chu-loi", url, detail: await docLoi(response) };
  }

  try {
    return { kind: "xong", url, body: (await response.json()) as T };
  } catch (problem) {
    const detail = chiTietLoi(problem);
    return {
      kind: "may-chu-loi",
      url,
      detail: detail ? `Phản hồi không phải JSON: ${detail}` : "Phản hồi không phải JSON.",
    };
  }
}

function chonLoi(results: RouteResult<unknown>[]): RouteFailure {
  for (const kind of ["bi-tu-choi", "khong-noi-duoc", "may-chu-loi"] as const) {
    const result = results.find((item) => item.kind === kind);
    if (result && result.kind !== "xong") return result;
  }
  throw new Error("ROUTE_RESULTS_HAVE_NO_FAILURE");
}

/** Load all four independent reads together, without spending a request anonymously. */
export async function napAiHieuNhom(
  contextId: string,
  opts: { base?: string; fetchImpl?: typeof fetch; actorId?: string },
): Promise<AiHieuNhomState> {
  if (!opts.actorId) return { kind: "chua-biet-la-ai" };

  const base = (opts.base ?? AI_HIEU_NHOM_BASE_URL).replace(/\/$/, "");
  const prefix = `${base}/contexts/${contextId}`;
  const fetchImpl = opts.fetchImpl ?? fetch;

  const [hoSo, goiY, theoChat, nganSach] = await Promise.all([
    goiRoute<PreferenceProfileResponse>(`${prefix}/preference-profile`, opts.actorId, fetchImpl),
    goiRoute<GroupSuggestionResponse>(`${prefix}/suggestion`, opts.actorId, fetchImpl),
    goiRoute<ContextualSuggestionResponse>(
      `${prefix}/contextual-suggestion`,
      opts.actorId,
      fetchImpl,
    ),
    goiRoute<GroupBudgetResponse>(`${prefix}/budget`, opts.actorId, fetchImpl),
  ]);

  if (
    hoSo.kind === "xong" &&
    goiY.kind === "xong" &&
    theoChat.kind === "xong" &&
    nganSach.kind === "xong"
  ) {
    return {
      kind: "xong",
      hoSo: hoSo.body,
      goiY: goiY.body,
      theoChat: theoChat.body,
      nganSach: nganSach.body,
    };
  }

  return chonLoi([hoSo, goiY, theoChat, nganSach]);
}

export function laNhanAi(source: unknown): boolean {
  return source === "ai";
}

export function nhanLyDo(reason: string): string {
  const labels: Record<string, string> = {
    ok: "Đã có dữ liệu của nhóm.",
    no_behaviour: "Nhóm chưa có đủ lượt check-in để tạo hồ sơ sở thích.",
    no_history: "Nhóm chưa có lịch sử buổi đi để đưa ra gợi ý.",
    no_conversation: "Đoạn chat chưa có đủ cuộc trò chuyện để đưa ra gợi ý.",
    unavailable: "Gợi ý đang tạm thời không dùng được.",
    ungrounded: "Gợi ý chưa có đủ căn cứ từ dữ liệu của nhóm.",
  };
  return labels[reason] ?? `Máy chủ trả về lý do chưa biết: ${reason}.`;
}

export function nhanTietMuc(section: string): string {
  if (section === "food") return "Món ăn";
  if (section === "activity") return "Hoạt động";
  return section;
}

export function nhanVerdictNganSach(verdict: string): string {
  if (verdict === "re-hon") return "Thấp hơn mức nhóm thường chi.";
  if (verdict === "nhu-thuong") return "Gần với mức nhóm thường chi.";
  if (verdict === "cao-hon") return "Cao hơn mức nhóm thường chi.";
  return `Mức so sánh chưa biết: ${verdict}.`;
}

export function khoangGia(
  place: Pick<SuggestionPlace, "price_min_vnd" | "price_max_vnd">,
): string {
  if (place.price_min_vnd === place.price_max_vnd) {
    return tienVnd(place.price_min_vnd);
  }
  return `${tienVnd(place.price_min_vnd).slice(0, -1)} – ${tienVnd(place.price_max_vnd)}`;
}
