/** The wall on Cá nhân: write a sentence, pick who may read it, see your posts.
 *
 * Extension of the existing profile, not a new world. Lead tone is `accent`
 * (this is a person, not a settlement) and `ai` purple never appears: a post
 * is written by a person, not produced by a machine.
 *
 * The four audiences are four different groups of people, not four rungs of
 * a ladder. They render as a vertical radio list. No slider, no chip row
 * ordered narrow-to-wide, no lock icon that opens in steps.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { attemptFor, type Attempt } from "../../api";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Choice, Field } from "../../ui/Kit";
import { toggleState } from "../../ui/a11y";
import { CoLoi, DangTai, TrongRong } from "../../ui/TrangThai";
import { ngayNgan } from "./tai-chinh";
import {
  AUDIENCES,
  MAC_DINH_NGUOI_DOC,
  MUC_NGUOI_DOC,
  TuongError,
  coTheDang,
  guiBai,
  layTuong,
  type Audience,
  type Bai,
} from "./bai-dang";

export type TrangTuong =
  | { pha: "dang-tai" }
  | { pha: "xong"; bai: Bai[] }
  | { pha: "loi"; loi: string };

export type KhoiDauTuong = {
  moSoan?: boolean;
  body?: string;
  audience?: Audience;
  contextId?: string | null;
  trang?: TrangTuong;
};

const HIT = 44;

export function Tuong({
  nguoi,
  nhom = [],
  doc = layTuong,
  dang = guiBai,
  khoiDau,
}: {
  nguoi: { personId: string };
  nhom?: { id: string; name: string }[];
  doc?: typeof layTuong;
  dang?: typeof guiBai;
  /** Injected so first-paint tests can skip the mount fetch. */
  khoiDau?: KhoiDauTuong;
}) {
  const c = usePalette();
  const [trang, setTrang] = useState<TrangTuong>(khoiDau?.trang ?? { pha: "dang-tai" });
  const [moSoan, setMoSoan] = useState(khoiDau?.moSoan ?? false);
  const [body, setBody] = useState(khoiDau?.body ?? "");
  const [audience, setAudience] = useState<Audience>(khoiDau?.audience ?? MAC_DINH_NGUOI_DOC);
  const [contextId, setContextId] = useState<string | null>(khoiDau?.contextId ?? null);
  const [loiDang, setLoiDang] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState(false);
  const book = useRef<Record<string, Attempt>>({});

  const tai = useCallback(async () => {
    try {
      setTrang({ pha: "xong", bai: await doc(nguoi.personId) });
    } catch (error) {
      const message =
        error instanceof TuongError ? error.message : "Chưa đọc được tường.";
      setTrang({ pha: "loi", loi: message });
    }
  }, [doc, nguoi.personId]);

  useEffect(() => {
    if (khoiDau?.trang) return;
    void tai();
  }, [tai, khoiDau?.trang]);

  function chonMuc(muc: Audience) {
    setAudience(muc);
    if (muc !== "group") setContextId(null);
  }

  async function gui() {
    const form = { body, audience, contextId };
    if (!coTheDang(form) || dangGui) return;
    setDangGui(true);
    setLoiDang(null);
    try {
      const bai = await dang(
        nguoi.personId,
        form,
        attemptFor(book.current, `dang:${form.body}:${form.audience}:${form.contextId ?? ""}`),
      );
      setTrang((truoc) =>
        truoc.pha === "xong" ? { pha: "xong", bai: [bai, ...truoc.bai] } : { pha: "xong", bai: [bai] },
      );
      setBody("");
      setAudience(MAC_DINH_NGUOI_DOC);
      setContextId(null);
    } catch (error) {
      setLoiDang(error instanceof TuongError ? error.message : "Chưa đăng được bài.");
    } finally {
      setDangGui(false);
    }
  }

  const form = { body, audience, contextId };
  const moDang = coTheDang(form) && !dangGui;

  return (
    <View style={{ gap: space.md }}>
      <Card>
        <Text style={{ ...type.title, color: c.ink }}>Tường của bạn</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Chọn ai đọc được trước khi đăng. Bốn lựa chọn là bốn nhóm người khác nhau,
          không phải bốn nấc rộng dần.
        </Text>
        {moSoan ? (
          <View style={{ gap: space.sm }}>
            <Field
              label="Viết một câu"
              value={body}
              onChangeText={setBody}
              placeholder="Hôm nay đi đâu, ăn gì..."
              maxLength={5000}
              hint="Tối đa 5000 chữ. Bài do bạn viết, không phải máy sinh."
              onSubmitEditing={() => {
                if (moDang) void gui();
              }}
            />
            <View
              accessibilityRole="radiogroup"
              aria-label="Ai đọc được bài này"
              style={{ gap: space.xs }}
            >
              {AUDIENCES.map((muc) => {
                const on = muc === audience;
                const { nhan, giaiThich } = MUC_NGUOI_DOC[muc];
                return (
                  <Pressable
                    key={muc}
                    onPress={() => chonMuc(muc)}
                    {...toggleState("radio", on)}
                    aria-label={`${nhan}. ${giaiThich}`}
                    style={({ pressed }) => ({
                      minHeight: HIT,
                      borderWidth: 1,
                      borderRadius: radius.base,
                      paddingVertical: space.sm,
                      paddingHorizontal: space.md,
                      borderColor: on ? c.accent : c.lineStrong,
                      backgroundColor: on ? c.accentSoft : "transparent",
                      opacity: pressed ? 0.85 : 1,
                      justifyContent: "center",
                      gap: 2,
                    })}
                  >
                    <Text
                      style={{
                        ...type.body,
                        fontWeight: on ? "600" : "400",
                        color: c.ink,
                      }}
                    >
                      {nhan}
                    </Text>
                    <Text style={{ ...type.micro, color: c.inkSoft }}>{giaiThich}</Text>
                  </Pressable>
                );
              })}
            </View>
            {audience === "group" ? (
              nhom.length === 0 ? (
                <Text style={{ ...type.body, color: c.inkSoft }}>
                  Bạn chưa có nhóm nào để chọn. Tạo nhóm rồi quay lại đăng.
                </Text>
              ) : (
                <Choice
                  label="Nhóm nào được đọc"
                  options={nhom.map((n) => ({ id: n.id, label: n.name }))}
                  value={contextId}
                  onChange={setContextId}
                />
              )
            ) : null}
            {loiDang ? (
              <Text style={{ ...type.label, color: c.warn }} accessibilityRole="alert">
                {loiDang}
              </Text>
            ) : null}
            <Button label="Đăng" onPress={() => void gui()} disabled={!moDang} />
          </View>
        ) : (
          <Button label="Viết lên tường" onPress={() => setMoSoan(true)} tone="ghost" />
        )}
      </Card>

      {trang.pha === "dang-tai" ? <DangTai noiDung="Đang tải tường..." /> : null}

      {trang.pha === "loi" ? (
        <CoLoi
          tieuDe="Chưa đọc được tường"
          than={trang.loi}
          viecTiepTheo="Thử lại sau một chút. Chưa có bài nào bị mất."
          onThuLai={() => void tai()}
        />
      ) : null}

      {trang.pha === "xong" && trang.bai.length === 0 ? (
        <TrongRong
          tieuDe="Chưa có bài nào trên tường"
          than="Viết một câu, chọn ai đọc được, rồi đăng."
        />
      ) : null}

      {trang.pha === "xong"
        ? trang.bai.map((bai) => <TheBai key={bai.id} bai={bai} />)
        : null}
    </View>
  );
}

function TheBai({ bai }: { bai: Bai }) {
  const c = usePalette();
  const muc = MUC_NGUOI_DOC[bai.audience] ?? MUC_NGUOI_DOC.only_me;
  return (
    <Card>
      <View
        style={{
          alignSelf: "flex-start",
          borderRadius: radius.pill,
          backgroundColor: c.accentSoft,
          paddingVertical: 4,
          paddingHorizontal: space.sm,
        }}
      >
        <Text style={{ ...type.micro, fontWeight: "600", color: c.accent }}>{muc.nhan}</Text>
      </View>
      <Text style={{ ...type.body, color: c.ink }}>{bai.body}</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>{ngayNgan(bai.created_at)}</Text>
    </Card>
  );
}
