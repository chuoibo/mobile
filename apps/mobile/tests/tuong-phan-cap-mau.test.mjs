/* Chữ và nền phải đủ tương phản, ở CẢ hai bảng màu, trên mọi màn.
 *
 * Vì sao có file này: màn `thanh-tich` đã ship một con chip "Level N" tô
 * `c.aiInk` trên `c.aiSoft`. Hai token đều có thật, đều viết đúng chính tả, và
 * cặp đó là #ffffff trên #f5f1ff — 1.11:1, trong khi AA đòi 4.5:1. Chữ có mặt
 * trên màn và không đọc được. Bảng tối cũng 1.10:1, nên không phải lỡ tay một
 * bảng.
 *
 * Cả bộ test cũ không thấy được nó. `renderToStaticMarkup` chỉ phát ra tên
 * class chứ không mang stylesheet, nên mọi ca render hiện có đang tính tương
 * phản với hư không — chính `dong-binh-chon-the.test.mjs` viết điều đó trong
 * phần đầu của nó. Thứ duy nhất bắt được là `imp detect` chạy live trên trang
 * đã dựng, cần Chrome + bundle + khoảng bốn phút. Đó là một lượt quét tuần tốt
 * và một cái cổng tồi.
 *
 * CHỨNG MINH: mọi cặp (màu chữ, màu nền) viết bằng `style={{...}}` trong
 * `src/**.tsx` đều đạt ngưỡng WCAG AA, ở cả bảng sáng lẫn bảng tối.
 *
 * KHÔNG CHỨNG MINH: màu đi qua prop / biến / hàm (bộ đọc không giải được, và
 * nó ĐẾM những chỗ đó ra thay vì lặng lẽ bỏ qua), độ mờ, gradient, ảnh nằm sau
 * chữ, chữ có bị che không, hay phần tử có nằm trong khung nhìn không. Một cặp
 * được duyệt là một cặp có hai token đủ xa nhau, không phải lời hứa rằng chữ
 * đọc được.
 *
 * Chạy từ apps/mobile:
 *     node --test tests/tuong-phan-cap-mau.test.mjs
 */
import assert from "node:assert/strict";
import test, { describe } from "node:test";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { GOC, nguong, quetFile, timTsx, tuongPhan } from "../tools/cap-mau-tinh.mjs";

