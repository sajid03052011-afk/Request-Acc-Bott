import os
import asyncio
import logging
import aiosqlite
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, ChatJoinRequest,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Logging setup
logging.basicConfig(level=logging.INFO)

# Hardcoded Bot Token and Admin ID
BOT_TOKEN = "8800949120:AAHpC9CV1c1oz4O47vLcSLOBbWbXUKSaDus"
ADMIN_ID = 8984439807

# Initialize Bot & Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

DB_FILE = "bot_database.db"

# Initialize SQLite Database
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                channel_id INTEGER,
                channel_title TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

# Flask App for Render 24/7 Web Service & Health Check
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running live and active! 🚀"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# FSM States
class BotStates(StatesGroup):
    waiting_for_welcome = State()
    waiting_for_broadcast = State()
    waiting_for_restore_file = State()

# Helper Functions for Settings
async def get_welcome_message():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT value FROM settings WHERE key = 'welcome_text'") as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
    return "Hello {name}! Welcome to our channel. 🎉"

async def save_welcome_message(text: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES ('welcome_text', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (text, text)
        )
        await db.commit()

# Keyboards
def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Dashboard & Stats", callback_data="stats")],
        [InlineKeyboardButton(text="⚙️ Set Welcome Message", callback_data="set_welcome")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="broadcast")],
        [InlineKeyboardButton(text="➕ Add Bot to Channel", callback_data="add_channel")],
        [InlineKeyboardButton(text="💾 Backup Data", callback_data="backup_data"),
         InlineKeyboardButton(text="🔄 Restore Data", callback_data="restore_data")]
    ])

def back_to_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu")]
    ])

