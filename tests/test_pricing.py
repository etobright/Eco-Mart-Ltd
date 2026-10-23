import unittest, json, tempfile, subprocess, os, socket, time, urllib.request, urllib.error, http.cookiejar
from decimal import Decimal, ROUND_HALF_UP
import pricing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Pricing(unittest.TestCase):
 def test_threshold_scope_and_rounding(self):
  for qty,total in [(5,50000),(6,51000),(7,59500),(12,102000)]:
   self.assertEqual(pricing.quote([{'price':10000,'qty':qty}])['total'],total)
  self.assertEqual(pricing.quote([{'price':10000,'qty':3},{'price':10000,'qty':3}])['discount'],0)
  lines=[{'price':10000,'qty':6},{'price':20000,'qty':1}]
  self.assertEqual(pricing.quote(lines)['total'],71000)
  self.assertEqual(pricing.quote(lines)['items'][1]['discount'],0)
  self.assertEqual(pricing.quote([{'price':1,'qty':10}])['discount'],2)
  self.assertEqual(pricing.quote([{'price':1,'qty':9},{'price':1,'qty':9}])['discount'],2)
 def test_server_discount_payment_tax_idempotency_and_refund(self):
  with tempfile.TemporaryDirectory() as tmp:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
   p=subprocess.Popen(['python3','server.py'],cwd=ROOT,env={**os.environ,'POS_DB':tmp+'/test.db','POS_PUBLIC':'0','PORT':str(port)},stdout=subprocess.DEVNULL)
   client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
   def call(path,data=None):
    return json.load(client.open(urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})))
   try:
    for _ in range(80):
     try:call('status');break
     except OSError:time.sleep(.03)
    call('setup',{'password':'discount-test-password'})
    call('product',{'name':'Savon','price':'100','stock':'100','barcode':''})
    call('product',{'name':'Riz','price':'200','stock':'100','barcode':''})
    state=call('state');products={item['name']:item for item in state['products']}
    st=state['settings'];call('settings',{**st,'vat_number':'TEST','vat_rate':'15'})
    rows=[{'id':products['Savon']['id'],'qty':6},{'id':products['Riz']['id'],'qty':1}]
    expected=pricing.quote([{'price':10000,'qty':6},{'price':20000,'qty':1}])
    request={'request_key':'discount','lines':rows,'payment':'Espèces','tendered':'800','expected_total':expected['total'],'discount':99999999}
    with self.assertRaises(urllib.error.HTTPError):call('sale',{**request,'tendered':'1'})
    with self.assertRaises(urllib.error.HTTPError):call('sale',{**request,'expected_total':1})
    sale=call('sale',request);self.assertEqual(sale,call('sale',request))
    state=call('state');saved=state['sales'][0];snapshot=json.loads(saved['pricing'])
    self.assertEqual(saved['total'],71000);self.assertEqual(snapshot['items'][0]['discount'],9000);self.assertEqual(snapshot['items'][1]['discount'],0);self.assertEqual(snapshot['subtotal'],80000);self.assertEqual(snapshot['discount'],80000-expected['total']);self.assertEqual(saved['total'],expected['total'])
    self.assertEqual(saved['tax'],int((Decimal(saved['total'])*15/115).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
    self.assertEqual(next(item['stock'] for item in state['products'] if item['name']=='Savon'),94)
    call('refund',sale);state=call('state');self.assertTrue(state['sales'][0]['refunded']);self.assertEqual(state['sales'][0]['pricing'],saved['pricing']);self.assertTrue(all(p['stock']==100 for p in state['products']))
   finally:p.terminate();p.wait()
if __name__=='__main__':unittest.main()
