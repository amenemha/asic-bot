import os, secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse
import db

db.init()
app = FastAPI()
security = HTTPBasic()

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")


def check(creds: HTTPBasicCredentials = Depends(security)):
    ok_u = secrets.compare_digest(creds.username, ADMIN_USER)
    ok_p = secrets.compare_digest(creds.password, ADMIN_PASS)
    if not (ok_u and ok_p):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username


@app.get("/", response_class=HTMLResponse)
def home(user: str = Depends(check)):
    s = db.stats()
    top_html = "".join(
        f"<tr><td>{u}</td><td>{c}</td></tr>" for u, c in s["top"]
    ) or "<tr><td colspan=2>нет данных</td></tr>"
    html = f"""
    <html><head><meta charset="utf-8"><title>ASIC Bot Admin</title>
    <style>
      body{{font-family:sans-serif;background:#111;color:#eee;padding:30px}}
      h1{{color:#4af}}
      .card{{background:#222;padding:20px;border-radius:8px;margin:10px 0;max-width:500px}}
      .num{{font-size:32px;color:#4af}}
      table{{border-collapse:collapse;margin-top:10px}}
      td,th{{border:1px solid #444;padding:6px 12px}}
    </style></head><body>
    <h1>ASIC Bot — Админка</h1>
    <div class="card"><div>Пользователей</div><div class="num">{s['users']}</div></div>
    <div class="card"><div>Запросов всего</div><div class="num">{s['requests']}</div></div>
    <div class="card"><div>Запросов за 24ч</div><div class="num">{s['requests_24h']}</div></div>
    <div class="card"><h3>Топ-10 юзеров</h3>
      <table><tr><th>user_id</th><th>запросов</th></tr>{top_html}</table>
    </div>
    </body></html>
    """
    return html


@app.get("/api/stats")
def api_stats(user: str = Depends(check)):
    return db.stats()
