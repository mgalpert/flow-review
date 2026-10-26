import { test, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const publication={siteUrl:'https://flow-review-demo.here.now/',claimUrl:'https://here.now/c/fixture-owner-only',expiresAt:'2026-10-22T00:00:00Z'};
async function open(page){await page.goto('/');await page.evaluate(()=>localStorage.clear());await page.reload();}
async function annotate(page){
  await page.locator('#addNote').click();await page.locator('#world .annotation-card textarea').fill('Demo note: keep café and 你好 in the shared review.');
  await page.locator('#commentMode').click();const target=await page.locator('#world > .node[data-id=welcome] .frame-wrap').boundingBox();
  await page.mouse.click(target.x+target.width*.4,target.y+target.height*.4);
  await page.locator('#world .comment-card textarea').fill('Demo comment: keep this resolved feedback visible.');
  await page.locator('#world .comment-card .resolve-note').check();
}

test('publishing captures the latest canvas and feedback, without owner links or local tokens',async({page},info)=>{
  await open(page);await annotate(page);const snapshots=[];
  const token=JSON.parse(await page.locator('#publisher-config').textContent()).token;
  await page.route('**/__flow_review/publish',async route=>{snapshots.push(route.request().postDataJSON());await route.fulfill({json:publication});});
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await expect(dialog).toContainText('1 note and 1 comment, including resolved feedback');expect(snapshots).toHaveLength(0);
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);
  await expect(dialog.getByRole('link',{name:'Keep this link permanently'})).toHaveAttribute('href',publication.claimUrl);
  await page.context().grantPermissions(['clipboard-read','clipboard-write']);
  await dialog.getByRole('button',{name:'Copy public link',exact:true}).click();
  expect(await page.evaluate(()=>navigator.clipboard.readText())).toBe(publication.siteUrl);
  await dialog.getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#world .annotation-card:not(.comment-card) textarea').fill('Latest demo note after the first publish.');
  await page.locator('#hereNow').click();await dialog.getByRole('button',{name:'Update published link',exact:true}).click();
  await expect.poll(()=>snapshots.length).toBe(2);await expect(dialog.locator('.publish-status')).toContainText('Updated.');
  const source=snapshots[1].html;
  expect(source).not.toContain(token);expect(source).not.toContain(publication.claimUrl);
  expect(source).not.toContain('id="publisher-config"');expect(source).not.toContain('<dialog');
  const file=info.outputPath('published-snapshot.html');await writeFile(file,source);
  const visitor=await page.context().newPage();await visitor.goto(pathToFileURL(file).href);
  await expect(visitor.locator('#world .annotation-card:not(.comment-card) textarea')).toHaveValue('Latest demo note after the first publish.');
  await expect(visitor.locator('#world .comment-card textarea')).toHaveValue('Demo comment: keep this resolved feedback visible.');
  await expect(visitor.locator('#world .comment-card .resolve-note')).toBeChecked();
  await expect(visitor.locator('#hereNow')).toBeEnabled();await visitor.locator('#hereNow').click();
  await expect(visitor.getByRole('dialog').locator('.publish-setup')).toBeVisible();
  await expect(visitor.getByRole('button',{name:'Publish snapshot',exact:true})).toBeHidden();
  await visitor.close();
  await page.reload();await page.locator('#hereNow').click();
  await expect(page.getByRole('dialog').locator('.publish-link')).toHaveText(publication.siteUrl);
  expect(snapshots).toHaveLength(2);
});

test('failed publishing preserves feedback and claim recovery; retry needs another explicit click',async({page})=>{
  await open(page);await annotate(page);let calls=0;
  await page.route('**/__flow_review/publish',async route=>{calls++;await route.fulfill({status:calls===1?502:200,json:calls===1?{error:'Upload failed. Your local review is unchanged.',claimUrl:publication.claimUrl}:publication});});
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await expect(dialog.locator('.publish-status')).toContainText('Upload failed');
  await expect(dialog.locator('.publish-result')).toBeHidden();await expect(dialog.locator('.publish-owner')).toBeVisible();
  await expect(dialog.getByRole('button',{name:'Publish snapshot',exact:true})).toBeEnabled();
  expect(calls).toBe(1);expect(await page.evaluate(()=>wiredAPI.getModel().annotations.length)).toBe(2);
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);expect(calls).toBe(2);
});