/** Ghi một mẩu .tsx ra đĩa rồi quét nó. */
function quetMau(nguon) {
  const d = mkdtempSync(join(tmpdir(), "cap-mau-"));
  const f = join(d, "Mau.tsx");
  writeFileSync(f, nguon, "utf8");
  try {
    return quetFile(f);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
}

describe("phép đo tự chứng minh nó đang đo", () => {
  /* Một con số 0 chỉ có nghĩa khi cùng bộ đọc đó ra khác 0 trên một mẩu cố ý
   * hỏng. Không có ca này thì "0 cặp hỏng" và "bộ đọc không parse được gì" là
   * hai thứ trông giống hệt nhau. */
  test("ĐỐI CHỨNG DƯƠNG: cặp cố ý hỏng phải bị bắt, ở cả hai bảng màu", () => {
    const { loi } = quetMau(`
      export function Mau() {
        return (
          <View style={{ backgroundColor: c.aiSoft }}>
            <Text style={{ ...type.label, color: c.aiInk }}>Level 3</Text>
          </View>
        );
      }
    `);
    assert.equal(loi.length, 2, "phải bắt cả bảng sáng lẫn bảng tối");
    assert.deepEqual(
      loi.map((l) => l.chuDe).sort(),
      ["sang", "toi"],
      "thiếu một bảng nghĩa là cổng chỉ gác được nửa sản phẩm",
    );
    for (const l of loi) {
      assert.equal(l.chu, "aiInk");
      assert.equal(l.nen, "aiSoft");
      assert.ok(l.ty < 1.5, `tỉ lệ đo được phải rất thấp, nhận ${l.ty}`);
    }
  });

  test("ĐỐI CHỨNG ÂM: cặp đúng thì im lặng", () => {
    const { loi, soCap } = quetMau(`
      export function Mau() {
        return (
          <View style={{ backgroundColor: c.aiSoft }}>
            <Text style={{ ...type.label, color: c.ai }}>Level 3</Text>
          </View>
        );
      }
    `);
    assert.equal(loi.length, 0);
    assert.ok(soCap > 0, "im lặng vì không đọc được gì thì không phải là đạt");
  });
});

describe("hai hình dạng ĐÚNG mà bản ngây thơ đã kết tội nhầm", () => {
  /* Bản đầu tiên của bộ đọc này báo 10 cặp hỏng. 8 trong số đó là oan, và cả 8
   * thuộc đúng hai hình dạng dưới đây. Giữ chúng lại làm ca test vì một cổng
   * kêu oan là một cổng sẽ bị tắt. */

  test("ternary tương quan: cùng một điều kiện gác cả nền lẫn chữ", () => {
    // `mo` bật thì trắng trên accent; `mo` tắt thì mực nhạt trên nền thừa kế.
    // Nhân chéo hai nhánh ra "accentInk trên card" — một trạng thái không tồn tại.
    const { loi } = quetMau(`
      export function Mau() {
        return (
          <View style={{ backgroundColor: c.card }}>
            <View style={{ backgroundColor: mo ? c.accent : "transparent" }}>
              <Text style={{ ...type.micro, color: mo ? c.accentInk : c.inkFaint }}>3</Text>
            </View>
          </View>
        );
      }
    `);
    assert.deepEqual(loi, [], "cặp tương quan bị kết tội oan");
  });

  test("dấu tích chỉ được vẽ khi ô đã tô: {chon ? <Text/> : null}", () => {
    // Hình dạng của MonCuaToi, BinhChon và MoBinhChon. Màu chữ ở đây là vô điều
    // kiện TẠI CHỖ NÓ ĐỨNG, nên nếu không mang điều kiện render xuống thì nó
    // trèo qua cái ô đã tô lên tới thẻ và thành "trắng trên trắng".
    const { loi } = quetMau(`
      export function Mau() {
        return (
          <View style={{ backgroundColor: c.card }}>
            <View style={{ backgroundColor: chon ? c.split : "transparent" }}>
              {chon ? (
                <Text style={{ ...type.micro, color: c.splitInk, fontWeight: "700" }}>✓</Text>
              ) : null}
            </View>
          </View>
        );
      }
    `);
    assert.deepEqual(loi, [], "điều kiện render chưa được mang xuống cây con");
  });

  test("nhưng bỏ điều kiện render đi thì đúng là lỗi thật", () => {
    // Đối chứng cho ca ngay trên: nếu dấu tích được vẽ vô điều kiện thì nó THẬT
    // SỰ có thể nằm trên nền trong suốt, và lúc đó phải đỏ. Nếu ca này cũng
    // xanh thì ca trên xanh vì bộ đọc mù, không phải vì nó hiểu.
    const { loi } = quetMau(`
      export function Mau() {
        return (
          <View style={{ backgroundColor: c.card }}>
            <View style={{ backgroundColor: "transparent" }}>
              <Text style={{ ...type.micro, color: c.splitInk, fontWeight: "700" }}>✓</Text>
            </View>
          </View>
        );
      }
    `);
    assert.ok(loi.length > 0, "splitInk trên card phải là lỗi");
  });
});

describe("ngưỡng WCAG", () => {
  test("chữ to được nới xuống 3:1, chữ thường giữ 4.5:1", () => {
    assert.equal(nguong({ size: 12, weight: "600" }), 4.5);
    assert.equal(nguong({ size: 28, weight: "700" }), 3);
    assert.equal(nguong({ size: 20, weight: "700" }), 3, "20px đậm đã qua mốc 18.66");
    assert.equal(nguong({ size: 16, weight: "700" }), 4.5, "16px đậm vẫn dưới mốc 18.66");
    assert.equal(nguong({ size: 20, weight: "400" }), 4.5, "to nhưng không đậm thì chưa đủ");
    assert.equal(nguong(null), 4.5, "không biết cỡ chữ thì phải giữ mốc chặt");
  });

  test("phép tính tương phản khớp mốc đã biết", () => {
    assert.equal(Number(tuongPhan("#ffffff", "#000000").toFixed(2)), 21);
    assert.equal(Number(tuongPhan("#ffffff", "#ffffff").toFixed(2)), 1);
  });
});

describe("cổng: toàn bộ màn", () => {
  const files = timTsx(resolve(GOC, "src"));
  const ket = files.map((f) => quetFile(f));
  const loi = ket.flatMap((k) => k.loi);
  const soCap = ket.reduce((t, k) => t + k.soCap, 0);

  test("bộ đọc thật sự đọc được cây này", () => {
    // Sàn coverage. Nếu ai đó đổi cách viết style và bộ đọc mù đi, số cặp tụt
    // về 0 và cổng sẽ báo xanh mãi mãi. Ca này biến im lặng đó thành đỏ.
    assert.ok(files.length > 40, `chỉ thấy ${files.length} file .tsx`);
    assert.ok(soCap > 300, `chỉ đọc được ${soCap} cặp màu, cổng đang mù`);
  });

  test("không màn nào có cặp chữ/nền dưới ngưỡng AA", () => {
    const bay = loi.map(
      (l) => `${l.file}:${l.dong} [${l.chuDe}] ${l.chu}(${l.mauChu}) trên ${l.nen}(${l.mauNen}) = ${l.ty}:1 < ${l.can}:1`,
    );
    assert.deepEqual(bay, [], `\n${bay.join("\n")}\n`);
  });
});

describe("neo hồi quy: chip Level của màn thành tích", () => {
  test("Level chip không dùng aiInk trên aiSoft", () => {
    const f = resolve(GOC, "src/rudi/screens/ky-niem/AchievementsLive.tsx");
    const { loi } = quetFile(f);
    assert.deepEqual(loi, [], "chip Level lại rơi về mực trắng trên nền nhạt");
  });
});
