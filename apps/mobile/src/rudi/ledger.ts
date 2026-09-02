/**
 * Talk to the live API from RuDi screens without pretending the fixture is a ledger.
 *
 * `/healthz` is the probe: it is defined not to touch the database. A failure
 * is shown as a draft. A success is "the process is up", not "this number is
 * from the allocator".
 */
import { ApiError, BASE_URL, thongDiepNguoiDoc } from "../api";

export type LedgerProbe = {
  connected: boolean;
  message: string;
  address: string;
};

export async function probeLedger(): Promise<LedgerProbe> {
  const address = BASE_URL;
  try {
    const response = await fetch(address + "/healthz");
    if (!response.ok) {
      return {
        connected: false,
        address,
        message: thongDiepNguoiDoc(response.status, null) + ` (${address})`,
      };
    }
    return {
      connected: true,
      address,
      message: `Máy chủ đang chạy tại ${address}. Số trên màn này vẫn là nháp cho đến khi xác nhận khoản chi vào sổ.`,
    };
  } catch (error) {
    const fallback =
      error instanceof ApiError
        ? error.message
        : `Không nối được ${address}. Đang xem nháp trên máy — chưa phải sổ cái.`;
    return { connected: false, address, message: fallback };
  }
}
