import { test, expect } from '@playwright/test';
async function clean(page){await page.goto('/examples/onboarding.html');await page.evaluate(()=>localStorage.clear());await page.reload();}
async function drag(page,locator,dx,dy){const r=await locator.boundingBox();await page.mouse.move(r.x+r.width*.3,r.y+r.height*.3);await page.mouse.down();await page.mouse.move(r.x+r.width*.3+dx,r.y+r.height*.3+dy,{steps:8});await page.mouse.up();}

test('whole-image drag and resize keep wires attached; background drag pans',async({page})=>{
  await clean(page);const n=page.locator('#world > .node[data-id=welcome]');
  const before=await page.evaluate(()=>structuredClone(wiredAPI.getModel().positions.welcome));const wire=await page.locator('#paths').innerHTML();
  await drag(page,n.locator('.frame-wrap'),50,30);expect((await page.evaluate(()=>wiredAPI.getModel().positions.welcome)).x).not.toBe(before.x);expect(await page.locator('#paths').innerHTML()).not.toBe(wire);
  await drag(page,n.locator('.resize'),-35,-25);expect((await page.evaluate(()=>wiredAPI.getModel().positions.welcome)).w).toBeLessThan(504);
  await page.evaluate(()=>{const v=document.getElementById('viewport');v.scrollLeft=100;v.scrollTop=100});const r=await page.locator('#viewport').boundingBox();await page.mouse.move(r.x+12,r.y+400);await page.mouse.down();await page.mouse.move(r.x-28,r.y+350,{steps:8});await page.mouse.up();expect(await page.evaluate(()=>document.getElementById('viewport').scrollTop)).toBeGreaterThan(100);
});

test('zoom preserves the world point under the cursor',async({page})=>{
  await clean(page);const r=await page.locator('#viewport').boundingBox(),cx=r.x+600,cy=r.y+350;
  const point=()=>page.evaluate(({cx,cy})=>{const v=document.getElementById('viewport'),r=v.getBoundingClientRect();return [(v.scrollLeft+cx-r.left)/scale,(v.scrollTop+cy-r.top)/scale,scale]},{cx,cy});
  const before=await point();await page.mouse.move(cx,cy);await page.keyboard.down('Control');await page.mouse.wheel(0,-100);await page.keyboard.up('Control');await page.waitForTimeout(100);const after=await point();expect(after[2]).toBeGreaterThan(before[2]);expect(Math.abs(after[0]-before[0])).toBeLessThan(3);expect(Math.abs(after[1]-before[1])).toBeLessThan(3);
});

test('notes, pinned comments and feedback survive export, reload and portable save',async({page},info)=>{
  await clean(page);await page.locator('#addNote').click();await page.locator('#world .annotation-card textarea').fill('Keep the setup paths separate.');await page.locator('#commentMode').click();
  const target=page.locator('#world > .node[data-id=welcome] .frame-wrap');const r=await target.boundingBox();await page.mouse.click(r.x+r.width*.4,r.y+r.height*.4);await page.locator('#world .comment-card textarea').fill('Shorten this copy.');await expect(page.locator('#world .annotation-pin')).toHaveCount(1);
  const pin=await page.locator('#world .annotation-pin').getAttribute('style');await drag(page,page.locator('#world > .node[data-id=welcome] .handle'),35,25);expect(await page.locator('#world .annotation-pin').getAttribute('style')).not.toBe(pin);
  const download=page.waitForEvent('download');await page.locator('#save').click();const file=await download;const saved=info.outputPath('feedback.json');await file.saveAs(saved);await page.reload();await expect(page.locator('#world .annotation-card')).toHaveCount(2);
  await page.evaluate(()=>localStorage.clear());await page.reload();await page.locator('#file').setInputFiles(saved);await expect(page.locator('#world .comment-card textarea')).toHaveValue('Shorten this copy.');
  const portable=page.waitForEvent('download');await page.locator('#portable').click();const html=await portable;const path=info.outputPath('portable.html');await html.saveAs(path);const other=await page.context().newPage();await other.goto(new URL('file://'+path).href);await expect(other.locator('#world .annotation-card')).toHaveCount(2);await other.close();
  await page.evaluate(()=>wiredAPI.buildPrint());await expect(page.locator('#printRoot .annotation-card')).toHaveCount(2);
});

test('invalid imported IDs cannot replace or inject into the current review',async({page})=>{
  await clean(page);const model=await page.evaluate(()=>structuredClone(wiredAPI.getModel()));model.flows[0].steps[0].id='bad" onmouseover="window.injected=true';
  await page.locator('#file').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(model))});await expect(page.locator('#world > .node[data-id=welcome]')).toHaveCount(1);expect(await page.evaluate(()=>window.injected)).toBeUndefined();await expect(page.locator('.toast')).toContainText('Choose an exported');
});
