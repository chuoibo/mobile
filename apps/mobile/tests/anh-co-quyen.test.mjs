/* Ảnh trên đường có kiểm quyền phải THẬT SỰ lên được màn.
 *
 * Vì sao có file này, nói thẳng:
 *
 * rd-fe-25 nối `<Anh uri="/people/{id}/avatar">` và mọi cổng đều xanh. Nhưng
 * mọi đường ảnh của sản phẩm này đều bị kiểm quyền bằng header, và một `<img>`
 * KHÔNG gửi được header. Đo trên máy chủ thật:
 *
 *     GET /people/{id}/avatar          không header -> 401 authentication_required
 *     GET /people/{id}/avatar          có header    -> 200 image/jpeg
 *     GET /contexts/{cid}/photos/{pid} không header -> 401
 *
 * Nên khung ảnh hỏi, bị từ chối, `Anh` bắt `onError` rồi vẽ hình thay thế --
 * mà hình thay thế của ảnh đại diện là chữ cái tên người, đúng thứ một người
 * CHƯA có ảnh cũng nhìn thấy. Tải lên trả 201, ảnh không bao giờ hiện, và
 * không màn nào, không test nào nói gì cả. Người dùng đổi ảnh, mở lại app, vẫn
 * thấy chữ cái cũ.
 *
 * `tab-snapshots.mjs` không thể bắt được, và lý do đáng chép lại vì nó là hình
 * dạng chung của phần lớn cổng mù trong repo này: nó TỰ trả lời request ảnh
 * bằng `req.respond({status: 200})` vô điều kiện. Bytes về được là vì harness
 * đặt sẵn ở đó, không phải vì app được phép lấy. Một màn không bao giờ tải nổi
 * ảnh trong sản phẩm thật vẫn qua bài quét đó mọi lần.
 *
 * `tools/anh-co-quyen-harness.mjs` đổi đúng một thứ: bộ chặn cưỡng chế cùng
 * luật máy chủ cưỡng chế -- muốn bytes thì phải có `x-actor-id`. Không có thì
 * 401, y như thật.
 *
 * File này KHÔNG chứng minh: ảnh đúng là của người đó, người ngoài nhóm bị
 * chặn, hay EXIF đã bị lột. Đó là việc của máy chủ và của test rò rỉ. Nó
 * chứng minh đúng một điều, thứ đã sai suốt #222: bytes đi được tới màn.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");
const HARNESS = path.join(MOBILE_ROOT, "tools", "anh-co-quyen-harness.mjs");

let ket;
try {
  ket = {
    ok: true,
    out: execFileSync("node", [HARNESS], {
      cwd: MOBILE_ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 240000,
    }),
  };
} catch (err) {
  // Giữ nguyên văn: cần biết hỏng Ở ĐÂU, không chỉ "đỏ".
  ket = { ok: false, out: `${err.stdout ?? ""}\n${err.stderr ?? ""}` };
}

/** Báo cáo của harness, hoặc null nếu nó chết trước khi in được gì. */
function docBaoCao() {
  const dau = ket.out.indexOf("{");
  const cuoi = ket.out.lastIndexOf("}");
  if (dau < 0 || cuoi < dau) return null;
  try {
    return JSON.parse(ket.out.slice(dau, cuoi + 1));
  } catch {
    return null;
  }
}

test("ảnh đại diện và tường ảnh nhóm lên được màn khi máy chủ đòi header", () => {
  assert.ok(ket.ok, `harness đỏ:\n${ket.out}`);
});

test("mỗi màn có ảnh phải có ít nhất một <img> mang pixel thật", () => {
  const bao = docBaoCao();
  assert.ok(bao, `không đọc được báo cáo JSON của harness:\n${ket.out}`);
  for (const man of bao.ketQua) {
    assert.equal(
      man.loiMan,
      null,
      `${man.ten}: màn chưa tải xong dữ liệu nên con số ảnh không có nghĩa -- ${man.loiMan}`,
    );
    assert.ok(
      man.anhThat > 0,
      `${man.ten}: 0 ảnh có pixel thật trên ${man.soImg} thẻ <img>. ` +
        `Gọi tới đường ảnh: ${JSON.stringify(man.goi)}`,
    );
  }
});

test("mọi lần xin bytes ảnh đều mang X-Actor-ID, nên không lần nào bị 401", () => {
  const bao = docBaoCao();
  assert.ok(bao, `không đọc được báo cáo JSON của harness:\n${ket.out}`);
  for (const man of bao.ketQua) {
    const xinBytes = man.goi.filter((g) => g.method === "GET");
    assert.ok(
      xinBytes.length > 0,
      `${man.ten}: app không hề hỏi đường ảnh nào. Đường đọc chưa được nối.`,
    );
    const thieuHeader = xinBytes.filter((g) => !g.coActor);
    assert.deepEqual(
      thieuHeader,
      [],
      `${man.ten}: ${thieuHeader.length} lần xin bytes KHÔNG kèm X-Actor-ID nên bị 401. ` +
        `Một <img> không gửi được header -- bytes phải được fetch kèm header rồi mới đưa cho khung ảnh.`,
    );
  }
});
