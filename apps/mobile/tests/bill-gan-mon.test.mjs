/* Bill được LƯU LẠI, và màn nói đúng sự thật về chỗ các ô tích đang nằm.
 *
 * Trước lượt này ma trận gán món chạy hoàn toàn trong state của React: người
 * dùng tích ai ăn món gì, `POST /expenses` chia tiền, và bản thân ma trận
 * không được ghi ở đâu cả. Đếm trong bundle: `/bills` 0 lần, `assignments`
 * 0 lần, `/balances` 0 lần. Đóng app là mất, và không ai mở lại được một cái
 * bill để xem nhóm đã chốt gì.
 *
 * File này gác phần ánh xạ -- thứ quyết định đúng/sai của tiền trước khi nó
 * ra khỏi máy -- chứ KHÔNG chứng minh:
 *
 *   - rằng máy chủ chấp nhận những body này. Không có request nào ở đây.
 *     `tests/postgres` và `services/api/tests` là chỗ trả lời câu đó.
 *   - rằng màn hình vẽ ra đẹp hay đọc được. Đó là việc của detector trên DOM
 *     sống (`tools/quet-man-sau-tap.mjs`), không phải của assert văn bản.
 *   - rằng allocator chia đúng. Không có phép chia nào trong file này, và đó
 *     là chủ ý: một hiện thực thứ hai của phép chia là cách chắc chắn nhất để
 *     hai màn hiện hai con số cho cùng một bữa ăn.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  assignmentFromBill,
  assignmentsBody,
  billCreateBody,
  moTaTrangThaiGan,
  nguyenDong,
  soDuFromWire,
} from "../dist-test/bill.js";
import { blockingProblem, chuaAiNhanVnd } from "../dist-test/assignment.js";

const A = "aaaa1111-bbbb-4ccc-8ddd-eeeeffff1111";
const B = "aaaa2222-bbbb-4ccc-8ddd-eeeeffff2222";
const NHOM = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";

function doc(lines, printedTotalVnd = null) {
  return { lines, printedTotalVnd, needsReview: false, warnings: [] };
}

function mon(id, name, lineTotalVnd, quantity = 1) {
  return { id, name, quantity, lineTotalVnd, read: null };
}

/* ------------------------------------------------------- số nguyên đồng --- */

test("nguyenDong ném khi gặp số lẻ, không làm tròn", () => {
  // Làm tròn ở đây là sản phẩm tự bịa ra một con số không hoá đơn nào in và
  // không ai đồng ý. Luật 1 cấm float ở cả giá trị trung gian, nên chỗ đúng để
  // chết là biên -- nơi còn biết tên trường.
  assert.throws(() => nguyenDong(12000.5, "giá"), /giá.*nguyên đồng/);
  assert.equal(nguyenDong(12000, "giá"), 12000);
});

test("một dòng giá lẻ làm cả body chết, thay vì lặng lẽ đi ra mạng", () => {
  const reading = doc([mon("mon-0", "Phở", 45000.5)]);
  assert.throws(() => billCreateBody(reading, NHOM, {}), /Phở/);
});

/* ------------------------------------------------------------ tạo bill --- */

test("item_key là id của dòng, không phải tên món", () => {
  // Hai món trùng tên là chuyện thường trên thực đơn. Lấy tên làm khoá thì hai
  // hàng gộp làm một và tiền của người này đổ sang người kia.
  const reading = doc([mon("mon-0", "Trà đá", 8000), mon("mon-1", "Trà đá", 8000)]);
  const body = billCreateBody(reading, NHOM, { "mon-0": [A], "mon-1": [B] });
  assert.deepEqual(
    body.items.map((item) => item.item_key),
    ["mon-0", "mon-1"],
  );
  assert.deepEqual(body.items[0].suggested_participant_ids, [A]);
  assert.deepEqual(body.items[1].suggested_participant_ids, [B]);
});

