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

# Real CS2 item names; prices below are virtual DanekCoin values for the simulator.
SKINS = [
    {"name":"Glock-18 | Candy Apple","price":120,"rarity":"Consumer","color":"#a8b3c7","emoji":"🔫"},
    {"name":"AK-47 | Safari Mesh","price":180,"rarity":"Industrial","color":"#7ca8d8","emoji":"🔫"},
    {"name":"AWP | Capillary","price":260,"rarity":"Mil-Spec","color":"#54c9d7","emoji":"🎯"},
    {"name":"M4A1-S | Decimator","price":650,"rarity":"Restricted","color":"#a78bfa","emoji":"🔫"},
    {"name":"USP-S | Cortex","price":900,"rarity":"Classified","color":"#ed83bf","emoji":"🔫"},
    {"name":"AK-47 | Neon Rider","price":1800,"rarity":"Covert","color":"#f06b6b","emoji":"🔫"},
    {"name":"AWP | Asiimov","price":2600,"rarity":"Covert","color":"#ff8b45","emoji":"🎯"},
    {"name":"Karambit | Doppler","price":6500,"rarity":"Rare Special","color":"#f3ca65","emoji":"🔪"},
    {"name":"M4A4 | Neo-Noir","price":3200,"rarity":"Covert","color":"#e879f9","emoji":"🔫"},
    {"name":"AK-47 | Bloodsport","price":3800,"rarity":"Covert","color":"#ef4444","emoji":"🔫"},
    {"name":"AWP | Hyper Beast","price":4200,"rarity":"Covert","color":"#22d3ee","emoji":"🎯"},
    {"name":"Desert Eagle | Printstream","price":2800,"rarity":"Covert","color":"#f8fafc","emoji":"🔫"},
    {"name":"AK-47 | The Empress","price":5200,"rarity":"Covert","color":"#fbbf24","emoji":"🔫"},
    {"name":"AWP | Dragon Lore","price":15000,"rarity":"Covert","color":"#f97316","emoji":"🎯"},
    {"name":"Butterfly Knife | Fade","price":18000,"rarity":"Rare Special","color":"#c084fc","emoji":"🔪"},
    {"name":"M9 Bayonet | Doppler","price":14000,"rarity":"Rare Special","color":"#818cf8","emoji":"🔪"},
    {"name":"Sport Gloves | Vice","price":12000,"rarity":"Rare Special","color":"#ec4899","emoji":"🧤"},
    {"name":"AK-47 | Wild Lotus","price":11000,"rarity":"Covert","color":"#4ade80","emoji":"🔫"},
    {"name":"AWP | Gungnir","price":16000,"rarity":"Covert","color":"#60a5fa","emoji":"🎯"},
    {"name":"Karambit | Gamma Doppler","price":20000,"rarity":"Rare Special","color":"#34d399","emoji":"🔪"},
    {"name":"P250 | See Ya Later","price":1450,"rarity":"Covert","color":"#f59e0b","emoji":"🔫"},
    {"name":"USP-S | Kill Confirmed","price":3400,"rarity":"Covert","color":"#fb7185","emoji":"🔫"},
    {"name":"AK-47 | Asiimov","price":4700,"rarity":"Covert","color":"#fb923c","emoji":"🔫"},
    {"name":"M4A4 | Howl","price":26000,"rarity":"Contraband","color":"#f97316","emoji":"🔫"},
    {"name":"AWP | Fade","price":22000,"rarity":"Covert","color":"#e879f9","emoji":"🎯"},
    {"name":"Butterfly Knife | Doppler","price":28000,"rarity":"Rare Special","color":"#a78bfa","emoji":"🔪"},
    {"name":"Karambit | Fade","price":35000,"rarity":"Rare Special","color":"#f9a8d4","emoji":"🔪"},
    {"name":"AWP | Medusa","price":42000,"rarity":"Covert","color":"#2dd4bf","emoji":"🎯"},
    {"name":"AK-47 | Gold Arabesque","price":50000,"rarity":"Covert","color":"#eab308","emoji":"🔫"},
    {"name":"AWP | Dragon Lore (Souvenir)","price":75000,"rarity":"Covert","color":"#d97706","emoji":"🎯"},
    {"name":"Karambit | Case Hardened","price":100000,"rarity":"Rare Special","color":"#60a5fa","emoji":"🔪"},
]

