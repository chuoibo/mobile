/** Kết bạn — F03 and F04, the half that a person can actually reach.
 *
 * The routes shipped in #196 and nothing called them. By this team's own way
 * of counting that means the feature did not exist: a bundle built from `main`
 * contained the string `friends` zero times, so every one of those five routes
 * was a green test suite in front of a door with no handle.
 *
 * ## Direction (Impeccable: extension, mode Operate)
 *
 * THESIS — adding a friend is a request, not a result. Every state on this
 * screen is drawn so the wait is the loudest thing on it.
 * WORLD — inherited, not invented. `src/ui/` belongs to the frontend lane;
 * this screen adds no token, no primitive and no radius of its own. Lead tone
 * is `accent`, because this is identity and not money -- `split` on this
 * screen would say "bill" about a thing that has no money in it.
 * STORY — type a number you already have -> see a face and a name -> ask ->
 * watch it sit in "đang chờ" until somebody else decides.
 * FIRST VIEWPORT — the search field and its one-line promise about the number,
 * then whatever is already waiting for an answer from *you*. Somebody who
 * opens this screen because a friend just asked them should not have to
 * scroll.
 * FORM — the row rhythm of `CaNhan`'s transaction list: round frame, name
 * column that may shrink, action column that may not.
 * FINISH: measured with `imp detect` against the rendered page at 390 and
 * 1280, plus `tests/ket-ban-web.test.mjs`, which drives the real DOM.
 *
 * ## The number
 *
 * It is typed here and it leaves in a POST body (`ban-be.ts`). Two things this
 * file does about it that a reader should not have to infer:
 *
 * 1. **A successful search clears the field.** The number's whole job was to
 *    name a person, and once there is a name the number is the one thing on
 *    screen nobody needs. Clearing it means the result card cannot be
 *    photographed, screen-shared or read over a shoulder with somebody else's
 *    telephone number beside it. A failed search keeps what was typed, because
 *    a person correcting a typo needs to see the typo.
 * 2. **The result card renders `display_name` and nothing else.** There is no
 *    field on `NguoiTimDuoc` to leak; that is the server's design and this
 *    screen does not add one back by keeping the typed string around and
 *    printing it next to the answer.
 *
 * ## What it does not do
 *
 * There is no photograph. `PersonMatchResponse` and `FriendSummary` carry a
 * name and an id, and no route in this product serves a profile picture yet,
 * so every frame here is a real `Anh` frame holding a monogram. The day an
 * avatar URL exists the frame is already the right size and already runs the
 * origin check; nothing about this layout moves.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { attemptFor, type Attempt } from "../../api";
import { Button, Card, Field } from "../../ui/Kit";
import { CoLoi, DangTai } from "../../ui/TrangThai";
import { Anh, khungTron } from "../../ui/Anh";
import { moTaLoi } from "../../ui/loi-tren-man";
import { radius, space, type, usePalette } from "../../theme";
import type { DemoPerson } from "../../navigation/nhom-demo";
import { ngayNgan } from "./tai-chinh";
import {
  chuDau,
  DIA_CHI_API,
  docDanhSachBan,
  docLoiMoi,
  guiLoiMoi,
  soCoTheGoi,
  timBanTheoSo,
  traLoiLoiMoi,
  type Ban,
  type LoiMoi,
  type NguoiTimDuoc,
} from "./ban-be";

/** The search box, as a state machine rather than four loose booleans. */
type PhaTim =
  | { pha: "chua" }
  | { pha: "dang-tim" }
  | { pha: "thay"; ai: NguoiTimDuoc }
  | { pha: "hong"; loi: string };

/** What happened to the one request this screen last tried to send. */
type PhaGui =
  | { pha: "chua" }
  | { pha: "dang-gui" }
  | { pha: "da-gui"; loiMoi: LoiMoi }
  | { pha: "hong"; loi: string };

type PhaDanhSach =
  | { pha: "dang-tai" }
  | { pha: "xong"; vao: LoiMoi[]; ra: LoiMoi[]; ban: Ban[] }
  | { pha: "hong"; loi: string };

