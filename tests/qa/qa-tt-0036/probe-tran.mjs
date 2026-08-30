import { chromium } from "playwright";
const CHROME="/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";
const b=await chromium.launch({executablePath:CHROME});
for (const w of [390,320]) {
  const p=await b.newPage({viewport:{width:w,height:844}});
  await p.goto("about:blank");
  await p.goto(process.argv[2]+"/?man=goi-y-chia",{waitUntil:"networkidle"});
  await p.waitForTimeout(800);
  const r=await p.evaluate(()=>{
    const ra=[];
    for(const el of document.querySelectorAll("*")){
      if(el.children.length>0) continue;
      const t=(el.textContent||"").trim(); if(!t) continue;
      const thua=el.scrollWidth-el.clientWidth;
      if(thua>1){
        const cs=getComputedStyle(el);
        const rect=el.getBoundingClientRect();
        ra.push({chu:t,thua,client:el.clientWidth,scroll:el.scrollWidth,
          overflow:cs.overflow,overflowX:cs.overflowX,textOverflow:cs.textOverflow,
          whiteSpace:cs.whiteSpace,fontSize:cs.fontSize,
          x:Math.round(rect.x),right:Math.round(rect.right),
          // does the box itself spill past the viewport?
          ngoaiKhung: rect.right > window.innerWidth});
      }
    }
    return {ra, vw:window.innerWidth, docScroll:document.documentElement.scrollWidth};
  });
  console.log(`\n=== ?man=goi-y-chia @${w}px  (viewport ${r.vw}, document scrollWidth ${r.docScroll}) ===`);
  for(const o of r.ra) console.log(JSON.stringify(o));
  await p.screenshot({path:`/tmp/qa36/tran-${w}.png`});
  await p.close();
}
await b.close();
