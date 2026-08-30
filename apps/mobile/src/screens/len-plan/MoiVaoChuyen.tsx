/** F14. Rủ thêm người vào MỘT chuyến, from inside that chuyến.
 *
 * The two invite routes have had a caller since the Quản trị nhóm screen
 * landed, but that caller starts from the group and makes you pick the trip
 * out of a dropdown. This one starts from the trip you are already looking at,
 * which is where somebody is standing when they decide to rủ thêm người, and
 * it is the door mockup 04.01 implies with its `Invite pending` state.
 *
 * Presentational on purpose: every request is a prop. That is what lets
 * `?man=moi-vao-chuyen` mount the real component over a frozen fixture, so a
 * detector, a screenshot pass and an accessibility sweep can open this screen
 * cold -- none of which can tap their way through a group, a trip and a
 * roster read to reach it.
 *
 * ## Two sentences the screen has to say out loud
 *
 * **The list is what this session made.** There is no `GET
 * /outings/{id}/invites`; the server mints an invite and answers with it once.
 * Empty here means "none made since this screen opened", never "this trip has
 * no invites".
 *
 * **Thu hồi is a one-way door for that person.** See `moi-vao-chuyen.ts`: the
 * row survives revocation and the unique index does not care, so the same
 * person cannot be invited to the same trip twice. The card says so before the
 * button is pressed rather than after the server answers 409.
 */
import React from "react";
import { ScrollView, Text, View } from "react-native";
import { BASE_URL } from "../../api";
import { space, type, usePalette } from "../../theme";
import { Button, Card, Screen } from "../../ui/Kit";
import { CoLoi, DangTai } from "../../ui/TrangThai";
import {
  coTheThuHoi,
  duongDanMoi,
  trangThaiLoiMoi,
  type LoiMoiBuoiDi,
} from "../quan-tri/quan-tri";
import type { ThanhVien } from "../vao-cua/cong-api";
import { nhanKhoangNgay, type BuoiDi } from "./buoi-di";
import {
  danhSachMoiDuoc,
  tenLoiMoi,
  tomTatLoiMoi,
  type HangMoi,
} from "./moi-vao-chuyen";

/** How the roster read went. A failed read is its own case rather than an
 *  empty roster: an empty roster means "nobody else is in this group", which
 *  is a sentence this screen prints, and a failure is not that sentence. */
export type SoThanhVien =
  | { kind: "dang-tai" }
  | { kind: "xong"; ds: readonly ThanhVien[] }
  | { kind: "loi"; loi: string };