export function KetBan({
  nguoi,
  onDong,
  tim = timBanTheoSo,
  gui = guiLoiMoi,
  traLoi = traLoiLoiMoi,
  docMoi = docLoiMoi,
  docBan = docDanhSachBan,
}: {
  nguoi: DemoPerson | null;
  onDong: () => void;
  /** Injected so the screen can be driven without a server in a unit test.
   *  The web gate does NOT use these -- it replaces `window.fetch`, so what it
   *  measures is the request this screen really builds. */
  tim?: typeof timBanTheoSo;
  gui?: typeof guiLoiMoi;
  traLoi?: typeof traLoiLoiMoi;
  docMoi?: typeof docLoiMoi;
  docBan?: typeof docDanhSachBan;
}) {
  const c = usePalette();
  const [so, setSo] = useState("");
  const [phaTim, setPhaTim] = useState<PhaTim>({ pha: "chua" });
  const [phaGui, setPhaGui] = useState<PhaGui>({ pha: "chua" });
  const [ds, setDs] = useState<PhaDanhSach>({ pha: "dang-tai" });
  // One book of attempts for the whole screen. In a ref because a re-render
  // between the press and the reply must not be able to mint a second key for
  // the same press -- that turns a retry into a second write.
  const soLanThu = useRef<Record<string, Attempt>>({});

  const toi = nguoi?.personId ?? null;

  const taiDanhSach = useCallback(async () => {
    if (!toi) return;
    setDs({ pha: "dang-tai" });
    try {
      // Sequential, not `Promise.all`. Three reads that fail independently,
      // and a rejected `Promise.all` reports one failure while the other two
      // keep running against a server that has already refused once.
      const vao = await docMoi(toi, toi, "incoming");
      const ra = await docMoi(toi, toi, "outgoing");
      const ban = await docBan(toi, toi);
      setDs({ pha: "xong", vao, ra, ban });
    } catch (problem) {
      setDs({ pha: "hong", loi: moTaLoi(problem) });
    }
  }, [toi, docMoi, docBan]);

  useEffect(() => {
    void taiDanhSach();
  }, [taiDanhSach]);

  async function chayTim() {
    if (!toi || !soCoTheGoi(so)) return;
    setPhaTim({ pha: "dang-tim" });
    setPhaGui({ pha: "chua" });
    try {
      const ai = await tim(so, toi);
      setPhaTim({ pha: "thay", ai });
      // The number has done its job. See the header: from here on the person
      // is a name, and the string that named them is not on screen anywhere.
      setSo("");
    } catch (problem) {
      setPhaTim({ pha: "hong", loi: moTaLoi(problem) });
    }
  }

  async function chayGui(ai: NguoiTimDuoc) {
    if (!toi) return;
    setPhaGui({ pha: "dang-gui" });
    try {
      const loiMoi = await gui(
        ai.person_id,
        toi,
        attemptFor(soLanThu.current, `gui-loi-moi:${ai.person_id}`),
      );
      setPhaGui({ pha: "da-gui", loiMoi });
      // Read the lists back rather than pushing the new row in locally: what
      // is on screen should be what the server says, not what this file hoped
      // it wrote.
      await taiDanhSach();
    } catch (problem) {
      setPhaGui({ pha: "hong", loi: moTaLoi(problem) });
    }
  }

  async function chayTraLoi(loiMoi: LoiMoi, quyetDinh: "accept" | "decline") {
    if (!toi) return;
    try {
      await traLoi(
        loiMoi.id,
        quyetDinh,
        toi,
        attemptFor(soLanThu.current, `tra-loi:${loiMoi.id}:${quyetDinh}`),
      );
      await taiDanhSach();
    } catch (problem) {
      setDs({ pha: "hong", loi: moTaLoi(problem) });
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <View style={{ gap: space.xs }}>
        <Text accessibilityRole="header" style={{ ...type.h1, color: c.ink }}>
          Kết bạn
        </Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Tìm bằng số điện thoại, gửi lời mời, và chờ người kia đồng ý.
        </Text>
      </View>

      <ScrollView
        // A keyboard stop on the scroller: the friend lists sit below the fold
        // at 390pt and there is no other key that reaches them.
        tabIndex={0}
        contentContainerStyle={{ gap: space.md, paddingBottom: space.md }}
      >
        {nguoi ? null : <ChuaChon />}

        <OTim
          so={so}
          onSo={setSo}
          onTim={() => void chayTim()}
          batDuoc={Boolean(toi) && soCoTheGoi(so)}
          pha={phaTim}
        />

        {phaTim.pha === "thay" ? (
          <TheKetQua
            ai={phaTim.ai}
            phaGui={phaGui}
            onGui={() => void chayGui(phaTim.ai)}
          />
        ) : null}

        <DanhSach
          ds={ds}
          onThuLai={() => void taiDanhSach()}
          onTraLoi={(loiMoi, q) => void chayTraLoi(loiMoi, q)}
          coNguoi={Boolean(toi)}
        />
      </ScrollView>

      <Button label="Đóng" onPress={onDong} tone="quiet" />
    </View>
  );
}

function ChuaChon() {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.body, color: c.ink }}>Bạn vào app bằng "Bỏ qua".</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Chưa có người nào được chọn nên chưa biết kết bạn dưới tên ai. Quay lại màn mở
        đầu và chọn một người trong nhóm.
      </Text>
    </Card>
  );
}

