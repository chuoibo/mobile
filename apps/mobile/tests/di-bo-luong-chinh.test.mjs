/* Đường đi chính phải đi bộ được từ đầu tới cuối, và phải để lại file quét được.
 *
 * Vì sao file này tồn tại, nói thẳng:
 *
 * `tools/screen-snapshots.mjs` là thứ duy nhất mở được 8 màn của luồng chia
 * tiền ra thành HTML cho máy quét đọc. KHÔNG có test nào gọi nó. Nên khi #113
 * đổi ma trận chia tiền từ "gõ tên" sang "chọn người trong nhóm" -- một bản sửa
 * đúng, sửa một lỗi TIỀN thật (bug-125301) -- nút `aria-label="Thêm"` mà walk
 * dùng để lái biến mất, walk treo 15 giây ở đó, và 5 trong 7 màn lặng lẽ ngừng
 * được quét. 498 test vẫn xanh. Không ai biết, suốt từ #113 tới giờ.
 *
 * Đó đúng là kiểu hỏng repo này gặp nhiều nhất và ghi hẳn vào CLAUDE.md: rỗng
 * vì không đo được, chứ không phải rỗng vì sạch. Một màn CHƯA quét và một màn
 * quét SẠCH nhìn từ ngoài giống hệt nhau -- cả hai đều là không có finding nào.
 *
 * Giá phải trả: walk chạy hết 3,6 giây trên bundle đã dựng sẵn. `npm test` đã
 * bỏ ra hàng chục giây cho `expo export` ngay trước đó, nên đây là cái gác rẻ
 * nhất trong cả bộ so với thứ nó giữ.
 *
 * File này KHÔNG chứng minh: các màn đẹp, dễ hiểu, hay sạch lỗi thiết kế. Nó
 * chứng minh đúng một điều -- chúng CÓ THẬT và ĐÃ được viết ra để quét. Việc
 * chấm điểm là của `imp detect`, chạy trên chính những file này.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { STEPS, EXTRA } from "../tools/screen-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");
const WALK = path.join(MOBILE_ROOT, "tools", "screen-snapshots.mjs");

/* Thư mục riêng, ngoài repo. Không giẫm lên `.screen-snapshots/` mà người đang
 * sửa giao diện vừa dựng bằng tay, và không để lại rác trong cây làm việc. */
const OUT = fs.mkdtempSync(path.join(os.tmpdir(), "di-bo-luong-chinh-"));

let ket;
try {
  ket = {
    ok: true,
    out: execFileSync("node", [WALK, "--out", OUT], {
      cwd: MOBILE_ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 180000,
    }),
  };
} catch (err) {
  // Giữ lại nguyên văn để lời kêu nói ĐƯỢC hỏng ở đâu, chứ không chỉ "đỏ".
  ket = { ok: false, out: `${err.stdout ?? ""}\n${err.stderr ?? ""}` };
}

test("đi bộ hết luồng chia tiền, từ chụp bill tới trang khách", () => {
  assert.ok(
    ket.ok,
    `walk dừng giữa chừng. Đây là bản ghi của nó:\n${ket.out}`,
  );
});

test("mỗi màn của luồng để lại một file quét được", () => {
  // Danh sách suy ra từ chính tool, nên thêm một bước mới là nó tự được gác.
  for (const step of [...STEPS, ...EXTRA]) {
    const file = path.join(OUT, `${step}.html`);
    assert.ok(
      fs.existsSync(file),
      `màn "${step}" không được viết ra. Chưa quét và quét sạch trông giống hệt nhau, nên đây là đỏ.`,
    );
    // Một file vài trăm byte là vỏ trang, không phải một màn.
    assert.ok(
      fs.statSync(file).size > 5000,
      `màn "${step}" chỉ có ${fs.statSync(file).size} byte, quá nhỏ để là một màn đã render`,
    );
  }
});

test("màn kết quả thanh toán vẽ được mã VietQR thật, không phải panel từ chối", () => {
  // Cái kim chống "quét nhầm màn". Màn này render đẹp và sạch CẢ KHI mã hỏng:
  // `readVietQr` ném thì nó vẽ panel "Chưa hiện được mã". Một file như thế vẫn
  // đủ lớn, vẫn qua hai assertion trên, và vẫn là ảnh của một thất bại.
  const html = fs.readFileSync(path.join(OUT, "ket-qua-thanh-toan.html"), "utf8");
  assert.ok(
    !html.includes("Chưa hiện được mã"),
    "màn thanh toán đang hiện panel từ chối chứ không phải mã",
  );
  assert.match(
    html,
    /aria-label="Mã VietQR[^"]*"/,
    "không thấy mã VietQR nào được vẽ trên màn thanh toán",
  );
});

test("ma trận chia tiền có người trên đó, không phải màn rỗng", () => {
  // Chính cái mà #113 làm gãy: walk không thêm được ai thì màn vẫn render,
  // vẫn sạch, và vẫn là màn SAI -- một ma trận không có cột nào.
  const html = fs.readFileSync(path.join(OUT, "goi-y.html"), "utf8");
  assert.ok(
    !html.includes("Chưa chọn ai đã ăn bữa này"),
    "ma trận vẫn đang rỗng: không ai được đưa lên bill",
  );
  for (const ten of ["Minh", "Trang", "Hải"]) {
    assert.ok(html.includes(ten), `không thấy ${ten} trên ma trận`);
  }
});
