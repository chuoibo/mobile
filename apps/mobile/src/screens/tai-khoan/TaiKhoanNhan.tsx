/** Where the money lands. The screen that was missing.
 *
 * `POST /batches` refuses to freeze a round when somebody who is owed money has
 * no bank destination on file, and it was right to. What was wrong is that the
 * app had no way to produce one: QA walked the second half of the flow by hand,
 * hit that refusal, listed every control still on screen, and found three
 * buttons none of which led anywhere. The app was asking for a thing it had no
 * screen to make. This is that screen.
 *
 * Two rules shape it, and both are about money rather than about layout:
 *
 * 1. **A wrong account number is money gone.** There is no verification source
 *    to ask -- spec section 8.5 says so outright -- so the number is typed
 *    twice, and nothing is sent until a review step has shown it back in full
 *    beside the holder name the sender's own banking app will display. A single
 *    box and a confident button is how a transposed digit reaches a stranger.
 * 2. **An account number is somebody's, and screens get photographed.** It is
 *    shown in full exactly twice: while it is being typed, because a person
 *    cannot check what they cannot see, and in the review step, which is the
 *    check. Everywhere afterwards it is `maskAccount`ed -- including the line
 *    this screen hands back to the flow it came from.
 *
 * The bank is picked, never typed. `bankDisplayName` will happily hand back
 * "Mã ngân hàng 970999" for a code nobody has, and a free-text box is how that
 * code gets in.
 */
