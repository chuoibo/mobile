import { chromium } from "playwright";
import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";
const CHROME=timTrinhDuyet();
const b=await chromium.launch({executablePath:CHROME});
const p=await b.newPage({viewport:{width:390,height:844}});
await p.goto(process.argv[2]+"/?man=nhan-dien",{waitUntil:"networkidle"});
await p.waitForTimeout(800);
const r=await p.evaluate(()=>{
  const inputs=[...document.querySelectorAll("input,textarea")].map(e=>({tag:e.tagName,val:e.value,ph:e.placeholder||null}));
  return {soInput:inputs.length, inputs, innerTextLen:document.body.innerText.length,
          textContentLen:(document.body.textContent||"").length};
});
console.log("so input/textarea:",r.soInput);
console.log("innerText",r.innerTextLen,"vs textContent",r.textContentLen);
for(const i of r.inputs) console.log(`  ${i.tag} value="${i.val}" placeholder=${JSON.stringify(i.ph)}`);
await b.close();