test('an in-flight publish cannot create a second request',async({page})=>{
  await open(page);let release;const pending=new Promise(resolve=>{release=resolve});let calls=0;
  await page.route('**/__flow_review/publish',async route=>{calls++;await pending;await route.fulfill({json:publication});});
  await page.locator('#hereNow').click();const submit=page.getByRole('button',{name:'Publish snapshot',exact:true});
  await submit.click();await expect(submit).toBeDisabled();await expect(page.locator('#hereNow')).toBeDisabled();
  expect(calls).toBe(1);release();await expect(page.getByRole('button',{name:'Update published link',exact:true})).toBeEnabled();expect(calls).toBe(1);
});

test('the publishing button and dialog fit a narrow viewport',async({page})=>{
  await page.setViewportSize({width:390,height:844});await open(page);
  const button=await page.locator('#hereNow').boundingBox();expect(button.x).toBeGreaterThanOrEqual(0);expect(button.x+button.width).toBeLessThanOrEqual(390);
  await page.locator('#hereNow').click();const dialog=await page.getByRole('dialog').boundingBox();
  expect(dialog.x).toBeGreaterThanOrEqual(0);expect(dialog.x+dialog.width).toBeLessThanOrEqual(390);
  await expect(page.getByRole('button',{name:'Publish snapshot',exact:true})).toBeInViewport();
});

test('updates keep the same public link and removal blanks it only after confirmation',async({page})=>{
  await page.goto('/');
  const writes=[];
  await page.route('**/__flow_review/publish',route=>{writes.push(route.request().postDataJSON());return route.fulfill({json:publication})});
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);
  await dialog.getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#addNote').click();await page.getByRole('textbox',{name:'Canvas note',exact:true}).fill('Updated review feedback.');
  await page.locator('#hereNow').click();
  await dialog.getByRole('button',{name:'Update published link',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(2);
  expect(writes[1].publication.siteUrl).toBe(publication.siteUrl);
  expect(writes[1].publication.claimUrl).toBe(publication.claimUrl);
  expect(writes[1].html).toContain('Updated review feedback.');
  expect(writes[1].html).not.toContain(publication.claimUrl);
  const removals=[];
  await page.route('**/__flow_review/remove',route=>{removals.push(route.request().postDataJSON());return route.fulfill({json:{...publication,removed:true,mode:'blanked'}})});
  await dialog.getByRole('button',{name:'Remove public review',exact:true}).click();
  expect(removals).toHaveLength(0);
  await dialog.getByRole('button',{name:'Cancel removal',exact:true}).click();expect(removals).toHaveLength(0);
  await dialog.getByRole('button',{name:'Remove public review',exact:true}).click();
  await dialog.getByRole('button',{name:'Remove review',exact:true}).click();
  await expect.poll(()=>removals.length).toBe(1);
  expect(removals[0].publication.siteUrl).toBe(publication.siteUrl);
  await expect(dialog.locator('.publish-status')).toContainText('blank page');
  await expect(page.getByRole('textbox',{name:'Canvas note',exact:true})).toHaveValue('Updated review feedback.');
});

test('failed updates preserve the published link and allow an explicit retry',async({page})=>{
  await page.goto('/');let calls=0;
  await page.route('**/__flow_review/publish',route=>{calls++;return route.fulfill(calls===2?{status:502,json:{error:'Update failed.'}}:{json:publication})});
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  const update=dialog.getByRole('button',{name:'Update published link',exact:true});await update.click();
  await expect(dialog.locator('.publish-status')).toContainText('Update failed');
  await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);expect(calls).toBe(2);
  await update.click();await expect.poll(()=>calls).toBe(3);
});