test("items_total_vnd là tổng các dòng, cộng bằng số nguyên", () => {
  const reading = doc([mon("mon-0", "Lẩu", 450000), mon("mon-1", "Trà đá", 8000)]);
  const body = billCreateBody(reading, NHOM, {});
  assert.equal(body.items_total_vnd, 458000);
  assert.ok(Number.isInteger(body.items_total_vnd));
});

test("printed_total_vnd giữ nguyên null, không bị điền bằng tổng các dòng", () => {
  // Tổng in trên giấy là phép kiểm ĐỘC LẬP với số học của mình. Điền nó bằng
  // tổng các dòng là làm nó hết khả năng bất đồng, mà khả năng bất đồng mới là
  // lý do nó có mặt.
  const body = billCreateBody(doc([mon("mon-0", "Phở", 45000)]), NHOM, {});
  assert.equal(body.printed_total_vnd, null);
});

test("confidence gửi 0 vì route đọc bill cố ý không trả về nó", () => {
  // ADR-0009 quyết định 4 từ chối trả confidence cho client: rd-qa-03 đo được
  // con số ấy bám vào độ rõ của bản in chứ không phải vào chuyện tiền có đúng
  // không. Bịa một con số mình không có là bịa bằng chứng.
  const body = billCreateBody(doc([mon("mon-0", "Phở", 45000)]), NHOM, {});
  assert.equal(body.confidence, 0);
});

/* ---------------------------------------------------------- gán và đọc --- */

test("assignmentsBody phát đủ mọi dòng, kể cả dòng chưa ai nhận", () => {
  // Bỏ dòng trống ra khỏi body thì máy chủ không có cách nào biết là người
  // dùng đã BỎ một người khỏi món đó, hay dòng ấy chưa từng được nhắc tới.
  const reading = doc([mon("mon-0", "Lẩu", 450000), mon("mon-1", "Trà đá", 8000)]);
  const body = assignmentsBody(reading, { "mon-0": [A, B] });
  assert.equal(body.assignments.length, 2);
  assert.deepEqual(body.assignments[1], { item_key: "mon-1", participant_ids: [] });
});

test("assignmentFromBill khớp theo item_key chứ không theo thứ tự mảng", () => {
  // Máy chủ có trả `position`, nhưng dựa vào thứ tự mảng để ghép hàng với chủ
  // của nó là cách món của người này bị tính cho người kia.
  const bill = {
    suggested_item_keys: [],
    items: [
      { item_key: "mon-1", position: 1, shares: [{ participant_id: B }] },
      { item_key: "mon-0", position: 0, shares: [{ participant_id: A }] },
    ],
  };
  assert.deepEqual(assignmentFromBill(bill), { "mon-1": [B], "mon-0": [A] });
});

/* ------------------------------------------------- còn thiếu bao nhiêu --- */

test("câu chặn nói ra SỐ TIỀN chưa ai nhận, không chỉ đếm dòng", () => {
  // "2 món chưa ai nhận" là sự thật về hàng. Cái người dùng đang cân là bao
  // nhiêu tiền chưa có người đứng sau: trà đá 8.000đ và lẩu 450.000đ chưa ai
  // nhận là hai tình huống hoàn toàn khác nhau.
  const reading = doc([mon("mon-0", "Lẩu", 450000), mon("mon-1", "Trà đá", 8000)]);
  const noi = blockingProblem(reading, [A, B], {});
  assert.match(noi, /458\.000/);
  assert.equal(chuaAiNhanVnd(reading, {}), 458000);
});

test("gán hết thì không còn tiền vô chủ, và không còn câu chặn", () => {
  const reading = doc([mon("mon-0", "Lẩu", 450000), mon("mon-1", "Trà đá", 8000)]);
  const day = { "mon-0": [A, B], "mon-1": [A] };
  assert.equal(chuaAiNhanVnd(reading, day), 0);
  assert.equal(blockingProblem(reading, [A, B], day), null);
});

