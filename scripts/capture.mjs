// Capture a sanitized board. Demo feedback is authored here, never read from a user's browser storage.
import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const source=path.resolve(process.argv[2]||'examples/onboarding.html');
const output=path.resolve('docs/screenshots');await mkdir(output,{recursive:true});
const browser=await chromium.launch();
const context=await browser.newContext({viewport:{width:1800,height:1120},deviceScaleFactor:2,recordVideo:{dir:'build/capture-video',size:{width:1800,height:1120}}});
const page=await context.newPage();await page.goto(pathToFileURL(source).href);
await page.waitForTimeout(200);await page.screenshot({path:path.join(output,'canvas-overview.png')});
const screens=await page.evaluate(()=>wiredAPI.getModel().flows[0].steps.map(s=>s.id));
await page.locator('#commentMode').click();const target=page.locator(`#world > .node[data-id="${screens[1]||screens[0]}"] .frame-wrap`);const r=await target.boundingBox();await page.mouse.click(r.x+r.width*.45,r.y+r.height*.35);
await page.locator('#world .comment-card textarea').fill('Make the permission explanation shorter.');
await page.locator('#addNote').click();await page.locator('#world .annotation-card:not(.comment-card) textarea').fill('Keep Messages and CLIs on separate setup paths.');
// Move the free note through the same pointer gesture used by reviewers.
const h=await page.locator('#world .annotation-card:not(.comment-card) .annotation-head').boundingBox();await page.mouse.move(h.x+50,h.y+10);await page.mouse.down();await page.mouse.move(h.x+110,h.y-120,{steps:16});await page.mouse.up();
await page.locator('#in').click();await page.locator('#in').click();
await page.evaluate(()=>{const v=document.getElementById('viewport');v.scrollTop=0;v.scrollLeft=550});
await page.screenshot({path:path.join(output,'canvas-feedback.png')});
// Short interaction for a directly playable repository video.
const node=page.locator(`#world > .node[data-id="${screens[1]||screens[0]}"] .frame-wrap`),b=await node.boundingBox();await page.mouse.move(b.x+80,b.y+80);await page.mouse.down();await page.mouse.move(b.x+135,b.y+110,{steps:25});await page.mouse.up();await page.waitForTimeout(350);
const video=page.video();await context.close();console.log(JSON.stringify({screenshots:output,video:await video.path()}));await browser.close();
