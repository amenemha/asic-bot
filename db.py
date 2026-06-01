import sqlite3, time, os

DB = "/data/bot.db"

def conn():
    os.makedirs("/data", exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      user_id INTEGER PRIMARY KEY,
      username TEXT,
      first_name TEXT,
      kwh_price REAL,
      asic_price REAL,
      premium INTEGER DEFAULT 0,
      created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS requests(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      kind TEXT,
      payload TEXT,
      created_at INTEGER
    );
    """)
    c.commit(); c.close()

def upsert_user(uid, username, first_name):
    c = conn()
    c.execute("INSERT OR IGNORE INTO users(user_id,username,first_name,created_at) VALUES(?,?,?,?)",
              (uid, username, first_name, int(time.time())))
    c.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
              (username, first_name, uid))
    c.commit(); c.close()

def get_user(uid):
    c = conn()
    r = c.execute("SELECT user_id,username,first_name,kwh_price,asic_price,premium FROM users WHERE user_id=?",(uid,)).fetchone()
    c.close()
    return r

def set_kwh(uid, v):
    c = conn(); c.execute("UPDATE users SET kwh_price=? WHERE user_id=?", (v, uid)); c.commit(); c.close()

def set_asic_price(uid, v):
    c = conn(); c.execute("UPDATE users SET asic_price=? WHERE user_id=?", (v, uid)); c.commit(); c.close()

def log_req(uid, kind, payload):
    c = conn()
    c.execute("INSERT INTO requests(user_id,kind,payload,created_at) VALUES(?,?,?,?)",
              (uid, kind, payload, int(time.time())))
    c.commit(); c.close()

def count_today(uid):
    c = conn()
    ts = int(time.time()) - 86400
    n = c.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND created_at>?", (uid, ts)).fetchone()[0]
    c.close()
    return n

def stats():
    c = conn()
    u = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    r = c.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    rt = c.execute("SELECT COUNT(*) FROM requests WHERE created_at>?", (int(time.time())-86400,)).fetchone()[0]
    top = c.execute("SELECT user_id, COUNT(*) c FROM requests GROUP BY user_id ORDER BY c DESC LIMIT 10").fetchall()
    c.close()
    return {"users": u, "requests": r, "requests_24h": rt, "top": top}
