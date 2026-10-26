export async function toolbarClick(page,selector){
  const button=page.locator(selector);
  if(!(await button.isVisible()))await page.locator('.more-tools summary').click();
  await button.click();
}
