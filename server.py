"""Eco Mart POS — local trusted workstation server, Python 3.12+."""
import re, os, json, sqlite3, secrets, hashlib, hmac, time, io
from threading import Lock
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit
from labels import label_pdf
from pricing import PROMOTION, quote
from returns import sale_items, prepare as prepare_return
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
# Content hashes change the asset URLs after each code update, including when
# browsers retain an older stylesheet/script from a previous Render deployment.
ASSET_VERSION = hashlib.sha256(b''.join((ROOT / name).read_bytes() for name in
    ('static/app.js','static/style.css','static/scanner.js','static/pricing.js','server.py','pricing.py','returns.py'))).hexdigest()[:12]
APP_VERSION = os.environ.get('RENDER_GIT_COMMIT') or ASSET_VERSION
DB = Path(os.environ.get('POS_DB', ROOT / 'data/pos.sqlite3'))
SESSIONS = {}
PUBLIC = os.environ.get("POS_PUBLIC") == "1"
AUTH_ATTEMPTS = []
AUTH_LOCK = Lock()

def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init():
    if PUBLIC and len(os.environ.get("POS_SETUP_TOKEN", "")) < 24:
        raise RuntimeError("POS_SETUP_TOKEN (24 caractères minimum) requis en mode public.")
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, barcode TEXT NOT NULL UNIQUE, category TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=0), stock INTEGER NOT NULL CHECK(stock>=0), active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, reference TEXT UNIQUE NOT NULL, created TEXT NOT NULL, total INTEGER NOT NULL, tax INTEGER NOT NULL, payment TEXT NOT NULL, tendered INTEGER NOT NULL, customer TEXT NOT NULL, lines TEXT NOT NULL, company TEXT NOT NULL, refunded INTEGER NOT NULL DEFAULT 0, refund_at TEXT, request_key TEXT UNIQUE NOT NULL, pricing TEXT NOT NULL DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS movements (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER REFERENCES products(id) ON DELETE SET NULL, product_name TEXT NOT NULL, quantity INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_ids (id INTEGER PRIMARY KEY CHECK(id=1), next_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS refunds (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL REFERENCES sales(id), reference TEXT NOT NULL UNIQUE, created TEXT NOT NULL, total INTEGER NOT NULL, tax INTEGER NOT NULL, method TEXT NOT NULL, reason TEXT NOT NULL, lines TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL, legacy INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','cashier')), password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, auth_version INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS refunds_sale_id ON refunds(sale_id);
        ''')
        if 'product_name' not in {r['name'] for r in c.execute('PRAGMA table_info(movements)')}:
            backup_path=DB.with_name(DB.name+'.before-delete-migration-'+secrets.token_hex(4)+'.bak')
            with sqlite3.connect(backup_path) as backup: c.backup(backup)
            os.chmod(backup_path,0o600)
            c.execute('BEGIN IMMEDIATE')
            c.execute("CREATE TABLE movements_new (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER REFERENCES products(id) ON DELETE SET NULL, product_name TEXT NOT NULL, quantity INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL)")
            c.execute("INSERT INTO movements_new SELECT m.id,m.product_id,p.name,m.quantity,m.reason,m.created FROM movements m JOIN products p ON p.id=m.product_id")
            c.execute('DROP TABLE movements')
            c.execute('ALTER TABLE movements_new RENAME TO movements')
        if 'pricing' not in {r['name'] for r in c.execute('PRAGMA table_info(sales)')}:
            c.execute("ALTER TABLE sales ADD COLUMN pricing TEXT NOT NULL DEFAULT '{}'")
        # Existing full refunds become ledger entries without touching stock again.
        for sale in c.execute('SELECT * FROM sales WHERE refunded=1 AND NOT EXISTS(SELECT 1 FROM refunds WHERE sale_id=sales.id)').fetchall():
            lines,paid=sale_items(sale)
            items=[dict(line_index=i,product_id=line['id'],name=line['name'],barcode=line.get('barcode',''),qty=line['qty'],amount=paid[i],restock_requested=None,restocked=None) for i,line in enumerate(lines)]
            c.execute('INSERT INTO refunds(sale_id,reference,created,total,tax,method,reason,lines,request_key,request_hash,legacy) VALUES(?,?,?,?,?,?,?,?,?,?,1)',(sale['id'],'RET-'+sale['reference'],sale['refund_at'] or sale['created'],sale['total'],sale['tax'],sale['payment'],'Ancien remboursement intégral',json.dumps(items),'legacy-full-'+str(sale['id']),'legacy'))
        c.execute('INSERT OR IGNORE INTO product_ids VALUES(1,(SELECT COALESCE(MAX(id),0)+1 FROM products))')
        c.execute('UPDATE product_ids SET next_id=MAX(next_id,(SELECT COALESCE(MAX(id),0)+1 FROM products)) WHERE id=1')
        c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (json.dumps(dict(name='Eco Mart Ltd', address="Royal Road, L’Escalier, Mauritius",brn='C26238002',phone='',vat_number='',vat_rate='0',footer='Merci pour votre visite !',paper='80',password_hash='')),))
        for table,prefix in [('sales','cashier'),('refunds','operator')]:
            columns={r['name'] for r in c.execute('PRAGMA table_info('+table+')')}
            if prefix+'_id' not in columns:
                c.execute('ALTER TABLE '+table+' ADD COLUMN '+prefix+'_id INTEGER')
                c.execute('ALTER TABLE '+table+' ADD COLUMN '+prefix+'_name TEXT')
        old=settings(c,True)
        if old.get('password_hash') and not c.execute('SELECT 1 FROM users').fetchone():
            c.execute("INSERT INTO users(username,name,role,password_hash,created) VALUES('admin','Administrateur','admin',?,?)",(old['password_hash'],now()))
        if old.get('password_hash'):
            old['password_hash']=''
            c.execute('UPDATE settings SET value=? WHERE id=1',(json.dumps(old),))


def movement(c,pid,quantity,reason,name=None):
    if name is None: name=c.execute('SELECT name FROM products WHERE id=?',(pid,)).fetchone()[0]
    c.execute('INSERT INTO movements(product_id,product_name,quantity,reason,created) VALUES(?,?,?,?,?)',(pid,name,quantity,reason,now()))

def now(): return datetime.now(ZoneInfo('Indian/Mauritius')).isoformat(timespec='seconds')
def integer(v, low=0, high=1000000):
    if isinstance(v,bool) or str(v) != str(int(v)) or not low <= int(v) <= high: raise ValueError('Nombre entier invalide.')
    return int(v)
def money(v):
    d=Decimal(str(v))
    if not d.is_finite() or d<0 or d>Decimal('10000000') or d.quantize(Decimal('.01'))!=d: raise ValueError('Montant invalide (2 décimales maximum).')
    return int(d*100)
def checksum(s): return str((-sum(int(x)*(1 if i%2==0 else 3) for i,x in enumerate(s)))%10)
def password_hash(p,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(salt),300000).hex()
def settings(c, private=False):
    s=json.loads(c.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])
    if not private: s.pop('password_hash',None)
    return s

def public_user(user):
    return {k:user[k] for k in ('id','username','name','role','active','created')}

def valid_username(value):
    username=str(value).strip().lower()
    if not re.fullmatch(r'[a-z0-9._-]{3,40}',username): raise ValueError('Identifiant : 3 à 40 lettres sans accent, chiffres, points, tirets ou underscores.')
    return username

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'static'),**kw)
    def send_head(self):
        if self.path.split('?')[0] in ('/', '/index.html'):
            body=(ROOT/'static/index.html').read_text().replace('__ASSET_VERSION__',ASSET_VERSION).encode()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            return io.BytesIO(body)
        return super().send_head()
    def log_message(self,fmt,*args): pass
    def send_json(self,data,status=200):
        b=json.dumps(data,ensure_ascii=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if PUBLIC: self.send_header('Strict-Transport-Security', 'max-age=31536000')
        super().end_headers()
    def session_token(self):
        cookie = SimpleCookie()
        try: cookie.load(self.headers.get('Cookie', ''))
        except Exception: return ''
        return cookie['pos_session'].value if 'pos_session' in cookie else ''
    def current_user(self,c):
        session=SESSIONS.get(self.session_token())
        if not session or session['expires']<=time.time(): return None
        user=c.execute('SELECT * FROM users WHERE id=? AND active=1',(session['user_id'],)).fetchone()
        return user if user and user['auth_version']==session['version'] else None
    def do_GET(self):
        path=self.path.split('?')[0]
        if not path.startswith('/api/'): return super().do_GET()
        with connect() as c:
            if path=='/api/health':
                c.execute('SELECT 1 FROM settings WHERE id=1').fetchone()
                return self.send_json({'ok':True})
            if path=='/api/status': return self.send_json(dict(setup=not bool(c.execute('SELECT 1 FROM users').fetchone()),setup_requires_token=PUBLIC,version=APP_VERSION,authenticated=bool(self.current_user(c))))
            user=self.current_user(c)
            if not user: return self.send_json({'error':'Connexion requise.'},401)
            admin=user['role']=='admin'
            if not admin and path not in ('/api/state',): return self.send_json({'error':'Accès réservé à l’administrateur.'},403)
            if path=='/api/state':
                sales=[dict(r) for r in c.execute('SELECT * FROM sales'+('' if admin else ' WHERE cashier_id=?')+' ORDER BY id DESC',() if admin else (user['id'],))]
                refunds=[dict(r) for r in c.execute('SELECT refunds.* FROM refunds JOIN sales ON sales.id=refunds.sale_id'+('' if admin else ' WHERE sales.cashier_id=?')+' ORDER BY refunds.id DESC',() if admin else (user['id'],))]
                return self.send_json(dict(current_user=public_user(user),users=[public_user(r) for r in c.execute('SELECT * FROM users ORDER BY name')] if admin else [],settings=settings(c),version=APP_VERSION,promotion=PROMOTION,products=[dict(r) for r in c.execute('SELECT * FROM products WHERE active=1 ORDER BY name')],archived_products=[dict(r) for r in c.execute('SELECT * FROM products WHERE active=0 ORDER BY name')] if admin else [],sales=sales,refunds=refunds,movements=[dict(r) for r in c.execute('SELECT m.*,COALESCE(p.name,m.product_name) AS name FROM movements m LEFT JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 500')] if admin else []))
            if path=='/api/labels/pdf':
                try:
                    query=parse_qs(urlsplit(self.path).query)
                    pid=integer(query.get('id',[''])[0],1)
                    count=integer(query.get('count',['1'])[0],1,200)
                    product=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                    if not product: return self.send_json({'error':'Produit introuvable.'},404)
                    b=label_pdf(product,count)
                except (ValueError,TypeError,OverflowError) as e:
                    return self.send_json({'error':str(e)},400)
                self.send_response(200);self.send_header('Content-Type','application/pdf')
                self.send_header('Content-Disposition','attachment; filename="eco-mart-etiquettes-50x25mm.pdf"')
                self.send_header('Content-Length',str(len(b)));self.end_headers();return self.wfile.write(b)
            if path=='/api/backup':
                backup=sqlite3.connect(':memory:');c.backup(backup);b=backup.serialize();backup.close()
                self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition','attachment; filename="eco-mart-backup.sqlite3"');self.send_header('Content-Length',str(len(b)));self.end_headers();return self.wfile.write(b)
        self.send_json({'error':'Introuvable'},404)
    def do_POST(self):
        # Reject cross-origin writes, including login/setup requests.
        origin=self.headers.get('Origin')
        if origin and origin.split('://',1)[-1]!=self.headers.get('Host'): return self.send_json({'error':'Origine refusée'},403)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n>100000: raise ValueError('Requête trop volumineuse')
            d=json.loads(self.rfile.read(n));path=self.path
            with connect() as c:
                c.execute('BEGIN IMMEDIATE')
                s=settings(c,True)
                if path in ['/api/setup','/api/login']:
                    with AUTH_LOCK:
                        cutoff=time.monotonic()-60
                        AUTH_ATTEMPTS[:]=[t for t in AUTH_ATTEMPTS if t>cutoff]
                        if len(AUTH_ATTEMPTS)>=30: return self.send_json({'error':'Trop de tentatives. Réessayez dans une minute.'},429)
                        AUTH_ATTEMPTS.append(time.monotonic())
                    p=str(d.get('password',''))
                    if path.endswith('setup'):
                        if c.execute('SELECT 1 FROM users').fetchone(): raise ValueError('Compte déjà créé.')
                        if PUBLIC and not hmac.compare_digest(str(d.get('setup_token','')),os.environ['POS_SETUP_TOKEN']):
                            return self.send_json({'error':'Code d’activation incorrect. Consultez POS_SETUP_TOKEN dans votre tableau de bord Render.'},403)
                        if len(p)<10: raise ValueError('Choisissez au moins 10 caractères.')
                        username=valid_username(d.get('username','admin'))
                        c.execute("INSERT INTO users(username,name,role,password_hash,created) VALUES(?,?,'admin',?,?)",(username,'Administrateur',password_hash(p),now()))
                    user=c.execute('SELECT * FROM users WHERE username=? AND active=1',(str(d.get('username','admin')).strip().lower(),)).fetchone()
                    stored=user['password_hash'] if user else password_hash('invalid-account')
                    if not user or not hmac.compare_digest(password_hash(p,stored.split(':')[0]),stored):
                        time.sleep(0.5);return self.send_json({'error':'Identifiant ou mot de passe incorrect.'},401)
                    for expired in [k for k,v in list(SESSIONS.items()) if v['expires']<=time.time()]: SESSIONS.pop(expired,None)
                    token=secrets.token_urlsafe(32);SESSIONS[token]=dict(expires=time.time()+43200,user_id=user['id'],version=user['auth_version']);c.commit()
                    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie',f'pos_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+('; Secure' if PUBLIC else ''));self.end_headers();return self.wfile.write(b'{}')
                user=self.current_user(c)
                if not user: return self.send_json({'error':'Connexion requise.'},401)
                if user['role']!='admin' and path not in ('/api/logout','/api/sale'):
                    return self.send_json({'error':'Accès réservé à l’administrateur.'},403)
                if path=='/api/logout':
                    SESSIONS.pop(self.session_token(),None)
                elif path=='/api/users/save':
                    uid=integer(d['id'],1) if d.get('id') else None
                    username=valid_username(d.get('username',''))
                    name=str(d.get('name','')).strip()[:100]
                    role=d.get('role','cashier');active=d.get('active',True)
                    if not name or role not in ('admin','cashier') or not isinstance(active,bool): raise ValueError('Nom, rôle ou statut invalide.')
                    old=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone() if uid else None
                    if uid and not old: raise ValueError('Compte introuvable.')
                    if c.execute('SELECT 1 FROM users WHERE username=? AND id!=?',(username,uid or 0)).fetchone(): raise ValueError('Cet identifiant est déjà utilisé.')
                    if old and old['role']=='admin' and old['active'] and (role!='admin' or not active) and c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1: raise ValueError('Conservez au moins un administrateur actif.')
                    password=str(d.get('password',''))
                    if (not uid or password) and not 10<=len(password)<=200: raise ValueError('Mot de passe : entre 10 et 200 caractères.')
                    if uid:
                        c.execute('UPDATE users SET username=?,name=?,role=?,active=?,auth_version=auth_version+1 WHERE id=?',(username,name,role,int(active),uid))
                        if password: c.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(password),uid))
                    else:
                        c.execute('INSERT INTO users(username,name,role,active,password_hash,created) VALUES(?,?,?,?,?,?)',(username,name,role,int(active),password_hash(password),now()))
                elif path=='/api/product':
                    name=str(d['name']).strip()[:150];category=str(d.get('category','Autres')).strip()[:80] or 'Autres'
                    if not name: raise ValueError('Nom requis.')
                    price=money(d['price']);stock=integer(d['stock']);pid=d.get('id');barcode=str(d.get('barcode','')).strip()
                    if not barcode:
                        for _ in range(50):
                            base='200'+str(secrets.randbelow(10**9)).zfill(9);barcode=base+checksum(base)
                            if not c.execute('SELECT 1 FROM products WHERE barcode=?',(barcode,)).fetchone(): break
                    if not barcode.isascii() or not barcode.isdigit() or len(barcode) not in (8,12,13,14): raise ValueError('Code numérique de 8, 12, 13 ou 14 chiffres requis.')
                    if len(barcode)==13 and checksum(barcode[:12])!=barcode[-1]: raise ValueError('Clé EAN-13 invalide.')
                    if pid: pid=integer(pid,1)
                    duplicate=c.execute('SELECT id,name,active FROM products WHERE barcode=? AND id!=?',(barcode,pid or 0)).fetchone()
                    if duplicate:
                        archived=not duplicate['active']
                        return self.send_json({'error':('Ce code-barres appartient à un produit archivé. Réactivez-le pour le remettre en vente.' if archived else 'Ce code-barres appartient déjà à un produit actif. Modifiez le produit existant.'),'code':('archived_barcode' if archived else 'duplicate_barcode'),'product_id':duplicate['id']},409)
                    if pid:
                        old=c.execute('SELECT stock FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                        if not old: raise ValueError('Produit introuvable.')
                        c.execute('UPDATE products SET name=?,category=?,price=?,stock=?,barcode=? WHERE id=?',(name,category,price,stock,barcode,pid));delta=stock-old[0]
                    else:
                        pid=c.execute('SELECT next_id FROM product_ids WHERE id=1').fetchone()[0]
                        c.execute('UPDATE product_ids SET next_id=next_id+1 WHERE id=1')
                        c.execute('INSERT INTO products(id,name,category,price,stock,barcode) VALUES(?,?,?,?,?,?)',(pid,name,category,price,stock,barcode));delta=stock
                    if delta: movement(c,pid,delta,'Inventaire / réception')
                elif path=='/api/archive': c.execute('UPDATE products SET active=0 WHERE id=?',(integer(d['id'],1),))
                elif path=='/api/delete-product':
                    pid=integer(d['id'],1)
                    if d.get('confirmation')!='SUPPRIMER': raise ValueError('Confirmation de suppression requise.')
                    product=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
                    if not product: return self.send_json({'error':'Produit déjà supprimé ou introuvable.'},404)
                    if d.get('barcode')!=product['barcode']: return self.send_json({'error':'Le produit a changé. Actualisez sa fiche avant de le supprimer.'},409)
                    if product['stock']: movement(c,pid,-product['stock'],'Suppression définitive de la fiche — retrait du stock')
                    c.execute('DELETE FROM products WHERE id=?',(pid,))
                elif path=='/api/restore':
                    pid=integer(d['id'],1)
                    if not c.execute('SELECT id FROM products WHERE id=?',(pid,)).fetchone(): return self.send_json({'error':'Produit introuvable.'},404)
                    c.execute('UPDATE products SET active=1 WHERE id=?',(pid,))
                elif path=='/api/sale':
                    key=str(d['request_key'])[:100]
                    existing=c.execute('SELECT id,cashier_id FROM sales WHERE request_key=?',(key,)).fetchone()
                    if existing:
                        if user['role']!='admin' and existing['cashier_id']!=user['id']: return self.send_json({'error':'Identifiant de vente déjà utilisé.'},409)
                        return self.send_json({'id':existing[0]})
                    if not d['lines']: raise ValueError('Panier vide.')
                    lines=[];total=0;seen=set()
                    for item in d['lines']:
                        pid=integer(item['id'],1);qty=integer(item['qty'],1,100000)
                        if pid in seen: raise ValueError('Produit dupliqué.')
                        seen.add(pid);p=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                        if not p or p['stock']<qty: raise ValueError('Stock insuffisant. Actualisez le panier.')
                        if 'expected_price' in item and item['expected_price'] != p['price']: raise ValueError('Le prix a changé. Actualisez le panier avant de payer.')
                        lines.append(dict(id=pid,name=p['name'],barcode=p['barcode'],qty=qty,price=p['price']));total+=p['price']*qty
                        c.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,pid));movement(c,pid,-qty,'Vente')
                    pricing=quote(lines);total=pricing['total']
                    if 'expected_total' in d and d['expected_total']!=total: raise ValueError('Le total a changé. Actualisez le panier avant de payer.')
                    payment=d['payment']
                    if payment not in ['Espèces','Carte','Virement']: raise ValueError('Mode de paiement invalide.')
                    tendered=money(d['tendered']) if payment=='Espèces' else total
                    if tendered<total: raise ValueError('Montant reçu insuffisant.')
                    rate=Decimal(s['vat_rate']);tax=int((Decimal(total)*rate/(100+rate)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                    company=settings(c);ref='EM-'+datetime.now(ZoneInfo('Indian/Mauritius')).strftime('%Y%m%d')+'-'+secrets.token_hex(4).upper()
                    saleid=c.execute('INSERT INTO sales(reference,created,total,tax,payment,tendered,customer,lines,company,request_key,pricing,cashier_id,cashier_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(ref,now(),total,tax,payment,tendered,str(d.get('customer',''))[:200],json.dumps(lines),json.dumps(company),key,json.dumps(pricing),user['id'],user['name'])).lastrowid
                    c.commit();return self.send_json({'id':saleid})
                elif path in ('/api/returns','/api/refund'):
                    legacy=path=='/api/refund'
                    sid=integer(d['id'] if legacy else d['sale_id'],1)
                    key=str(d.get('request_key',''))
                    if not legacy and not 8<=len(key)<=100: raise ValueError('Identifiant de retour invalide.')
                    key=key or secrets.token_urlsafe(24)
                    digest=hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
                    existing=c.execute('SELECT * FROM refunds WHERE request_key=?',(key,)).fetchone()
                    if existing:
                        if existing['sale_id']!=sid or existing['request_hash']!=digest: return self.send_json({'error':'Cet identifiant de retour a déjà été utilisé pour une autre demande.'},409)
                        skipped=[{'name':i['name'],'qty':i['qty']} for i in json.loads(existing['lines']) if i['restock_requested'] and not i['restocked']]
                        return self.send_json({'ok':True,'refund_id':existing['id'],'total':existing['total'],'skipped_restock':skipped})
                    sale=c.execute('SELECT * FROM sales WHERE id=?',(sid,)).fetchone()
                    if not sale: raise ValueError('Vente introuvable.')
                    records=c.execute('SELECT * FROM refunds WHERE sale_id=? ORDER BY id',(sid,)).fetchall()
                    if legacy and records: raise ValueError('Ce ticket a déjà un retour. Utilisez « Retour / Retirer des articles » pour les quantités restantes.')
                    requested=d.get('items')
                    if legacy: requested=[{'line_index':i,'qty':line['qty'],'restock':True} for i,line in enumerate(json.loads(sale['lines']))]
                    items,total,tax,fully_returned=prepare_return(sale,records,requested)
                    if 'expected_total' in d and d['expected_total']!=total: return self.send_json({'error':'Le montant a changé après un autre retour. Rouvrez le ticket et vérifiez les quantités.'},409)
                    method=sale['payment'] if legacy else d.get('method')
                    if method not in ['Espèces','Carte','Virement']: raise ValueError('Mode de remboursement invalide.')
                    reason=str(d.get('reason','Retour client')).strip()[:300] or 'Retour client'
                    reference='RET-'+datetime.now(ZoneInfo('Indian/Mauritius')).strftime('%Y%m%d')+'-'+secrets.token_hex(4).upper()
                    skipped=[]
                    for item in items:
                        product=c.execute('SELECT id FROM products WHERE id=?',(item['product_id'],)).fetchone()
                        item['restocked']=bool(item['restock_requested'] and product)
                        if item['restocked']:
                            c.execute('UPDATE products SET stock=stock+? WHERE id=?',(item['qty'],item['product_id']))
                            movement(c,item['product_id'],item['qty'],'Retour '+reference)
                        else:
                            if item['restock_requested']: skipped.append({'name':item['name'],'qty':item['qty']})
                            movement(c,item['product_id'] if product else None,0,'Retour '+reference+' — '+str(item['qty'])+' unité(s) sans remise en stock',item['name'])
                    rid=c.execute('INSERT INTO refunds(sale_id,reference,created,total,tax,method,reason,lines,request_key,request_hash,operator_id,operator_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,reference,now(),total,tax,method,reason,json.dumps(items),key,digest,user['id'],user['name'])).lastrowid
                    if fully_returned: c.execute('UPDATE sales SET refunded=1,refund_at=? WHERE id=?',(now(),sid))
                    c.commit();return self.send_json({'ok':True,'refund_id':rid,'total':total,'skipped_restock':skipped})
                elif path=='/api/settings':
                    for k in ['name','address','brn','phone','vat_number','footer']: s[k]=str(d.get(k,s[k])).strip()[:300]
                    rate=Decimal(str(d['vat_rate']))
                    if not rate.is_finite() or not 0<=rate<=100: raise ValueError('Taux de TVA invalide.')
                    if rate and not s['vat_number']: raise ValueError('Numéro de TVA requis avant activation.')
                    s['vat_rate']=str(rate);s['paper']=str(d['paper'])
                    if s['paper'] not in ['58','80']: raise ValueError('Largeur invalide.')
                    if not s['name']: raise ValueError('Raison sociale requise.')
                    c.execute('UPDATE settings SET value=?',(json.dumps(s),))
                else: return self.send_json({'error':'Introuvable'},404)
            self.send_json({'ok':True})
        except sqlite3.IntegrityError: self.send_json({'error':'Code-barres déjà utilisé ou données invalides.'},400)
        except (ValueError,KeyError,TypeError,InvalidOperation,OverflowError) as e: self.send_json({'error':str(e) or 'Données invalides.'},400)

if __name__=='__main__':
    init();print('Eco Mart POS: http://127.0.0.1:'+os.environ.get('PORT','8000'),flush=True)
    ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
