/** Quản trị nhóm: who is in the group, what they may do, and who is invited
 *  to a trip.
 *
 * Five routes, all real, all of them writes or reads against the same server
 * every other screen talks to:
 *
 *   GET    /contexts/{id}                              the group's own row
 *   GET    /contexts/{id}/members                      the roster
 *   PUT    /contexts/{id}/members/{pid}/role           promote / demote
 *   DELETE /contexts/{id}/members/{pid}                leave (yourself only)
 *   POST   /outings/{oid}/invites                      invite to a trip
 *   POST   /outings/{oid}/invites/{iid}/revoke         pull one back
 *
 * The group handle comes from `khoiDongNhom`, the same way chat and Lên plan
 * get theirs -- `CONTEXT_ID` in `api.ts` has never had a row in `contexts`,
 * and every call on this screen is a group-scoped one that would be a 403
 * under it.
 *
 * ## Two honest limits, drawn on the screen rather than left to be discovered
 *
 * **There is no "remove this person" here, because there is no route for it.**
 * `DELETE /contexts/{id}/members/{pid}` requires `is_self`, so it is the
 * *leave* button and it only appears on your own row. A button labelled
 * "Xoá thành viên" on somebody else's row would be a 403 wearing a label that
 * blames the network.
 *
 * **The invite list is what this session created, not what exists.** The API
 * has no `GET /outings/{id}/invites`; the server mints an invite and answers
 * with it once. So an empty list here means "none created since this screen
 * opened" and the card says exactly that instead of implying a trip with no
 * invitations.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import {
  ApiError,
  attemptFor,
  BASE_URL,
  docDanhSachBuoiDi,
  thongDiepNguoiDoc,
  type Attempt,
  type BuoiDi,
} from "../../api";
import type { DemoPerson } from "../../navigation/nhom-demo";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Choice } from "../../ui/Kit";
import { CoLoi, DangTai, TrongRong } from "../../ui/TrangThai";
import { khoiDongNhom, type NhomState } from "../chat/nhom";
import { danhSachThanhVien, type ThanhVien } from "../vao-cua/cong-api";
import {
  coTheDoiVaiTro,
  coTheRoiNhom,
  coTheThuHoi,
  datVaiTro,
  docNhom,
  duongDanMoi,
  laQuanTri,
  loiNhacQuanTriCuoi,
  moTaHang,
  nhanNutVaiTro,
  roiNhom,
  taoLoiMoiBuoiDi,
  tenThanhVien,
  thuHoiLoiMoi,
  trangThaiLoiMoi,
  vaiTroDoiThanh,
  type LoiMoiBuoiDi,
  type NhomChiTiet,
} from "./quan-tri";

type NhomMan = { kind: "dang-tai" } | { kind: "chua-chon" } | NhomState;
/** The three reads this screen makes after it has a group id, as one state:
 *  the group row, the roster, and the trips an invite can point at. They are
 *  fetched together because none of the three is useful alone -- a roster with
 *  no group name is a list of strangers, and a trip picker with no roster
 *  cannot name anybody to invite. */
type DuLieu =
  | { kind: "dang-tai" }
  | { kind: "xong"; nhom: NhomChiTiet; ds: ThanhVien[]; buoi: BuoiDi[] }
  /** You left, and the screen has nothing left to read.
   *
   *  A state of its own rather than a re-read, because measured against a live
   *  server the re-read is a 403: `view_context_members` and `get_context`
   *  both require ACTIVE membership, so the moment `DELETE .../members/{me}`
   *  succeeds, every read this screen makes starts answering
   *  `permission_denied`. Re-reading would print a refusal underneath a
   *  success and leave somebody unsure whether they left. */
  | { kind: "da-roi" }
  | { kind: "loi"; loi: string };