import React, { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { space, type, usePalette } from "../../theme";
import { Button, Card, Choice, Field, Screen } from "../../ui/Kit";
import { bankDisplayName, maskAccount } from "../../ui/vietqr";
import {
  chuanHoaSoTaiKhoan,
  chuanHoaTen,
  FORM_TRONG,
  locNganHang,
  trungSoTaiKhoan,
  vanDeCuaForm,
  vanDeSoTaiKhoan,
  type FormTaiKhoan,
} from "./kiem-tra";

/** What the screen hands back, in the shape `saveBankRecipient` wants. */
export type DichDen = {
  bankBin: string;
  accountNumber: string;
  accountName: string;
};

/* A shape hint, not an account. Grouped in fours because that is how a banking
 * app displays one, and because the form is meant to accept what gets pasted
 * out of it, spaces and all. */
// repo-guard: allow=long-number reason=synthetic-placeholder-account-number
const VI_DU_SO_TAI_KHOAN = "0011 0022 0033";

/**
 * Group the digits in fours, for reading only.
 *
 * The value sent to the server is `chuanHoaSoTaiKhoan`, which has no spaces in
 * it. This is the review step's job: fourteen unbroken characters are read by
 * skipping, and skipping is exactly how a transposition survives a check.
 */
export function nhomBon(so: string): string {
  return (so.match(/.{1,4}/g) ?? []).join(" ");
}

export function TaiKhoanNhan({
  nguoiNhan,
  busy,
  banDau,
  onLuu,
  onBack,
}: {
  /** Whose account this is. The server only lets a person set their own. */
  nguoiNhan: { id: string; name: string };
  busy?: boolean;
  /**
   * Where to start. Used by the URL view only, and for one reason.
   *
   * The review step is the last screen anybody reads before money is committed
   * to a destination, and it is four fields and a press past the opening
   * screen. A detector renders a URL and cannot press anything, so without a
   * way to mount straight into it, "the screen was scanned" would quietly mean
   * "the empty form was scanned" -- and the empty form is the half that
   * matters least. Same argument, and the same narrowness, as `XemTrangThai`
   * in App.tsx.
   *
   * Initial state only: nothing reads it after mount, so it cannot be used to
   * drive the screen from outside.
   */
  banDau?: { form: FormTaiKhoan; dangDuyet: boolean };
  onLuu: (dichDen: DichDen) => void;
  onBack: () => void;
}) {
  const c = usePalette();
  const [form, setForm] = useState<FormTaiKhoan>(banDau?.form ?? FORM_TRONG);
  const [timNganHang, setTimNganHang] = useState("");
  // The review step is a step, not a dialog. A confirm dialog over a form is
  // read as "are you sure" and dismissed as one; this has to be read.
  const [dangDuyet, setDangDuyet] = useState(banDau?.dangDuyet ?? false);

  const set = <K extends keyof FormTaiKhoan>(key: K, value: FormTaiKhoan[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const danhSach = locNganHang(timNganHang);
  const vanDe = vanDeCuaForm(form);
  const sanSang = vanDe.length === 0;

  const soDaChuan = chuanHoaSoTaiKhoan(form.soTaiKhoan);
  const tenDaChuan = chuanHoaTen(form.tenChuTaiKhoan);
  const soHopLe = vanDeSoTaiKhoan(form.soTaiKhoan) === null;
  // Only after the second box has something in it. An empty box is not a
  // mismatch yet, and shouting at somebody mid-word is how a form feels hostile.
  const lechSo =
    soHopLe &&
    form.nhapLai.trim() !== "" &&
    !trungSoTaiKhoan(form.soTaiKhoan, form.nhapLai);

  if (dangDuyet && sanSang && form.bin !== null) {
    return (
      <Screen
        title="Kiểm lại trước khi lưu"
        hint={`Chuyển nhầm tài khoản thì không lấy lại được. Đọc lại ba dòng này một lượt.`}
        gap={space.lg}
        footer={
          <>
            <Button
              label="Đúng, lưu tài khoản này"
              disabled={busy}
              onPress={() =>
                onLuu({
                  bankBin: form.bin!,
                  accountNumber: soDaChuan,
                  accountName: tenDaChuan,
                })
              }
            />
            <Button label="Sửa lại" tone="quiet" onPress={() => setDangDuyet(false)} />
          </>
        }
      >
        <ScrollView contentContainerStyle={{ gap: space.md }}>
          <Card>
            <Text style={{ ...type.label, color: c.inkSoft }}>Ngân hàng</Text>
            <Text style={{ ...type.title, color: c.ink }}>
              {bankDisplayName(form.bin)}
            </Text>
          </Card>

          <Card>
            <Text style={{ ...type.label, color: c.inkSoft }}>Số tài khoản</Text>
            {/* Full, and grouped. This is the one screen whose entire job is
                letting somebody compare what they typed against the card or the
                banking app in their other hand. */}
            <Text style={{ ...type.amountSmall, color: c.ink }}>
              {nhomBon(soDaChuan)}
            </Text>
          </Card>

          <Card>
            <Text style={{ ...type.label, color: c.inkSoft }}>Tên chủ tài khoản</Text>
            <Text style={{ ...type.title, color: c.ink }}>{tenDaChuan}</Text>
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Đây là tên app ngân hàng của người chuyển sẽ hiện ra trước khi họ
              bấm gửi. Không khớp thì họ nên dừng lại và hỏi.
            </Text>
          </Card>

          <Card style={{ backgroundColor: c.accentSoft, borderColor: c.warn }}>
            <Text style={{ ...type.label, color: c.warn }}>
              App không kiểm tra được số tài khoản này có thật hay thuộc về ai.
              Không có nguồn nào để hỏi. Người chuyển tiền đối chiếu tên chủ tài
              khoản trong app ngân hàng của họ là bước kiểm duy nhất.
            </Text>
          </Card>
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen
      title="Tài khoản nhận tiền"
      hint={`Tiền của cả nhóm sẽ chuyển về tài khoản của ${nguoiNhan.name}.`}
      gap={space.lg}
      footer={
        <>
          {vanDe.length > 0 ? (
            <Text style={{ ...type.label, color: c.inkSoft }}>{vanDe[0]}</Text>
          ) : null}
          <Button
            label="Xem lại rồi lưu"
            disabled={!sanSang || busy}
            onPress={() => setDangDuyet(true)}
          />
          <Button label="Quay lại" tone="quiet" onPress={onBack} />
        </>
      }
    >
      <ScrollView
        contentContainerStyle={{ gap: space.md }}
        keyboardShouldPersistTaps="handled"
      >
        <Card>
          <Field
            label="Tìm ngân hàng"
            value={timNganHang}
            onChangeText={setTimNganHang}
            placeholder="Vietcombank"
          />
          {danhSach.length === 0 ? (
            <Text style={{ ...type.label, color: c.inkSoft }}>
              Không có ngân hàng nào tên như vậy trong danh bạ. Xoá bớt chữ để
              xem cả danh sách.
            </Text>
          ) : (
            <Choice
              label="Ngân hàng"
              options={danhSach.map((bank) => ({ id: bank.bin, label: bank.ten }))}
              value={form.bin}
              onChange={(bin) => set("bin", bin)}
            />
          )}
        </Card>

        <Card>
          <Field
            label="Số tài khoản"
            value={form.soTaiKhoan}
            onChangeText={(value) => set("soTaiKhoan", value)}
            placeholder={VI_DU_SO_TAI_KHOAN}
          />
          {/* Typed twice on purpose. The server cannot tell a transposed digit
              from a correct one, and neither can anybody else downstream. */}
          <Field
            label="Nhập lại số tài khoản"
            value={form.nhapLai}
            onChangeText={(value) => set("nhapLai", value)}
            placeholder={VI_DU_SO_TAI_KHOAN}
          />
          {lechSo ? (
            <Text style={{ ...type.label, color: c.warn }}>
              Hai ô chưa giống nhau. Xoá cả hai rồi gõ lại thì chắc hơn là sửa
              một ô.
            </Text>
          ) : null}
          {soHopLe && !lechSo && form.nhapLai.trim() !== "" ? (
            <Text style={{ ...type.label, color: c.split }}>Hai ô khớp nhau.</Text>
          ) : null}
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Gõ có khoảng trắng cũng được, app tự bỏ. Chỉ nhận chữ và số, tối đa
            19 ký tự.
          </Text>
        </Card>

        <Card>
          <Field
            label="Tên chủ tài khoản"
            value={form.tenChuTaiKhoan}
            onChangeText={(value) => set("tenChuTaiKhoan", value)}
            placeholder="NGUYEN VAN A"
          />
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Gõ đúng như ngân hàng hiển thị. Người chuyển tiền đối chiếu tên này
            trước khi bấm gửi, nên nó là bước kiểm duy nhất mà app có.
          </Text>
        </Card>

        <Card>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Chỉ {nguoiNhan.name} sửa được tài khoản này. Người khác trong nhóm
            chỉ thấy tên ngân hàng và bốn số cuối.
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
}

/** One line naming a saved destination, safe to show anywhere in the group. */
export function dongTomTat(bankBin: string, accountNumber: string): string {
  return `${bankDisplayName(bankBin)} ${maskAccount(accountNumber)}`;
}