for(const mode of ['deleted','failure']){
  test(`removal ${mode} reports the result without losing the local review`,async({page})=>{
    await page.goto('/');
    await page.locator('#addNote').click();await page.getByRole('textbox',{name:'Canvas note',exact:true}).fill('Keep my local review.');
    await page.route('**/__flow_review/publish',route=>route.fulfill({json:publication}));
    await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
    await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
    await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);
    await page.route('**/__flow_review/remove',route=>route.fulfill(mode==='failure'?{status:502,json:{error:'Removal failed.'}}:{json:{siteUrl:publication.siteUrl,removed:true,mode:'deleted'}}));
    await dialog.getByRole('button',{name:'Remove public review',exact:true}).click();
    await dialog.getByRole('button',{name:'Remove review',exact:true}).click();
    if(mode==='failure'){
      await expect(dialog.locator('.publish-status')).toContainText('Removal failed');
      await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);
      await expect(dialog.getByRole('button',{name:'Remove review',exact:true})).toBeEnabled();
    }else{
      await expect(dialog.locator('.publish-status')).toContainText('Deleted.');
      await expect(dialog.locator('.publish-result')).toBeHidden();
      await expect(dialog.getByRole('button',{name:'Publish snapshot',exact:true})).toBeEnabled();
    }
    await expect(page.getByRole('textbox',{name:'Canvas note',exact:true})).toHaveValue('Keep my local review.');
  });
}

test('an expired link can be replaced only by explicitly publishing a new link',async({page})=>{
  await page.goto('/');const writes=[];
  const replacement={siteUrl:'https://replacement-demo.here.now/',claimUrl:'https://here.now/c/replacement-fixture'};
  await page.route('**/__flow_review/publish',route=>{
    writes.push(route.request().postDataJSON());
    return route.fulfill(writes.length===2?{status:502,json:{error:'Publication expired.',upstreamStatus:410}}:{json:writes.length===1?publication:replacement});
  });
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await dialog.getByRole('button',{name:'Update published link',exact:true}).click();
  const start=dialog.getByRole('button',{name:'Publish as new link',exact:true});await expect(start).toBeVisible();
  expect(writes).toHaveLength(2);await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);
  await start.click();await dialog.getByRole('button',{name:'Cancel new link',exact:true}).click();expect(writes).toHaveLength(2);
  await start.click();await dialog.getByRole('button',{name:'Publish new link',exact:true}).click();
  await expect(dialog.locator('.publish-link')).toHaveText(replacement.siteUrl);
  expect(writes).toHaveLength(3);expect(writes[2]).not.toHaveProperty('publication');
});

test('a failed replacement keeps the original link and owner details',async({page})=>{
  await page.goto('/');let calls=0;
  await page.route('**/__flow_review/publish',route=>{
    calls++;
    return route.fulfill(calls===1?{json:publication}:calls===2?{status:502,json:{error:'Expired.',upstreamStatus:410}}:{status:502,json:{error:'Replacement upload failed.',claimUrl:'https://here.now/c/new-incomplete-fixture'}});
  });
  await page.locator('#hereNow').click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Publish snapshot',exact:true}).click();
  await dialog.getByRole('button',{name:'Update published link',exact:true}).click();
  await dialog.getByRole('button',{name:'Publish as new link',exact:true}).click();
  await dialog.getByRole('button',{name:'Publish new link',exact:true}).click();
  await expect(dialog.locator('.publish-status')).toContainText('Replacement upload failed');
  await expect(dialog.locator('.publish-link')).toHaveText(publication.siteUrl);
  await expect(dialog.locator('.publish-owner a')).toHaveAttribute('href',publication.claimUrl);
  await expect(dialog.getByRole('button',{name:'Publish as new link',exact:true})).toBeVisible();
});
