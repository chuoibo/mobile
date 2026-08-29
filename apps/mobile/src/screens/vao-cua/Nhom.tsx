/** F03 and F04. Open a group, add friends to it, and let them accept.
 *
 * Every button here sends a real request: `POST /contexts`,
 * `PUT /people/{id}`, `POST /contexts/{id}/members`,
 * `POST /memberships/{id}/accept`, and `GET /contexts/{id}/members` to read
 * the result back. Nothing is kept in a local array pretending to be a roster
 * -- after each write the list is re-read from the server, so what is on
 * screen is what the database says and not what this file hoped it wrote.
 *
 * ## Two limits, stated rather than hidden
 *
 * **The group lasts as long as the session.** There is no storage in this app
 * (see `danh-tinh.ts`), and no route that lists the groups a person belongs
 * to, so a reload loses the handle to the group even though the rows survive
 * in Postgres. The group is real; the app's memory of it is not.
 *
 * **The roster arrives without names.** `MembershipResponse` carries
 * `person_id` and no `display_name`, so the server can say who is in a group
 * but not what to call them. Rendering the ids would reproduce, on the group's
 * own screen, the exact defect `routes/people.py` was written to fix -- a
 * person shown a UUID where a name belongs. So names are held here, keyed by
 * the id they were registered under. That is sound only because every member
 * of this group was added through this screen; a group that predates the
 * session would render strangers as ids, which is why this screen does not
 * offer to open one.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import {
  ApiError,
  type Attempt,
  attemptFor,
  registerPerson,
} from "../../api";
import { Button, Card, Field } from "../../ui/Kit";
import { radius, space, type, usePalette } from "../../theme";
import type { NguoiDung } from "../../navigation/nhom-demo";
import { chuDau, idNgauNhien, tenHopLe } from "./danh-tinh";
import {
  type Nhom as NhomWire,
  type ThanhVien,
  danhSachThanhVien,
  moiVaoNhom,
  nhanLoiMoi,
  taoNhom,
} from "./cong-api";

type Trang =
  | { pha: "chua-co-nhom" }
  | { pha: "dang-lam"; viec: string }
  | { pha: "co-nhom"; nhom: NhomWire; ds: ThanhVien[] }
  | { pha: "hong"; loi: string; nhom: NhomWire | null };

export function Nhom({ nguoi, onDong }: {
  /** Who the app is acting as. Null means nobody pressed a name on the way
   *  in, and this screen cannot send anything without one -- every call it
   *  makes is authorised by `X-Actor-ID`. */
  nguoi: NguoiDung | null;
  onDong: () => void;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "chua-co-nhom" });
  const [tenNhom, setTenNhom] = useState("");
  const [tenBan, setTenBan] = useState("");
  const soLanThu = useRef<Record<string, Attempt>>({});
  // person_id -> the name it was registered under. See the header.
  const ten = useRef<Record<string, string>>({});

  const nhomHienTai =
    trang.pha === "co-nhom" ? trang.nhom : trang.pha === "hong" ? trang.nhom : null;

  const docLai = useCallback(
    async (nhom: NhomWire) => {
      if (!nguoi) return;
      const ds = await danhSachThanhVien(nhom.id, nguoi.personId);
      setTrang({ pha: "co-nhom", nhom, ds });
    },
    [nguoi],
  );

  useEffect(() => {
    if (nguoi) ten.current[nguoi.personId] = nguoi.name;
  }, [nguoi]);

  function hong(loi: unknown, nhom: NhomWire | null) {
    setTrang({
      pha: "hong",
      nhom,
      // Same rule as the sign-in screen: only `ApiError` text is known to be
      // safe to show. A friend's name could be inside any other throw.
      loi:
        loi instanceof ApiError
          ? loi.message
          : "Chưa làm được việc này. Thử lại sau một chút.",
    });
  }

  async function moNhom() {
    if (!nguoi || !tenHopLe(tenNhom)) return;
    setTrang({ pha: "dang-lam", viec: "Đang mở nhóm…" });
    try {
      const nhom = await taoNhom(
        tenNhom.trim(),
        nguoi.personId,
        attemptFor(soLanThu.current, `tao-nhom:${tenNhom.trim()}`),
      );
      await docLai(nhom);
    } catch (loi) {
      hong(loi, null);
    }
  }

  /** F03 then F04, in that order and for a stated reason.
   *
   * The server refuses an invite for a person it has never been told a name
   * for (`_require_registered_person`), so naming has to come first. Doing it
   * the other way round earns a refusal whose wording is about the friend
   * rather than about the order this screen chose. */
  async function themVaMoi() {
    if (!nguoi || !nhomHienTai || !tenHopLe(tenBan)) return;
    const name = tenBan.trim();
    const id = idNgauNhien();
    setTrang({ pha: "dang-lam", viec: `Đang thêm ${name}…` });
    try {
      await registerPerson(
        { id, name },
        nguoi.personId,
        attemptFor(soLanThu.current, `dat-ten-ban:${id}:${name}`),
      );
      ten.current[id] = name;
      await moiVaoNhom(
        nhomHienTai.id,
        id,
        nguoi.personId,
        attemptFor(soLanThu.current, `moi:${nhomHienTai.id}:${id}`),
      );
      setTenBan("");
      await docLai(nhomHienTai);
    } catch (loi) {
      hong(loi, nhomHienTai);
    }
  }

  async function nhan(tv: ThanhVien) {
    if (!nguoi || !nhomHienTai) return;
    setTrang({ pha: "dang-lam", viec: "Đang nhận lời mời…" });
    try {
      await nhanLoiMoi(
        tv.id,
        // The invitee, which the button has already checked is this person.
        // `accept_context_membership` compares `is_invitee` against this
        // header, so passing anybody else would be asserting their identity.
        nguoi.personId,
        attemptFor(soLanThu.current, `nhan:${tv.id}`),
      );
      await docLai(nhomHienTai);
    } catch (loi) {
      hong(loi, nhomHienTai);
    }
  }

  if (!nguoi) {
    return (
      <KhungNhom onDong={onDong}>
        <Card>
          <Text style={{ ...type.body, color: c.ink }}>
            Chưa biết bạn là ai nên chưa mở được nhóm. Quay ra màn mở đầu và
            đăng ký bằng số điện thoại, hoặc chọn một người trong danh sách demo.
          </Text>
        </Card>
      </KhungNhom>
    );
  }

  return (
    <KhungNhom onDong={onDong}>
      {trang.pha === "hong" ? (
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
          <Text style={{ ...type.body, color: c.warn }}>{trang.loi}</Text>
        </View>
      ) : null}

      {trang.pha === "dang-lam" ? (
        <Text role="status" style={{ ...type.body, color: c.inkSoft }}>
          {trang.viec}
        </Text>
      ) : null}

      {nhomHienTai === null ? (
        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Lập hội mới</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Nhóm mở ra là thật và nằm trong máy chủ. Nhưng app chưa nhớ được
            nhóm qua lần mở lại, nên tải lại trang là mất đường quay về nhóm này.
          </Text>
          <Field
            label="Tên nhóm"
            value={tenNhom}
            onChangeText={setTenNhom}
            placeholder="Team Đà Lạt"
          />
          <Button
            label="Mở nhóm"
            onPress={moNhom}
            disabled={!tenHopLe(tenNhom) || trang.pha === "dang-lam"}
          />
        </Card>
      ) : (
        <>
          <Card>
            <Text style={{ ...type.title, color: c.ink }}>{nhomHienTai.display_name}</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              {trang.pha === "co-nhom"
                ? moTaSiSo(trang.ds)
                : "Chưa đọc lại được danh sách."}
            </Text>
          </Card>

          <Card>
            <Text style={{ ...type.title, color: c.ink }}>Thêm bạn</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Thêm một người là đặt tên cho họ trên máy chủ rồi mời vào nhóm.
              Họ vào hẳn khi chính họ nhận lời mời.
            </Text>
            <Field
              label="Tên bạn của bạn"
              value={tenBan}
              onChangeText={setTenBan}
              placeholder="Tên người bạn muốn rủ"
            />
            <Button
              label="Thêm và mời"
              onPress={themVaMoi}
              disabled={!tenHopLe(tenBan) || trang.pha === "dang-lam"}
            />
          </Card>

          {trang.pha === "co-nhom" ? (
            <Card>
              <Text style={{ ...type.title, color: c.ink }}>Thành viên</Text>
              {trang.ds.map((tv) => (
                <HangThanhVien
                  key={tv.id}
                  tv={tv}
                  ten={ten.current[tv.person_id] ?? null}
                  laMinh={tv.person_id === nguoi.personId}
                  onNhan={() => nhan(tv)}
                />
              ))}
            </Card>
          ) : null}
        </>
      )}
    </KhungNhom>
  );
}