export function QuanTriNhom({ nguoi, contextId: nhomSan, onDong }: {
  /** Who the app is acting as. Null means nobody was picked on the way in, and
   *  nothing on this screen can be sent without one: every call is authorised
   *  by `X-Actor-ID`, and the two admin routes compare it against the group's
   *  own membership rows. */
  nguoi: DemoPerson | null;
  /** The group this session already has open, if it has one.
   *
   *  Given, this screen administers THAT group -- pressing "Quản trị nhóm"
   *  right after opening "Hội Cà Phê" must not silently administer the demo
   *  group instead. Null falls back to `khoiDongNhom`, which is what a cold
   *  start and a URL both produce: the app has no storage, so a session that
   *  did not open a group has no handle to one. */
  contextId?: string | null;
  onDong: () => void;
}) {
  const c = usePalette();
  const [nhom, setNhom] = useState<NhomMan>(
    nhomSan
      ? { kind: "xong", contextId: nhomSan, tenNhom: "", members: [] }
      : nguoi
        ? { kind: "dang-tai" }
        : { kind: "chua-chon" },
  );
  const [du, setDu] = useState<DuLieu>({ kind: "dang-tai" });
  const [busy, setBusy] = useState(false);
  const [loiGhi, setLoiGhi] = useState<string | null>(null);
  const [tinNhan, setTinNhan] = useState<string | null>(null);
  const [buoiChon, setBuoiChon] = useState<string | null>(null);
  const [nguoiChon, setNguoiChon] = useState<string | null>(null);
  // Session-only, and the card underneath says so. See the file header.
  const [moiDaTao, setMoiDaTao] = useState<LoiMoiBuoiDi[]>([]);
  const soLanThu = useRef<Record<string, Attempt>>({});

  const taiNhom = useCallback(() => {
    // A handle handed down is a handle: `GET /contexts/{id}` below is what
    // proves it is real and readable, so there is nothing for `khoiDongNhom`
    // to add -- and running it anyway would open the DEMO group over the top
    // of the one the caller named.
    if (nhomSan) {
      setNhom({ kind: "xong", contextId: nhomSan, tenNhom: "", members: [] });
      return;
    }
    if (!nguoi) {
      setNhom({ kind: "chua-chon" });
      return;
    }
    let huy = false;
    setNhom({ kind: "dang-tai" });
    khoiDongNhom(nguoi.id).then((s) => {
      if (!huy) setNhom(s);
    });
    return () => {
      huy = true;
    };
  }, [nguoi, nhomSan]);

  useEffect(() => taiNhom(), [taiNhom]);

  const contextId = nhom.kind === "xong" ? nhom.contextId : null;

  const taiDu = useCallback(() => {
    if (!nguoi || !contextId) return;
    let huy = false;
    setDu({ kind: "dang-tai" });
    // The three reads run together rather than in sequence: they are
    // independent, and chaining them would make the screen three round trips
    // slow for no ordering that matters.
    Promise.all([
      docNhom(contextId, nguoi.personId),
      danhSachThanhVien(contextId, nguoi.personId),
      docDanhSachBuoiDi(contextId, nguoi.personId),
    ])
      .then(([chiTiet, ds, trang]) => {
        if (huy) return;
        setDu({ kind: "xong", nhom: chiTiet, ds, buoi: trang.outings });
        // Pre-select the newest trip so the invite card is usable in one tap
        // rather than two. Only when nothing is chosen yet -- a re-read after
        // an invite must not move the selection out from under somebody.
        setBuoiChon((truoc) => truoc ?? trang.outings[0]?.id ?? null);
      })
      .catch((err) => {
        if (huy) return;
        setDu({
          kind: "loi",
          loi: err instanceof ApiError ? err.message : thongDiepNguoiDoc(0, null),
        });
      });
    return () => {
      huy = true;
    };
  }, [nguoi, contextId]);

  useEffect(() => taiDu(), [taiDu]);

  /** Re-read the roster after a write, rather than patching the array.
   *
   *  The list is what the database says about a group other people are also
   *  changing, and this is the moment we are already talking to the server
   *  about it. Patching would show a role that the write may not have made. */
  async function docLaiRoster() {
    if (!nguoi || !contextId || du.kind !== "xong") return;
    const ds = await danhSachThanhVien(contextId, nguoi.personId);
    setDu((truoc) => (truoc.kind === "xong" ? { ...truoc, ds } : truoc));
  }

  function bao(err: unknown, mac: string) {
    // Only `ApiError` text is known to have been written for a person;
    // anything else may carry a name or a raw server string.
    setLoiGhi(err instanceof ApiError ? err.message : mac);
  }

  async function doiVaiTro(hang: ThanhVien) {
    if (!nguoi || !contextId) return;
    const moi = vaiTroDoiThanh(hang);
    setBusy(true);
    setLoiGhi(null);
    setTinNhan(null);
    try {
      await datVaiTro(
        contextId,
        hang.person_id,
        moi,
        nguoi.personId,
        attemptFor(soLanThu.current, `vai-tro:${contextId}:${hang.person_id}:${moi}`),
      );
      await docLaiRoster();
      setTinNhan(
        `${tenThanhVien(hang)} giờ là ${moi === "admin" ? "quản trị viên" : "thành viên"}.`,
      );
    } catch (err) {
      bao(err, "Chưa đổi được vai trò. Thử lại sau một chút.");
    } finally {
      setBusy(false);
    }
  }

  async function roi(hang: ThanhVien) {
    if (!nguoi || !contextId) return;
    setBusy(true);
    setLoiGhi(null);
    setTinNhan(null);
    try {
      await roiNhom(
        contextId,
        hang.person_id,
        nguoi.personId,
        attemptFor(soLanThu.current, `roi-nhom:${contextId}:${hang.person_id}`),
      );
      // Deliberately no re-read. See `DuLieu`'s `da-roi` case: every read this
      // screen makes is 403 from here on, so asking again would print a
      // refusal under a success.
      setDu({ kind: "da-roi" });
      setTinNhan(
        "Bạn đã rời nhóm. Các khoản đã chia vẫn còn trong sổ; rời nhóm không xoá nghĩa vụ nào.",
      );
    } catch (err) {
      bao(err, "Chưa rời được nhóm. Thử lại sau một chút.");
    } finally {
      setBusy(false);
    }
  }

  async function moiVaoChuyen(kieu: "link" | "group") {
    if (!nguoi || !contextId || !buoiChon) return;
    if (kieu === "group" && !nguoiChon) return;
    setBusy(true);
    setLoiGhi(null);
    setTinNhan(null);
    try {
      const than =
        kieu === "link"
          ? ({ source: "link" } as const)
          : ({ source: "group", person_id: nguoiChon! } as const);
      const moi = await taoLoiMoiBuoiDi(
        buoiChon,
        than,
        nguoi.personId,
        attemptFor(
          soLanThu.current,
          `moi-chuyen:${buoiChon}:${kieu}:${kieu === "group" ? nguoiChon : "link"}`,
        ),
        contextId,
      );
      setMoiDaTao((truoc) => [moi, ...truoc]);
      setTinNhan(
        kieu === "link"
          ? "Đã tạo lời mời bằng link. Gửi đường dẫn dưới đây cho người bạn muốn rủ."
          : "Đã mời người này vào chuyến.",
      );
    } catch (err) {
      bao(err, "Chưa tạo được lời mời. Thử lại sau một chút.");
    } finally {
      setBusy(false);
    }
  }

  async function thuHoi(moi: LoiMoiBuoiDi) {
    if (!nguoi || !contextId) return;
    setBusy(true);
    setLoiGhi(null);
    setTinNhan(null);
    try {
      const sau = await thuHoiLoiMoi(
        moi.outing_id,
        moi.id,
        nguoi.personId,
        attemptFor(soLanThu.current, `thu-hoi:${moi.id}`),
        contextId,
      );
      // The revoke reply carries no token, so the row is merged rather than
      // replaced: the link must keep rendering, struck through, instead of
      // disappearing the moment it stops working.
      setMoiDaTao((truoc) =>
        truoc.map((m) => (m.id === sau.id ? { ...m, revoked_at: sau.revoked_at } : m)),
      );
      setTinNhan("Đã thu hồi lời mời. Đường dẫn đó không dùng được nữa.");
    } catch (err) {
      bao(err, "Chưa thu hồi được lời mời. Thử lại sau một chút.");
    } finally {
      setBusy(false);
    }
  }

  const quanTri = du.kind === "xong" && laQuanTri(du.ds, nguoi?.personId ?? null);
  const bayGio = Date.now();

  return (
    <Khung onDong={onDong}>
      {loiGhi ? <BangLoi text={loiGhi} /> : null}
      {tinNhan ? <BangTin text={tinNhan} /> : null}

      {nhom.kind === "chua-chon" ? (
        <TrongRong
          tieuDe="Chưa chọn người"
          than="Quay ra màn mở đầu và chọn một người. Không biết bạn là ai thì máy chủ không cho xem nhóm nào cả."
        />
      ) : null}

      {nhom.kind === "dang-tai" ? (
        <DangTai noiDung="Đang mở nhóm" phu="Hỏi máy chủ nhóm demo, rồi đọc thành viên." />
      ) : null}

      {nhom.kind === "hong" ? (
        <CoLoi
          tieuDe="Chưa vào được nhóm"
          than={thongDiepNguoiDoc(nhom.status, nhom.detail)}
          viecTiepTheo="Kiểm tra máy chủ đang chạy, rồi bấm thử lại."
          diaChi={nhom.url}
          onThuLai={taiNhom}
        />
      ) : null}

      {nhom.kind === "xong" && du.kind === "dang-tai" ? (
        <DangTai noiDung="Đang đọc nhóm và thành viên" />
      ) : null}

      {du.kind === "da-roi" ? (
        <TrongRong
          tieuDe="Bạn đã rời nhóm"
          than="Từ giờ máy chủ không cho tài khoản này đọc nhóm đó nữa, nên màn này không còn gì để hiện. Nhờ một người trong nhóm mời lại nếu bạn muốn quay vào."
        />
      ) : null}

      {nhom.kind === "xong" && du.kind === "loi" ? (
        <CoLoi
          tieuDe="Chưa đọc được nhóm"
          than={du.loi}
          viecTiepTheo="Bấm thử lại. Chưa có gì bị ghi sai."
          diaChi={BASE_URL}
          onThuLai={taiDu}
        />
      ) : null}

      {du.kind === "xong" ? (
        <>
          <TheNhom nhom={du.nhom} soThanhVien={du.ds.length} quanTri={quanTri} />

          <Card>
            <TieuDeThe
              tieuDe="Thành viên"
              phu={
                quanTri
                  ? "Bạn là quản trị của nhóm này, nên đổi được vai trò của người khác."
                  : "Chỉ quản trị của chính nhóm này mới đổi được vai trò. Bạn vẫn rời nhóm được."
              }
            />
            {loiNhacQuanTriCuoi(du.ds, nguoi?.personId ?? null) ? (
              <Text style={{ ...type.label, color: c.warn }}>
                {loiNhacQuanTriCuoi(du.ds, nguoi?.personId ?? null)}
              </Text>
            ) : null}
            {du.ds.map((hang) => (
              <HangThanhVien
                key={hang.id}
                hang={hang}
                laToi={hang.person_id === nguoi?.personId}
                choDoiVaiTro={coTheDoiVaiTro(du.ds, nguoi?.personId ?? null, hang)}
                choRoi={coTheRoiNhom(nguoi?.personId ?? null, hang)}
                busy={busy}
                onDoiVaiTro={() => void doiVaiTro(hang)}
                onRoi={() => void roi(hang)}
              />
            ))}
          </Card>

          <Card>
            <TieuDeThe
              tieuDe="Mời vào chuyến"
              phu="Lời mời gắn với một chuyến đi, không phải với cả nhóm. Ai trong nhóm cũng mời được."
            />
            {du.buoi.length === 0 ? (
              <Text style={{ ...type.body, color: c.inkSoft }}>
                Nhóm chưa có chuyến nào. Sang tab Lên plan tạo một chuyến rồi quay lại đây.
              </Text>
            ) : (
              <>
                <Choice
                  label="Chuyến"
                  options={du.buoi.map((b) => ({ id: b.id, label: b.title }))}
                  value={buoiChon}
                  onChange={setBuoiChon}
                />
                <Choice
                  label="Mời thành viên nào (bỏ trống nếu mời bằng link)"
                  options={du.ds.map((t) => ({ id: t.person_id, label: tenThanhVien(t) }))}
                  value={nguoiChon}
                  onChange={setNguoiChon}
                />
                <Button
                  label="Mời thành viên này"
                  onPress={() => void moiVaoChuyen("group")}
                  disabled={busy || !buoiChon || !nguoiChon}
                />
                <Button
                  label="Tạo link mời"
                  tone="quiet"
                  onPress={() => void moiVaoChuyen("link")}
                  disabled={busy || !buoiChon}
                />
              </>
            )}
          </Card>

          <Card>
            <TieuDeThe
              tieuDe="Lời mời vừa tạo"
              phu="Chỉ những lời mời tạo từ lúc mở màn này. Máy chủ chưa có đường đọc lại danh sách lời mời, nên trống ở đây không có nghĩa là chuyến không có lời mời nào."
            />
            {moiDaTao.length === 0 ? (
              <Text style={{ ...type.body, color: c.inkSoft }}>
                Chưa tạo lời mời nào trong lượt này.
              </Text>
            ) : (
              moiDaTao.map((moi) => (
                <HangLoiMoi
                  key={moi.id}
                  moi={moi}
                  bayGio={bayGio}
                  busy={busy}
                  onThuHoi={() => void thuHoi(moi)}
                />
              ))
            )}
          </Card>
        </>
      ) : null}
    </Khung>
  );
}

