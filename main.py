import asyncio
import sqlite3
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading

# ================= CONFIGURATION =================
BOT_TOKEN = "8862945504:AAEVfIpOqm5N25ZhVRWK10WRCAzKa1hM740"
WEBAPP_URL = "https://your-domain.vercel.app"  # Link to index.html

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 10,
            max_energy INTEGER DEFAULT 10,
            energy_level INTEGER DEFAULT 1,
            last_click_time REAL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            channel_id TEXT,
            link TEXT,
            reward INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            user_id INTEGER,
            task_id INTEGER,
            PRIMARY KEY (user_id, task_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance, energy, max_energy, energy_level, last_click_time FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, last_click_time) VALUES (?, ?)", (user_id, time.time()))
        conn.commit()
        user = (user_id, 0, 10, 10, 1, time.time())
    conn.close()
    
    u_id, balance, energy, max_energy, level, last_time = user
    now = time.time()
    elapsed = now - last_time
    if elapsed >= 300: # 5 minutes recovery
        energy = max_energy
        conn = sqlite3.connect("database.db")
        conn.cursor().execute("UPDATE users SET energy = ?, last_click_time = ? WHERE user_id = ?", (energy, now, u_id))
        conn.commit()
        conn.close()
    
    return {
        "user_id": u_id,
        "balance": balance,
        "energy": energy,
        "max_energy": max_energy,
        "energy_level": level
    }

# ================= API FOR MINI APP =================
@app.get("/api/get_user")
def api_get_user(user_id: int):
    return get_user(user_id)

@app.post("/api/tap")
async def api_tap(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    count = data.get("count", 1)
    
    user = get_user(user_id)
    if user["energy"] >= count:
        new_balance = user["balance"] + count
        new_energy = user["energy"] - count
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ?, energy = ?, last_click_time = ? WHERE user_id = ?", 
                       (new_balance, new_energy, time.time(), user_id))
        conn.commit()
        conn.close()
        return {"status": "ok", "balance": new_balance, "energy": new_energy}
    return {"status": "error", "message": "Not enough energy"}

@app.post("/api/upgrade")
async def api_upgrade(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    user = get_user(user_id)
    
    cost = user["energy_level"] * 500
    if user["balance"] >= cost:
        new_balance = user["balance"] - cost
        new_max = user["max_energy"] + 5
        new_level = user["energy_level"] + 1
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ?, max_energy = ?, energy_level = ? WHERE user_id = ?", 
                       (new_balance, new_max, new_level, user_id))
        conn.commit()
        conn.close()
        return {"status": "ok", "balance": new_balance, "max_energy": new_max, "energy_level": new_level}
    return {"status": "error", "message": "Not enough coins"}

@app.get("/api/tasks")
def api_tasks(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, link, reward FROM tasks")
    all_tasks = cursor.fetchall()
    
    cursor.execute("SELECT task_id FROM user_tasks WHERE user_id = ?", (user_id,))
    completed = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    result = []
    for t in all_tasks:
        result.append({
            "id": t[0],
            "title": t[1],
            "link": t[2],
            "reward": t[3],
            "completed": t[0] in completed
        })
    return result

# ================= TELEGRAM BOT & ADMIN PANEL =================
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    get_user(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Play KING COIN", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("Welcome! Tap KING COIN and upgrade your mining power!", reply_markup=kb)

# Admin Command: /add_task Title | @channel | https://t.me/link | 100
@dp.message(Command("add_task"))
async def add_task_cmd(message: types.Message):
    try:
        data = message.text.replace("/add_task ", "").split(" | ")
        title, channel_id, link, reward = data[0], data[1], data[2], int(data[3])
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (title, channel_id, link, reward) VALUES (?, ?, ?, ?)",
                       (title, channel_id, link, reward))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Task added successfully!\nTitle: {title}\nReward: {reward} coins")
    except Exception as e:
        await message.answer("❌ Error! Format:\n`/add_task Title | @channel | https://t.me/link | 100`", parse_mode="Markdown")

def start_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def main():
    threading.Thread(target=start_fastapi, daemon=True).start()
    print("🚀 Server and Bot are running!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
