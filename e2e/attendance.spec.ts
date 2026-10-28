import { expect, test, Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

const password=process.env.APP_DEMO_PASSWORD;
test.skip(!password,'Set APP_DEMO_PASSWORD to the private demo password');

async function login(page:Page,email='employee@timedesk.test'){
  await page.goto('/');
  await page.getByRole('textbox',{name:'Email',exact:true}).fill(email);
  await page.getByLabel('Sandi',{exact:true}).fill(password!);
  const response=page.waitForResponse(r=>r.url().endsWith('/api/auth/login')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Masuk',exact:true}).click();
  expect((await response).status()).toBe(200);
  await expect(page.getByRole('heading',{name:'Kehadiran',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Muat ulang',exact:true})).toBeEnabled();
}

async function waitWrite(page:Page,fragment:string,action:()=>Promise<void>,status=200){
  const response=page.waitForResponse(r=>r.url().includes(fragment)&&r.request().method()==='POST');
  await action();expect((await response).status()).toBe(status);
  await expect(page.getByRole('button',{name:'Muat ulang',exact:true})).toBeEnabled();
}

test('employee checks in and out with server timestamps',async({page})=>{
  await login(page);
  const checkout=page.getByRole('button',{name:'Catat pulang',exact:true});
  if(await checkout.isVisible())await waitWrite(page,'/check-out',()=>checkout.click());
  await waitWrite(page,'/check-in',()=>page.getByRole('button',{name:'Catat masuk',exact:true}).click(),201);
  await expect(page.getByRole('heading',{name:'Anda sedang bekerja'})).toBeVisible();
  await expect(page.getByLabel('Durasi sesi aktif')).toHaveText(/\d{2}:\d{2}:\d{2}/);
  await waitWrite(page,'/check-out',()=>page.getByRole('button',{name:'Catat pulang',exact:true}).click());
  await expect(page.getByRole('button',{name:'Catat masuk',exact:true})).toBeVisible();
});

test('manager direct team and recap use real scoped records',async({page})=>{
  await login(page,'manager@timedesk.test');
  await page.getByRole('button',{name:'Tim langsung',exact:true}).click();
  await expect(page.getByRole('button',{name:'Muat ulang',exact:true})).toBeEnabled();
  await expect(page.getByText('Training Karyawan Operasional',{exact:true}).first()).toBeVisible();
  await expect(page.getByText('Training Karyawan Cabang',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Rekap harian',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Rekap harian',exact:true})).toBeVisible();
  await expect(page.getByText('Total sesi selesai',{exact:true})).toBeVisible();
  await expect(page.getByText('Detik selesai',{exact:true})).toHaveCount(1);
});

test('employee correction draft survives conflict and refresh',async({page})=>{
  await login(page);
  const edit=page.getByRole('button',{name:/Ajukan koreksi sesi/});
  await edit.last().click();
  await page.getByRole('textbox',{name:'Alasan koreksi',exact:true}).fill('Training: draf koreksi tetap tersimpan setelah konflik data.');
  await page.route('**/api/attendance/*/corrections',route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'Data berubah. Muat ulang sebelum mengirim kembali.'})}));
  await page.getByRole('button',{name:'Kirim koreksi',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Data berubah');
  await expect(page.getByRole('button',{name:'Kirim koreksi',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Muat ulang',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'Alasan koreksi',exact:true})).toHaveValue('Training: draf koreksi tetap tersimpan setelah konflik data.');
  await expect(page.getByRole('button',{name:'Kirim koreksi',exact:true})).toBeEnabled();
});

test('employee proposes a correction and direct manager approves through UI',async({page})=>{
  const reason=`Training: pemeriksaan koreksi browser ${Date.now()}`;
  await login(page);
  await page.getByRole('button',{name:/Ajukan koreksi sesi/}).last().click();
  await page.getByRole('textbox',{name:'Alasan koreksi',exact:true}).fill(reason);
  await waitWrite(page,'/corrections',()=>page.getByRole('button',{name:'Kirim koreksi',exact:true}).click(),201);
  await expect(page.getByRole('status')).toContainText('Koreksi dikirim');
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(page,'manager@timedesk.test');
  await page.getByRole('button',{name:'Koreksi waktu',exact:true}).click();
  await page.getByRole('button',{name:'Tim langsung',exact:true}).click();
  const card=page.getByRole('article').filter({hasText:reason});
  await expect(card).toBeVisible();
  await card.getByRole('textbox',{name:'Catatan keputusan (wajib saat menolak)',exact:true}).fill('Training: waktu dan alasan telah diperiksa melalui browser.');
  await waitWrite(page,'/approve',()=>card.getByRole('button',{name:/Setujui koreksi/}).click());
  await expect(page.getByRole('status')).toContainText('Koreksi disetujui');
  await page.getByLabel('Status koreksi',{exact:true}).selectOption('approved');
  await expect(page.getByRole('article').filter({hasText:reason})).toContainText('Disetujui');
});

test('correction reason is scoped to owner and manager',async({page})=>{
  await login(page,'manager@timedesk.test');
  await page.getByRole('button',{name:'Koreksi waktu',exact:true}).click();
  await page.getByRole('button',{name:'Tim langsung',exact:true}).click();
  await expect(page.getByText('Training: jam masuk perlu dikoreksi setelah pemeriksaan catatan kerja',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Keluar',exact:true}).click();
  await login(page,'manager2@timedesk.test');
  await page.getByRole('button',{name:'Koreksi waktu',exact:true}).click();
  await page.getByRole('button',{name:'Tim langsung',exact:true}).click();
  await expect(page.getByText('Tidak ada koreksi dengan status ini.',{exact:false})).toBeVisible();
  await expect(page.getByText('Training: jam masuk perlu dikoreksi setelah pemeriksaan catatan kerja',{exact:true})).toHaveCount(0);
});

test('CSV download and invalid range are handled',async({page})=>{
  await login(page);
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'Unduh CSV',exact:true}).click();
  expect((await download).suggestedFilename()).toBe('timedesk-attendance.csv');
  await page.getByLabel('Dari',{exact:true}).fill('2026-01-01');
  await page.getByLabel('Sampai',{exact:true}).fill('2026-12-31');
  await page.getByRole('button',{name:'Terapkan',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('1 sampai 31 hari');
});

for(const width of [320,390])test(`mobile ${width} fits and keyboard focus remains visible`,async({page})=>{
  await page.setViewportSize({width,height:844});await login(page);
  await expect(page.getByRole('button',{name:'Catat masuk',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  const focus=await page.evaluate(()=>{const node=document.activeElement;return node instanceof HTMLElement?getComputedStyle(node).outlineStyle:'';});
  expect(focus).not.toBe('none');
  await page.getByRole('button',{name:'Rekap harian',exact:true}).click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('@capture employee, team review and mobile screenshots',async({page})=>{
  await mkdir('docs/screenshots',{recursive:true});await login(page);
  await page.screenshot({path:'docs/screenshots/employee-attendance.png'});
  await page.getByRole('button',{name:'Rekap harian',exact:true}).click();
  await page.screenshot({path:'docs/screenshots/daily-recap.png'});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'docs/screenshots/mobile-recap.png'});
  await page.getByRole('button',{name:'Keluar',exact:true}).click();await page.setViewportSize({width:1440,height:1000});
  await login(page,'manager@timedesk.test');await page.getByRole('button',{name:'Koreksi waktu',exact:true}).click();await page.getByRole('button',{name:'Tim langsung',exact:true}).click();
  await expect(page.getByText('Training: jam masuk perlu dikoreksi setelah pemeriksaan catatan kerja',{exact:true})).toBeVisible();
  await page.screenshot({path:'docs/screenshots/manager-corrections.png'});
});