SKINS.extend([
    {"name":"AK-47 | Fire Serpent","price":135000,"rarity":"Covert","color":"#d97706","emoji":"🔫"},
    {"name":"AWP | The Prince","price":160000,"rarity":"Covert","color":"#fbbf24","emoji":"🎯"},
    {"name":"M4A4 | Poseidon","price":185000,"rarity":"Covert","color":"#22d3ee","emoji":"🔫"},
    {"name":"Glock-18 | Fade","price":210000,"rarity":"Restricted","color":"#f472b6","emoji":"🔫"},
    {"name":"AK-47 | Wild Lotus (Factory New)","price":250000,"rarity":"Covert","color":"#4ade80","emoji":"🔫"},
    {"name":"AWP | Medusa (Factory New)","price":300000,"rarity":"Covert","color":"#2dd4bf","emoji":"🎯"},
    {"name":"Karambit | Doppler Sapphire","price":380000,"rarity":"Rare Special","color":"#38bdf8","emoji":"🔪"},
    {"name":"Butterfly Knife | Doppler Sapphire","price":450000,"rarity":"Rare Special","color":"#38bdf8","emoji":"🔪"},
    {"name":"Sport Gloves | Pandora's Box","price":520000,"rarity":"Rare Special","color":"#a78bfa","emoji":"🧤"},
    {"name":"AWP | Dragon Lore (Factory New)","price":650000,"rarity":"Covert","color":"#f97316","emoji":"🎯"},
    {"name":"Souvenir AWP | Dragon Lore","price":850000,"rarity":"Covert","color":"#f59e0b","emoji":"🎯"},
    {"name":"M4A4 | Howl (Factory New)","price":1000000,"rarity":"Contraband","color":"#ef4444","emoji":"🔫"},
    {"name":"AK-47 | Case Hardened (Blue Gem)","price":1250000,"rarity":"Covert","color":"#60a5fa","emoji":"🔫"},
    {"name":"Karambit | Case Hardened (Blue Gem)","price":1500000,"rarity":"Rare Special","color":"#60a5fa","emoji":"🔪"},
    {"name":"Souvenir AWP | Dragon Lore (Factory New)","price":2000000,"rarity":"Covert","color":"#f59e0b","emoji":"🎯"},
])

# Case drop pools use the real CS2 skin catalog above. All prices are virtual DNC values.
def case(name, price, drops, theme, emoji):
    return {"name": name, "price": price, "drops": drops, "theme": theme, "emoji": emoji}

CASES = {
    "starter": case("STARTER CASE",300,[0,1,2,3,4],"red","📦"),
    "weapon": case("WEAPON CASE",850,[1,2,3,4,5,6],"blue","🧰"),
    "neon": case("NEON CASE",1500,[2,3,5,8,9,20],"pink","🌌"),
    "elite": case("ELITE CASE",2200,[3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19],"gold","💎"),
    "phoenix": case("PHOENIX CASE",2500,[4,5,6,9,10,11,20,21],"orange","🔥"),
    "cyber": case("CYBER CASE",3500,[5,8,9,10,11,20,21,22],"cyan","🧬"),
    "inferno": case("INFERNO CASE",4500,[5,6,8,9,10,11,12],"red","🌋"),
    "royal": case("ROYAL CASE",5000,[6,7,10,12,13,14,15,16],"gold","👑"),
    "vanguard": case("VANGUARD CASE",6000,[9,10,11,12,13,14,17,18],"blue","🛡️"),
    "knife": case("KNIFE CASE",8000,[7,14,15,16,19,24,25,26],"purple","🔪"),
    "dragon": case("DRAGON CASE",10000,[10,12,13,17,18,22,23,27],"orange","🐉"),
    "mythic": case("MYTHIC CASE",12000,[12,13,14,15,16,17,18,19,23,24],"purple","✨"),
    "legend": case("LEGEND CASE",20000,[15,16,17,18,19,23,24,25,26],"gold","🏆"),
    "titan": case("TITAN CASE",30000,[22,23,24,25,26,27],"cyan","⚡"),
    "royal_gold": case("GOLDEN ROYAL",50000,[23,24,25,26,27,28],"gold","💠"),
    "ultra": case("ULTRA CASE",75000,[24,25,26,27,28,29,31,32,33],"purple","🌠"),
    "apex": case("APEX CASE",100000,[25,26,27,28,29,30,35,38,40,44,45],"red","👑"),
    "godlike": case("GODLIKE CASE",150000,[31,32,33,34,35,36,37,38,39,40,41,42,43,44,45],"gold","💠"),
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
