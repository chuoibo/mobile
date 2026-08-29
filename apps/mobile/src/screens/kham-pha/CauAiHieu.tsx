/** The reading shown back, and the four ways a search can come back empty.
 *
 * ## Why the reading is on screen at all
 *
 * rd-fe-15's brief calls this non-negotiable, and the reason is narrow: it is
 * how a person finds out the AI misread them. Someone types "dưới 300k", the
 * model hears 30.000đ, and the screen fills with cheap places or nothing at
 * all. Without the reading, the only signal is that the results are strange,
 * and strange results are indistinguishable from a bad catalogue -- so the
 * person retypes the same sentence, gets the same misreading, and concludes the
 * feature does not work. With the reading, "Ngân sách 30k/người" is sitting
 * there and the fix is obvious in one glance.
 *
 * It is deliberately not decoration and deliberately not a debug panel. Every
 * value in it is a closed-vocabulary token the server already checked against
 * the catalogue (`ground_search` refuses the whole answer over one unknown
 * category), so it is safe to render and it is about the person's own sentence.
 *
 * ## Tone
 *
 * `ai` purple, which DESIGN.md gives to "thứ do máy sinh ra, người còn sửa
 * được" -- both halves of that are true here, and the second half is the point.
 * The lead tone of Khám phá stays `accent`; this is the same borrowed accent
 * `NhanAi.tsx` already spends on the badge and the reason card, not a second
 * lead. Border only, no shadow: DESIGN.md, tách bằng bóng HOẶC bằng viền.
 */
import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { thanLoiMayChu } from "../../ui/loi-may-chu";
import { hieuDuocGi, type TimKiemState, type Understood } from "./tim-kiem";
import { type Category } from "./places";

/**
 * "AI hiểu câu của bạn" plus the rows it drew.
 *
 * Rendered whenever a model answered, including when the answer was that
 * nothing fits -- that is the case where it matters most, because an empty
 * result with a visible misreading is a solvable problem and an empty result
 * with no reading is a dead end.
 */
