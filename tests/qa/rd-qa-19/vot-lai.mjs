/** The exact hole the server's refusal exists to close: a body that says
 *  source="none" while still carrying places. If the UI draws them, an answer
 *  the server refused reaches the user anyway. */
import { chromium } from "playwright";
const WEB = "http://127.0.0.1:8548", API = "http://127.0.0.1:8547";
const cat = await (await fetch(`${API}/places`)).json();
const real = (cat.places ?? cat).slice(0, 2);
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await p.goto(`${WEB}/#tab=kham-pha`, { waitUntil: "networkidle" });
await p.route("**/places/search", (r) => r.fulfill({ status: 200, contentType: "application/json",
  body: JSON.stringify({ query: "x", understood: null, source: "none", places: real, group: cat.group ?? {} }) }));
await p.getByLabel("Tìm bằng lời").fill("câu bị từ chối");
await p.getByRole("button", { name: /Tìm bằng AI|Đang hỏi AI/ }).click();
await p.waitForFunction(() => /Chưa tìm được|Không có chỗ|AI hiểu|Kết quả|Máy chủ/.test(document.body.innerText), { timeout: 30000 });
await p.waitForTimeout(600);
const t = await p.evaluate(() => document.body.innerText);
const drawn = real.map(x => x.name).filter(n => t.includes(n));
console.log("thân trả lời: source=none NHƯNG mang 2 địa điểm hợp lệ:", real.map(x=>x.name).join(", "));
console.log("địa điểm bị VỚT LÊN MÀN :", drawn.length ? drawn.join(", ") : "KHÔNG CÓ");
console.log("màn hiện              :", t.split("\n").map(s=>s.trim()).filter(Boolean).slice(6,9).join(" | "));
console.log(drawn.length === 0 ? "\n=> ĐẠT: câu đã bị từ chối thì không phần nào của nó lên màn"
                               : "\n=> HỎNG: client vớt lại kết quả server đã từ chối");
await p.screenshot({ path: "/tmp/qa19-shots/q2-vot-lai.png", fullPage: true });
await b.close();
