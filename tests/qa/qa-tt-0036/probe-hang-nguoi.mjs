import { chromium } from "playwright";
import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";
const CHROME=timTrinhDuyet();
const b=await chromium.launch({executablePath:CHROME});
const p=await b.newPage({viewport:{width:320,height:844}});
await p.goto(process.argv[2]+"/?man=goi-y-chia",{waitUntil:"networkidle"});
await p.waitForTimeout(800);
// Any container (leaf or not) whose content is wider than its box, plus
// whether that container can actually be scrolled to reach the overflow.
const r=await p.evaluate(()=>{
  const ra=[];
  for(const el of document.querySelectorAll("*")){
    const thua=el.scrollWidth-el.clientWidth;
    if(thua<=1) continue;
    const cs=getComputedStyle(el);
    ra.push({tag:el.tagName,cls:(el.className||"").toString().slice(0,30),
      thua,client:el.clientWidth,scroll:el.scrollWidth,
      overflowX:cs.overflowX,laLa:el.children.length===0,
      chu:(el.textContent||"").trim().slice(0,60)});
  }
  // Can we reach "Đức Duy" / its amount by scrolling something?
  const tim=[...document.querySelectorAll("*")].filter(e=>e.children.length===0 &&
     /Đức Duy|262\.500/.test(e.textContent||""));
  const vt=tim.map(e=>{const r=e.getBoundingClientRect();
     return {chu:e.textContent.trim(),x:Math.round(r.x),right:Math.round(r.right),
             ngoaiKhung:r.right>window.innerWidth, rong:Math.round(r.width)};});
  return {ra,vt,vw:window.innerWidth};
});
console.log("viewport",r.vw);
console.log("=== moi container co noi dung rong hon hop ===");
for(const o of r.ra) console.log(" ",JSON.stringify(o));
console.log("=== vi tri cua Duc Duy / 262.500 ===");
for(const o of r.vt) console.log(" ",JSON.stringify(o));
await b.close();
