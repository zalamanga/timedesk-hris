import {expect,test} from '@playwright/test';
import {checkReadability,checkWorkspace} from './accessibility';

test('readable login, employee clock and manager review at five widths',async({page})=>{
  await page.goto('/');
  await expect(page.locator('input[type=password]')).toBeVisible();
  await checkReadability(page);
  await checkWorkspace(page,'colleague@timedesk.test');
  await checkWorkspace(page,'manager@timedesk.test');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await expect(page.locator('input[type=password]')).toBeVisible();
});