/** The search box, its promise about the number, and the refusal it earned. */
function OTim({
  so,
  onSo,
  onTim,
  batDuoc,
  pha,
}: {
  so: string;
  onSo: (t: string) => void;
  onTim: () => void;
  batDuoc: boolean;
  pha: PhaTim;
}) {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Tìm bạn bằng số điện thoại</Text>
      <Field
        label="Số điện thoại của người bạn muốn thêm"
        value={so}
        onChangeText={onSo}
        keyboardType="number-pad"
        // A mask, not a number. `DangKy.tsx` draws the same one, and for the
        // same two reasons: `scripts/repo_guard.py` is fail-closed on anything
        // shaped like a Vietnamese mobile and cannot tell an invented number
        // from a real one -- nor should it have to -- and a concrete example
        // reads as a required format rather than as a shape.
        placeholder="09xx xxx xxx"
        maxLength={20}
        onSubmitEditing={onTim}
        hint="Số chỉ dùng để tìm. Máy chủ không lưu số, và màn kết quả chỉ hiện tên."
      />
      <Button label="Tìm" onPress={onTim} disabled={!batDuoc} />
      {pha.pha === "dang-tim" ? <DangTai noiDung="Đang tìm…" /> : null}
      {pha.pha === "hong" ? (
        <CoLoi
          tieuDe="Chưa tìm được"
          than={pha.loi}
          viecTiepTheo="Kiểm tra lại số rồi bấm Tìm một lần nữa."
          diaChi={DIA_CHI_API}
        />
      ) : null}
    </Card>
  );
}

/**
 * Who was found, and what has been asked of them.
 *
 * The whole point of the card is the third block. A found person and a friend
 * look the same in a list; what tells them apart is a sentence saying nothing
 * has happened yet, so the sentence is drawn at body size in a chip of its
 * own rather than as a caption somebody skims past.
 */
function TheKetQua({
  ai,
  phaGui,
  onGui,
}: {
  ai: NguoiTimDuoc;
  phaGui: PhaGui;
  onGui: () => void;
}) {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Tìm thấy</Text>
      <HangNguoi ten={ai.display_name} phu="Đang có tài khoản Rủ Đi" />

      {phaGui.pha === "chua" ? (
        <View style={{ gap: space.xs }}>
          <Button label={`Gửi lời mời cho ${ai.display_name}`} onPress={onGui} />
          <Text style={{ ...type.micro, color: c.inkSoft }}>
            Gửi lời mời chưa làm hai người thành bạn. {ai.display_name} phải bấm đồng ý
            ở máy của họ.
          </Text>
        </View>
      ) : null}

      {phaGui.pha === "dang-gui" ? <DangTai noiDung="Đang gửi lời mời…" /> : null}

      {phaGui.pha === "da-gui" ? (
        <ChoDongY ten={ai.display_name} trangThai={phaGui.loiMoi.state} />
      ) : null}

      {phaGui.pha === "hong" ? (
        <CoLoi
          tieuDe="Chưa gửi được lời mời"
          than={phaGui.loi}
          viecTiepTheo="Xem hai danh sách bên dưới để biết hai bạn đang ở đâu."
          diaChi={DIA_CHI_API}
        />
      ) : null}
    </Card>
  );
}

/**
 * "Đã gửi lời mời. Đang chờ Bình đồng ý."
 *
 * Requirement 3 of this work, and the one most likely to be got wrong by
 * accident: a 201 from `POST /friends/requests` is the app being told the
 * *asking* was recorded, and a screen that answers it with a tick reads as
 * "you are now friends". `state` is rendered rather than assumed, so if the
 * server ever answered something other than `pending` this would say so
 * instead of quietly showing the wait anyway.
 */
