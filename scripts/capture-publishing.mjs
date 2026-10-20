// Only the repository's sanitized example may be used for this publishing demo.
// Default: mocked here.now response. --live makes one real anonymous publication.
import { chromium } from '@playwright/test';
import { mkdir, writeFile, copyFile } from 'node:fs/promises';
import path from 'node:path';

const url=process.argv[2],live=process.argv.includes('--live');
if(!url||!/^http:\/\/127\.0\.0\.1:\d+\/$/.test(url))throw Error('Pass a loopback publishing preview URL.');
await mkdir('docs/screenshots',{recursive:true});await mkdir('build/publishing-capture',{recursive:true});
const browser=await chromium.launch();
const context=await browser.newContext({viewport:{width:1600,height:1050},deviceScaleFactor:1,recordVideo:{dir:'build/publishing-capture',size:{width:1600,height:1050}}});
try{
  const page=await context.newPage();await page.goto(url);await page.evaluate(()=>localStorage.clear());await page.reload();
  if(await page.evaluate(()=>wiredAPI.getModel().boardId)!=='example-onboarding')throw Error('Use only examples/onboarding.html for this demo.');
  await page.locator('#addNote').click();await page.locator('#world .annotation-card textarea').fill('Demo note: keep each setup path separate.');
  await page.locator('#commentMode').click();const target=await page.locator('#world > .node[data-id=welcome] .frame-wrap').boundingBox();
  await page.mouse.click(target.x+target.width*.4,target.y+target.height*.4);
  await page.locator('#world .comment-card textarea').fill('Demo comment: simplify this first screen.');
  await page.locator('#world .comment-card .resolve-note').check();
  if(!live)await page.route('**/__flow_review/publish',route=>route.fulfill({json:{siteUrl:'https://flow-review-demo.here.now/',claimUrl:'https://here.now/c/demo-placeholder'}}));
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await page.screenshot({path:'docs/screenshots/publish-confirmation.png'});
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.publish-status').textContent.startsWith('Published.')||!document.querySelector('[data-publish-submit]').disabled,{},{timeout:120000});
  const siteUrl=await dialog.locator('.publish-link').getAttribute('href');
  if(!siteUrl)throw Error(await dialog.locator('.publish-status').textContent());
  await page.screenshot({path:'docs/screenshots/publish-desktop.png'});
  const claimUrl=await dialog.locator('.publish-owner a').getAttribute('href');
  await writeFile('build/publishing-capture/owner-receipt.json',JSON.stringify({siteUrl,claimUrl,live}),{mode:0o600});
  if(live){
    const visitorContext=await browser.newContext();const visitor=await visitorContext.newPage();await visitor.goto(siteUrl);
    await visitor.locator('#world .annotation-card').last().waitFor();
    if(await visitor.locator('#world .annotation-card').count()!==2||!(await visitor.locator('#world .comment-card .resolve-note').isChecked()))throw Error('Published feedback did not survive the real upload.');
    const token=JSON.parse(await page.locator('#publisher-config').textContent()).token;
    const source=await (await visitor.request.get(siteUrl)).text();
    if(source.includes(claimUrl)||source.includes(token)||source.includes('id="publisher-config"'))throw Error('Public snapshot contains private publishing metadata.');
    await visitor.screenshot({path:'docs/screenshots/published-canvas.png'});await visitorContext.close();
  }
  const model=await page.evaluate(()=>structuredClone(wiredAPI.getModel()));
  const mobile=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1});const small=await mobile.newPage();
  await small.goto(url);await small.evaluate(m=>{Object.assign(wiredAPI.getModel(),m);wiredAPI.render();persist()},model);
  await small.locator('#hereNow').click();await small.screenshot({path:'docs/screenshots/publish-mobile.png'});await mobile.close();
  await page.waitForTimeout(500);const video=page.video();await context.close();
  await copyFile(await video.path(),'docs/screenshots/publishing.webm');
  console.log(JSON.stringify({siteUrl,live,screenshots:'docs/screenshots',video:path.resolve('docs/screenshots/publishing.webm')}));
}finally{await browser.close()}
