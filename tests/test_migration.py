import unittest, sqlite3, tempfile, subprocess, os, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DeletionMigration(unittest.TestCase):
 def test_existing_database_is_preserved_and_backed_up(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'legacy.sqlite3'
   with sqlite3.connect(db) as c:
    c.executescript('''
    CREATE TABLE products (id INTEGER PRIMARY KEY,name TEXT NOT NULL,barcode TEXT NOT NULL UNIQUE,category TEXT NOT NULL,price INTEGER NOT NULL,stock INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE movements (id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL);
    INSERT INTO products VALUES(42,'Ancien produit','2001948374145','Épicerie',1000,6,1);
    INSERT INTO movements VALUES(8,42,6,'Inventaire','2026-10-01');
    ''')
   result=subprocess.run(['python3','-c','import server; server.init(); server.init()'],cwd=ROOT,env={**os.environ,'POS_DB':str(db),'POS_PUBLIC':'0'},capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   backups=list(Path(tmp).glob('*.bak'));self.assertEqual(len(backups),1)
   with sqlite3.connect(backups[0]) as backup:self.assertEqual(backup.execute('SELECT product_id,quantity FROM movements').fetchone(),(42,6))
   with sqlite3.connect(db) as c:
    c.execute('PRAGMA foreign_keys=ON')
    self.assertEqual(c.execute('SELECT id,barcode,stock FROM products').fetchone(),(42,'2001948374145',6))
    self.assertEqual(c.execute('SELECT product_id,product_name,quantity FROM movements').fetchone(),(42,'Ancien produit',6))
    self.assertEqual(c.execute('SELECT next_id FROM product_ids').fetchone()[0],43)
    c.execute('DELETE FROM products WHERE id=42')
    self.assertEqual(c.execute('SELECT product_id,product_name FROM movements').fetchone(),(None,'Ancien produit'))
    self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
if __name__=='__main__':unittest.main()
