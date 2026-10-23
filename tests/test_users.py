"""Accounts, authorization and migration on isolated databases."""
import unittest, json, tempfile, subprocess, os, socket, time, urllib.request, urllib.error, http.cookiejar, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Accounts(unittest.TestCase):
 def test_accounts_permissions_attribution_and_revocation(self):
  with tempfile.TemporaryDirectory() as tmp:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
   process=subprocess.Popen(['python3','server.py'],cwd=ROOT,env={**os.environ,'POS_DB':tmp+'/test.db','POS_PUBLIC':'0','PORT':str(port)},stdout=subprocess.DEVNULL)
   def client():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
   admin=client();cashier=client();other=client()
   def call(client,path,data=None):
    return json.load(client.open(urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})))
   def denied(client,path,data=None,status=403):
    with self.assertRaises(urllib.error.HTTPError) as error:call(client,path,data)
    self.assertEqual(error.exception.code,status)
   try:
    for _ in range(100):
     try:call(admin,'status');break
     except OSError:time.sleep(.03)
    for code in ['1234','123456','abcde','12 34','１２３４５']:
     denied(admin,'setup',{'password':code},400)
    call(admin,'setup',{'password':'12345'})
    for code in ['1234','123456','abcde','12 34','１２３４５']:
     denied(admin,'users/save',{'username':'invalid','name':'Invalid','password':code},400)
    call(admin,'users/save',{'username':'caisse1','name':'Alice','role':'cashier','password':'01234'})
    call(admin,'users/save',{'username':'caisse2','name':'Bob','role':'cashier','password':'01234'})
    denied(admin,'users/save',{'username':'CAISSE1','name':'Duplicate','password':'01234'},400)
    call(cashier,'login',{'username':'CAISSE1','password':'01234'})
    call(other,'login',{'username':'caisse2','password':'01234'})
    call(admin,'product',{'name':'Savon','price':'100','stock':'20','barcode':''})
    pid=call(admin,'state')['products'][0]['id']
    sale={'lines':[{'id':pid,'qty':1}],'payment':'Carte','request_key':'alice-sale','cashier_id':1,'cashier_name':'Forged'}
    call(cashier,'sale',sale);call(other,'sale',{**sale,'request_key':'bob-sale'})
    state=call(cashier,'state');self.assertEqual(len(state['sales']),1);self.assertEqual(state['sales'][0]['cashier_name'],'Alice');self.assertEqual(state['users'],[]);self.assertEqual(state['movements'],[])
    self.assertNotIn('password_hash',json.dumps(state))
    self.assertEqual(len(call(admin,'state')['sales']),2)
    for endpoint,data in [('product',{}),('archive',{'id':pid}),('delete-product',{}),('restore',{}),('settings',{}),('returns',{}),('refund',{}),('users/save',{})]:denied(cashier,endpoint,data)
    for endpoint in ['backup','labels/pdf?id='+str(pid)]:denied(cashier,endpoint)
    denied(other,'sale',sale,409)
    users=call(admin,'state')['users'];alice=next(u for u in users if u['username']=='caisse1');admin_user=next(u for u in users if u['role']=='admin')
    denied(admin,'users/save',{**admin_user,'active':False},400)
    call(admin,'users/save',{**alice,'active':False})
    denied(cashier,'state',status=401);denied(cashier,'login',{'username':'caisse1','password':'01234'},401)
    call(admin,'users/save',{**alice,'active':True,'password':'54321'})
    denied(cashier,'login',{'username':'caisse1','password':'01234'},401)
    call(cashier,'login',{'username':'caisse1','password':'54321'})
    call(admin,'users/save',{**alice,'active':True,'password':'98765'})
    denied(cashier,'state',status=401)
    self.assertEqual(call(admin,'state')['sales'][1]['cashier_name'],'Alice')
   finally:process.terminate();process.wait()
 def test_existing_admin_password_migrates_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   script="""import server,json
server.init()
with server.connect() as c:
 s=server.settings(c,True);s['password_hash']=server.password_hash('existing-admin-password');c.execute('UPDATE settings SET value=?',(json.dumps(s),))
server.init();server.init()
with server.connect() as c:
 users=c.execute('SELECT * FROM users').fetchall();assert len(users)==1
 u=users[0];assert u['username']=='admin' and u['role']=='admin'
 assert server.password_hash('existing-admin-password',u['password_hash'].split(':')[0])==u['password_hash']
 assert not server.settings(c,True)['password_hash']
"""
   subprocess.run(['python3','-c',script],cwd=ROOT,env={**os.environ,'POS_DB':tmp+'/migration.db','POS_PUBLIC':'0'},check=True)
if __name__=='__main__':unittest.main()
