import asyncio
import hashlib
import hmac
import json
import os
import random
import sqlite3
import time
from pathlib import Path
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import uvicorn

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
CREATOR_ID = int(os.getenv("CREATOR_TELEGRAM_ID", "0") or 0)
BASE_DIR = Path(__file__).resolve().parent
# Supports both layouts: app.py + web/index.html, or app.py + index.html.
if (BASE_DIR.parent / "web" / "index.html").exists():
    WEB = BASE_DIR.parent / "web"
elif (BASE_DIR / "web" / "index.html").exists():
    WEB = BASE_DIR / "web"
else:
    WEB = BASE_DIR
DB = Path(os.getenv("DATABASE_PATH", str(BASE_DIR.parent.parent / "danekcase.db")))
START_BALANCE = 2500
DAILY_BONUS = 500

# All values below are fictional in-game DNC values. They are not market prices.
# Generic collectible catalog (not real-world weapon/market items).
SKINS = [
    {"name":"Ruby Core","price":120,"rarity":"Common","color":"#f87171","emoji":"💎","category":"Gems"},
    {"name":"Azure Shard","price":180,"rarity":"Common","color":"#60a5fa","emoji":"🔹","category":"Gems"},
    {"name":"Solar Token","price":260,"rarity":"Uncommon","color":"#fbbf24","emoji":"🪙","category":"Tokens"},
    {"name":"Emerald Relic","price":420,"rarity":"Uncommon","color":"#34d399","emoji":"🟢","category":"Relics"},
    {"name":"Violet Crystal","price":650,"rarity":"Rare","color":"#c084fc","emoji":"🔮","category":"Gems"},
    {"name":"Neon Badge","price":900,"rarity":"Rare","color":"#22d3ee","emoji":"🏅","category":"Badges"},
    {"name":"Phoenix Emblem","price":1400,"rarity":"Epic","color":"#fb923c","emoji":"🔥","category":"Emblems"},
    {"name":"Aurora Orb","price":2200,"rarity":"Epic","color":"#a78bfa","emoji":"🌌","category":"Orbs"},
    {"name":"Cyber Crown","price":3200,"rarity":"Epic","color":"#e879f9","emoji":"👑","category":"Crowns"},
    {"name":"Golden Compass","price":4700,"rarity":"Legendary","color":"#facc15","emoji":"🧭","category":"Relics"},
    {"name":"Starlight Medallion","price":6500,"rarity":"Legendary","color":"#93c5fd","emoji":"🌟","category":"Medallions"},
    {"name":"Obsidian Heart","price":9000,"rarity":"Legendary","color":"#94a3b8","emoji":"🖤","category":"Artifacts"},
    {"name":"Prism Butterfly","price":13000,"rarity":"Mythic","color":"#f0abfc","emoji":"🦋","category":"Artifacts"},
    {"name":"Celestial Crown","price":18000,"rarity":"Mythic","color":"#fde68a","emoji":"👑","category":"Crowns"},
    {"name":"Eternal Star","price":25000,"rarity":"Mythic","color":"#fef08a","emoji":"✨","category":"Stars"},
    {"name":"Dragon Pearl","price":35000,"rarity":"Mythic","color":"#86efac","emoji":"🐉","category":"Orbs"},
    {"name":"Quantum Cube","price":50000,"rarity":"Mythic","color":"#67e8f9","emoji":"🧊","category":"Artifacts"},
    {"name":"Galaxy Relic","price":70000,"rarity":"Exotic","color":"#c4b5fd","emoji":"☄️","category":"Relics"},
    {"name":"Infinity Sigil","price":95000,"rarity":"Exotic","color":"#f9a8d4","emoji":"♾️","category":"Sigils"},
    {"name":"Eclipse Core","price":125000,"rarity":"Exotic","color":"#818cf8","emoji":"🌑","category":"Cores"},
    {"name":"Nova Crown","price":160000,"rarity":"Exotic","color":"#fb7185","emoji":"💠","category":"Crowns"},
    {"name":"Astral Phoenix","price":210000,"rarity":"Exotic","color":"#fdba74","emoji":"🪶","category":"Emblems"},
    {"name":"Chrono Artifact","price":280000,"rarity":"Ancient","color":"#fcd34d","emoji":"⌛","category":"Artifacts"},
    {"name":"Prismatic Heart","price":360000,"rarity":"Ancient","color":"#5eead4","emoji":"💖","category":"Cores"},
    {"name":"Cosmic Relic","price":460000,"rarity":"Ancient","color":"#a5b4fc","emoji":"🌠","category":"Relics"},
    {"name":"Genesis Orb","price":580000,"rarity":"Ancient","color":"#bef264","emoji":"🔆","category":"Orbs"},
    {"name":"Eternity Emblem","price":700000,"rarity":"Divine","color":"#f0abfc","emoji":"🏵️","category":"Emblems"},
    {"name":"Universe Key","price":820000,"rarity":"Divine","color":"#93c5fd","emoji":"🗝️","category":"Artifacts"},
    {"name":"Danek Relic","price":950000,"rarity":"Divine","color":"#fbbf24","emoji":"🏆","category":"Relics"},
    {"name":"Infinity Crown","price":1_000_000,"rarity":"Divine","color":"#fde68a","emoji":"👑","category":"Crowns"},
    {"name":"Creator's Comet","price":1_250_000,"rarity":"Divine","color":"#fda4af","emoji":"☄️","category":"Stars"},
    {"name":"Absolute Singularity","price":1_500_000,"rarity":"Divine","color":"#c4b5fd","emoji":"🪐","category":"Cores"},
    {"name":"Danekverse Artifact","price":2_000_000,"rarity":"Divine","color":"#67e8f9","emoji":"🌌","category":"Artifacts"},
]

