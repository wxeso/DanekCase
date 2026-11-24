import asyncio, hashlib, hmac, json, os, random, sqlite3, time
from pathlib import Path
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
import uvicorn

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
CREATOR_ID = int(os.getenv("CREATOR_TELEGRAM_ID", "0") or 0)
DB = Path(__file__).resolve().parent.parent / "danekcase.db"
WEB = Path(__file__).resolve().parent.parent / "web"
START_BALANCE = 2500
CREATOR_BALANCE = 10**15
DAILY_BONUS = 500

SKINS = [
    {"name":"Glock-18 | Candy Apple","price":120,"rarity":"Consumer","color":"#a8b3c7"},
    {"name":"AK-47 | Safari Mesh","price":180,"rarity":"Industrial","color":"#7ca8d8"},
    {"name":"AWP | Capillary","price":260,"rarity":"Mil-Spec","color":"#54c9d7"},
    {"name":"M4A1-S | Decimator","price":650,"rarity":"Restricted","color":"#a78bfa"},
    {"name":"USP-S | Cortex","price":900,"rarity":"Classified","color":"#ed83bf"},
    {"name":"AK-47 | Neon Rider","price":1800,"rarity":"Covert","color":"#f06b6b"},
    {"name":"AWP | Asiimov","price":2600,"rarity":"Covert","color":"#ff8b45"},
    {"name":"Karambit | Doppler","price":6500,"rarity":"Rare Special","color":"#f3ca65"},
]
CASES = {
    "starter":{"name":"STARTER CASE","price":300,"drops":[0,1,2,3,4]},
    "weapon":{"name":"WEAPON CASE","price":850,"drops":[1,2,3,4,5,6]},
    "elite":{"name":"ELITE CASE","price":2200,"drops":[3,4,5,6,7]},
}

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 2500,
          creator_balance INTEGER NOT NULL DEFAULT 0, daily_at INTEGER NOT NULL DEFAULT 0)""")
        cols=[r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()]
        if "creator_balance" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN creator_balance INTEGER NOT NULL DEFAULT 0")
        c.execute("""CREATE TABLE IF NOT EXISTS inventory(
          id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,
          skin_idx INTEGER NOT NULL,obtained_at INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS stats(
          user_id INTEGER PRIMARY KEY,opened INTEGER NOT NULL DEFAULT 0,
          upgrades_won INTEGER NOT NULL DEFAULT 0,upgrades_lost INTEGER NOT NULL DEFAULT 0)""")

def ensure(uid):
    is_creator = bool(CREATOR_ID and uid == CREATOR_ID)
    with db() as c:
        c.execute("INSERT OR IGNORE INTO users(user_id,balance,creator_balance) VALUES(?,?,?)",
                  (uid, CREATOR_BALANCE if is_creator else START_BALANCE,
                   CREATOR_BALANCE if is_creator else 0))
        c.execute("INSERT OR IGNORE INTO stats(user_id) VALUES(?)",(uid,))
        # Make creator wallet available in pre-existing databases too.
        if is_creator:
            c.execute("UPDATE users SET balance=?,creator_balance=? WHERE user_id=? AND creator_balance=0",
                      (CREATOR_BALANCE,CREATOR_BALANCE,uid))

def telegram_user(init_data: str):
    if not TOKEN or not init_data:
        raise HTTPException(401,"Open this app from its Telegram bot.")
    vals=dict(parse_qsl(init_data, keep_blank_values=True))
    received=vals.pop("hash",None)
    if not received:
        raise HTTPException(401,"Invalid Telegram session.")
    check="\n".join(f"{k}={v}" for k,v in sorted(vals.items()))
    secret=hmac.new(b"WebAppData",TOKEN.encode(),hashlib.sha256).digest()
    expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,received):
        raise HTTPException(401,"Telegram session verification failed.")
    auth_date=int(vals.get("auth_date","0"))
    if time.time()-auth_date > 86400:
        raise HTTPException(401,"Telegram session expired. Reopen the app.")
    try:
        user=json.loads(vals["user"])
        uid=int(user["id"])
    except Exception:
        raise HTTPException(401,"Could not read Telegram account.")
    ensure(uid)
    return uid, user

app=FastAPI(title="DanekCase Mini App")
app.mount("/static",StaticFiles(directory=str(WEB)),name="static")

class Action(BaseModel):
    item_id:int|None=None
    case_id:str|None=None
    target_idx:int|None=None

def state_for(uid, user):
    ensure(uid)
    with db() as c:
        u=c.execute("SELECT * FROM users WHERE user_id=?",(uid,)).fetchone()
        stats=c.execute("SELECT * FROM stats WHERE user_id=?",(uid,)).fetchone()
        rows=c.execute("SELECT id,skin_idx,obtained_at FROM inventory WHERE user_id=? ORDER BY id DESC",(uid,)).fetchall()
    items=[]
    for r in rows:
        s=SKINS[r["skin_idx"]]
        items.append({"id":r["id"],"skin_idx":r["skin_idx"],**s})
    return {
      "user":{"id":uid,"first_name":user.get("first_name","Игрок"),"username":user.get("username","")},
      "balance":u["balance"],"creator_balance":u["creator_balance"] if uid==CREATOR_ID else None,
      "is_creator":uid==CREATOR_ID,"daily_ready":time.time()-u["daily_at"]>=86400,
      "inventory":items,"stats":{"opened":stats["opened"],"upgrades_won":stats["upgrades_won"],"upgrades_lost":stats["upgrades_lost"]},
      "cases":[{"id":k,"name":v["name"],"price":v["price"]} for k,v in CASES.items()],
      "skins":SKINS
    }

@app.get("/")
def index():
    return FileResponse(WEB/"index.html")

@app.get("/api/state")
def get_state(x_telegram_init_data: str = Header(default="")):
    uid,user=telegram_user(x_telegram_init_data)
    return state_for(uid,user)

@app.post("/api/open")
def open_case(action:Action, x_telegram_init_data: str = Header(default="")):
    uid,user=telegram_user(x_telegram_init_data)
    case=CASES.get(action.case_id or "")
    if not case: raise HTTPException(400,"Unknown case")
    with db() as c:
        u=c.execute("SELECT balance FROM users WHERE user_id=?",(uid,)).fetchone()
        if u["balance"] < case["price"]: raise HTTPException(400,"Не хватает DanekCoin")
        pool=case["drops"]; weights=list(range(len(pool),0,-1))
        idx=random.choices(pool,weights=weights,k=1)[0]
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?",(case["price"],uid))
        cur=c.execute("INSERT INTO inventory(user_id,skin_idx,obtained_at) VALUES(?,?,?)",(uid,idx,int(time.time())))
        c.execute("UPDATE stats SET opened=opened+1 WHERE user_id=?",(uid,))
        item_id=cur.lastrowid
    return {"result":{"id":item_id,"skin":SKINS[idx]},"state":state_for(uid,user)}

@app.post("/api/sell")
def sell(action:Action, x_telegram_init_data: str = Header(default="")):
    uid,user=telegram_user(x_telegram_init_data)
    with db() as c:
        row=c.execute("SELECT skin_idx FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid)).fetchone()
        if not row: raise HTTPException(404,"Предмет уже продан или не найден")
        price=SKINS[row["skin_idx"]]["price"]
        c.execute("DELETE FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid))
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(price,uid))
    return {"sold":price,"state":state_for(uid,user)}

@app.post("/api/upgrade")
def upgrade(action:Action, x_telegram_init_data: str = Header(default="")):
    uid,user=telegram_user(x_telegram_init_data)
    if action.item_id is None or action.target_idx is None or not 0<=action.target_idx<len(SKINS):
        raise HTTPException(400,"Invalid upgrade")
    with db() as c:
        row=c.execute("SELECT skin_idx FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid)).fetchone()
        if not row: raise HTTPException(404,"Исходный скин не найден")
        src=row["skin_idx"]; dst=action.target_idx
        src_price=SKINS[src]["price"]; dst_price=SKINS[dst]["price"]
        if dst_price<=src_price: raise HTTPException(400,"Цель должна быть дороже")
        chance=max(5,min(85,int(src_price/dst_price*75)))
        success=random.randint(1,100)<=chance
        c.execute("DELETE FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid))
        if success:
            c.execute("INSERT INTO inventory(user_id,skin_idx,obtained_at) VALUES(?,?,?)",(uid,dst,int(time.time())))
            c.execute("UPDATE stats SET upgrades_won=upgrades_won+1 WHERE user_id=?",(uid,))
        else:
            c.execute("UPDATE stats SET upgrades_lost=upgrades_lost+1 WHERE user_id=?",(uid,))
    return {"success":success,"chance":chance,"skin":SKINS[dst] if success else None,"state":state_for(uid,user)}

@app.post("/api/daily")
def daily(x_telegram_init_data: str = Header(default="")):
    uid,user=telegram_user(x_telegram_init_data)
    now=int(time.time())
    with db() as c:
        u=c.execute("SELECT daily_at FROM users WHERE user_id=?",(uid,)).fetchone()
        if now-u["daily_at"]<86400: raise HTTPException(400,"Бонус уже получен")
        c.execute("UPDATE users SET balance=balance+?,daily_at=? WHERE user_id=?",(DAILY_BONUS,now,uid))
    return {"state":state_for(uid,user)}

dp=Dispatcher()
@dp.message(CommandStart())
async def start(message:Message):
    if not WEBAPP_URL.startswith("https://"):
        await message.answer("Mini App пока не опубликован: сначала укажи HTTPS-адрес в WEBAPP_URL.")
        return
    kb=InlineKeyboardMarkup(inline_keyboard=[[
      InlineKeyboardButton(text="🎮 Открыть DanekCase",web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer(
      "🎮 <b>DANEKCASE</b>\n\nКейсы, CS2-скины, инвентарь и апгрейды.\n"
      "DanekCoin — только виртуальная игровая валюта, без денежных ставок и вывода.",
      reply_markup=kb,parse_mode="HTML"
    )

async def serve():
    config=uvicorn.Config(app,host="0.0.0.0",port=int(os.getenv("PORT","8000")),log_level="info")
    server=uvicorn.Server(config)
    await server.serve()

async def main():
    if not TOKEN: raise RuntimeError("Укажи BOT_TOKEN в .env")
    init_db()
    bot=Bot(TOKEN)
    await asyncio.gather(dp.start_polling(bot),serve())

if __name__=="__main__":
    asyncio.run(main())
