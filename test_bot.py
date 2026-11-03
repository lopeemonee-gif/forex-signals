#!/usr/bin/env python3
import json
from telegram import Bot
import asyncio

async def test_telegram():
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    token = config['telegram']['bot_token']
    chat_id = config['telegram']['chat_id']
    
    print(f"Token: {token[:15]}...")
    print(f"Chat ID: {chat_id}")
    
    bot = Bot(token=token)
    
    try:
        message = "🧪 Test message - Bot aktif!"
        await bot.send_message(chat_id=chat_id, text=message)
        print("✓ Message sent successfully")
    except Exception as e:
        print(f"✗ Error: {e}")

asyncio.run(test_telegram())