function ChoDongY({ ten, trangThai }: { ten: string; trangThai: LoiMoi["state"] }) {
  const c = usePalette();
  const dangCho = trangThai === "pending";
  return (
    <View
      accessibilityRole="alert"
      style={{
        gap: space.xs,
        padding: space.sm,
        borderRadius: radius.control,
        backgroundColor: c.accentSoft,
        borderColor: c.accent,
        borderWidth: 1,
      }}
    >
      <Text style={{ ...type.body, fontWeight: "600", color: c.ink }}>
        {dangCho
          ? `Đã gửi lời mời. Đang chờ ${ten} đồng ý.`
          : `Máy chủ trả lời trạng thái "${trangThai}", không phải đang chờ.`}
      </Text>
      {dangCho ? (
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Hai bạn chưa phải là bạn bè. Khi {ten} bấm Đồng ý, tên họ sẽ xuất hiện ở mục
          "Bạn bè" bên dưới.
        </Text>
      ) : null}
    </View>
  );
}

/** The three lists, in the order somebody opening this screen needs them. */
function DanhSach({
  ds,
  onThuLai,
  onTraLoi,
  coNguoi,
}: {
  ds: PhaDanhSach;
  onThuLai: () => void;
  onTraLoi: (loiMoi: LoiMoi, quyetDinh: "accept" | "decline") => void;
  coNguoi: boolean;
}) {
  const c = usePalette();
  if (!coNguoi) return null;
  if (ds.pha === "dang-tai") return <DangTai noiDung="Đang đọc danh sách bạn bè…" />;
  if (ds.pha === "hong") {
    return (
      <CoLoi
        tieuDe="Chưa đọc được danh sách"
        than={ds.loi}
        viecTiepTheo="Bấm Tải lại. Nếu vẫn vậy, kiểm tra máy chủ ở địa chỉ dưới."
        diaChi={DIA_CHI_API}
        onThuLai={onThuLai}
        nhanThuLai="Tải lại"
      />
    );
  }

  return (
    <>
      {/* Incoming first: this is the only list on the screen that is waiting
          on the person reading it. */}
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>
          Lời mời đang chờ bạn trả lời ({ds.vao.length})
        </Text>
        {ds.vao.length === 0 ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Chưa ai mời bạn kết bạn. Lời mời người khác gửi cho bạn sẽ hiện ở đây.
          </Text>
        ) : (
          ds.vao.map((m) => (
            <HangNguoi
              key={m.id}
              ten={m.other_display_name}
              // Not "<tên> muốn kết bạn với bạn". The name is already the line
              // above, so repeating it said nothing and cost the row its width:
              // measured at 390pt the name column fell to ~126px and rendered
              // "Nguyễn Qu…" over a subtitle cut mid-word, on the one screen
              // where somebody decides whether they know that person.
              phu="Muốn kết bạn với bạn"
              duoi={
                <View style={{ flexDirection: "row", gap: space.xs }}>
                  <NutNho
                    nhan="Đồng ý"
                    // The visible word stays "Đồng ý" and the spoken name says
                    // which request it belongs to. Three pending invitations
                    // otherwise announce three identical buttons. WCAG 2.5.3
                    // holds because the visible label is inside the spoken one.
                    doc={`Đồng ý kết bạn với ${m.other_display_name}`}
                    mau={c.accent}
                    dam
                    onPress={() => onTraLoi(m, "accept")}
                  />
                  <NutNho
                    nhan="Từ chối"
                    doc={`Từ chối kết bạn với ${m.other_display_name}`}
                    mau={c.inkSoft}
                    onPress={() => onTraLoi(m, "decline")}
                  />
                </View>
              }
            />
          ))
        )}
      </Card>

      {/* Outgoing second. Same people-shaped rows as the friends list below on
          purpose -- the difference between them is the words, and the words
          are the feature. */}
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>
          Lời mời bạn đã gửi ({ds.ra.length})
        </Text>
        {ds.ra.length === 0 ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Bạn chưa gửi lời mời nào đang chờ.
          </Text>
        ) : (
          ds.ra.map((m) => (
            <HangNguoi
              key={m.id}
              ten={m.other_display_name}
              phu={`Đang chờ ${m.other_display_name} đồng ý. Chưa phải bạn bè.`}
            />
          ))
        )}
      </Card>

      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Bạn bè ({ds.ban.length})</Text>
        {ds.ban.length === 0 ? (
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Chưa có ai trong danh sách. Một người chỉ vào đây khi cả hai đã đồng ý.
          </Text>
        ) : (
          ds.ban.map((b) => (
            <HangNguoi
              key={b.person_id}
              ten={b.display_name}
              phu={`Bạn bè từ ${ngayNgan(b.friends_since)}`}
            />
          ))
        )}
      </Card>
    </>
  );
}

