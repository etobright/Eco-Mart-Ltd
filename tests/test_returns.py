import unittest, tempfile, subprocess, os, json, socket, time, sqlite3, urllib.request, urllib.error, http.cookiejar
from pathlib import Path
from returns import prepare, portion
ROOT=Path(__file__).resolve().parents[1]
class ReturnAllocation(unittest.TestCase):
 def test_cent_rounding_is_exhaustive_across_separate_returns(self):
  sale={'lines':json.dumps([{'id':1,'name':'Petite ligne','qty':6,'price':1}]),'pricing':json.dumps({'items':[{'total':5}]}),'total':5,'tax':1}
  records=[];amounts=[];taxes=[]
  for _ in range(6):
   items,total,tax,full=prepare(sale,records,[{'line_index':0,'qty':1,'restock':False}]);records.append({'total':total,'lines':json.dumps(items)});amounts.append(total);taxes.append(tax)
  self.assertTrue(full);self.assertEqual(sum(amounts),5);self.assertEqual(sum(taxes),1)
  with self.assertRaises(ValueError):prepare(sale,records,[{'line_index':0,'qty':1,'restock':False}])
class PartialReturns(unittest.TestCase):
 def test_discounted_returns_stock_idempotency_and_limits(self):
  with tempfile.TemporaryDirectory() as tmp:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();url=f'http://127.0.0.1:{port}'
   proc=subprocess.Popen(['python3','server.py'],cwd=ROOT,env={**os.environ,'POS_DB':tmp+'/db.sqlite3','POS_PUBLIC':'0','PORT':str(port)},stdout=subprocess.DEVNULL)
   client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
   def call(route,data=None):return json.load(client.open(urllib.request.Request(url+'/api/'+route,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})))
   try:
    for _ in range(100):
     try:call('status');break
     except OSError:time.sleep(.03)
    call('setup',{'password':'partial-return-test'})
    call('product',{'name':'Savon','price':'100','stock':'20','barcode':''});call('product',{'name':'Riz','price':'200','stock':'20','barcode':''})
    state=call('state');products={p['name']:p for p in state['products']};st=state['settings'];call('settings',{**st,'vat_number':'TEST','vat_rate':'15'})
    sid=call('sale',{'request_key':'original-sale','lines':[{'id':products['Savon']['id'],'qty':6},{'id':products['Riz']['id'],'qty':1}],'payment':'Espèces','tendered':'800'})['id']
    original=call('state')['sales'][0];self.assertEqual(original['total'],71000)
    request={'sale_id':sid,'request_key':'partial-return-1','items':[{'line_index':0,'qty':1,'restock':False}],'method':'Espèces','reason':'Produit ouvert','expected_total':8500}
    first=call('returns',request);self.assertEqual(first['total'],8500);self.assertEqual(call('returns',request),first)
    state=call('state');self.assertFalse(state['sales'][0]['refunded']);self.assertEqual(len(state['refunds']),1);self.assertEqual(next(p['stock'] for p in state['products'] if p['name']=='Savon'),14)
    for payload in [{**request,'items':[{'line_index':0,'qty':2,'restock':False}]},{**request,'request_key':'too-many-units','items':[{'line_index':0,'qty':6,'restock':True}]},{**request,'request_key':'wrong-total','expected_total':1},{**request,'request_key':'duplicate-lines','items':[{'line_index':0,'qty':1,'restock':True}]*2}]:
     with self.assertRaises(urllib.error.HTTPError):call('returns',payload)
    state=call('state');self.assertEqual(len(state['refunds']),1)
    # Deletion and reusing a barcode must never credit stock to the replacement.
    soap=products['Savon'];call('delete-product',{'id':soap['id'],'barcode':soap['barcode'],'confirmation':'SUPPRIMER'});call('product',{'name':'Autre savon','price':'300','stock':'3','barcode':soap['barcode']})
    second=call('returns',{'sale_id':sid,'request_key':'partial-return-2','items':[{'line_index':0,'qty':5,'restock':True},{'line_index':1,'qty':1,'restock':True}],'method':'Carte','reason':'Solde du retour','expected_total':62500})
    self.assertEqual(second['skipped_restock'],[{'name':'Savon','qty':5}]);state=call('state');self.assertTrue(state['sales'][0]['refunded']);self.assertEqual(state['sales'][0]['total'],original['total']);self.assertEqual(state['sales'][0]['lines'],original['lines']);self.assertEqual(state['sales'][0]['pricing'],original['pricing'])
    self.assertEqual(sum(r['total'] for r in state['refunds']),original['total']);self.assertEqual(sum(r['tax'] for r in state['refunds']),original['tax']);self.assertEqual(next(p['stock'] for p in state['products'] if p['name']=='Riz'),20);self.assertEqual(next(p['stock'] for p in state['products'] if p['name']=='Autre savon'),3)
    with self.assertRaises(urllib.error.HTTPError):call('returns',{**request,'request_key':'already-returned'})
    # Two independent clerks cannot both return five of six units.
    from concurrent.futures import ThreadPoolExecutor
    race_id=call('sale',{'request_key':'concurrent-original','lines':[{'id':products['Riz']['id'],'qty':6}],'payment':'Carte','tendered':'0'})['id']
    def race_return(i):
     try:return call('returns',{'sale_id':race_id,'request_key':'concurrent-return-'+str(i),'items':[{'line_index':0,'qty':5,'restock':True}],'method':'Carte'})
     except urllib.error.HTTPError as e:return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(race_return,[1,2]))
    self.assertEqual(sum(isinstance(r,dict) for r in results),1);self.assertIn(400,results)
    state=call('state');self.assertEqual(len([r for r in state['refunds'] if r['sale_id']==race_id]),1);self.assertEqual(next(p['stock'] for p in state['products'] if p['name']=='Riz'),19)
    # Authorization applies to the new financial endpoint.
    call('logout',{})
    with self.assertRaises(urllib.error.HTTPError) as denied:call('returns',request)
    self.assertEqual(denied.exception.code,401)
   finally:proc.terminate();proc.wait()
 def test_legacy_full_refunds_migrate_once_without_stock_changes(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'legacy.db'
   result=subprocess.run(['python3','-c','import server; server.init()'],cwd=ROOT,env={**os.environ,'POS_DB':str(db),'POS_PUBLIC':'0'},capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
   with sqlite3.connect(db) as c:
    c.execute("INSERT INTO products VALUES(9,'Produit historique','2001948374145','Épicerie',1000,12,1)")
    c.execute("INSERT INTO sales(reference,created,total,tax,payment,tendered,customer,lines,company,refunded,refund_at,request_key) VALUES('OLD','2026-10-01',2000,0,'Carte',2000,'',?,'{}',1,'2026-10-02','old')",(json.dumps([{'id':9,'name':'Produit historique','barcode':'2001948374145','qty':2,'price':1000}]),))
   result=subprocess.run(['python3','-c','import server; server.init(); server.init()'],cwd=ROOT,env={**os.environ,'POS_DB':str(db),'POS_PUBLIC':'0'},capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
   with sqlite3.connect(db) as c:
    self.assertEqual(c.execute('SELECT COUNT(*),SUM(total) FROM refunds').fetchone(),(1,2000));self.assertEqual(c.execute('SELECT stock FROM products').fetchone()[0],12);self.assertEqual(c.execute('SELECT created FROM refunds').fetchone()[0],'2026-10-02')
if __name__=='__main__':unittest.main()
