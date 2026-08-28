/** The two places the screen speaks for the model: the badge and the reason.
 *
 * rd-be-05's brief is blunt about which of the two matters: "Con số 95% không
 * có giá trị tự thân. LÝ DO mới là thứ khiến người ta tin." So the badge is
 * small and the reason card is the widest element on the detail screen, and
 * neither of them is allowed to appear without the other having a source.
 *
 * `ai` purple is the palette's stated meaning for "thứ do máy sinh ra, người
 * còn sửa được" (DESIGN.md, "Ba tông mang nghĩa"). It is used here and nowhere
 * else on these screens; the lead tone of Khám phá stays `accent`, because a
 * screen with two lead tones is a defect in that same section.
 */
import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { matchLabel, type Match } from "./places";

/**
 * "AI MATCH 95%" -- or a quieter chip that cannot be read as one.
 *
 * The whole gate is `matchLabel()`, and the decision is not this component's to
 * second-guess: purple and the words AI MATCH require both `source: "ai"` and a
 * verdict of `hop`. A score with no model behind it gets the same treatment
 * `ManVo` gives an unbuilt screen -- neutral ground, quiet ink, plainly not a
 * claim -- because a demo where an uncomputed 95% wears the real badge is the
 * exact failure the brief names.
 *
 * `label.real` means "a model actually answered", not "the answer was yes". A
 * `khong-hop` verdict is still purple: the model did the work, and the work
 * produced a no.
 */
export function HuyHieuMatch({ match, big = false }: { match: Match | null; big?: boolean }) {
  const c = usePalette();
  const label = matchLabel(match);
  if (!label) return null;

  const pad = big ? { paddingHorizontal: space.sm, paddingVertical: space.xs } : { paddingHorizontal: space.xs, paddingVertical: 3 };
  const font = big ? { ...type.label, fontWeight: "700" as const } : type.micro;

  if (!label.real) {
    return (
      <View
        style={{
          alignSelf: "flex-start",
          backgroundColor: c.card,
          borderColor: c.lineStrong,
          borderWidth: 1,
          borderRadius: radius.small,
          ...pad,
        }}
      >
        <Text style={{ ...font, color: c.inkSoft }}>{label.text}</Text>
      </View>
    );
  }

  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: c.ai,
        borderRadius: radius.small,
        ...pad,
      }}
    >
      <Text style={{ ...font, color: c.aiInk }}>{label.text}</Text>
    </View>
  );
}

/**
 * The card that says *why*.
 *
 * Rendered only when there is a reason to render. There is no fallback
 * sentence: a screen that always has something warm to say about every place
 * is a screen whose compliments mean nothing, and the acceptance criterion for
 * this work is specifically that the reason is generated rather than written
 * here.
 */
export function TheLyDoAi({ match }: { match: Match | null }) {
  const c = usePalette();
  if (!match) {
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
        <Text style={{ ...type.title, color: c.ink }}>Chưa có gợi ý</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Máy chủ chưa chấm được chỗ này cho nhóm bạn, nên ở đây không có điểm và không có lý do.
        </Text>
      </View>
    );
  }

  const that = match.source === "ai";
  return (
    <View
      // Border only, no shadow. DESIGN.md: tách bằng bóng HOẶC bằng viền,
      // không bao giờ cả hai.
      style={{
        backgroundColor: that ? c.aiSoft : c.card,
        borderColor: that ? c.ai : c.line,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.sm,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
        <Text style={{ ...type.title, color: that ? c.ai : c.inkSoft }}>
          {that ? "AI gợi ý" : "Điểm do máy tính"}
        </Text>
        {that ? <Text style={{ ...type.label, color: c.ai }}>✦</Text> : null}
      </View>

      <Text style={{ ...type.body, color: c.ink, lineHeight: 24 }}>{match.reason}</Text>

      {match.factors.length > 0 ? (
        <View style={{ gap: space.xs, marginTop: space.xs }}>
          {match.factors.map((f) => (
            <View key={f.label} style={{ flexDirection: "row", gap: space.sm, alignItems: "baseline" }}>
              <Text style={{ ...type.micro, color: that ? c.ai : c.inkSoft, width: 74 }}>
                {f.label.toUpperCase()}
              </Text>
              <Text style={{ ...type.label, color: c.ink, flex: 1 }}>{f.detail}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {that ? null : (
        // Said inside the card rather than in a toast somebody dismisses: the
        // person most likely to read a computed line as a model's opinion is
        // the person being shown the app by somebody else.
        <Text style={{ ...type.micro, color: c.inkSoft }}>
          Điểm và các dòng trên do máy tính từ dữ liệu nhóm. AI chưa nhận xét chỗ này.
        </Text>
      )}
    </View>
  );
}
