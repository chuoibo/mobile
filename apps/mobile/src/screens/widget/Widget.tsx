/** F38. The Locket-style widget: one photograph, whose it is, and when.
 *
 * ## Why this screen exists at all, and what was actually missing
 *
 * `GET /contexts/{id}/widget` merged on 2026-08-30 in #319, complete with a
 * permission that asks the roster instead of believing the gateway header, a
 * response shape narrowed to three facts, and a passing test tier. It was also,
 * from the point of view of anybody holding this phone, not a feature: the
 * reverse-direction gate added in #333 measured `apps/mobile/src` and found no
 * literal `widget` anywhere in it. A route nothing calls has shipped, gone
 * green, been merged, and cannot be reached.
 *
 * So this file is the other half of that route and nothing more. It invents no
 * request field -- the server takes no body and no query string, and this
 * screen sends neither -- and it reads no fact the response does not carry.
 *
 * ## The direction, inherited rather than chosen
 *
 * This is an extension of a world that already exists, so there is no identity
 * exercise here: cream `ground`, the shared 4pt scale, `radius.base` on cards,
 * terracotta reserved for actions. What the surface adds is one decision.
 *
 *   THESIS      A widget is a photograph somebody left for you, not a card
 *               with a photograph in it. So the picture is the largest thing
 *               on the screen by a wide margin, and every other element is a
 *               caption to it.
 *   FORM        One square frame at the page's full width, `radius.base`, then
 *               a single line: name, middot, when. No counters, no hearts, no
 *               place -- the server does not send them and a widget that grew
 *               them would be the wall again at half the size.
 *   GROUND      Text sits UNDER the photograph on the card's own ground, never
 *               across it. `Anh`'s header states the rule and the reason: the
 *               scrims elsewhere in this app were measured against painted
 *               stand-ins, and a real photograph can be brighter than any of
 *               them. A widget draws a picture nobody has vetted, at the one
 *               size where a washed-out caption is unreadable rather than
 *               merely ugly, so it does not take the bet.
 *
 * ## Three states, all of them real
 *
 *   - a photograph          -> the frame, filled, with its line under it
 *   - `photo: null`         -> the frame, empty, saying the group has none yet.
 *                              This is a 200 and the server refuses to spell it
 *                              as a 404 on purpose; treating it as a failure
 *                              here would rebuild the "empty vs forbidden"
 *                              distinction it went out of its way not to leak.
 *   - a refusal             -> words from `loiWidget`, never a code or a status
 *
 * The empty state keeps the frame at its full size rather than collapsing to a
 * sentence. A widget that changes shape between "nothing yet" and "a picture"
 * is a widget that jumps on the home screen the first time somebody posts.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { ApiError, docWidget, type WidgetWire } from "../../api";
import type { NguoiDung } from "../../navigation/nhom-demo";
import { Anh } from "../../ui/Anh";
import { Card } from "../../ui/Kit";
import { CoLoi, DangTai } from "../../ui/TrangThai";
import { radius, space, type, usePalette } from "../../theme";
import { timNhomDemo } from "../ky-niem/ky-uc";
import { dongTacGia, loiWidget, moTaAnh } from "./cau-chu";

type Trang =
  | { pha: "dang-tai" }
  | { pha: "xong"; w: WidgetWire }
  | { pha: "loi"; loi: string };

export function Widget({
  nguoi,
  contextId,
  onDong,
  doc = docWidget,
  timNhom = timNhomDemo,
  /** The clock, injected so a snapshot of this screen is stable and so the
   *  boundaries in `batDauTu` can be stood on either side of. Defaulted to the
   *  real one rather than made required: a screen that cannot tell the time
   *  unless somebody passes it one is a screen with a second way to be wrong. */
  bayGio = () => Date.now(),
}: {
  nguoi: NguoiDung | null;
  /** Which group's widget, when the link named one. Null means "go and find
   *  the demo group", the same way the memory wall does. */
  contextId?: string | null;
  onDong?: () => void;
  doc?: typeof docWidget;
  timNhom?: typeof timNhomDemo;
  bayGio?: () => number;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-tai" });
  // Which group answered. Held rather than recomputed because the photograph's
  // bytes are fetched against a context id, and asking `timNhom` a second time
  // at render could answer differently and check the wrong group's membership.
  const [nhom, setNhom] = useState<string | null>(contextId ?? null);

  const tai = useCallback(async () => {
    if (!nguoi) return;
    setTrang({ pha: "dang-tai" });
    try {
      let id = contextId ?? null;
      if (id === null) id = (await timNhom(nguoi.personId)).contextId;
      setNhom(id);
      setTrang({ pha: "xong", w: await doc(id, nguoi.personId) });
    } catch (error) {
      // `ApiError` already carries words from the shared refusal table; anything
      // else is a shape this screen did not expect and gets the generic line
      // rather than `error.message`, which on a TypeError is English.
      setTrang({
        pha: "loi",
        loi:
          error instanceof ApiError
            ? loiWidget(error.status, error.code)
            : loiWidget(0, ""),
      });
    }
  }, [nguoi, contextId, doc, timNhom]);

  useEffect(() => {
    void tai();
  }, [tai]);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.ground }}
      contentContainerStyle={{ padding: space.md, gap: space.lg }}
      // The keyboard tab-stop the Cá nhân and Kỷ niệm scrollers carry, for the
      // same axe finding (`scrollable-region-focusable`): without it there is no
      // key that scrolls this column and anything below the fold is unreachable.
      tabIndex={0}
    >
      <Bia onDong={onDong} />

      {nguoi === null ? (
        <ChuaChonNguoi />
      ) : trang.pha === "dang-tai" ? (
        <DangTai noiDung="Đang lấy ảnh mới nhất của nhóm…" />
      ) : trang.pha === "loi" ? (
        <CoLoi
          tieuDe="Chưa hiện được ảnh"
          than={trang.loi}
          viecTiepTheo="Thử lại, hoặc mở Kỷ niệm để xem cả tường ảnh."
          onThuLai={() => void tai()}
        />
      ) : (
        <KhungWidget wire={trang.w} nhom={nhom} personId={nguoi.personId} bayGio={bayGio} />
      )}
    </ScrollView>
  );
}

