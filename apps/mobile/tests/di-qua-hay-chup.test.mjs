/* Mỗi chặng cái walk dừng lại đều phải: hoặc được chụp, hoặc được khai lý do.
 *
 * `MoDau` là màn app mở ra đầu tiên, là chặng "mở app → đăng nhập" của đường
 * hero, và nó chưa từng một lần đi qua detector. Không phải vì ai đó quyết
 * định bỏ nó -- mà vì `drive()` bấm "Bỏ qua" ngay dòng đầu rồi đi tiếp, và
 * không có chỗ nào bắt buộc một chặng phải là "đã chụp" hay "cố tình bỏ".
 * File đầu tiên walk ghi ra là cái viewfinder, nên báo cáo đọc thành "đã quét
 * toàn bộ luồng" trong khi màn mở đầu chưa ai nhìn.
 *
 * Cổng tab (`quet-du-tab.test.mjs`) không đỡ được ca này: nó đối chiếu với
 * `tabs.ts`, mà `MoDau` không phải tab. Màn thiếu và màn sạch cho ra cùng một
 * dấu xanh, và đây đúng là màn thiếu.
 *
 * Nên cổng này đọc chính các phép gán `step = "..."` trong `drive()` và đòi
 * mỗi cái phải nằm trong `STEPS`, `EXTRA`, hoặc `PASS_THROUGH`. Thêm một chặng
 * mới mà không quyết định gì thì đỏ ở đây.
 *
 * Cái này CHỨNG MINH: danh sách chụp phủ hết những chặng walk dừng lại, và
 * mọi ca bỏ qua đều có người ký tên vào.
 * KHÔNG chứng minh: rằng walk đã chạy, chạy trên bundle hiện tại, hay detector
 * tìm ra gì. Xem ADR-0010 -- digest không phải bằng chứng.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { STEPS, EXTRA, PASS_THROUGH } from "../tools/screen-snapshots.mjs";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = join(MOBILE_ROOT, "tools/screen-snapshots.mjs");

/**
 * Các chặng, đọc thẳng từ thân `drive()`.
 *
 * Đọc dạng văn bản chứ không chạy hàm: `drive()` cần Chromium, một bundle đã
 * dựng và một server tĩnh. Cổng này phải chạy được trong `npm test` mà không
 * có gì trong ba thứ đó, nếu không nó sẽ bị bỏ qua đúng lúc cần nhất.
 *
 * Cắt đúng thân `drive` chứ không quét cả file: `STEPS` ở đầu file cũng chứa
 * các chuỗi y hệt, quét cả file thì mọi chặng tự khớp chính nó và mọi khẳng
 * định bên dưới thành đúng một cách rỗng tuếch.
 */
function changTrongWalk() {
  const src = readFileSync(TOOL, "utf8");
  const than = /async function drive\([^)]*\)\s*\{(.*?)\n\}/s.exec(src);
  // Regex không khớp gì sẽ làm mọi assert bên dưới đúng một cách vô nghĩa --
  // đúng kiểu hỏng mà file này sinh ra để bắt. Nên hình dạng của khối cũng là
  // một khẳng định.
  assert.ok(than, `không tìm thấy thân drive() trong ${TOOL}`);

  const rows = [...than[1].matchAll(/\bstep = "([^"]+)"/g)].map((m) => m[1]);
  assert.ok(rows.length > 0, "drive() không có chặng nào");
  return [...new Set(rows)];
}

test("mọi chặng walk dừng lại đều được chụp hoặc được khai là cố tình bỏ", () => {
  const chang = changTrongWalk();
  const daBiet = new Set([...STEPS, ...EXTRA, ...Object.keys(PASS_THROUGH)]);

  // Gọi tên từng cái chứ không trả về hiệu hai tập hợp: khi đỏ, dòng chữ phải
  // nói màn nào chưa ai nhìn, không phải "hai danh sách khác nhau".
  const chuaQuyet = chang.filter((s) => !daBiet.has(s));
  assert.deepEqual(
    chuaQuyet,
    [],
    `chặng dừng lại mà chưa chụp cũng chưa khai lý do: ${chuaQuyet.join(", ")}`,
  );
});

test("mo-dau nằm trong danh sách chụp", () => {
  // Ghim riêng, không để nó tan vào phép kiểm tổng quát ở trên. Chuyển
  // `mo-dau` từ `STEPS` sang `PASS_THROUGH` kèm một câu lý do nghe xuôi tai
  // sẽ làm cổng kia xanh trở lại, và màn mở đầu lại rơi ra khỏi tầm quét đúng
  // theo cách nó đã rơi lần đầu.
  assert.ok(
    STEPS.includes("mo-dau"),
    "mo-dau phải được CHỤP, không phải được khai lý do: đây là màn app mở ra đầu tiên",
  );
});

test("mọi lý do bỏ qua đều có chữ, và không trùng với màn đã chụp", () => {
  const daChup = new Set([...STEPS, ...EXTRA]);
  for (const [chang, lyDo] of Object.entries(PASS_THROUGH)) {
    // Chuỗi rỗng hoặc một dấu cách vẫn "có khai" theo nghĩa hẹp nhất, nên đòi
    // đủ dài để buộc phải là một câu thật.
    assert.ok(
      typeof lyDo === "string" && lyDo.trim().length >= 20,
      `${chang}: lý do bỏ qua phải là một câu thật, đang là ${JSON.stringify(lyDo)}`,
    );
    // Vừa chụp vừa khai bỏ qua là mâu thuẫn, và cái sai nằm ở chỗ nó đọc như
    // đã có chủ đích ở cả hai phía.
    assert.ok(
      !daChup.has(chang),
      `${chang} vừa nằm trong danh sách chụp vừa nằm trong PASS_THROUGH`,
    );
  }
});
