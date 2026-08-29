/** F46 on screen: "nhóm mình đã tới đây", and the button that says so.
 *
 * Mockup reference is `product/features/06-ho-so-va-hanh-trinh.png`, screen 3,
 * where a check-in appears in the activity feed ("Bạn đã check-in tại Quảng
 * trường Lâm Viên"). That feed is the group memory wall, and this is the place
 * a row gets written from.
 *
 * ## The three states this card can be in, and why none of them is hidden
 *
 * **No group.** The app has no storage and no route that lists somebody's
 * groups (see `screens/vao-cua/Nhom.tsx`), so on a cold start there is no
 * context to write to. The card says that and points at the [+] menu instead
 * of rendering a button that would 404. A disabled control with no explanation
 * is the version of this that gets filed as a bug.
 *
 * **Nobody signed in.** Every write here is authorised by `X-Actor-ID`. A
 * check-in with no actor is not a check-in.
 *
 * **Working.** The button posts, and the list underneath is re-read from the
 * server afterwards rather than being appended to locally -- the same rule the
 * group screen follows. What is on screen is what the database says.
 *
 * ## Location, and what this card deliberately does not do
 *
 * It does not read GPS. The coordinates stored are the catalogue's, and they
 * are the server's to supply; automatic detection of which venue a group is
 * standing in is F47 and is not built. The card says "đang ở đây" only as the
 * person's own claim, because that is all it is.
 *
 * It also does not name who checked in. The wall carries `author_id`, and this
 * app has no route that turns a person id into a name for somebody it did not
 * register itself -- the scar `Nhom.tsx` documents. Printing the UUID would
 * reproduce exactly the defect `routes/people.py` exists to fix, so the rows
 * say when and not who, and say so out loud.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card } from "../../ui/Kit";
import { attemptFor, type Attempt } from "../../api";
import type { NguoiDung } from "../../navigation/nhom-demo";
import type { Nhom as NhomWire } from "../vao-cua/cong-api";
import { checkIn, checkInTaiDay, gioNgan, loiCheckIn, type KyNiem } from "./check-in";
import type { Place } from "./places";

type Trang =
  | { pha: "dang-tai" }
  | { pha: "xong"; ds: KyNiem[] }
  | { pha: "dang-gui" }
  | { pha: "hong"; loi: string; ds: KyNiem[] };

export function CheckIn({ place, nguoi, nhom }: {
  place: Place;
  nguoi: NguoiDung | null;
  nhom: NhomWire | null;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "dang-tai" });
  const soLanThu = useRef<Record<string, Attempt>>({});

  const san = nguoi !== null && nhom !== null;

  const docLai = useCallback(async () => {
    if (!nguoi || !nhom) return;
    try {
      setTrang({ pha: "xong", ds: await checkInTaiDay(nhom.id, place.id, nguoi.personId) });
    } catch (loi) {
      setTrang({ pha: "hong", loi: loiCheckIn(loi), ds: [] });
    }
  }, [nguoi, nhom, place.id]);

  useEffect(() => {
    if (san) void docLai();
  }, [san, docLai]);

  async function gui() {
    if (!nguoi || !nhom) return;
    const truoc = trang.pha === "xong" ? trang.ds : [];
    setTrang({ pha: "dang-gui" });
    try {
      await checkIn(
        nhom.id,
        place.id,
        nguoi.personId,
        // Keyed on the group and the place, so a double press on a flaky
        // connection is one mark on the timeline rather than two.
        attemptFor(soLanThu.current, `check-in:${nhom.id}:${place.id}`),
      );
      await docLai();
    } catch (loi) {
      setTrang({ pha: "hong", loi: loiCheckIn(loi), ds: truoc });
    }
  }

  if (!san) {
    return (
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Check-in ở đây</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          {nguoi === null
            ? "Chưa biết bạn là ai nên chưa check-in được. Quay ra màn mở đầu và đăng ký bằng số điện thoại, hoặc chọn một người trong danh sách demo."
            : "Chưa có nhóm nào đang mở trong phiên này. Bấm [+] ở thanh dưới rồi \"Tạo nhóm\" — check-in là mốc của một nhóm, không phải của một người."}
        </Text>
      </Card>
    );
  }

  const ds = trang.pha === "xong" ? trang.ds : trang.pha === "hong" ? trang.ds : [];

  return (
    <Card>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
        <Text style={{ ...type.title, color: c.ink }}>Check-in ở đây</Text>
        {trang.pha === "xong" && ds.length > 0 ? (
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            {ds.length} lần
          </Text>
        ) : null}
      </View>

      <Text style={{ ...type.label, color: c.inkSoft }}>
        Ghi lại là nhóm {nhom.display_name} đã tới {place.name}. Nó thành một mốc
        trên tường kỷ niệm của nhóm, và chỉ người trong nhóm đọc được.
      </Text>

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
          <Text style={{ ...type.label, color: c.warn }}>{trang.loi}</Text>
        </View>
      ) : null}

      <Button
        label={trang.pha === "dang-gui" ? "Đang ghi…" : "Nhóm đang ở đây"}
        onPress={gui}
        disabled={trang.pha === "dang-gui" || trang.pha === "dang-tai"}
      />

      {trang.pha === "dang-tai" ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
          <ActivityIndicator color={c.accent} />
          <Text style={{ ...type.label, color: c.inkSoft }}>Đang đọc lịch sử check-in…</Text>
        </View>
      ) : null}

      {trang.pha === "xong" && ds.length === 0 ? (
        <Text style={{ ...type.label, color: c.inkFaint }}>
          Nhóm chưa check-in ở đây lần nào.
        </Text>
      ) : null}

      {ds.length > 0 ? (
        <View style={{ gap: space.xs, marginTop: space.xs }}>
          {ds.map((k) => (
            <Dong key={k.id} k={k} />
          ))}
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            Chỉ ghi thời điểm, chưa ghi tên người check-in — app chưa có đường
            tra tên từ mã tài khoản của người khác.
          </Text>
        </View>
      ) : null}
    </Card>
  );
}

/** One past visit. Time first, because that is the only fact this row has that
 *  the heading above does not already carry. */
function Dong({ k }: { k: KyNiem }) {
  const c = usePalette();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, minHeight: 32 }}>
      <View
        style={{
          width: 8,
          height: 8,
          borderRadius: 999,
          backgroundColor: c.split,
        }}
      />
      <Text style={{ ...type.label, color: c.ink, fontVariant: ["tabular-nums"] }}>
        {gioNgan(k.created_at)}
      </Text>
      {k.caption ? (
        <Text numberOfLines={1} style={{ ...type.label, color: c.inkSoft, flex: 1 }}>
          {k.caption}
        </Text>
      ) : null}
    </View>
  );
}
