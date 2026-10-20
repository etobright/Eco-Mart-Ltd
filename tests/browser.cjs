// Optional UI regression check: requires Playwright and Chromium.
// Uses an isolated temporary database; never changes the real store.
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const net=require('node:net');
const assert=require('node:assert/strict');
(async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'eco-ui-'));
 const root=path.resolve(__dirname,'..');
 const artifacts=process.env.POS_ARTIFACT_DIR||path.join(temp,'screenshots');fs.mkdirSync(artifacts,{recursive:true});
 const listener=net.createServer();await new Promise(r=>listener.listen(0,'127.0.0.1',r));const port=listener.address().port;await new Promise(r=>listener.close(r));
 const server=spawn('python3',['server.py'],{cwd:root,env:{...process.env,PORT:String(port),POS_DB:path.join(temp,'test.sqlite3')},stdio:'ignore'});
 let browser;
 try{
  const url=`http://127.0.0.1:${port}`;
  for(let i=0;i<100;i++){try{const r=await fetch(url+'/api/status');if(r.ok)break}catch{}await new Promise(r=>setTimeout(r,50))}
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1060}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.getByRole('heading',{name:'Configurons votre caisse.'}).waitFor();await page.screenshot({path:path.join(artifacts,'login.png'),fullPage:true});
  await page.locator('[name=password]').fill('isolated-ui-test-password');await page.locator('#toggle-password').click();assert.equal(await page.locator('[name=password]').getAttribute('type'),'text');await page.locator('#toggle-password').click();
  await page.locator('#login-submit').click();await page.locator('.welcome-banner').waitFor();assert.equal(await page.locator('.dashboard-stats .stat').count(),4);assert.match(await page.locator('.dashboard-stats').innerText(),/0/);
  await page.screenshot({path:path.join(artifacts,'dashboard-empty.png'),fullPage:true});
  await page.locator('nav [data-page=products]').click();await page.locator('#add-product').click();await page.locator('[name=name]').fill('Riz basmati · 1 kg');await page.locator('[name=price]').fill('85');await page.locator('[name=stock]').fill('20');await page.locator('#product-form button[type=submit], #product-form .primary').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);
  const fixtures=[['Lait entier · 1 L','Produits laitiers','65',15],['Jus de mangue · 1 L','Boissons','75',10],['Pommes rouges · pièce','Fruits & légumes','18',4],['Pain de campagne','Boulangerie','45',12],['Farine de blé · 1 kg','Épicerie','42',18],['Savon doux','Entretien','35',3],['Eau minérale · 1,5 L','Boissons','25',0]];
  for(const [name,category,price,stock]of fixtures){const r=await page.request.post(url+'/api/product',{data:{name,category,price,stock:String(stock),barcode:''}});assert.ok(r.ok())}
  await page.locator('nav [data-page=pos]').click();await page.locator('#search').waitFor();assert.equal(await page.locator('[data-add]').count(),8);
  const state=await(await page.request.get(url+'/api/state')).json();const rice=state.products.find(p=>p.name.startsWith('Riz'));
  await page.locator('#search').fill(rice.barcode);await page.locator('#search').press('Enter');assert.equal(await page.locator('#cart-count').innerText(),'1');
  await page.locator('#checkout').click();await page.locator('#tendered').fill('100');assert.match(await page.locator('#change').innerText(),/15/);await page.locator('#pay-submit').click();await page.locator('#print-receipt').waitFor();assert.match(await page.locator('.receipt').innerText(),/C26238002/);
  await page.evaluate(()=>window.print=()=>{});await page.locator('#print-receipt').click();assert.match(await page.locator('#print-area').innerText(),/85/);await page.locator('#close-modal').click();
  await page.locator('nav [data-page=labels]').click();await page.locator('#label-search').fill('Riz');assert.equal(await page.locator('[data-label]').count(),1);await page.locator('[data-label]').click();await page.locator('#label-count').fill('2');await page.locator('#print-label').click();assert.equal(await page.locator('#print-area .print-label').count(),2);await page.locator('#close-modal').click();
  await page.locator('nav [data-page=pos]').click();await page.locator('#search').waitFor();await page.locator('[data-add]:not([disabled])').first().click();await page.screenshot({path:path.join(artifacts,'pos-desktop.png'),fullPage:true});
  await page.locator('nav [data-page=dashboard]').click();await page.locator('.welcome-banner').waitFor();await page.screenshot({path:path.join(artifacts,'dashboard-desktop.png'),fullPage:true});
  await page.setViewportSize({width:768,height:1024});await page.screenshot({path:path.join(artifacts,'dashboard-tablet.png'),fullPage:true});
  await page.locator('nav [data-page=pos]').click();await page.locator('#search').waitFor();await page.screenshot({path:path.join(artifacts,'pos-tablet.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  for(const section of ['dashboard','pos','products','labels','sales','reports','settings']){
   await page.locator(`nav [data-page=${section}]`).click();await page.waitForFunction(section=>document.title.startsWith(({dashboard:'Tableau de bord',pos:'Point de vente',products:'Produits',labels:'Codes-barres',sales:'Ventes',reports:'Rapports',settings:'Paramètres'})[section]),section);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`Horizontal overflow: ${section}`);
   if(section==='dashboard'||section==='pos')await page.screenshot({path:path.join(artifacts,`${section}-mobile.png`),fullPage:true});
  }
  await page.locator('#help').click();await page.getByRole('heading',{name:'À vos côtés, en caisse'}).waitFor();await page.locator('#close-modal').click();
  assert.deepEqual(errors,[]);console.log('PASS: desktop/tablet/mobile, dashboard, catalogue, scan, payment, receipt, labels, navigation, help; no JS errors.');console.log('Screenshots:',artifacts);
 }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.once('exit',r));}
})().catch(e=>{console.error(e);process.exitCode=1});
