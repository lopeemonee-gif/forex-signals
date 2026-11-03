#!/usr/bin/env python3
import json
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
from telegram import Bot
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def gen_data(pair):
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
    returns = np.random.normal(0.001, 0.05, 100)
    prices = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame({'Close': prices}, index=dates)

def calc_rsi(prices, period=14):
    deltas = prices.diff()
    gains = deltas.where(deltas > 0, 0)
    losses = -deltas.where(deltas < 0, 0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

async def send_signal(bot, chat_id, pair, signal_type, price, rsi):
    msg = f"🚨 <b>{signal_type}</b>\n\nPair: {pair}\nPrice: {price:.5f}\nRSI: {rsi:.2f}\nTime: {datetime.now().strftime('%H:%M:%S')}"
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode='HTML')
    logger.info(f"✓ {signal_type} sent for {pair}")

async def main():
    with open('config.json') as f:
        cfg = json.load(f)
    
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = int(cfg['telegram']['chat_id'].strip())
    pairs = cfg['trading']['pairs']
    
    logger.info("Bot started - checking every 30 seconds")
    
    count = 0
    while True:
        count += 1
        for pair in pairs:
            data = gen_data(pair)
            close = data['Close']
            rsi = calc_rsi(close, 14)
            ma20 = close.rolling(20).mean()
            
            price = close.iloc[-1]
            rsi_val = rsi.iloc[-1]
            ma20_val = ma20.iloc[-1]
            
            # Check signals
            if rsi_val < 30 and price > ma20_val:
                await send_signal(bot, chat_id, pair, "BUY", price, rsi_val)
            elif rsi_val > 70 and price < ma20_val:
                await send_signal(bot, chat_id, pair, "SELL", price, rsi_val)
        
        logger.info(f"Check #{count} - {len(pairs)} pairs scanned")
        time.sleep(30)

asyncio.run(main())
