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
 * The handle itself now lives one level up, in `VoTab`, so it survives this
 * screen being closed and can be read by Khám phá when somebody checks in.
 * That changes how long the app remembers, not whether it does: a reload still
 * loses it, and the sentence above still holds.
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
import { docMaBan, type TheBan } from "./ma-ban";
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

export function Nhom({ nguoi, nhomDangCo, onNhom, banQuetDuoc, onDong }: {
  /** Who the app is acting as. Null means nobody pressed a name on the way
   *  in, and this screen cannot send anything without one -- every call it
   *  makes is authorised by `X-Actor-ID`. */
  nguoi: NguoiDung | null;
  /** The group this session already opened, held by `VoTab` so it outlives
   *  this screen. Null on a first visit. */
  nhomDangCo?: NhomWire | null;
  /** Hands the handle upward the moment a group exists. */
  onNhom?: (nhom: NhomWire) => void;
  /** F05. A friend scanned in on the way here. */
  banQuetDuoc?: TheBan | null;
  onDong: () => void;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "chua-co-nhom" });
  const [tenNhom, setTenNhom] = useState("");
  const [tenBan, setTenBan] = useState("");
  // Whatever somebody pasted into the code box, unparsed. Kept raw so the
  // field shows what was typed rather than a normalised version of it.
  const [maDan, setMaDan] = useState("");
  const soLanThu = useRef<Record<string, Attempt>>({});
  // person_id -> the name it was registered under. See the header.
  const ten = useRef<Record<string, string>>({});

  const nhomHienTai =
    trang.pha === "co-nhom"
      ? trang.nhom
      : trang.pha === "hong"
        ? trang.nhom
        : (nhomDangCo ?? null);

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

  // Re-read a group this screen was handed rather than opened. Without it the
  // roster stays empty on a second visit and the screen reports "0 người" for
  // a group that has members -- an empty answer that looks like a true one.
  useEffect(() => {
    if (nhomDangCo && trang.pha === "chua-co-nhom") void docLai(nhomDangCo);
  }, [nhomDangCo, trang.pha, docLai]);

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
      onNhom?.(nhom);
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
   * rather than about the order this screen chose.
   *
   * `PUT /people/{id}` is idempotent on an unchanged name and only asks for
   * the rename permission when the name actually differs, so running this for
   * somebody who registered themselves -- which is what a scanned code means
   * -- names nobody twice and renames nobody at all. */
  async function themVaMoi(id: string, name: string) {
    if (!nguoi || !nhomHienTai) return;
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
      setMaDan("");
      await docLai(nhomHienTai);
    } catch (loi) {
      hong(loi, nhomHienTai);
    }
  }

  /** F03 by hand: a name typed in, and an id minted for it.
   *
   * The id is random rather than derived, because a name is not an identity --
   * see `idNgauNhien`'s own comment on the two people called Nam. */
  function themBangTen() {
    if (!tenHopLe(tenBan)) return;
    void themVaMoi(idNgauNhien(), tenBan.trim());
  }

  /**
   * F05: the same act, but the friend identified themselves.
   *
   * The difference from `themBangTen` is the whole point of the feature. There
   * the id is minted here and the person on the other side of the table ends
   * up with a second account they cannot log into; here the id came off their
   * own code, so the row this invites is the row they actually sign in as.
   *
   * A code with no name in it is still usable -- the person is identified,
   * which is the part that cannot be guessed -- and the typed name is used for
   * the label. Refusing would make a code read aloud across a table useless.
   */
  function themBangMa(the: TheBan) {
    const name = the.ten ?? (tenHopLe(tenBan) ? tenBan.trim() : null);
    if (name === null) return;
    void themVaMoi(the.personId, name);
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

          {banQuetDuoc ? (
            <TheQuetDuoc
              ban={banQuetDuoc}
              tenGoTay={tenBan}
              onTenGoTay={setTenBan}
              dangLam={trang.pha === "dang-lam"}
              onThem={() => themBangMa(banQuetDuoc)}
            />
          ) : null}

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
              onPress={themBangTen}
              disabled={!tenHopLe(tenBan) || trang.pha === "dang-lam"}
            />
          </Card>

          <ThemBangMa
            ma={maDan}
            onMa={setMaDan}
            tenGoTay={tenBan}
            onTenGoTay={setTenBan}
            dangLam={trang.pha === "dang-lam"}
            onThem={themBangMa}
          />

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

/** F05, arriving side. The card a scanned code opens on.
 *
 * "Scan QR → mở profile → Add friend" is three steps in the spec, and this is
 * the middle one: enough of a profile to decide, and one button that acts. It
 * is not a full profile screen and does not pretend to be -- the only facts
 * the code carries are a name and an id, and inventing trips or a rating here
 * would be filling a shell with plausible numbers.
 *
 * The id is shown, shortened. Not decoration: two friends can share a name,
 * and the eight characters are the only thing on this card that distinguishes
 * the person who actually held up the square from somebody who happens to be
 * called the same thing.
 */
function TheQuetDuoc({ ban, tenGoTay, onTenGoTay, dangLam, onThem }: {
  ban: TheBan;
  tenGoTay: string;
  onTenGoTay: (value: string) => void;
  dangLam: boolean;
  onThem: () => void;
}) {
  const c = usePalette();
  const ten = ban.ten;
  const nhan = ten ?? (tenHopLe(tenGoTay) ? tenGoTay.trim() : null);

  return (
    <View
      style={{
        backgroundColor: c.accentSoft,
        borderColor: c.accent,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.sm,
      }}
    >
      <Text style={{ ...type.micro, color: c.accent, letterSpacing: 1 }}>
        QUÉT ĐƯỢC MÃ KẾT BẠN
      </Text>

      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <View
          style={{
            width: 44,
            height: 44,
            borderRadius: 999,
            backgroundColor: c.card,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Text style={{ ...type.title, color: c.accent }}>
            {ten ? chuDau(ten) : "?"}
          </Text>
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={{ ...type.title, color: c.ink }}>
            {ten ?? "Chưa rõ tên"}
          </Text>
          <Text style={{ ...type.micro, color: c.inkSoft }}>
            Mã tài khoản {ban.personId.slice(0, 8)}
          </Text>
        </View>
      </View>

      {ten === null ? (
        <>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Mã này chỉ mang mã tài khoản, không mang tên. Đặt tên để nhận ra
            người này trong danh sách nhóm.
          </Text>
          <Field
            label="Gọi người này là"
            value={tenGoTay}
            onChangeText={onTenGoTay}
            placeholder="Tên người bạn vừa quét"
          />
        </>
      ) : null}

      <Button
        label="Mời vào nhóm"
        onPress={onThem}
        disabled={nhan === null || dangLam}
      />
    </View>
  );
}

/** The same door, for a code that arrived as text rather than as a scan.
 *
 * There is no in-app camera here and the card says so instead of implying
 * one. A QR decoder is finder-pattern detection, a perspective transform and
 * Reed–Solomon correction -- days of work whose output is a string that the
 * phone's own camera app already produces for free. What this box needs is
 * that string, and a person reading a code aloud across a table produces the
 * same thing.
 *
 * The parse runs on every keystroke and its verdict is shown live, so the
 * button being off is explained rather than merely observed.
 */
function ThemBangMa({ ma, onMa, tenGoTay, onTenGoTay, dangLam, onThem }: {
  ma: string;
  onMa: (value: string) => void;
  /** Shared with the card above, on purpose: both write the name that the
   *  friend will be registered under, and two independent boxes for one value
   *  is how somebody fills the wrong one and wonders why the button is off. */
  tenGoTay: string;
  onTenGoTay: (value: string) => void;
  dangLam: boolean;
  onThem: (ban: TheBan) => void;
}) {
  const c = usePalette();
  const doc = ma.trim() === "" ? null : docMaBan(ma);
  const hong = ma.trim() !== "" && doc === null;
  const canTen = doc !== null && doc.ten === null;
  const duTen = doc !== null && (doc.ten !== null || tenHopLe(tenGoTay));

  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>Thêm bằng mã kết bạn</Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>
        Quét mã của bạn mình bằng camera điện thoại rồi dán đường dẫn vào đây.
        App chưa có máy quét riêng, và camera sẵn có của máy làm việc đó tốt hơn.
      </Text>
      <Field
        label="Mã hoặc đường dẫn"
        value={ma}
        onChangeText={onMa}
        placeholder="Dán mã kết bạn vào đây"
      />

      {hong ? (
        <Text role="status" style={{ ...type.label, color: c.warn }}>
          Chưa đọc ra người nào từ đoạn này. Dán cả đường dẫn, hoặc dán riêng mã
          tài khoản.
        </Text>
      ) : null}
      {doc ? (
        <Text role="status" style={{ ...type.label, color: c.split }}>
          Đọc ra: {doc.ten ?? "một tài khoản chưa rõ tên"} ·{" "}
          {doc.personId.slice(0, 8)}
        </Text>
      ) : null}

      {canTen ? (
        <Field
          label="Gọi người này là"
          value={tenGoTay}
          onChangeText={onTenGoTay}
          placeholder="Tên người trong mã"
        />
      ) : null}

      <Button
        label="Thêm người này"
        tone="quiet"
        onPress={() => {
          if (doc) onThem(doc);
        }}
        disabled={!duTen || dangLam}
      />
    </Card>
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
