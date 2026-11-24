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
from pydantic import BaseModel
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import uvicorn

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
CREATOR_ID = int(os.getenv("CREATOR_TELEGRAM_ID", "0") or 0)
FRIEND_ID = 904963057
FRIEND_BONUS = 1_000_000
FRIEND_CLAIM_AMOUNT = 1_000_000
FRIEND_CLAIM_COOLDOWN = 30
DB = Path(__file__).resolve().parent / "danekcase.db"
WEB = Path(__file__).resolve().parent / "web"
START_BALANCE = 2500
CREATOR_BALANCE = 10**15
DAILY_BONUS = 500

# Values are virtual in-game DNC, not real-world prices.
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
    "ultra": case("ULTRA CASE",75000,[24,25,26,27,28,29],"purple","🌠"),
    "apex": case("APEX CASE",100000,[25,26,27,28,29,30],"red","👑"),
}

def db():
    conn = sqlite3.connect(DB, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 2500,
            creator_balance INTEGER NOT NULL DEFAULT 0,
            daily_at INTEGER NOT NULL DEFAULT 0
        )""")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        migrations = {
            "is_vip": "INTEGER NOT NULL DEFAULT 0",
            "friend_bonus_granted": "INTEGER NOT NULL DEFAULT 0",
            "total_spent": "INTEGER NOT NULL DEFAULT 0",
            "total_earned": "INTEGER NOT NULL DEFAULT 0",
            "friend_claim_at": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in migrations.items():
            if name not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
        c.execute("""CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skin_idx INTEGER NOT NULL,
            obtained_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS stats(
            user_id INTEGER PRIMARY KEY,
            opened INTEGER NOT NULL DEFAULT 0,
            upgrades_won INTEGER NOT NULL DEFAULT 0,
            upgrades_lost INTEGER NOT NULL DEFAULT 0
        )""")

def ensure(uid):
    creator = bool(CREATOR_ID and uid == CREATOR_ID)
    with db() as c:
        c.execute(
            """INSERT OR IGNORE INTO users
               (user_id,balance,creator_balance,total_earned)
               VALUES(?,?,?,?)""",
            (uid, CREATOR_BALANCE if creator else START_BALANCE,
             CREATOR_BALANCE if creator else 0,
             CREATOR_BALANCE if creator else START_BALANCE)
        )
        c.execute("INSERT OR IGNORE INTO stats(user_id) VALUES(?)", (uid,))
        if creator:
            c.execute("""UPDATE users SET balance=?,creator_balance=?
                         WHERE user_id=? AND creator_balance=0""",
                      (CREATOR_BALANCE, CREATOR_BALANCE, uid))
        if uid == FRIEND_ID:
            c.execute("""UPDATE users SET balance=balance+?,total_earned=total_earned+?,
                         is_vip=1,friend_bonus_granted=1
                         WHERE user_id=? AND friend_bonus_granted=0""",
                      (FRIEND_BONUS, FRIEND_BONUS, uid))
            c.execute("UPDATE users SET is_vip=1 WHERE user_id=?", (uid,))

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
    auth_date = int(vals.get("auth_date", "0"))
    if time.time() - auth_date > 86400:
        raise HTTPException(401, "Сессия устарела. Открой приложение заново.")
    try:
        user = json.loads(vals["user"])
        uid = int(user["id"])
    except Exception:
        raise HTTPException(401, "Не удалось прочитать аккаунт Telegram.")
    ensure(uid)
    return uid, user

app = FastAPI(title="DanekCase Mini App")
app.mount("/static", StaticFiles(directory=str(WEB), check_dir=False), name="static")

class Action(BaseModel):
    item_id: int | None = None
    case_id: str | None = None
    target_idx: int | None = None
    chance: int | None = None

def state_for(uid, user):
    ensure(uid)
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        stats = c.execute("SELECT * FROM stats WHERE user_id=?", (uid,)).fetchone()
        rows = c.execute(
            "SELECT id,skin_idx,obtained_at FROM inventory WHERE user_id=? ORDER BY id DESC",
            (uid,)
        ).fetchall()
        items = []
        for r in rows:
            s = SKINS[r["skin_idx"]]
            items.append({"id":r["id"], "skin_idx":r["skin_idx"], "obtained_at":r["obtained_at"], **s})
        now = int(time.time())
        claim_remaining = max(0, FRIEND_CLAIM_COOLDOWN - (now - int(u["friend_claim_at"] or 0)))
        return {
            "user": {
                "id": uid,
                "first_name": user.get("first_name", "Игрок"),
                "username": user.get("username", ""),
                "is_vip": bool(u["is_vip"])
            },
            "balance": u["balance"],
            "creator_balance": u["creator_balance"] if uid == CREATOR_ID else None,
            "is_creator": uid == CREATOR_ID,
            "is_friend": uid == FRIEND_ID,
            "special_upgrade_bonus": uid == FRIEND_ID,
            "friend_claim_remaining": claim_remaining,
            "daily_ready": now - u["daily_at"] >= 86400,
            "inventory": items,
            "stats": {
                "opened": stats["opened"],
                "upgrades_won": stats["upgrades_won"],
                "upgrades_lost": stats["upgrades_lost"],
                "total_spent": u["total_spent"],
                "total_earned": u["total_earned"],
                "net": u["total_earned"] - u["total_spent"],
                "inventory_value": sum(x["price"] for x in items)
            },
            "cases": [{"id":k, "name":v["name"], "price":v["price"], "theme":v["theme"], "emoji":v["emoji"]} for k,v in CASES.items()],
            "skins": SKINS
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
    with db() as c:
        u = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        if u["balance"] < selected["price"]:
            raise HTTPException(400, "Не хватает DanekCoin")
        pool = selected["drops"]
        # Higher-value drops are rarer; order is not used as a security control.
        weights = [max(1, int(100000 / (SKINS[i]["price"] ** 0.72))) for i in pool]
        idx = random.choices(pool, weights=weights, k=1)[0]
        c.execute("UPDATE users SET balance=balance-?,total_spent=total_spent+? WHERE user_id=?",
                  (selected["price"], selected["price"], uid))
        cur = c.execute("INSERT INTO inventory(user_id,skin_idx,obtained_at) VALUES(?,?,?)",
                        (uid, idx, int(time.time())))
        c.execute("UPDATE stats SET opened=opened+1 WHERE user_id=?", (uid,))
        item_id = cur.lastrowid
    return {"result":{"id":item_id, "skin":SKINS[idx]}, "state":state_for(uid, user)}

@app.post("/api/sell")
def sell(action: Action, x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    with db() as c:
        row = c.execute("SELECT skin_idx FROM inventory WHERE id=? AND user_id=?",
                        (action.item_id, uid)).fetchone()
        if not row:
            raise HTTPException(404, "Предмет уже продан или не найден")
        price = SKINS[row["skin_idx"]]["price"]
        c.execute("DELETE FROM inventory WHERE id=? AND user_id=?", (action.item_id, uid))
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+? WHERE user_id=?",
                  (price, price, uid))
    return {"sold":price, "state":state_for(uid, user)}

@app.post("/api/upgrade")
def upgrade(action: Action, x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    if action.item_id is None or action.target_idx is None or not 0 <= action.target_idx < len(SKINS):
        raise HTTPException(400, "Некорректный апгрейд")
    with db() as c:
        row = c.execute("SELECT skin_idx FROM inventory WHERE id=? AND user_id=?",
                        (action.item_id, uid)).fetchone()
        if not row:
            raise HTTPException(404, "Исходный скин не найден")
        src, dst = row["skin_idx"], action.target_idx
        src_price, dst_price = SKINS[src]["price"], SKINS[dst]["price"]
        if dst_price <= src_price:
            raise HTTPException(400, "Цель должна быть дороже")
        normal_chance = max(5, min(85, int(src_price / dst_price * 75)))
        if uid == FRIEND_ID:
            chance = action.chance if action.chance is not None else 70
            if not 10 <= chance <= 70:
                raise HTTPException(400, "Для этого апгрейда выбери шанс от 10% до 70%.")
        else:
            chance = normal_chance
        success = random.randint(1, 100) <= chance
        c.execute("DELETE FROM inventory WHERE id=? AND user_id=?", (action.item_id, uid))
        if success:
            c.execute("INSERT INTO inventory(user_id,skin_idx,obtained_at) VALUES(?,?,?)",
                      (uid, dst, int(time.time())))
            c.execute("UPDATE stats SET upgrades_won=upgrades_won+1 WHERE user_id=?", (uid,))
        else:
            c.execute("UPDATE stats SET upgrades_lost=upgrades_lost+1 WHERE user_id=?", (uid,))
    return {"success":success, "chance":chance, "skin":SKINS[dst] if success else None,
            "state":state_for(uid, user)}

@app.post("/api/daily")
def daily(x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    now = int(time.time())
    with db() as c:
        u = c.execute("SELECT daily_at FROM users WHERE user_id=?", (uid,)).fetchone()
        if now - u["daily_at"] < 86400:
            raise HTTPException(400, "Ежедневный бонус уже получен")
        c.execute("UPDATE users SET balance=balance+?,total_earned=total_earned+?,daily_at=? WHERE user_id=?",
                  (DAILY_BONUS, DAILY_BONUS, now, uid))
    return {"state":state_for(uid, user)}

@app.post("/api/friend-million")
def friend_million(x_telegram_init_data: str = Header(default="")):
    uid, user = telegram_user(x_telegram_init_data)
    if uid != FRIEND_ID:
        raise HTTPException(403, "Эта функция доступна только специальному игроку.")
    now = int(time.time())
    with db() as c:
        row = c.execute("SELECT friend_claim_at FROM users WHERE user_id=?", (uid,)).fetchone()
        remaining = FRIEND_CLAIM_COOLDOWN - (now - int(row["friend_claim_at"] or 0))
        if remaining > 0:
            raise HTTPException(429, f"Подожди ещё {remaining} сек.")
        c.execute("""UPDATE users SET balance=balance+?,total_earned=total_earned+?,
                     friend_claim_at=? WHERE user_id=?""",
                  (FRIEND_CLAIM_AMOUNT, FRIEND_CLAIM_AMOUNT, now, uid))
    return {"claimed":FRIEND_CLAIM_AMOUNT, "state":state_for(uid, user)}

dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    if not WEBAPP_URL.startswith("https://"):
        await message.answer("Mini App пока не опубликован: укажи HTTPS-адрес в WEBAPP_URL.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎮 Открыть DanekCase", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer(
        "🎮 <b>DANEKCASE</b>\n\nКейсы, CS2-скины, инвентарь и апгрейды.\n"
        "DanekCoin — только виртуальная игровая валюта, без денежных ставок и вывода.",
        reply_markup=kb, parse_mode="HTML"
    )

async def serve():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")
    await uvicorn.Server(config).serve()

async def main():
    if not TOKEN:
        raise RuntimeError("Укажи BOT_TOKEN в переменных окружения.")
    WEB.mkdir(parents=True, exist_ok=True)
    init_db()
    bot = Bot(TOKEN)
    try:
        await asyncio.gather(dp.start_polling(bot), serve())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