/** The group's own row, read through `GET /contexts/{id}`.
 *
 *  Worth its own read rather than reusing the name `khoiDongNhom` already
 *  returned: that name came from the create/replay call, and this one is what
 *  the server says the group is called now. They differ the moment anybody
 *  renames a group, and the screen that administers the group is the wrong
 *  place to be showing a cached name. */
function TheNhom({ nhom, soThanhVien, quanTri }: {
  nhom: NhomChiTiet;
  soThanhVien: number;
  quanTri: boolean;
}) {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>{nhom.display_name}</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        {soThanhVien} dòng thành viên · {quanTri ? "bạn là quản trị" : "bạn là thành viên"}
      </Text>
      {/* Eight characters, not the whole id. Enough to tell two groups apart in
          a bug report, and not a value anybody is invited to copy around. */}
      <Text style={{ ...type.micro, color: c.inkFaint }}>Mã nhóm {nhom.id.slice(0, 8)}</Text>
    </Card>
  );
}

function TieuDeThe({ tieuDe, phu }: { tieuDe: string; phu: string }) {
  const c = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>{phu}</Text>
    </View>
  );
}

function HangThanhVien({ hang, laToi, choDoiVaiTro, choRoi, busy, onDoiVaiTro, onRoi }: {
  hang: ThanhVien;
  laToi: boolean;
  choDoiVaiTro: boolean;
  choRoi: boolean;
  busy: boolean;
  onDoiVaiTro: () => void;
  onRoi: () => void;
}) {
  const c = usePalette();
  return (
    <View
      style={{
        gap: space.xs,
        paddingVertical: space.sm,
        borderTopWidth: 1,
        borderTopColor: c.line,
        minHeight: 48,
      }}
    >
      <Text style={{ ...type.body, color: c.ink }}>
        {tenThanhVien(hang)}
        {laToi ? " (bạn)" : ""}
      </Text>
      <Text style={{ ...type.label, color: hang.state === "active" ? c.split : c.inkSoft }}>
        {moTaHang(hang)}
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>
        {choDoiVaiTro ? (
          <View style={{ flexGrow: 1, minWidth: 160 }}>
            <Button label={nhanNutVaiTro(hang)} tone="ghost" onPress={onDoiVaiTro} disabled={busy} />
          </View>
        ) : null}
        {/* Only on your own row, and the label says "rời" rather than "xoá":
            the route behind it requires `is_self`, so there is no version of
            this button that removes somebody else. */}
        {choRoi ? (
          <View style={{ flexGrow: 1, minWidth: 160 }}>
            <Button label="Rời nhóm" tone="quiet" onPress={onRoi} disabled={busy} />
          </View>
        ) : null}
      </View>
    </View>
  );
}

