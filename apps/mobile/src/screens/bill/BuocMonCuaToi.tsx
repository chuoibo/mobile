/** The `mon-cua-toi` step: `MonCuaToi` with a bill behind it and a write in front.
 *
 * `MonCuaToi.tsx` is pure -- props in, callbacks out -- and stays that way.
 * This is the thin layer that gives it the four things it cannot own: which
 * dishes exist, which ones I have already claimed, whether a save is in
 * flight, and what to do when the save comes back. All the decisions are in
 * `mon-cua-toi.ts`, which is plain functions over plain values; what is left
 * here is `useState` and one `await`.
 *
 * Ticks are seeded from the server's bill on every mount, never carried across
 * from the previous visit. `POST /bills/{id}/my-items` takes the caller's
 * COMPLETE set, so a stale local list is not a smaller mistake than a wrong
 * one: saving it releases every dish missing from it.
 *
 * The parent gets the bill that came back, not the list that was sent. What
 * the server stored is the only thing that may move the matrix -- see
 * `apDungMonCuaToi` on why the matrix has to move at all.
 */
import React, { useState } from "react";
import { SafeAreaView } from "react-native";

import { nhanMonCuaToi } from "../../api";
import type { BillWire } from "../../bill";
import { usePalette } from "../../theme";
import { moTaLoi } from "../../ui/loi-tren-man";
import { MonCuaToi } from "./MonCuaToi";
import { monToiDaNhan, monTuBill } from "./mon-cua-toi";

export function BuocMonCuaToi({
  bill,
  toiId,
  contextId,
  tenNhom,
  onXong,
  onQuayLai,
}: {
  bill: BillWire;
  /** Whose dishes these are. The route charges the caller and has no field
   *  that could name anybody else, so this is both the actor and the subject. */
  toiId: string;
  contextId: string;
  tenNhom: string;
  /** Called with the bill the server returned, once it has been stored. */
  onXong: (bill: BillWire) => void;
  onQuayLai: () => void;
}) {
  const c = usePalette();
  const [daChon, setDaChon] = useState<string[]>(() => monToiDaNhan(bill, toiId));
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <MonCuaToi
        tenNhom={tenNhom}
        mon={monTuBill(bill)}
        daChon={daChon}
        dangLuu={dangLuu}
        loi={loi}
        onBat={(itemKey) =>
          setDaChon((cu) =>
            cu.includes(itemKey) ? cu.filter((k) => k !== itemKey) : [...cu, itemKey],
          )
        }
        onLuu={() => {
          if (dangLuu) return;
          setDangLuu(true);
          setLoi(null);
          // No attempt key, and that is a property of the route rather than an
          // omission. The body is the caller's COMPLETE set, so arriving twice
          // stores the same set twice -- unlike `POST /expenses`, where a
          // replay is a second expense in the ledger.
          nhanMonCuaToi(bill.id, daChon, toiId, contextId)
            .then(onXong)
            .catch((problem: unknown) => {
              // Stay on the screen with the ticks intact. Bouncing back to the
              // matrix on a failed write would leave a person believing the
              // claim landed, which is the one thing this screen must never
              // say when it did not.
              setLoi(moTaLoi(problem));
              setDangLuu(false);
            });
        }}
        onQuayLai={dangLuu ? () => {} : onQuayLai}
      />
    </SafeAreaView>
  );
}
