"""Public Render entry point, tested in a fresh interpreter and database."""
import os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PublicWSGI(unittest.TestCase):
 def test_public_entry_point(self):
  script=r'''
import io,json
from wsgi import application
cookie=''
def call(path,data=None,method=None,origin=None,modified_since=None):
 global cookie
 raw=b'' if data is None else json.dumps(data).encode()
 env={'REQUEST_METHOD':method or ('GET' if data is None else 'POST'),'PATH_INFO':path,'wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json','HTTP_HOST':'eco.example','HTTP_COOKIE':cookie}
 if origin:env['HTTP_ORIGIN']=origin
 if modified_since:env['HTTP_IF_MODIFIED_SINCE']=modified_since
 result={}
 def start(status,headers):result.update(status=int(status[:3]),headers=dict(headers))
 result['body']=b''.join(application(env,start))
 if 'Set-Cookie' in result['headers']:cookie=result['headers']['Set-Cookie'].split(';')[0]
 return result
assert call('/api/health')['status']==200
home=call('/',modified_since='Wed, 31 Dec 2099 23:59:59 GMT')
assert home['status']==200 and home['headers']['Cache-Control']=='no-store'
assert b'__ASSET_VERSION__' not in home['body']
assert b'/app.js?v=' in home['body'] and b'/style.css?v=' in home['body']
assert call('/index.html')['body']==home['body']
assert call('/app.js')['headers']['Cache-Control']=='no-store'
assert call('/app.js')['status']==200
assert call('/manifest.webmanifest')['status']==200
assert call('/api/state')['status']==401
assert call('/api/labels/pdf')['status']==401
status=json.loads(call('/api/status')['body']);assert status['setup'] and status['setup_requires_token']
assert call('/api/setup',{'password':'a-long-test-password'})['status']==403
assert call('/api/setup',{'password':'a-long-test-password','setup_token':'test-activation-token-long-enough'},origin='https://evil.example')['status']==403
setup=call('/api/setup',{'password':'a-long-test-password','setup_token':'test-activation-token-long-enough'},origin='https://eco.example')
assert setup['status']==200,setup
assert 'Secure' in setup['headers']['Set-Cookie']
assert 'HttpOnly' in setup['headers']['Set-Cookie']
assert setup['headers']['X-Frame-Options']=='DENY'
assert call('/api/state')['status']==200
assert call('/api/product',{'name':'Produit Render','price':'50','stock':'4','barcode':''})['status']==200
product=json.loads(call('/api/state')['body'])['products'][0]
# Query parsing, PDF output and limits also work through the production adapter.
pdf_env={'REQUEST_METHOD':'GET','PATH_INFO':'/api/labels/pdf','QUERY_STRING':f'id={product["id"]}&count=2','wsgi.input':io.BytesIO(b''),'HTTP_HOST':'eco.example','HTTP_COOKIE':cookie}
pdf_result={}
def pdf_start(status,headers):pdf_result.update(status=int(status[:3]),headers=dict(headers))
pdf=b''.join(application(pdf_env,pdf_start))
assert pdf_result['status']==200 and pdf_result['headers']['Content-Type']=='application/pdf'
assert pdf.startswith(b'%PDF-1.4') and b'/Count 2' in pdf
assert b'/MediaBox [0 0 141.732283 70.866142]' in pdf
pdf_env['QUERY_STRING']=f'id={product["id"]}&count=201'
b''.join(application(pdf_env,pdf_start));assert pdf_result['status']==400
assert call('/api/sale',{'request_key':'render-test','lines':[{'id':product['id'],'qty':1,'expected_price':5000}],'payment':'Carte','tendered':'0'})['status']==200
assert call('/api/backup')['body'].startswith(b'SQLite format 3')
assert call('/api/logout',{})['status']==200
assert call('/api/state')['status']==401
assert call('/api/login',{'password':'a-long-test-password'})['status']==200
assert len(json.loads(call('/api/state')['body'])['sales'])==1
print('Public WSGI workflow passed')
'''
  with tempfile.TemporaryDirectory() as tmp:
   env={**os.environ,'POS_DB':tmp+'/test.db','POS_PUBLIC':'1','POS_SETUP_TOKEN':'test-activation-token-long-enough'}
   result=subprocess.run(['python3','-c',script],cwd=ROOT,env=env,capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