# /start Command Handler (Restricted to Admin Only)
@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ You are not authorized to use this bot.")
        return

    welcome_caption = (
        "🤖 **Channel Automation & Manager Bot**\n\n"
        "Welcome Boss! Use the control panel buttons below to manage your channels, "
        "accept join requests, customize welcome messages, broadcast, and handle backups."
    )
    await message.answer(welcome_caption, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

# Callback: Back to Main Menu
@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await callback.message.edit_text(
        "🤖 **Channel Automation & Manager Bot**\n\nChoose an option below:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

# Callback: Stats & Dashboard
@router.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        
        async with db.execute("SELECT COUNT(DISTINCT channel_id) FROM users") as cursor:
            channels_count = (await cursor.fetchone())[0]
    
    stats_text = (
        "📊 **Bot Statistics & Dashboard**\n\n"
        f"👥 **Total Saved Users in DB:** `{total_users}`\n"
        f"📢 **Connected Channels:** `{channels_count}`\n"
        f"🚀 **Status:** `Active & Ready`"
    )
    await callback.message.edit_text(stats_text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()

# Callback: Add Channel
@router.callback_query(F.data == "add_channel")
async def cb_add_channel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    add_link = f"https://t.me/{bot_username}?startgroup=true&admin=invite_users+manage_chat"
    
    text = (
        "➕ **Add Bot to Multiple Channels:**\n\n"
        "Click the button below to add this bot as an **Administrator** to any of your channels.\n\n"
        "💡 *Note:* Make sure to give it permissions to **'Invite Users via Link'** or **'Manage Chat'**."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Add to Channel / Group", url=add_link)],
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# Callback: Manual Backup Button
@router.callback_query(F.data == "backup_data")
async def cb_backup_data(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    if os.path.exists(DB_FILE):
        file = FSInputFile(DB_FILE)
        await callback.message.answer_document(
            document=file,
            caption="💾 **Here is your database backup file!**\nKeep it safe. You can use it later with the Restore button if you redeploy."
        )
    else:
        await callback.message.answer("⚠️ No database file found yet!", reply_markup=back_to_menu_keyboard())
    await callback.answer()

# Callback: Restore Data Prompt
@router.callback_query(F.data == "restore_data")
async def cb_restore_data(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    text = (
        "🔄 **Restore Database**\n\n"
        "Please **forward** or **upload** your backup `.db` file here to restore all data."
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_restore_file)
    await callback.answer()

# Handle Restore File Upload/Forward
@router.message(BotStates.waiting_for_restore_file, F.document)
async def process_restore_file(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    document = message.document
    if not document.file_name.endswith(".db"):
        await message.answer("⚠️ Please send a valid `.db` backup file!", reply_markup=back_to_menu_keyboard())
        return

    try:
        file_info = await bot.get_file(document.file_id)
        file_path = file_info.file_path
        
        await bot.download(file_path, destination=DB_FILE)
        await state.clear()
        
        await message.answer(
            "✅ **Database restored successfully with 100% data!**",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Failed to restore: {e}", reply_markup=main_menu_keyboard())
        await state.clear()

# Callback: Set Welcome Message Prompt
@router.callback_query(F.data == "set_welcome")
async def cb_set_welcome(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    current_msg = await get_welcome_message()
    text = (
        "⚙️ **Configure Welcome Message**\n\n"
        f"Current Message:\n`{current_msg}`\n\n"
        "💡 *Tip:* You can use `{name}` to insert the user's name dynamically.\n\n"
        "Please send the new welcome message text now:"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_welcome)
    await callback.answer()

# Handle New Welcome Text Input
@router.message(BotStates.waiting_for_welcome)
async def process_new_welcome(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_text = message.text
    await save_welcome_message(new_text)
    await state.clear()
    
    await message.answer(
        "✅ **Welcome message updated successfully!**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu")]
        ]),
        parse_mode="Markdown"
    )

# Callback: Broadcast Prompt
@router.callback_query(F.data == "broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]

    text = (
        "📢 **Broadcast Message**\n\n"
        f"Total users who will receive the broadcast: `{total_users}`\n\n"
        "Please send the message (Text, Photo, or Video with caption) you want to broadcast:"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="Markdown")
    await state.set_state(BotStates.waiting_for_broadcast)
    await callback.answer()

# Execute Broadcast
@router.message(BotStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await state.clear()
    status_msg = await message.answer("🚀 **Broadcast started...** Please wait.", parse_mode="Markdown")
    
    success = 0
    failed = 0
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            async for row in cursor:
                user_id = row[0]
                try:
                    await message.copy_to(chat_id=user_id)
                    success += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1
            
    report = (
        "📊 **Broadcast Completed!**\n\n"
        f"✅ **Successful:** `{success}`\n"
        f"❌ **Failed (Blocked/Deleted):** `{failed}`"
    )
    await status_msg.edit_text(report, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

# Auto-Accept Join Requests
@router.chat_join_request()
async def handle_join_request(join_request: ChatJoinRequest):
    chat = join_request.chat
    user = join_request.from_user
    
    try:
        await join_request.approve()
        
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, channel_id, channel_title)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    channel_id = excluded.channel_id,
                    channel_title = excluded.channel_title
            """, (user.id, user.username, user.first_name, chat.id, chat.title))
            await db.commit()
        
        welcome_template = await get_welcome_message()
        final_welcome = welcome_template.replace("{name}", user.first_name)
        
        await bot.send_message(chat_id=user.id, text=final_welcome)
        logging.info(f"Accepted join request for {user.id} in channel {chat.title}")
    except Exception as e:
        logging.error(f"Error handling join request: {e}")

# Background task for Automatic 1-Hour Backup
async def automated_backup_loop():
    while True:
        await asyncio.sleep(3600)  # Wait for 1 hour
        try:
            if os.path.exists(DB_FILE):
                file = FSInputFile(DB_FILE)
                await bot.send_document(
                    chat_id=ADMIN_ID,
                    document=file,
                    caption="🕒 **Automated 1-Hour Database Backup**\nHere is your periodic backup file."
                )
                logging.info("Automated backup sent successfully to admin.")
        except Exception as e:
            logging.error(f"Error in automated backup: {e}")

# Main entry point
async def main():
    await init_db()
    
    # Start Flask server in background thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logging.info("Flask server started in background thread.")
    
    # Start 1-hour automated backup background task
    asyncio.create_task(automated_backup_loop())
    
    # Start bot polling
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot polling started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