function HangLoiMoi({ moi, bayGio, busy, onThuHoi }: {
  moi: LoiMoiBuoiDi;
  bayGio: number;
  busy: boolean;
  onThuHoi: () => void;
}) {
  const c = usePalette();
  const duong = duongDanMoi(moi, BASE_URL);
  const conDung = coTheThuHoi(moi);
  return (
    <View
      style={{
        gap: space.xs,
        paddingVertical: space.sm,
        borderTopWidth: 1,
        borderTopColor: c.line,
      }}
    >
      <Text style={{ ...type.body, color: c.ink }}>
        {moi.source === "link" ? "Lời mời bằng link" : "Lời mời cho một thành viên"} ·{" "}
        {trangThaiLoiMoi(moi, bayGio)}
      </Text>
      {duong ? (
        // Rendered even after revoking, struck through. A link that vanishes
        // the moment it stops working leaves somebody wondering which of the
        // three they just pulled back.
        <Text
          selectable
          style={{
            ...type.micro,
            color: conDung ? c.inkSoft : c.inkFaint,
            textDecorationLine: conDung ? "none" : "line-through",
          }}
        >
          {duong}
        </Text>
      ) : (
        <Text style={{ ...type.micro, color: c.inkFaint }}>
          Lời mời cho một người trong nhóm không có link; máy chủ không phát token cho nó.
        </Text>
      )}
      {conDung ? (
        <Button label="Thu hồi" tone="quiet" onPress={onThuHoi} disabled={busy} />
      ) : null}
    </View>
  );
}