/** Chrome shared by every state, so the way out never depends on the request
 *  having succeeded. A screen whose close button only renders on the happy
 *  path is a screen somebody gets stuck in. */
function KhungNhom({ children, onDong }: {
  children: React.ReactNode;
  onDong: () => void;
}) {
  const c = usePalette();
  return (
    <View style={{ flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }}>
      <View style={{ gap: space.xs }}>
        <Text style={{ ...type.h1, color: c.ink }}>Nhóm của bạn</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Mở nhóm, rủ bạn vào, và xem ai đã nhận lời.
        </Text>
      </View>
      <ScrollView contentContainerStyle={{ gap: space.md, paddingBottom: space.md }}>
        {children}
      </ScrollView>
      <Button label="Đóng" onPress={onDong} tone="quiet" />
    </View>
  );
}

/** "3 người đã vào, 2 người chưa nhận lời" -- counted from what the server
 *  returned, so it cannot drift from the list printed under it. */
function moTaSiSo(ds: ThanhVien[]): string {
  const vao = ds.filter((t) => t.state === "active").length;
  const cho = ds.filter((t) => t.state === "invited").length;
  if (cho === 0) return `${vao} người trong nhóm`;
  return `${vao} người trong nhóm · ${cho} người chưa nhận lời`;
}

