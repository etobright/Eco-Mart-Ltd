import unittest, tempfile, subprocess, os, json, urllib.request, urllib.error, http.cookiejar, socket, time, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class POS(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.db=cls.tmp.name+'/test.db'
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();cls.url=f'http://127.0.0.1:{port}'
  cls.proc=subprocess.Popen(['python3','server.py'],cwd=ROOT,env={**os.environ,'POS_DB':cls.db,'PORT':str(port)},stdout=subprocess.DEVNULL)
  cls.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  for _ in range(80):
   try: cls.call('status');break
   except OSError: time.sleep(.05)
 @classmethod
 def tearDownClass(cls): cls.proc.terminate();cls.proc.wait();cls.tmp.cleanup()
 @classmethod
 def call(cls,path,data=None):
  r=cls.http.open(urllib.request.Request(cls.url+'/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'}));return json.load(r)
 def test_workflow(self):
  self.assertTrue(self.call('status')['setup'])
  with self.assertRaises(urllib.error.HTTPError):self.call('state')
  self.call('setup',{'password':'test-password-123'})
  self.call('product',dict(name='Riz',category='Épicerie',price='42.50',stock='10',barcode=''))
  p=self.call('state')['products'][0];self.assertEqual(len(p['barcode']),13)
  with self.assertRaises(urllib.error.HTTPError):self.call('product',dict(name='Duplicata',price='2',stock='1',barcode=p['barcode']))
  request=dict(request_key='sale-1',lines=[dict(id=p['id'],qty=2)],payment='Espèces',tendered='100',customer='Client test')
  sale=self.call('sale',request);self.assertEqual(sale,self.call('sale',request))
  s=self.call('state');self.assertEqual(s['products'][0]['stock'],8);self.assertEqual(s['sales'][0]['total'],8500)
  self.assertEqual(s['sales'][0]['tax'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('sale',{**request,'request_key':'sale-2','lines':[dict(id=p['id'],qty=99)]})
  self.assertEqual(self.call('state')['products'][0]['stock'],8)
  with self.assertRaises(urllib.error.HTTPError):self.call('sale',{**request,'request_key':'sale-3','tendered':'1'})
  self.assertEqual(self.call('state')['products'][0]['stock'],8)
  self.call('refund',sale)
  self.assertEqual(self.call('state')['products'][0]['stock'],10)
  with self.assertRaises(urllib.error.HTTPError):self.call('refund',sale)
  st=self.call('state')['settings'];self.call('settings',{**st,'vat_number':'TEST','vat_rate':'15'})
  new=self.call('sale',{**request,'request_key':'sale-4','payment':'Carte'})
  ss=self.call('state')['sales'][0];self.assertEqual(ss['tax'],1109)
  self.assertEqual(json.loads(self.call('state')['sales'][1]['company'])['vat_rate'],'0')
  backup=self.http.open(self.url+'/api/backup').read();self.assertTrue(backup.startswith(b'SQLite format 3'))
  before_archive=self.call('state');original=before_archive['products'][0]
  self.call('archive',{'id':p['id']});self.assertEqual(self.call('state')['products'],[])
  archived=self.call('state')['archived_products'][0];self.assertEqual(archived['barcode'],p['barcode']);self.assertEqual(archived['stock'],original['stock'])
  with self.assertRaises(urllib.error.HTTPError) as conflict:self.call('product',dict(name='Nouveau nom à ne pas appliquer',price='999',stock='999',barcode=p['barcode']))
  self.assertEqual(conflict.exception.code,409)
  payload=json.load(conflict.exception);self.assertEqual(payload['code'],'archived_barcode');self.assertEqual(payload['product_id'],p['id'])
  with self.assertRaises(urllib.error.HTTPError):self.call('sale',{**request,'request_key':'archived-sale'})
  self.call('restore',{'id':p['id']});self.call('restore',{'id':p['id']})
  restored=self.call('state');self.assertEqual(restored['archived_products'],[]);self.assertEqual(len(restored['products']),1)
  self.assertEqual(restored['products'][0],original);self.assertEqual(restored['sales'],before_archive['sales']);self.assertEqual(restored['movements'],before_archive['movements'])
  with self.assertRaises(urllib.error.HTTPError):self.call('restore',{'id':99999})
  self.call('logout',{})
  with self.assertRaises(urllib.error.HTTPError):self.call('state')
  self.call('login',{'password':'test-password-123'})
  self.assertEqual(len(self.call('state')['sales']),2)
  sales_before=self.call('state')['sales']
  with self.assertRaises(urllib.error.HTTPError):self.call('delete-product',{'id':p['id'],'barcode':p['barcode']})
  self.assertEqual(len(self.call('state')['products']),1)
  with self.assertRaises(urllib.error.HTTPError):self.call('delete-product',{'id':p['id'],'barcode':'wrong','confirmation':'SUPPRIMER'})
  self.call('delete-product',{'id':p['id'],'barcode':p['barcode'],'confirmation':'SUPPRIMER'})
  after=self.call('state');self.assertEqual(after['products'],[]);self.assertEqual(after['archived_products'],[]);self.assertEqual(after['sales'],sales_before)
  self.assertTrue(after['movements']);self.assertTrue(all(m['product_id'] is None for m in after['movements']))
  self.call('product',dict(name='Nouvelle fiche',category='Épicerie',price='9',stock='7',barcode=p['barcode']))
  replacement=self.call('state')['products'][0];self.assertGreater(replacement['id'],p['id']);self.assertEqual(replacement['barcode'],p['barcode'])
  refunded=self.call('refund',new);self.assertEqual(refunded['skipped_restock'],[{'name':'Riz','qty':2}]);self.assertEqual(self.call('state')['products'][0]['stock'],7)
  self.call('archive',{'id':replacement['id']});self.call('delete-product',{'id':replacement['id'],'barcode':p['barcode'],'confirmation':'SUPPRIMER'});self.assertEqual(self.call('state')['archived_products'],[])

if __name__=='__main__':unittest.main()
