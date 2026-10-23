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
  await page.locator('.layout>aside nav [data-page=products]').click();await page.locator('#add-product').click();await page.locator('[name=name]').fill('Riz basmati · 1 kg');await page.locator('[name=price]').fill('85');await page.locator('[name=stock]').fill('20');await page.locator('#product-form button[type=submit], #product-form .primary').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);
  // Archival reserves a code; restore the same product instead of creating a duplicate.
  const initial=(await(await page.request.get(url+'/api/state')).json()).products[0];
  async function archiveInitial(){await page.locator(`[data-edit="${initial.id}"]`).click();page.once('dialog',d=>d.accept());await page.locator('#archive').click();await page.waitForFunction(()=>!document.querySelector('dialog').open)}
  await archiveInitial();await page.locator('[data-product-status=archived]').click();await page.locator(`[data-restore="${initial.id}"]`).waitFor();
  await page.locator('#add-product').click();await page.locator('[name=name]').fill('Doublon à ne pas créer');await page.locator('[name=barcode]').fill(initial.barcode);await page.locator('[name=price]').fill('999');await page.locator('[name=stock]').fill('999');await page.locator('#product-form .primary').click();await page.locator('#product-error button').waitFor();assert.match(await page.locator('#product-error').innerText(),/archivé/);await page.locator('#product-error button').click();await page.waitForFunction(()=>document.querySelector('[name=name]')?.value==='Riz basmati · 1 kg');assert.equal(await page.locator('[name=stock]').inputValue(),'20');assert.equal(await page.locator('[name=price]').inputValue(),'85.00');await page.locator('#close-modal').click();
  await archiveInitial();await page.locator('[data-product-status=archived]').click();await page.locator(`[data-restore="${initial.id}"]`).click();await page.waitForFunction(()=>document.querySelector('[name=name]')?.value==='Riz basmati · 1 kg');await page.locator('#close-modal').click();
  // Delete a separate fixture through both UI entry points without touching sale fixtures.
  const deleting=await page.request.post(url+'/api/product',{data:{name:'À supprimer',price:'2',stock:'3',barcode:''}});assert.ok(deleting.ok());let deletionState=await(await page.request.get(url+'/api/state')).json();const doomed=deletionState.products.find(p=>p.name==='À supprimer');
  await page.locator('.layout>aside nav [data-page=products]').click();await page.locator(`[data-edit="${doomed.id}"]`).click();await page.locator('#delete-product').click();await page.locator('#cancel-delete').click();assert.equal(await page.locator('[name=name]').inputValue(),'À supprimer');await page.locator('#delete-product').click();await page.locator('#delete-confirmation').fill('SUPPRIMER');await page.locator('#confirm-delete').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);
  const reuse=await page.request.post(url+'/api/product',{data:{name:'Code réutilisé',price:'3',stock:'4',barcode:doomed.barcode}});assert.ok(reuse.ok());deletionState=await(await page.request.get(url+'/api/state')).json();const replacement=deletionState.products.find(p=>p.name==='Code réutilisé');assert.ok(replacement.id>doomed.id);await page.request.post(url+'/api/archive',{data:{id:replacement.id}});await page.locator('.layout>aside nav [data-page=products]').click();await page.locator('[data-product-status=archived]').click();await page.locator(`[data-delete-product="${replacement.id}"]`).click();await page.locator('#delete-confirmation').fill('SUPPRIMER');await page.locator('#confirm-delete').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);await page.locator('[data-product-status=active]').click();
  const fixtures=[['Lait entier · 1 L','Produits laitiers','65',15],['Jus de mangue · 1 L','Boissons','75',10],['Pommes rouges · pièce','Fruits & légumes','18',4],['Pain de campagne','Boulangerie','45',12],['Farine de blé · 1 kg','Épicerie','42',18],['Savon doux','Entretien','35',3],['Eau minérale · 1,5 L','Boissons','25',0]];
  for(const [name,category,price,stock]of fixtures){const r=await page.request.post(url+'/api/product',{data:{name,category,price,stock:String(stock),barcode:''}});assert.ok(r.ok())}
  await page.locator('.layout>aside nav [data-page=pos]').click();await page.locator('#search').waitFor();assert.equal(await page.locator('[data-add]').count(),8);
  const state=await(await page.request.get(url+'/api/state')).json();const rice=state.products.find(p=>p.name.startsWith('Riz'));
  await page.locator('#search').fill(rice.barcode);await page.locator('#search').press('Enter');assert.equal(await page.locator('#cart-count').innerText(),'1');
  const azerty=['à','&','é','"',"'",'(','-','è','_','ç'];const encoded=[...rice.barcode].map(c=>azerty[+c]).join('');
  await page.locator('#search').fill(encoded);await page.locator('#search').press('Enter');assert.equal(await page.locator('#cart-count').innerText(),'2');
  await page.locator(`[data-step="${rice.id}"][data-delta="-1"]`).click();
  await page.locator('#test-scanner').click();await page.locator('#scanner-test-input').fill(encoded);await page.locator('#scanner-test-input').press('Enter');await page.getByText('Produit reconnu :',{exact:false}).waitFor();assert.match(await page.locator('#scanner-test-result').innerText(),new RegExp(rice.barcode));assert.equal(await page.locator('#cart-count').innerText(),'1');await page.locator('#close-modal').click();
  // A product added on a different terminal must be discovered without reloading.
  const late=await page.request.post(url+'/api/product',{data:{name:'Nouveau sur un autre poste',price:'1',stock:'2',barcode:''}});assert.ok(late.ok());const updated=await(await page.request.get(url+'/api/state')).json();const newProduct=updated.products.find(p=>p.name==='Nouveau sur un autre poste');
  await page.locator('#search').fill(newProduct.barcode);await page.locator('#search').press('Enter');await page.waitForFunction(()=>document.querySelector('#cart-count').textContent==='2');await page.locator(`[data-step="${newProduct.id}"][data-delta="-1"]`).click();
  await page.locator('#checkout').click();await page.locator('#tendered').fill('100');assert.match(await page.locator('#change').innerText(),/15/);await page.locator('#pay-submit').click();await page.locator('#print-receipt').waitFor();assert.match(await page.locator('.receipt').innerText(),/C26238002/);
  await page.evaluate(()=>window.print=()=>{});await page.locator('#print-receipt').click();assert.match(await page.locator('#print-area').innerText(),/85/);await page.locator('#close-modal').click();
  await page.locator('.layout>aside nav [data-page=labels]').click();await page.locator('#label-search').fill('Riz');assert.equal(await page.locator('[data-label]').count(),1);await page.locator('[data-label]').click();await page.locator('#label-count').fill('2');await page.locator('#print-label').click();assert.equal(await page.locator('#print-area .print-label').count(),2);
  const downloadPromise=page.waitForEvent('download');await page.locator('#download-label-pdf').click();const download=await downloadPromise;await download.saveAs(path.join(artifacts,'labels-exact.pdf'));
  await page.emulateMedia({media:'print'});
  const labelBounds=await page.locator('#print-area .print-label').evaluateAll(labels=>labels.map(label=>{const box=label.getBoundingClientRect(),price=label.querySelector('.label-price').getBoundingClientRect(),barcode=label.querySelector('.barcode').getBoundingClientRect();return {bottom:box.bottom,priceBottom:price.bottom,priceTop:price.top,barcodeBottom:barcode.bottom,width:box.width,height:box.height}}));
  for(const b of labelBounds){assert.ok(b.priceBottom<=b.bottom-2,'Printed price must fit inside label with bottom clearance');assert.ok(b.priceTop>=b.barcodeBottom,'Price must not overlap barcode');assert.ok(Math.abs(b.height-25*96/25.4)<1,'Label must stay 25mm high')}
  await page.pdf({path:path.join(artifacts,'labels.pdf'),preferCSSPageSize:true,printBackground:true});
  await page.emulateMedia({media:'screen'});await page.locator('#close-modal').click();
  await page.locator('.layout>aside nav [data-page=pos]').click();await page.locator('#search').waitFor();await page.locator('[data-add]:not([disabled])').first().click();await page.screenshot({path:path.join(artifacts,'pos-desktop.png'),fullPage:true});
  await page.locator('.layout>aside nav [data-page=dashboard]').click();await page.locator('.welcome-banner').waitFor();await page.screenshot({path:path.join(artifacts,'dashboard-desktop.png'),fullPage:true});
  await page.setViewportSize({width:768,height:1024});await page.screenshot({path:path.join(artifacts,'dashboard-tablet.png'),fullPage:true});
  await page.locator('.layout>aside nav [data-page=pos]').click();await page.locator('#search').waitFor();await page.screenshot({path:path.join(artifacts,'pos-tablet.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.locator('.mobile-bottom-nav').waitFor({state:'visible'});assert.ok(await page.locator('.mobile-bottom-nav button>span').getByText('Accueil',{exact:true}).isVisible());
  assert.equal(await page.locator('.layout>aside').isVisible(),false);
  for(const section of ['dashboard','pos','products','labels','sales','reports','settings']){
   if(['labels','reports','settings'].includes(section)){
    await page.locator('#mobile-more').click();await page.locator('#mobile-more-content').waitFor();assert.equal(await page.locator('#mobile-more').getAttribute('aria-expanded'),'true');await page.locator(`#mobile-more-content [data-page=${section}]`).click();await page.waitForFunction(()=>!document.querySelector('dialog').open);
   }else await page.locator(`.mobile-bottom-nav [data-page=${section}]`).click();await page.waitForFunction(section=>document.title.startsWith(({dashboard:'Tableau de bord',pos:'Point de vente',products:'Produits',labels:'Codes-barres',sales:'Ventes',reports:'Rapports',settings:'Paramètres'})[section]),section);
   if(section==='products')assert.ok(await page.locator('[data-product-status=archived]').isVisible());
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`Horizontal overflow: ${section}`);
   assert.ok(await page.locator('.mobile-bottom-nav').evaluate(el=>Math.abs(el.getBoundingClientRect().bottom-window.innerHeight)<1),'Mobile tabs must stay at the bottom');
   if(section==='pos')assert.ok(await page.locator('#mobile-cart').evaluate(el=>el.getBoundingClientRect().bottom<document.querySelector('.mobile-bottom-nav').getBoundingClientRect().top),'Cart must sit above bottom tabs');
   if(section==='dashboard'||section==='pos')await page.screenshot({path:path.join(artifacts,`${section}-mobile.png`),fullPage:false});
  }
  await page.locator('#mobile-account').click();await page.locator('#mobile-more-content').waitFor();await page.screenshot({path:path.join(artifacts,'mobile-more-menu.png'),fullPage:false});await page.locator('#close-modal').click();await page.waitForFunction(()=>document.querySelector('#mobile-more').getAttribute('aria-expanded')==='false');
  for(const width of [320,430]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`Overflow at ${width}px`)}
  await page.setViewportSize({width:1440,height:1060});assert.ok(await page.locator('.layout>aside').isVisible());assert.equal(await page.locator('.mobile-bottom-nav').isVisible(),false);assert.equal(await page.locator('.mobile-brand').isVisible(),false);
  await page.locator('#help').click();await page.getByRole('heading',{name:'À vos côtés, en caisse'}).waitFor();await page.locator('#close-modal').click();
  assert.deepEqual(errors,[]);console.log('PASS: desktop/tablet/mobile, dashboard, catalogue, scan, payment, receipt, labels, navigation, help; no JS errors.');console.log('Screenshots:',artifacts);
 }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.once('exit',r));}
})().catch(e=>{console.error(e);process.exitCode=1});