export function CauAiHieu({
  understood,
  categories,
}: {
  understood: Understood;
  categories: Category[];
}) {
  const c = usePalette();
  const rows = hieuDuocGi(understood, categories);

  return (
    <View
      style={{
        backgroundColor: c.aiSoft,
        borderColor: c.ai,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.sm,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
        <Text style={{ ...type.title, color: c.ai }}>AI hiểu câu của bạn</Text>
        <Text style={{ ...type.label, color: c.ai }}>✦</Text>
      </View>

      {rows.length === 0 ? (
        // Not an empty box, and not silence. A model that drew no conditions
        // still answered, and the person needs to know the search ran on the
        // sentence as a whole rather than on any budget or headcount in it.
        <Text style={{ ...type.body, color: c.ink, lineHeight: 24 }}>
          AI không rút được điều kiện cụ thể nào từ câu này, nên nó tìm theo cả câu. Thử nói rõ ngân
          sách, số người hoặc loại chỗ để kết quả sát hơn.
        </Text>
      ) : (
        <View style={{ gap: space.xs }}>
          {rows.map((r) => (
            <View key={r.label} style={{ flexDirection: "row", gap: space.sm, alignItems: "baseline" }}>
              <Text style={{ ...type.micro, color: c.ai, width: 74 }}>{r.label.toUpperCase()}</Text>
              <Text style={{ ...type.label, color: c.ink, flex: 1 }}>{r.value}</Text>
            </View>
          ))}
        </View>
      )}

      {/* The actionable half. A reading nobody is invited to correct is a
          readout; a reading with this line under it is a control. */}
      <Text style={{ ...type.micro, color: c.inkSoft }}>
        Hiểu chưa đúng ý bạn? Viết lại câu rõ hơn rồi tìm lại.
      </Text>
    </View>
  );
}

/**
 * What the screen says when a search produced no places.
 *
 * Two different sentences for two genuinely different situations, and merging
 * them would cost the person the only thing that tells them what to do next:
 *
 * * A model answered and nothing fits. The reading is on screen above this
 *   card, so the next move is to read it and loosen whichever line is wrong.
 * * Nothing came back at all. There is no reading to loosen, so the next move
 *   is to say it differently.
 */
export function KhongCoKetQua({ coCachHieu }: { coCachHieu: boolean }) {
  const c = usePalette();
  return (
    <View
      style={{
        borderColor: c.line,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.xs,
        backgroundColor: c.card,
      }}
    >
      <Text style={{ ...type.title, color: c.ink }}>
        {coCachHieu ? "Không có chỗ nào hợp câu này" : "Chưa tìm được, thử nói khác xem"}
      </Text>
      <Text style={{ ...type.body, color: c.inkSoft, lineHeight: 24 }}>
        {coCachHieu
          ? "AI đã đọc câu của bạn nhưng không có chỗ nào trong danh mục khớp. Xem lại phần AI hiểu ở trên rồi nới điều kiện nào đang chặt quá."
          : // Deliberately does not name a cause. The server returns the same
            // answer whether the model was unreachable or whether it named a
            // place that does not exist and the whole reply was refused, and it
            // does not tell the client which. Naming one would be inventing the
            // single piece of information that was withheld on purpose.
            "Lần này không có câu trả lời nào chắc chắn, nên app không đoán bừa. Thử nói khác đi, ví dụ thêm loại chỗ, số người hoặc mức tiền."}
      </Text>
    </View>
  );
}

/**
 * The search could not run, as opposed to the search running and finding
 * nothing. Same split `ChuaCoDuLieu` makes for the catalogue, same reason:
 * "máy chủ không mở" and "máy chủ mở nhưng thiếu route" are two afternoons.
 *
 * The server's own words stay in the small diagnostic line and never become the
 * headline. A person reading "Chưa tìm được" can act on it; a person reading a
 * FastAPI validation body cannot.
 */
export function TimKhongDuoc({ state, baseUrl }: { state: TimKiemState; baseUrl: string }) {
  const c = usePalette();
  let tieuDe = "Không tìm được";
  let than = "";
  let diaChi = "";

  if (state.kind === "cau-khong-hop-le") {
    tieuDe = "Câu tìm kiếm chưa dùng được";
    than = `Viết một câu ngắn hơn ${state.max} chữ và đừng để trống, rồi tìm lại.`;
  } else if (state.kind === "chua-co-endpoint") {
    tieuDe = "Máy chủ này chưa có tìm kiếm bằng lời";
    than = `Máy chủ đang chạy nhưng không có route POST /places/search. Route đó có trong ${state.work}, nên nhiều khả năng app đang trỏ vào một bản API cũ hơn, không phải app thiếu gì.`;
    diaChi = state.url;
  } else if (state.kind === "khong-noi-duoc") {
    tieuDe = "Không mở được máy chủ";
    than = `Không kết nối được tới API. Chi tiết: ${state.detail}`;
    diaChi = state.url;
  } else if (state.kind === "may-chu-loi") {
    tieuDe = `Máy chủ trả lỗi ${state.status}`;
    // The clause is this screen's own: somebody typed a sentence and pressed a
    // button, so "it is not your sentence" is the thing they are about to
    // wonder. `ChuaCoDuLieu` says the same lead without it, because on the
    // catalogue nobody typed anything. See `ui/loi-may-chu.ts` (bug-185426).
    than = thanLoiMayChu(state.status, state.detail, "Câu bạn viết không phải nguyên nhân.");
    diaChi = state.url;
  } else if (state.kind === "du-lieu-sai") {
    tieuDe = "Kết quả tìm kiếm không đúng dạng";
    than = `App từ chối hiển thị thay vì vẽ ra kết quả sai. Chi tiết: ${state.detail}`;
    diaChi = state.url;
  }

  return (
    <View
      style={{
        borderColor: c.line,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.xs,
        backgroundColor: c.card,
      }}
    >
      <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
      <Text style={{ ...type.body, color: c.inkSoft, lineHeight: 24 }}>{than}</Text>
      {diaChi ? <Text style={{ ...type.micro, color: c.inkFaint }}>Đã thử: {diaChi}</Text> : null}
      {diaChi ? (
        /* The env var's name is deliberately NOT spelled out, same as
           `KhamPha.tsx`: `tests/base-url.test.mjs` greps the built bundle for
           that token to prove Expo substituted the read, and printing the name
           in copy would put it in the bundle and cost the gate its meaning. */
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          API app đang trỏ tới: {baseUrl} rồi mở lại app.
        </Text>
      ) : null}
    </View>
  );
}