function HangThanhVien({ tv, ten, laMinh, onNhan }: {
  tv: ThanhVien;
  /** Null when this person was not added in this session. See the file header
   *  for why that is possible and what it costs. */
  ten: string | null;
  laMinh: boolean;
  onNhan: () => void;
}) {
  const c = usePalette();
  const daVao = tv.state === "active";
  // A name this screen never learned is shown as a stated absence rather than
  // as a UUID. "Thành viên chưa rõ tên" is honest and readable; sixteen bytes
  // of hex is neither.
  const nhan = ten ?? "Thành viên chưa rõ tên";
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, minHeight: 48 }}>
      <View
        style={{
          width: 36,
          height: 36,
          borderRadius: 999,
          backgroundColor: c.accentSoft,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ ...type.body, fontWeight: "700", color: c.accent }}>
          {ten ? chuDau(ten) : "?"}
        </Text>
      </View>

      <View style={{ flex: 1, gap: 2 }}>
        <Text style={{ ...type.body, color: c.ink }}>
          {nhan}
          {laMinh ? " (bạn)" : ""}
        </Text>
        <Text style={{ ...type.label, color: daVao ? c.split : c.inkSoft }}>
          {daVao
            ? tv.role === "admin"
              ? "Người mở nhóm"
              : "Đã vào nhóm"
            : "Đã mời, chờ nhận lời"}
        </Text>
      </View>

      {/* Only on this person's own invitation. Putting it on every pending row
          would mean the app asserting somebody else's `X-Actor-ID` to make its
          own button work, which is the one thing the header auth makes easy
          and the reason it must not be built on. */}
      {!daVao && laMinh ? <Button label="Nhận lời mời" onPress={onNhan} tone="ghost" /> : null}
    </View>
  );
}
