/** F14. Redeem an outing invite. Orange lead: a person is acting.
 *
 * The reply names ids and `membership_state` only. A link redeemer is not a
 * member yet, so this screen must not invent a group name or a trip name.
 * `active` means they are in. `invited` means the invite was taken and the
 * group still has to accept them. Those are two sentences, never one
 * "success".
 *
 * Since ADR-0014 there are two doors behind one button, chosen by whether this
 * phone is signed in:
 *
 * - **Not signed in** -- the token is treated as a named invitation and
 *   exchanged for a session at `POST /sessions`. Nobody is picked locally;
 *   the server answers with whose session it is. This is the only way into a
 *   production host, and it is why this screen no longer refuses with "chưa
 *   chọn người" when there is no session: choosing a person locally is exactly
 *   the claim that stopped being believed.
 * - **Signed in** -- the token is treated as a forwardable link and redeemed
 *   the old way, which needs an identity the app already has.
 *
 * A link token tried by somebody with no session gets the ordinary refusal.
 * That is truthful: a link names nobody, so there is no account for it to be.
 */
import React, { useRef, useState } from "react";
import { Text, View } from "react-native";
import {
  ApiError,
  newAttempt,
  nhanLoiMoiBuoiDi,
  thongDiepNguoiDoc,
  tokenPhienHienTai,
  type Attempt,
} from "../../api";
import { doiLoiMoiLayPhien } from "../../phien";
import type { DemoPerson } from "../../navigation/nhom-demo";
import { type, usePalette } from "../../theme";
import { Button, Card, Screen } from "../../ui/Kit";

export const CAU_MOI_CHUA_BIET =
  "App chưa biết đây là buổi đi nào cho tới khi nhận.";

import { cauSauKhiNhan } from "../../rudi/loi-moi-den";

export { cauSauKhiNhan };

type Trang =
  | { pha: "chua-nhan" }
  | { pha: "dang-gui" }
  | { pha: "xong"; state: "invited" | "active"; qua: "lien-ket" | "phien" }
  | { pha: "hong"; loi: string };

export function NhanLoiMoi({
  token,
  nguoi,
  onDong,
}: {
  token: string;
  nguoi: DemoPerson | null;
  onDong: () => void;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<Trang>({ pha: "chua-nhan" });
  const lanBam = useRef<Attempt | null>(null);

  async function nhan() {
    const attempt = (lanBam.current ??= newAttempt());
    setTrang({ pha: "dang-gui" });
    try {
      if (tokenPhienHienTai() === null) {
        // The session door. No `nguoi` is read here on purpose: who this
        // becomes is written on the invitation, server-side.
        const phien = await doiLoiMoiLayPhien(token);
        setTrang({
          pha: "xong",
          state: phien.membership_state === "active" ? "active" : "invited",
          qua: "phien",
        });
        return;
      }
      if (!nguoi) {
        setTrang({
          pha: "hong",
          loi: "Chưa chọn người, nên chưa nhận được lời mời.",
        });
        return;
      }
      const wire = await nhanLoiMoiBuoiDi(token, nguoi.personId, attempt);
      setTrang({ pha: "xong", state: wire.membership_state, qua: "lien-ket" });
    } catch (err) {
      setTrang({
        pha: "hong",
        loi: err instanceof ApiError ? err.message : thongDiepNguoiDoc(0, null),
      });
    }
  }

  function thuLai() {
    lanBam.current = null;
    void nhan();
  }

  return (
    <Screen title="Lời mời buổi đi">
      <View style={{ flex: 1, justifyContent: "center" }}>
        <Card>
          {trang.pha === "chua-nhan" || trang.pha === "dang-gui" ? (
            <>
              <Text style={{ ...type.title, color: c.ink }}>
                Bạn được mời vào một buổi đi
              </Text>
              <Text style={{ ...type.body, color: c.ink }}>{CAU_MOI_CHUA_BIET}</Text>
              <Button
                label={trang.pha === "dang-gui" ? "Đang nhận…" : "Nhận lời mời"}
                disabled={trang.pha === "dang-gui"}
                onPress={() => {
                  void nhan();
                }}
              />
            </>
          ) : null}

          {trang.pha === "xong" ? (
            <Text style={{ ...type.body, color: c.ink }}>
              {cauSauKhiNhan(trang.state, trang.qua)}
            </Text>
          ) : null}

          {trang.pha === "hong" ? (
            <>
              <Text style={{ ...type.body, color: c.ink }}>{trang.loi}</Text>
              <Button label="Thử lại" onPress={thuLai} />
            </>
          ) : null}
        </Card>
      </View>
      <Button label="Đóng" tone="quiet" onPress={onDong} />
    </Screen>
  );
}