/** Chrome shared by every state, so the way out never depends on a request
 *  having succeeded. Same shape as `vao-cua/Nhom.tsx`, for the same reason. */
function Khung({ children, onDong }: { children: React.ReactNode; onDong: () => void }) {
  const c = usePalette();
  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.lg }}>
      <View style={{ gap: space.xs }}>
        <Text style={{ ...type.h1, color: c.ink }}>Quản trị nhóm</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Ai trong nhóm, ai được làm gì, và ai đang được mời đi chuyến nào.
        </Text>
      </View>
      <ScrollView
        contentContainerStyle={{ gap: space.lg, paddingBottom: space.lg }}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
      <Button label="Đóng" onPress={onDong} tone="quiet" />
    </View>
  );
}

function BangLoi({ text }: { text: string }) {
  const c = usePalette();
  return (
    <View
      role="alert"
      style={{
        backgroundColor: c.accentSoft,
        borderColor: c.warn,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.sm,
      }}
    >
      <Text style={{ ...type.body, color: c.warn }}>{text}</Text>
    </View>
  );
}

function BangTin({ text }: { text: string }) {
  const c = usePalette();
  return (
    <View
      role="status"
      accessibilityLiveRegion="polite"
      style={{
        backgroundColor: c.splitSoft,
        borderColor: c.split,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.sm,
      }}
    >
      <Text style={{ ...type.body, color: c.split }}>{text}</Text>
    </View>
  );
}
