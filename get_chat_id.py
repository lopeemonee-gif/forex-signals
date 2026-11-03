#!/usr/bin/env python3
from telegram import Bot
import asyncio

async def get_chat_id():
    token = '9254054753:AAF3bR0fhPZ-S37-keoHumBcw2DkvDPy1HI'
    bot = Bot(token=token)
    
    print("Fetching updates...")
    updates = await bot.get_updates()
    
    if updates:
        print("\n✓ Chat IDs found:")
        for update in updates:
            if update.message:
                chat_id = update.message.chat_id
                username = update.message.from_user.username or "N/A"
                print(f"  Chat ID: {chat_id} (User: @{username})")
    else:
        print("\n✗ No updates. Kirim /start ke bot dulu di Telegram.")

asyncio.run(get_chat_id())
