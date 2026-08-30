/** F38. What this group's home-screen widget is showing right now.
 *
 * There is no home-screen widget on a web build and there is no native widget
 * extension in this repo, so the honest framing is the one on the card itself:
 * this is a PREVIEW of the widget, drawn inside the app, from the same
 * `GET /contexts/{id}/widget` a real widget would call. Nothing here is a
 * mock-up of that response -- the picture, the name and the moment are the six
 * fields the route returns and nothing else.
 *
 * Worth having even without the extension, for two reasons. It is the only
 * screen in the app that exercises that route, so a widget answering 403 or
 * drawing the wrong group's photograph is visible to somebody holding a phone
 * rather than only to a test. And it is the thing a person can be shown when
 * they ask what the widget will look like.
 *
 * The empty state is a first-class answer, not a failure: the route returns 200
 * with `photo: null` for a group that has not posted yet, deliberately, so that
 * a stranger cannot tell "empty" from "not yours" by the status code. This card
 * says "chưa có ảnh nào" and stays exactly as large, because a widget that
 * changes size when the group goes quiet is a widget that moves the icons under
 * it.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Card } from "../../ui/Kit";
import { Anh } from "../../ui/Anh";
import { Gradient, HERO_SUNSET } from "../../navigation/Gradient";
import { docWidgetNhom, type AnhWidget } from "../../api";

/** What the card can be showing. `trong` -- a real 200 with no photograph -- is
 *  separate from `loi` on purpose; they are different sentences and only one of
 *  them is anybody's fault. */
type TrangThai =
  | { kind: "dang-tai" }
  | { kind: "co-anh"; anh: AnhWidget }
  | { kind: "trong" }
  | { kind: "loi"; detail: string };

/**
 * "hôm nay", "hôm qua", then a date.
 *
 * Relative only for the two days a person can hold in their head. "5 ngày
 * trước" is arithmetic the reader then has to undo to know which evening it
 * was, and this card has room for the date itself.
 */
export function khiNao(iso: string, now: Date = new Date()): string {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return "";
  const ngay = (d: Date) => Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
  const cach = Math.round((ngay(now) - ngay(t)) / 86_400_000);
  if (cach === 0) return "hôm nay";
  if (cach === 1) return "hôm qua";
  return `${t.getDate()}/${t.getMonth() + 1}`;
}

export function TheWidget({
  contextId,
  personId,
  doc = docWidgetNhom,
}: {
  contextId: string;
  /** Whose headers the picture is fetched with. The photo route is members-only
   *  and an `<img>` cannot send a header -- see `Anh`. */
  personId: string;
  /** Seam for the tests. */
  doc?: typeof docWidgetNhom;
}) {
  const c = usePalette();
  const [tt, setTt] = useState<TrangThai>({ kind: "dang-tai" });

  const tai = useCallback(async () => {
    try {
      const anh = await doc(contextId, personId);
      setTt(anh ? { kind: "co-anh", anh } : { kind: "trong" });
    } catch (e) {
      setTt({ kind: "loi", detail: e instanceof Error ? e.message : String(e) });
    }
  }, [contextId, personId, doc]);

  useEffect(() => {
    void tai();
  }, [tai]);

  return (
    <Card>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
        <Text style={{ ...type.title, color: c.ink }}>Widget màn hình chính</Text>
        <Text style={{ ...type.micro, color: c.inkFaint }}>xem trước</Text>
      </View>

      {/* Fixed height in every state. A widget is a fixed rectangle on somebody
          else's home screen; a preview that grows and shrinks would be showing
          a shape the real thing cannot take. */}
      <View
        style={{
          height: 148,
          marginTop: space.xs,
          borderRadius: radius.small,
          overflow: "hidden",
          backgroundColor: c.ground,
          borderWidth: 1,
          borderColor: c.line,
        }}
      >
        {tt.kind === "co-anh" ? (
          <Anh
            uri={tt.anh.imageUrl}
            alt={
              tt.anh.caption?.trim()
                ? `Ảnh widget: ${tt.anh.caption}`
                : `Ảnh widget của nhóm, ${tt.anh.authorName} đăng`
            }
            nguoiXem={personId}
            nhom={contextId}
            style={{ flex: 1 }}
            cho={<Gradient colors={HERO_SUNSET} style={{ flex: 1 }} />}
          >
            {/* The two facts a widget carries besides the picture, on their own
                ground: a real photograph can be brighter than any scrim, and
                this text has to stay readable over all of them. */}
            <View style={{ flex: 1, justifyContent: "flex-end" }}>
              <View style={{ backgroundColor: c.card, padding: space.xs }}>
                <Text numberOfLines={1} style={{ ...type.label, color: c.ink }}>
                  {tt.anh.authorName} · {khiNao(tt.anh.createdAt)}
                </Text>
                {tt.anh.caption?.trim() ? (
                  <Text numberOfLines={1} style={{ ...type.micro, color: c.inkSoft }}>
                    {tt.anh.caption}
                  </Text>
                ) : null}
              </View>
            </View>
          </Anh>
        ) : (
          <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.sm }}>
            <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
              {tt.kind === "dang-tai"
                ? "Đang hỏi máy chủ…"
                : tt.kind === "trong"
                  ? "Nhóm chưa có ảnh nào. Widget sẽ trống cho tới khi ai đó đăng tấm đầu tiên."
                  : tt.detail}
            </Text>
          </View>
        )}
      </View>

      <Text style={{ ...type.micro, color: c.inkFaint, marginTop: space.xs }}>
        Bản dựng này chưa có widget thật trên màn hình chính. Ô trên là kết quả
        thật của GET /contexts/{"{id}"}/widget, vẽ trong app.
      </Text>
    </Card>
  );
}
