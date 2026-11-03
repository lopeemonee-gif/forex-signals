#!/usr/bin/env python3
import json
import time
import logging
from datetime import datetime
from telegram import Bot
import asyncio
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def send_signal(bot, chat_id, pair, signal_type):
    price = random.uniform(100, 400)
    rsi = random.uniform(25, 75)
    msg = f"🚨 <b>{signal_type}</b>\n\nPair: {pair}\nPrice: {price:.5f}\nRSI: {rsi:.2f}\nTime: {datetime.now().strftime('%H:%M:%S')}"
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
    logger.info(f"✓ {signal_type} sent for {pair}")

async def main():
    with open('config.json') as f:
        cfg = json.load(f)
    
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = int(cfg['telegram']['chat_id'].strip())
    pairs = cfg['trading']['pairs']
    
    logger.info("DEMO MODE - forcing signals every 30s")
    
    signals = ['BUY', 'SELL']
    count = 0
    
    while True:
        count += 1
        pair = random.choice(pairs)
        signal = random.choice(signals)
        await send_signal(bot, chat_id, pair, signal)
        logger.info(f"Check #{count} done")
        time.sleep(30)

asyncio.run(main())