test("một món ăn chung ba người vẫn là đã phủ kín, không phải gán thừa", () => {
  // Trong mô hình này không có "gán quá tay": một món ba người tích vẫn được
  // phủ 100% và allocator chia nó. Cảnh báo cho trạng thái ấy là mô tả một
  // trạng thái dữ liệu không vào được.
  const reading = doc([mon("mon-0", "Lẩu", 450000)]);
  assert.equal(chuaAiNhanVnd(reading, { "mon-0": [A, B, NHOM] }), 0);
});

/* -------------------------------------------------- ticks nằm ở đâu ------ */

test("chưa lưu được thì màn nói thẳng, không im lặng", () => {
  // Một app lặng lẽ chạy tiếp sau khi ghi hỏng sẽ dạy người dùng rằng các ô
  // tích của họ an toàn, và bài học chỉ được đính chính vào lúc họ đóng app và
  // mất cả buổi tối số học.
  assert.match(moTaTrangThaiGan(null), /Chưa lưu được/);
});

test("prop không tới nơi cũng là chưa lưu, không phải trạng thái thứ ba", () => {
  // Bản viết `=== null` ném ngay ở dòng dưới với mọi caller quên truyền prop.
  // Cùng họ lỗi mà `readingFromWire` đã gác: trường thiếu bị đọc thành câu trả
  // lời thay vì thành sự vắng mặt.
  assert.match(moTaTrangThaiGan(undefined), /Chưa lưu được/);
});

test("chốt hết rồi thì không còn gọi là máy đoán", () => {
  const bill = { suggested_item_keys: [], items: [{ item_key: "mon-0" }] };
  const noi = moTaTrangThaiGan(bill);
  assert.match(noi, /Đã lưu/);
  assert.match(noi, /chốt/);
  assert.doesNotMatch(noi, /đoán/);
});

test("chốt 4/6 dòng KHÔNG bị báo thành chưa có gì được lưu", () => {
  // assignment_state ở mức trên vẫn là "ai_suggested" trong đúng ca này. Chỉ
  // đọc trường đó là bảo người dùng làm lại việc họ đã làm xong.
  const bill = {
    suggested_item_keys: ["mon-4", "mon-5"],
    items: ["mon-0", "mon-1", "mon-2", "mon-3", "mon-4", "mon-5"].map((k) => ({
      item_key: k,
    })),
  };
  const noi = moTaTrangThaiGan(bill);
  assert.match(noi, /Đã lưu/);
  assert.match(noi, /2 món/);
});

/* ----------------------------------------------------------- số dư nhóm --- */

test("transfers đọc sender_id/recipient_id, không phải from_id/to_id", () => {
  // Bản đoán tên trường parse trót lọt rồi đặt undefined vào chỗ tên người:
  // render ra một dòng trống chứ không phải một lỗi ai nhìn thấy. Tên đúng lấy
  // từ SettlementTransferProposal trong schemas.py.
  const soDu = soDuFromWire({
    balances: [{ person_id: A, net_vnd: -120000 }],
    transfers: [{ sender_id: A, recipient_id: B, amount_vnd: 120000 }],
    proven_minimal: true,
    transfer_count: 1,
  });
  assert.equal(soDu.transfers[0].fromId, A);
  assert.equal(soDu.transfers[0].toId, B);
  assert.equal(soDu.transfers[0].amountVnd, 120000);
});

test("proven_minimal thiếu thì coi như chưa chứng minh, không mặc định là rồi", () => {
  // "Ít nhất có thể" trên một danh sách không ai chứng minh là một lời nói dối
  // nhỏ, đổi lấy không gì cả, ngay trên màn tiền.
  const soDu = soDuFromWire({
    balances: [],
    transfers: [],
    transfer_count: 0,
  });
  assert.equal(soDu.provenMinimal, false);
});

test("net_vnd lẻ bị chặn ngay khi đọc về, không lọt vào màn", () => {
  assert.throws(
    () =>
      soDuFromWire({
        balances: [{ person_id: A, net_vnd: 120000.5 }],
        transfers: [],
        proven_minimal: true,
        transfer_count: 0,
      }),
    /nguyên đồng/,
  );
});