def case(name, price, drops, theme, emoji):
    return {"name": name, "price": price, "drops": drops, "theme": theme, "emoji": emoji}

CASES = {
    "starter": case("STARTER CASE",300,[0,1,2,3,4,5],"red","📦"),
    "solar": case("SOLAR CASE",850,[2,3,4,5,6,7],"gold","☀️"),
    "neon": case("NEON CASE",1500,[4,5,6,7,8,9],"pink","🌌"),
    "epic": case("EPIC CASE",2500,[6,7,8,9,10,11,12],"purple","💜"),
    "mythic": case("MYTHIC CASE",5000,[9,10,11,12,13,14,15,16],"blue","✨"),
    "exotic": case("EXOTIC CASE",12000,[13,14,15,16,17,18,19,20],"cyan","🪐"),
    "ancient": case("ANCIENT CASE",30000,[17,18,19,20,21,22,23,24,25],"orange","🏛️"),
    "divine": case("DIVINE CASE",75000,[22,23,24,25,26,27,28,29,30,31,32],"gold","👑"),
    "apex": case("APEX CASE",150000,[26,27,28,29,30,31,32],"red","💠"),
}


def db():
    conn = sqlite3.connect(DB, timeout=25)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL DEFAULT 'Игрок',
            username TEXT NOT NULL DEFAULT '',
            balance INTEGER NOT NULL DEFAULT 2500,
            creator_balance INTEGER NOT NULL DEFAULT 0,
            daily_at INTEGER NOT NULL DEFAULT 0,
            total_spent INTEGER NOT NULL DEFAULT 0,
            total_earned INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT 0
        )""")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        migrations = {
            "first_name": "TEXT NOT NULL DEFAULT 'Игрок'", "username": "TEXT NOT NULL DEFAULT ''",
            "creator_balance": "INTEGER NOT NULL DEFAULT 0", "daily_at": "INTEGER NOT NULL DEFAULT 0",
            "total_spent": "INTEGER NOT NULL DEFAULT 0", "total_earned": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "INTEGER NOT NULL DEFAULT 0", "is_vip": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in migrations.items():
            if name not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
        c.execute("""CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            skin_idx INTEGER NOT NULL, obtained_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS stats(
            user_id INTEGER PRIMARY KEY, opened INTEGER NOT NULL DEFAULT 0,
            upgrades_won INTEGER NOT NULL DEFAULT 0, upgrades_lost INTEGER NOT NULL DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS drop_feed(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            display_name TEXT NOT NULL, skin_idx INTEGER NOT NULL, source TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_id INTEGER NOT NULL,
            to_id INTEGER NOT NULL, amount INTEGER NOT NULL, created_at INTEGER NOT NULL
        )""")


def ensure(uid, user=None):
    supplied_user = user is not None
    user = user or {}
    first_name = str(user.get("first_name") or "Игрок")[:64]
    username = str(user.get("username") or "")[:64]
    now = int(time.time())
    is_creator = bool(CREATOR_ID and uid == CREATOR_ID)
    with db() as c:
        c.execute("""INSERT OR IGNORE INTO users
            (user_id,first_name,username,balance,creator_balance,total_earned,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (uid, first_name, username, START_BALANCE, 0, START_BALANCE, now))
        if supplied_user:
            c.execute("UPDATE users SET first_name=?,username=? WHERE user_id=?", (first_name, username, uid))
        c.execute("INSERT OR IGNORE INTO stats(user_id) VALUES(?)", (uid,))
        if is_creator:
            # The creator has a separate unlimited admin wallet; regular player balance remains ordinary.
            c.execute("UPDATE users SET creator_balance=CASE WHEN creator_balance=0 THEN 1000000000000 ELSE creator_balance END WHERE user_id=?", (uid,))


def telegram_user(init_data: str):
    if not TOKEN or not init_data:
        raise HTTPException(401, "Открой приложение через Telegram-бота.")
    vals = dict(parse_qsl(init_data, keep_blank_values=True))
    received = vals.pop("hash", None)
    if not received:
        raise HTTPException(401, "Недействительная Telegram-сессия.")
    check = "\n".join(f"{k}={v}" for k, v in sorted(vals.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(401, "Проверка Telegram-сессии не пройдена.")
    try:
        auth_date = int(vals.get("auth_date", "0"))
        if time.time() - auth_date > 86400 or auth_date > time.time() + 60:
            raise HTTPException(401, "Сессия устарела. Открой приложение заново.")
        user = json.loads(vals["user"])
        uid = int(user["id"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Не удалось прочитать аккаунт Telegram.")
    ensure(uid, user)
    return uid, user


def require_creator(uid):
    if not CREATOR_ID or uid != CREATOR_ID:
        raise HTTPException(403, "Раздел доступен только создателю DanekCase.")


app = FastAPI(title="DanekCase Mini App")
app.mount("/static", StaticFiles(directory=str(WEB), check_dir=False), name="static")


class Action(BaseModel):
    item_id: int | None = None
    case_id: str | None = None
    target_idx: int | None = None
    multiplier: int | None = Field(default=2, ge=2, le=10)
    amount: int | None = Field(default=None, ge=1, le=1_000_000_000)
    target_user_id: int | None = None


def add_drop(c, uid, display_name, skin_idx, source):
    c.execute("INSERT INTO drop_feed(user_id,display_name,skin_idx,source,created_at) VALUES(?,?,?,?,?)",
              (uid, display_name[:80], skin_idx, source[:32], int(time.time())))


def state_for(uid, user):
    ensure(uid, user)
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        stats = c.execute("SELECT * FROM stats WHERE user_id=?", (uid,)).fetchone()
        rows = c.execute("SELECT id,skin_idx,obtained_at FROM inventory WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
        items = [{"id":r["id"], "skin_idx":r["skin_idx"], "obtained_at":r["obtained_at"], **SKINS[r["skin_idx"]]} for r in rows]
        now = int(time.time())
        feed_rows = c.execute("SELECT display_name,skin_idx,source,created_at FROM drop_feed ORDER BY id DESC LIMIT 25").fetchall()
        feed = [{"player":r["display_name"], "item":SKINS[r["skin_idx"]]["name"], "skin":SKINS[r["skin_idx"]], "source":r["source"], "created_at":r["created_at"]} for r in feed_rows]
        return {
            "user":{"id":uid,"first_name":user.get("first_name",u["first_name"]),"username":user.get("username",u["username"]),"is_vip":bool(u["is_vip"]) if "is_vip" in u.keys() else False},
            "balance":u["balance"], "creator_balance":u["creator_balance"] if uid == CREATOR_ID else None,
            "is_creator":uid == CREATOR_ID, "daily_ready":now-int(u["daily_at"] or 0)>=86400,
            "inventory":items,
            "stats":{"opened":stats["opened"],"upgrades_won":stats["upgrades_won"],"upgrades_lost":stats["upgrades_lost"],"total_spent":u["total_spent"],"total_earned":u["total_earned"],"net":u["total_earned"]-u["total_spent"],"inventory_value":sum(x["price"] for x in items)},
            "cases":[{"id":k,"name":v["name"],"price":v["price"],"theme":v["theme"],"emoji":v["emoji"]} for k,v in CASES.items()],
            "skins":SKINS, "drop_feed":feed
        }


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/state")
def get_state(x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    return state_for(uid, user)


@app.post("/api/open")
def open_case(action: Action, x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    selected = CASES.get(action.case_id or "")
    if not selected:
        raise HTTPException(400, "Неизвестный кейс")
    display = user.get("first_name") or "Игрок"
    with db() as c:
        u = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        if u["balance"] < selected["price"]:
            raise HTTPException(400, "Не хватает DanekCoin")
        pool = selected["drops"]
        weights = [max(1, int(100000 / (SKINS[i]["price"] ** 0.72))) for i in pool]
        idx = random.choices(pool, weights=weights, k=1)[0]
        c.execute("UPDATE users SET balance=balance-?,total_spent=total_spent+? WHERE user_id=?", (selected["price"], selected["price"], uid))
        cur = c.execute("INSERT INTO inventory(user_id,skin_idx,obtained_at) VALUES(?,?,?)", (uid, idx, int(time.time())))
        c.execute("UPDATE stats SET opened=opened+1 WHERE user_id=?", (uid,))
        add_drop(c, uid, display, idx, "Кейс")
    return {"result":{"id":cur.lastrowid,"skin":SKINS[idx]},"state":state_for(uid,user)}


@app.post("/api/sell")
def sell(action: Action, x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    with db() as c:
        row = c.execute("SELECT skin_idx FROM inventory WHERE id=? AND user_id=?", (action.item_id,uid)).fetchone()
        if not row:
            raise HTTPException(404,"Предмет не найден")
        price = SKINS[row["skin_idx"]]["price"]
        c.execute("DELETE FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid))
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(price,price,uid))
    return {"sold":price,"state":state_for(uid,user)}


@app.post("/api/upgrade")
def upgrade(action: Action, x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    if action.item_id is None or action.target_idx is None or not 0 <= action.target_idx < len(SKINS):
        raise HTTPException(400,"Выбери исходный и целевой предмет")
    multiplier = action.multiplier or 2
    if multiplier not in (2,3,5,10):
        raise HTTPException(400,"Недопустимый множитель")
    with db() as c:
        row = c.execute("SELECT skin_idx FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid)).fetchone()
        if not row:
            raise HTTPException(404,"Исходный предмет не найден")
        src_idx, dst_idx = row["skin_idx"], action.target_idx
        src_price, dst_price = SKINS[src_idx]["price"], SKINS[dst_idx]["price"]
        if dst_price < src_price * multiplier:
            raise HTTPException(400,f"Для x{multiplier} цель должна стоить минимум {src_price*multiplier:,} DNC".replace(","," "))
        # Server-controlled chance: x2=50%, x3=33.33%, x5=20%, x10=10%.
        chance = 100.0 / multiplier
        success = random.random() < chance / 100.0
        c.execute("DELETE FROM inventory WHERE id=? AND user_id=?",(action.item_id,uid))
        if success:
            c.execute("INSERT INTO inventory(user_id,skin_idx,obtained_at) VALUES(?,?,?)",(uid,dst_idx,int(time.time())))
            c.execute("UPDATE stats SET upgrades_won=upgrades_won+1 WHERE user_id=?",(uid,))
            add_drop(c,uid,user.get("first_name") or "Игрок",dst_idx,"Апгрейд")
        else:
            c.execute("UPDATE stats SET upgrades_lost=upgrades_lost+1 WHERE user_id=?",(uid,))
    return {"success":success,"chance":round(chance,2),"multiplier":multiplier,"skin":SKINS[dst_idx] if success else None,"state":state_for(uid,user)}


@app.post("/api/daily")
def daily(x_telegram_init_data: str = Header(default="")):
    uid,user=telegram_user(x_telegram_init_data); now=int(time.time())
    with db() as c:
        row=c.execute("SELECT daily_at FROM users WHERE user_id=?",(uid,)).fetchone()
        if now-int(row["daily_at"] or 0)<86400: raise HTTPException(400,"Ежедневный бонус уже получен")
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+?,daily_at=? WHERE user_id=?",(DAILY_BONUS,DAILY_BONUS,now,uid))
    return {"state":state_for(uid,user)}


@app.get("/api/admin/players")
def admin_players(x_telegram_init_data: str = Header(default="")):
    uid,_=telegram_user(x_telegram_init_data); require_creator(uid)
    with db() as c:
        rows=c.execute("""SELECT u.user_id,u.first_name,u.username,u.balance,u.created_at,
            s.opened,s.upgrades_won,s.upgrades_lost,
            (SELECT COUNT(*) FROM inventory i WHERE i.user_id=u.user_id) AS inventory_count
            FROM users u LEFT JOIN stats s ON s.user_id=u.user_id ORDER BY u.created_at DESC""").fetchall()
    return {"players":[dict(r) for r in rows]}


@app.post("/api/admin/topup")
def admin_topup(action: Action, x_telegram_init_data: str = Header(default="")):
    uid,owner_user=telegram_user(x_telegram_init_data); require_creator(uid)
    if not action.amount or not action.target_user_id: raise HTTPException(400,"Укажи Telegram ID и сумму")
    with db() as c:
        target=c.execute("SELECT user_id FROM users WHERE user_id=?",(action.target_user_id,)).fetchone()
        if not target: raise HTTPException(404,"Игрок не найден. Он должен хотя бы раз открыть DanekCase.")
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(action.amount,action.amount,action.target_user_id))
    return {"ok":True,"state":state_for(uid,owner_user)}


@app.post("/api/admin/transfer")
def admin_transfer(action: Action, x_telegram_init_data: str = Header(default="")):
    uid,owner_user=telegram_user(x_telegram_init_data); require_creator(uid)
    if not action.amount or not action.target_user_id: raise HTTPException(400,"Укажи Telegram ID и сумму")
    with db() as c:
        target=c.execute("SELECT user_id FROM users WHERE user_id=?",(action.target_user_id,)).fetchone()
        if not target: raise HTTPException(404,"Игрок не найден. Он должен хотя бы раз открыть DanekCase.")
        owner=c.execute("SELECT creator_balance FROM users WHERE user_id=?",(uid,)).fetchone()
        if owner["creator_balance"] < action.amount: raise HTTPException(400,"Недостаточно средств в кошельке создателя")
        c.execute("UPDATE users SET creator_balance=creator_balance-? WHERE user_id=?",(action.amount,uid))
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(action.amount,action.amount,action.target_user_id))
        c.execute("INSERT INTO transfers(from_id,to_id,amount,created_at) VALUES(?,?,?,?)",(uid,action.target_user_id,action.amount,int(time.time())))
    return {"ok":True,"state":state_for(uid,owner_user)}


@app.post("/api/admin/send")
def admin_send(action: Action, x_telegram_init_data: str = Header(default="")):
    uid,owner_user=telegram_user(x_telegram_init_data); require_creator(uid)
    if not action.amount or not action.target_user_id: raise HTTPException(400,"Укажи Telegram ID и сумму")
    with db() as c:
        target=c.execute("SELECT user_id FROM users WHERE user_id=?",(action.target_user_id,)).fetchone()
        if not target: raise HTTPException(404,"Игрок не найден. Он должен хотя бы раз открыть DanekCase.")
        owner=c.execute("SELECT balance FROM users WHERE user_id=?",(uid,)).fetchone()
        if owner["balance"] < action.amount: raise HTTPException(400,"Недостаточно DNC на твоём игровом балансе")
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?",(action.amount,uid))
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(action.amount,action.amount,action.target_user_id))
        c.execute("INSERT INTO transfers(from_id,to_id,amount,created_at) VALUES(?,?,?,?)",(uid,action.target_user_id,action.amount,int(time.time())))
    return {"ok":True,"state":state_for(uid,owner_user)}


@app.post("/api/admin/self-topup")
def admin_self_topup(action: Action, x_telegram_init_data: str = Header(default="")):
    uid,owner_user=telegram_user(x_telegram_init_data); require_creator(uid)
    if not action.amount: raise HTTPException(400,"Укажи сумму")
    with db() as c:
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",(action.amount,action.amount,uid))
    return {"ok":True,"state":state_for(uid,owner_user)}


dp=Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    if not WEBAPP_URL.startswith("https://"):
        await message.answer("Mini App пока не опубликован: укажи HTTPS-адрес в WEBAPP_URL."); return
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Открыть DanekCase",web_app=WebAppInfo(url=WEBAPP_URL))]])
    await message.answer("🎮 <b>DANEKCASE</b>\n\nКоллекция, виртуальные кейсы и апгрейды. DanekCoin — игровая валюта без вывода и обмена.",reply_markup=kb,parse_mode="HTML")

async def serve():
    config=uvicorn.Config(app,host="0.0.0.0",port=int(os.getenv("PORT","8000")),log_level="info")
    await uvicorn.Server(config).serve()

async def main():
    if not TOKEN: raise RuntimeError("Укажи BOT_TOKEN в переменных окружения.")
    WEB.mkdir(parents=True,exist_ok=True); init_db(); bot=Bot(TOKEN)
    try: await asyncio.gather(dp.start_polling(bot),serve())
    finally: await bot.session.close()

if __name__=="__main__": asyncio.run(main())
