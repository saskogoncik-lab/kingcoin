import sqlite3
import threading
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8862945504:AAEVflpOqm5N25ZhVRWK10WRCAzKa1hM740"
WEBAPP_URL = "https://saskogoncik-lab.github.io/kingcoin/"
ADMIN_ID = 8719426633

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 10,
            max_energy INTEGER DEFAULT 10
        )
    """)
    conn.commit()
    conn.close()

init_db()

class TapData(BaseModel):
    user_id: int

# ==================== API ENDPOINTS ====================
@app.get("/api/user/{user_id}")
def get_user(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, energy, max_energy FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, energy, max_energy) VALUES (?, 0, 10, 10)", (user_id,))
        conn.commit()
        row = (0, 10, 10)
    conn.close()
    return {"balance": row[0], "energy": row[1], "max_energy": row[2]}

@app.post("/api/tap")
def tap(data: TapData):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + 1, energy = MAX(0, energy - 1) WHERE user_id=?", (data.user_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

# ==================== BOT HANDLERS ====================
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👑 Play KING COIN", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await msg.answer("Welcome to KING COIN! Click the button below to start playing:", reply_markup=kb)

@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("❌ Access denied.")
        return
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(balance) FROM users")
    stats = cursor.fetchone()
    conn.close()
    
    total_users = stats[0] or 0
    total_coins = stats[1] or 0
    
    await msg.answer(
        f"⚙️ **Admin Panel**\n\n"
        f"👥 Total Players: **{total_users}**\n"
        f"🪙 Total Tapped Coins: **{total_coins}**"
    )

# ==================== RUN SERVER & BOT ====================
def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def main():
    print("🚀 Server and Bot are running!")
    threading.Thread(target=run_fastapi, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