export function MoiVaoChuyen({
  buoi,
  roster,
  toiId,
  daMoi,
  busy,
  loi,
  tinNhan,
  bayGio,
  onMoiThanhVien,
  onTaoLink,
  onThuHoi,
  onTaiLaiRoster,
  onQuayLai,
}: {
  buoi: BuoiDi;
  roster: SoThanhVien;
  /** Who is looking, so their own row says "Đây là bạn" instead of offering
   *  an invite they do not need. Null when nobody is identified yet. */
  toiId: string | null;
  /** Invites created in THIS session. Never the trip's real list. */
  daMoi: readonly LoiMoiBuoiDi[];
  busy?: boolean;
  loi?: string | null;
  tinNhan?: string | null;
  /** Passed in rather than read here, so a screenshot of this screen is the
   *  same screenshot twice. */
  bayGio: number;
  onMoiThanhVien: (personId: string) => void;
  onTaoLink: () => void;
  onThuHoi: (moi: LoiMoiBuoiDi) => void;
  onTaiLaiRoster: () => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const hang =
    roster.kind === "xong" ? danhSachMoiDuoc(roster.ds, toiId, daMoi) : [];

  return (
    <Screen
      title="Mời vào chuyến"
      hint={`${buoi.title} · ${nhanKhoangNgay(buoi.starts_on, buoi.ends_on)}`}
      footer={<Button label="Quay lại chuyến" tone="quiet" onPress={onQuayLai} />}
    >
      <ScrollView
        contentContainerStyle={{ gap: space.md, paddingBottom: space.sm }}
        keyboardShouldPersistTaps="handled"
      >
        {loi ? (
          <Text style={{ ...type.body, color: c.warn }}>{loi}</Text>
        ) : null}
        {tinNhan ? (
          <Text style={{ ...type.body, color: c.ink }}>{tinNhan}</Text>
        ) : null}

        {/* `DangTai` and `CoLoi` each draw their own `Card`, so they are
            siblings here rather than children of one -- nesting them put a
            card inside a card and gave the failure state two borders. */}
        {roster.kind === "dang-tai" ? (
          <DangTai noiDung="Đang đọc danh sách thành viên" />
        ) : null}

        {roster.kind === "loi" ? (
          <CoLoi
            tieuDe="Chưa đọc được danh sách thành viên"
            than={roster.loi}
            viecTiepTheo="Bấm thử lại. Chưa có lời mời nào bị tạo."
            diaChi={BASE_URL}
            onThuLai={onTaiLaiRoster}
          />
        ) : null}

        {roster.kind === "xong" ? (
          <Card>
            <Text style={{ ...type.title, color: c.ink }}>Người trong nhóm</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Lời mời gắn với chuyến này, không phải với cả nhóm. Ai trong nhóm
              cũng mời được.
            </Text>

            {hang.length === 0 ? (
              <Text style={{ ...type.body, color: c.inkSoft }}>
                Nhóm chưa có thành viên nào. Dùng link mời ở dưới để rủ người
                chưa ở trong nhóm.
              </Text>
            ) : null}

            {hang.map((h) => (
              <HangNguoi
                key={h.personId}
                hang={h}
                busy={busy}
                onMoi={() => onMoiThanhVien(h.personId)}
              />
            ))}
          </Card>
        ) : null}

        <Card>
          <Text style={{ ...type.title, color: c.ink }}>
            Rủ người chưa ở trong nhóm
          </Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Link mời không gọi tên ai, nên ai cầm cũng dùng được một lần. Người
            nhận vào chuyến ở trạng thái chờ nhóm duyệt, không thấy ngay dữ
            liệu nhóm.
          </Text>
          <Button
            label={busy ? "Đang tạo…" : "Tạo link mời"}
            disabled={busy}
            onPress={onTaoLink}
          />
        </Card>

        <Card>
          <Text style={{ ...type.title, color: c.ink }}>Lời mời vừa tạo</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Chỉ những lời mời tạo từ lúc mở màn này. Máy chủ chưa có đường đọc
            lại danh sách lời mời của một chuyến, nên trống ở đây không có nghĩa
            là chuyến chưa mời ai.
          </Text>
          <Text style={{ ...type.body, color: c.ink }}>
            {tomTatLoiMoi(daMoi, bayGio)}
          </Text>
          {daMoi.map((moi) => (
            <HangLoiMoi
              key={moi.id}
              moi={moi}
              ten={tenLoiMoi(moi, roster.kind === "xong" ? roster.ds : [])}
              bayGio={bayGio}
              busy={busy}
              onThuHoi={() => onThuHoi(moi)}
            />
          ))}
        </Card>
      </ScrollView>
    </Screen>
  );
}

function HangNguoi({
  hang,
  busy,
  onMoi,
}: {
  hang: HangMoi;
  busy?: boolean;
  onMoi: () => void;
}) {
  const c = usePalette();
  return (
    <View
      style={{
        gap: space.xs,
        paddingVertical: space.sm,
        borderTopWidth: 1,
        borderTopColor: c.line,
        minHeight: 44,
      }}
    >
      <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>
        {hang.ten}
      </Text>
      {/* The reason is text, not a greyed-out button with a tooltip nobody on
          a phone can open. Somebody who cannot invite this person is entitled
          to the sentence explaining why without hovering anything. */}
      {hang.vi ? (
        <Text style={{ ...type.label, color: c.inkSoft }}>{hang.vi}</Text>
      ) : null}
      {hang.moiDuoc ? (
        <View style={{ alignSelf: "flex-start" }}>
          <Button
            label="Mời vào chuyến"
            tone="quiet"
            disabled={busy}
            onPress={onMoi}
          />
        </View>
      ) : null}
    </View>
  );
}

function HangLoiMoi({
  moi,
  ten,
  bayGio,
  busy,
  onThuHoi,
}: {
  moi: LoiMoiBuoiDi;
  ten: string;
  bayGio: number;
  busy?: boolean;
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
        {ten} · {trangThaiLoiMoi(moi, bayGio)}
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
          Lời mời cho một người trong nhóm không có link; máy chủ không phát
          token cho nó.
        </Text>
      )}
      {conDung ? (
        <>
          <Button
            label="Thu hồi"
            tone="quiet"
            disabled={busy}
            onPress={onThuHoi}
          />
          <Text style={{ ...type.micro, color: c.inkFaint }}>
            Thu hồi xong không mời lại người đó vào chuyến này được nữa.
          </Text>
        </>
      ) : null}
    </View>
  );
}
