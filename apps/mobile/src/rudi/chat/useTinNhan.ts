/**
 * One group's conversation, kept fresh while the screen is in front.
 *
 * - First page (newest 50) on mount; older pages on demand (`napCuHon`).
 * - Forward poll every 4 s while focused and the app is active, and once
 *   right after a send, using the newest cursor held. The server echoes the
 *   cursor on an empty page (BE6), so a quiet group polls in place instead of
 *   re-reading the top.
 * - Read mark: the newest message id goes to `PUT /read-mark` whenever the
 *   held list changes while focused, so the conversation list's unread counts
 *   fall as the person reads.
 *
 * State is a plain object rather than a reducer: five fields, one owner.
 */
import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";

import { ApiError, newAttempt, thongDiepNguoiDoc } from "../../api";
import {
  boPhanUng,
  cursorCuNhat,
  cursorMoiNhat,
  danhDauDaDoc,
  docTrangTin,
  gopTin,
  guiTin,
  thayPhanUng,
  themPhanUng,
  type LoaiPhanUng,
  type Tin,
  type TinDaGui,
} from "./tin-song";

export const NHIP_POLL_MS = 4000;

export type TrangThaiChat = {
  tin: Tin[];
  dangNap: boolean;
  dangNapCu: boolean;
  hetTinCu: boolean;
  loi: string | null;
};

function loiRaChu(error: unknown): string {
  return error instanceof ApiError ? error.message : thongDiepNguoiDoc(0, null);
}

export function useTinNhan(contextId: string, personId: string) {
  const [trang, setTrang] = useState<TrangThaiChat>({
    tin: [],
    dangNap: true,
    dangNapCu: false,
    hetTinCu: false,
    loi: null,
  });
  const tinRef = useRef<Tin[]>([]);
  const dangFocus = useRef(false);
  const daDanhDau = useRef<string | null>(null);

  const dat = useCallback((tin: Tin[], phan: Partial<TrangThaiChat> = {}) => {
    tinRef.current = tin;
    setTrang((cu) => ({ ...cu, tin, ...phan }));
  }, []);

  const napDau = useCallback(async () => {
    try {
      const page = await docTrangTin(contextId, personId);
      dat(gopTin([], page.messages), { dangNap: false, hetTinCu: !page.has_more, loi: null });
    } catch (error) {
      setTrang((cu) => ({ ...cu, dangNap: false, loi: loiRaChu(error) }));
    }
  }, [contextId, personId, dat]);

  const napMoi = useCallback(async () => {
    const after = cursorMoiNhat(tinRef.current);
    try {
      const page = after === null
        ? await docTrangTin(contextId, personId)
        : await docTrangTin(contextId, personId, { after });
      if (page.messages.length > 0) dat(gopTin(tinRef.current, page.messages), { loi: null });
    } catch {
      // A missed poll is not an error the person needs to read; the next tick
      // tries again and a send surfaces its own failure.
    }
  }, [contextId, personId, dat]);

  const napCuHon = useCallback(async () => {
    const before = cursorCuNhat(tinRef.current);
    if (before === null || trang.hetTinCu || trang.dangNapCu) return;
    setTrang((cu) => ({ ...cu, dangNapCu: true }));
    try {
      const page = await docTrangTin(contextId, personId, { before });
      dat(gopTin(tinRef.current, page.messages), { dangNapCu: false, hetTinCu: !page.has_more });
    } catch (error) {
      setTrang((cu) => ({ ...cu, dangNapCu: false, loi: loiRaChu(error) }));
    }
  }, [contextId, personId, dat, trang.hetTinCu, trang.dangNapCu]);

  useEffect(() => {
    void napDau();
  }, [napDau]);

  // Poll while focused and the app is in the foreground.
  useFocusEffect(
    useCallback(() => {
      dangFocus.current = true;
      let hen: ReturnType<typeof setInterval> | null = null;
      const bat = () => {
        if (hen === null) hen = setInterval(() => void napMoi(), NHIP_POLL_MS);
      };
      const tat = () => {
        if (hen !== null) clearInterval(hen);
        hen = null;
      };
      if (AppState.currentState === "active") bat();
      const sub = AppState.addEventListener("change", (s) => (s === "active" ? bat() : tat()));
      void napMoi();
      return () => {
        dangFocus.current = false;
        tat();
        sub.remove();
      };
    }, [napMoi]),
  );

  // Read mark follows the newest message the person has in front of them.
  useEffect(() => {
    const moiNhat = trang.tin[0]?.id;
    if (!moiNhat || !dangFocus.current || daDanhDau.current === moiNhat) return;
    daDanhDau.current = moiNhat;
    void danhDauDaDoc(contextId, personId, moiNhat).catch(() => undefined);
  }, [trang.tin, contextId, personId]);

  const gui = useCallback(
    async (body: string): Promise<TinDaGui> => {
      const daGui = await guiTin(contextId, personId, body, newAttempt());
      const them: Tin[] = [daGui];
      if (daGui.companion?.message) them.push(daGui.companion.message);
      if (daGui.expense_card) them.push(daGui.expense_card);
      dat(gopTin(tinRef.current, them), { loi: null });
      // A poll card or anything else the server wrote arrives on the next poll.
      void napMoi();
      return daGui;
    },
    [contextId, personId, dat, napMoi],
  );

  const doiPhanUng = useCallback(
    async (messageId: string, kind: LoaiPhanUng, dangCoCuaToi: boolean) => {
      const ket = dangCoCuaToi
        ? await boPhanUng(contextId, messageId, personId, kind)
        : await themPhanUng(contextId, messageId, personId, kind);
      dat(thayPhanUng(tinRef.current, messageId, ket.reactions));
    },
    [contextId, personId, dat],
  );

  return { ...trang, napCuHon, napMoi, gui, doiPhanUng, taiLai: napDau };
}