function Bia({ onDong }: { onDong?: () => void }) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      {onDong ? (
        <Pressable
          onPress={onDong}
          accessibilityRole="button"
          accessibilityLabel="Đóng widget, quay lại màn trước"
          style={({ pressed }) => ({
            // 44pt is the touch-target floor, which is why this is padding
            // around a small glyph rather than a small box.
            minWidth: 44,
            minHeight: 44,
            alignSelf: "flex-start",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: radius.pill,
            borderWidth: 1,
            // `lineStrong`, not `line`: this is a control, and WCAG 1.4.11 asks
            // 3:1 of the edge that is the whole affordance on an unfilled shape.
            borderColor: c.lineStrong,
            opacity: pressed ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>←</Text>
        </Pressable>
      ) : null}
      <Text style={{ ...type.h1, color: c.ink }}>Ảnh mới nhất</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Tấm gần nhất ai đó trong nhóm vừa đăng. Chỉ thành viên mở được.
      </Text>
    </View>
  );
}

function ChuaChonNguoi() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.body, color: c.ink }}>Bạn vào app bằng "Bỏ qua".</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Ảnh của nhóm chỉ mở ra cho thành viên, nên màn này cần biết bạn là ai. Quay lại
        màn mở đầu và chọn một người trong nhóm.
      </Text>
    </Card>
  );
}

/**
 * The frame, and the line under it.
 *
 * Exported so a test can render it directly. The screen around it reaches this
 * component only after an effect resolves, and `renderToStaticMarkup` does not
 * run effects -- so a test driving `Widget` gets the loading state every time
 * and the two states that matter here would be rendered by nothing. The empty
 * one is the state most likely to be wrong: it is a 200, and a client that
 * mistook it for a failure would print a refusal over a perfectly normal group.
 *
 * `padding: 0` on the card with the footer bringing its own: the photograph
 * runs to the card's edge, which is the difference between a widget and a
 * thumbnail sitting inside a box. `overflow: hidden` on the card is what keeps
 * the picture's square corners from poking out of the card's rounded ones.
 */
export function KhungWidget({
  wire,
  nhom,
  personId,
  bayGio,
}: {
  wire: WidgetWire;
  nhom: string | null;
  personId: string;
  bayGio: () => number;
}) {
  const c = usePalette();
  const anh = wire.photo;
  const now = bayGio();

  return (
    <Card style={{ padding: 0, gap: 0, overflow: "hidden" }}>
      <Anh
        uri={anh?.image_url ?? null}
        alt={anh ? moTaAnh(anh.author_name, anh.caption) : ""}
        // `nguoiXem` is not optional and null is not the answer here: the photo
        // route answers 401 without `X-Actor-ID`, and an `<img>` cannot send a
        // header. Passing null would produce a request guaranteed to be refused
        // and a stand-in indistinguishable from an empty group. See `Anh`.
        nguoiXem={personId}
        nhom={nhom ?? undefined}
        cho={<ChoTrong coAnh={anh !== null} />}
        style={{ width: "100%", aspectRatio: 1 }}
      />
      <View style={{ padding: space.md, gap: space.xs }}>
        {anh ? (
          <>
            <Text style={{ ...type.title, color: c.ink }}>
              {dongTacGia(anh.author_name, anh.created_at, now)}
            </Text>
            {anh.caption?.trim() ? (
              <Text style={{ ...type.body, color: c.inkSoft }}>{anh.caption.trim()}</Text>
            ) : null}
          </>
        ) : (
          <>
            <Text style={{ ...type.title, color: c.ink }}>Nhóm chưa có ảnh nào</Text>
            <Text style={{ ...type.body, color: c.inkSoft }}>
              Tấm đầu tiên ai đó đăng lên tường sẽ hiện ở đây.
            </Text>
          </>
        )}
      </View>
    </Card>
  );
}

/**
 * What the frame draws while there is no picture in it.
 *
 * Two different sentences for two different facts, and they must not be the
 * same drawing. A group with no photograph and a photograph that is still
 * arriving are states a person can act on differently -- one is "post one", the
 * other is "wait" -- and rd-fe-25 is the whole reason this app is careful here:
 * a stand-in that means both is a stand-in that hid a broken image route for a
 * release.
 *
 * `line` on `card`, so it reads as a reserved area rather than as a failure.
 * The word inside sits at `inkSoft`, which measures 5.46:1 on that fill.
 */
function ChoTrong({ coAnh }: { coAnh: boolean }) {
  const c = usePalette();
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: c.line,
        alignItems: "center",
        justifyContent: "center",
        padding: space.md,
      }}
    >
      <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
        {coAnh ? "Đang tải ảnh…" : "Chưa có ảnh nào trên tường nhóm"}
      </Text>
    </View>
  );
}
