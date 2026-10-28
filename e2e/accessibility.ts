import {expect, Page} from '@playwright/test';

export async function checkReadability(page: Page) {
  const result = await page.evaluate(() => {
    const rgb = (v: string) => (v.match(/[\d.]+/g) || []).map(Number);
    const luminance = (c: number[]) => c.slice(0, 3).map(v => {const n=v/255; return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
    const ratio = (a: number[],b: number[]) => {const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
    const background = (node: Element) => {
      let current: Element|null=node;
      while(current){const value=rgb(getComputedStyle(current).backgroundColor);if(value.length>=3&&(value.length<4||value[3]>0)){return value;}current=current.parentElement;}
      return [255,255,255];
    };
    const violations: {kind:string;text:string;ratio:number}[]=[];
    let checked=0;
    for(const node of document.body.querySelectorAll<HTMLElement>('*')){
      const style=getComputedStyle(node);
      if(!node.getClientRects().length||style.visibility==='hidden'||node.closest(':disabled,[aria-hidden="true"]'))continue;
      const bg=background(node);
      if([...node.childNodes].some(n=>n.nodeType===Node.TEXT_NODE&&n.textContent?.trim())){
        const fg=rgb(style.color);if(fg.length<3)continue;
        const size=parseFloat(style.fontSize),large=size>=24||(size>=18.66&&Number(style.fontWeight)>=700);
        const contrast=ratio(fg,bg);checked++;
        if(contrast<(large?3:4.5))violations.push({kind:'text',text:(node.textContent||'').trim().slice(0,80),ratio:contrast});
      }
      if(node.matches('input:not([type=checkbox]),select,textarea')&&parseFloat(style.borderTopWidth)>0){
        const edge=rgb(style.borderTopColor);const contrast=ratio(edge,bg);
        if(contrast<3)violations.push({kind:'input border',text:node.getAttribute('aria-label')||node.id||node.tagName,ratio:contrast});
        if(node instanceof HTMLInputElement||node instanceof HTMLTextAreaElement){
          const placeholder=!node.value&&Boolean(node.placeholder);
          const color=rgb(placeholder?getComputedStyle(node,'::placeholder').color:style.color);
          const contrast=ratio(color,bg);
          if(contrast<4.5)violations.push({kind:placeholder?'placeholder':'input text',text:node.placeholder||node.id||node.type,ratio:contrast});
        }
      }
    }
    return {checked,violations};
  });
  expect(result.checked).toBeGreaterThan(0);
  expect(result.violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
}

export async function checkWorkspace(page: Page, email: string) {
  const result=await page.request.post('/api/auth/login',{data:{email,password:process.env.APP_DEMO_PASSWORD}});
  expect(result.status()).toBe(200);
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Keluar',exact:true})).toBeVisible();
  await expect(page.locator('main h1')).toBeVisible();
  await page.waitForLoadState('networkidle');
  for(const width of [1440,1024,768,390,320]){
    await page.setViewportSize({width,height:1000});
    await checkReadability(page);
  }
}
