/* Đi bộ lượt "hỏi thẳng AI" trên máy chủ SỐNG, bằng chính module app import.
 *
 * Không phải test trong npm test: nó cần Postgres, uvicorn và một GEMINI_API_KEY
 * thật, nên nó là hiện vật của phiếu bug-002847, chạy tay qua e2e_slice.sh --keep.
 *
 * Cái nó chứng minh mà tầng fake KHÔNG chứng minh được: cờ requested đi qua dây
 * thật tới plan_turn thật, và mô hình thật trả lời ở đúng lượt mà lượt tự động
 * bị nhịp chặn. Tầng fake chỉ chứng minh client GỬI cờ.
 *
 *   EXPO_PUBLIC_API_URL=http://127.0.0.1:PORT node tests/e2e/hoi-thang-ai.probe.mjs
 */
import { goiAiTurn } from "../../dist-test/screens/chat/ai.js";
import { khoiDongNhom } from "../../dist-test/screens/chat/nhom.js";
import { guiTinNhan } from "../../dist-test/screens/chat/tin-nhan.js";
import { personById } from "../../dist-test/navigation/nhom-demo.js";
import { khoaGhi } from "../../dist-test/screens/chat/uuid5.js";

const BASE = process.env.EXPO_PUBLIC_API_URL;
if (!BASE) throw new Error("thiếu EXPO_PUBLIC_API_URL");

const minh = personById("minh");
let khoa = 0;
const key = () => khoaGhi(`bug-002847-${Date.now()}-${khoa++}`);

function in_(nhan, s) {
  const phu =
    s.kind === "da-noi"
      ? `message.kind=${s.message.kind} card=${s.message.card?.kind ?? "null"}`
      : s.kind === "im-lang"
        ? `reason=${s.reason} (MÀN HÌNH KHÔNG HIỆN GÌ)`
        : s.kind === "khong-tra-loi-duoc"
          ? `reason=${s.reason} câu="${s.cau}"`
          : JSON.stringify(s);
  console.log(`  ${nhan.padEnd(34)} -> ${s.kind.padEnd(20)} ${phu}`);
  return s;
}

const nhom = await khoiDongNhom({ id: "minh", personId: minh.personId, name: minh.name }, { base: BASE });
if (nhom.kind !== "xong") throw new Error(`không mở được nhóm: ${JSON.stringify(nhom)}`);
const ctx = nhom.contextId;
console.log(`nhóm: ${ctx}\nAPI : ${BASE}\n`);

const gui = async (body) => {
  const s = await guiTinNhan({ contextId: ctx, actorId: minh.personId, body, idempotencyKey: key(), base: BASE });
  if (s.kind !== "xong") throw new Error(`gửi tin hỏng: ${JSON.stringify(s)}`);
};
const turn = (hoiThang) =>
  goiAiTurn({ contextId: ctx, actorId: minh.personId, idempotencyKey: key(), base: BASE, hoiThang });

await gui("Cuối tuần này nhóm mình đi Đà Lạt nhé");
const a = in_("1. lượt TỰ ĐỘNG (không cờ)", await turn(false));

await gui("lên giúp lịch trình chi tiết từng giờ");
const b = in_("2. lượt TỰ ĐỘNG ngay sau đó", await turn(false));

const c = in_("3. HỎI THẲNG (requested:true)", await turn(true));

console.log("\n--- phán quyết ---");
const nhipChan = b.kind === "im-lang" && ["cooldown", "already_spoke_last"].includes(b.reason);
console.log(`lượt tự động bị nhịp chặn và vẽ ra KHÔNG GÌ CẢ : ${nhipChan ? "ĐÚNG" : "KHÔNG (" + b.kind + "/" + (b.reason ?? "") + ")"}`);
console.log(`hỏi thẳng vượt qua đúng chỗ đó                 : ${c.kind === "da-noi" ? "ĐÚNG, AI đã trả lời" : "KHÔNG (" + c.kind + ")"}`);
if (c.kind === "khong-tra-loi-duoc") {
  console.log(`  (không im lặng: người bấm nút vẫn nhận một câu) "${c.cau}"`);
}
console.log(`bước 1 để đối chứng máy chủ có AI sống         : ${a.kind}`);