/**
 * One person: frame, name, one line about where they stand, optional action.
 *
 * `minWidth: 0` on the name column is load-bearing and not tidying -- a flex
 * item defaults to `min-width: auto` and refuses to shrink below its content,
 * so a long name pushes the column wider than the row and runs underneath the
 * buttons on its right. Measured on this same screen family in `CaNhan`.
 *
 * Actions go in `duoi`, on their own line, rather than beside the name. The
 * side-by-side version was tried first and photographed: at 390pt the two
 * buttons took ~140px of a 302px row, the name column shrank to ~126px, and
 * "Nguyễn Quốc Thắng" rendered as "Nguyễn Qu…". Truncating somebody's name is
 * bad anywhere and worst here, because the only question this row asks is
 * whether the reader recognises that person. A line of vertical space is a
 * cheaper price than a name nobody can read.
 */
function HangNguoi({
  ten,
  phu,
  duoi,
}: {
  ten: string;
  phu: string;
  /** Controls for this person, drawn under the identity block at full width. */
  duoi?: React.ReactNode;
}) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs, paddingVertical: space.xs }}>
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: space.sm,
      }}
    >
      <Anh
        uri={null}
        alt={`Ảnh đại diện của ${ten}`}
        // `uri` is hard-null here: this row draws the monogram and asks for no
        // photograph, so there is no viewer to fetch as. Pointing it at
        // `/people/{id}/avatar` would work now that `Anh` can send a header --
        // that is a small follow-up, not part of the #222 fix, and it wants its
        // own pass over what a 403 means for somebody you have not shared a
        // group with yet.
        nguoiXem={null}
        cho={
          <View
            style={{
              flex: 1,
              backgroundColor: c.accentSoft,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ ...type.title, color: c.accent }}>{chuDau(ten)}</Text>
          </View>
        }
        style={khungTron(44)}
      />
      <View style={{ flex: 1, minWidth: 0, gap: 1 }}>
        <Text numberOfLines={1} style={{ ...type.body, fontWeight: "600", color: c.ink }}>
          {ten}
        </Text>
        <Text numberOfLines={2} style={{ ...type.micro, color: c.inkSoft }}>
          {phu}
        </Text>
      </View>
    </View>
      {duoi ?? null}
    </View>
  );
}

/**
 * The two answers to a request, side by side in a row that is already narrow.
 *
 * Not `Button` from the kit: that one is full-width with 14pt of vertical
 * padding and two of them inside a list row would be taller than the row. This
 * keeps the kit's radius, border weight and label treatment and only changes
 * the box, which is the line between using the system and redefining it --
 * `src/ui/` belongs to the frontend lane and gains nothing from this file.
 *
 * 44pt minimum height, so the smaller box does not become a smaller target.
 */
function NutNho({
  nhan,
  doc,
  mau,
  dam,
  onPress,
}: {
  nhan: string;
  /** What a screen reader says, when the visible word alone is ambiguous.
   *  Must contain `nhan` verbatim: WCAG 2.5.3 asks that the visible label be
   *  part of the accessible name, so somebody using voice control can say the
   *  word they can see. */
  doc?: string;
  mau: string;
  dam?: boolean;
  onPress: () => void;
}) {
  const c = usePalette();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={doc ?? nhan}
      style={({ pressed }) => ({
        minHeight: 44,
        justifyContent: "center",
        paddingHorizontal: space.sm,
        borderWidth: 1,
        borderColor: dam ? mau : c.lineStrong,
        backgroundColor: dam ? mau : "transparent",
        borderRadius: radius.control,
        opacity: pressed ? 0.85 : 1,
      })}
    >
      <Text
        style={{ ...type.label, fontWeight: "600", color: dam ? c.accentInk : mau }}
      >
        {nhan}
      </Text>
    </Pressable>
  );
}
