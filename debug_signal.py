#!/usr/bin/env python3
import json
import pandas as pd
import numpy as np
from datetime import datetime
import asyncio
from telegram import Bot

# Generate mock data
def gen_data(pair):
    dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
    returns = np.random.normal(0.001, 0.02, 100)
    prices = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame({'Close': prices}, index=dates)

# Calculate RSI
def calc_rsi(prices, period=14):
    deltas = prices.diff()
    gains = deltas.where(deltas > 0, 0)
    losses = -deltas.where(deltas < 0, 0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

async def test_signal():
    with open('config.json') as f:
        cfg = json.load(f)
    
    bot = Bot(token=cfg['telegram']['bot_token'])
    chat_id = int(cfg['telegram']['chat_id'].strip())
    
    # Generate data for SPY
    data = gen_data('SPY')
    close = data['Close']
    rsi = calc_rsi(close, 14)
    ma20 = close.rolling(20).mean()
    
    latest_price = close.iloc[-1]
    latest_rsi = rsi.iloc[-1]
    latest_ma20 = ma20.iloc[-1]
    
    print(f"SPY Price: {latest_price:.2f}")
    print(f"RSI: {latest_rsi:.2f}")
    print(f"MA20: {latest_ma20:.2f}")
    
    # Force BUY signal for testing
    message = (
        f"🚨 <b>BUY</b> Signal TEST\n\n"
        f"Pair: SPY\n"
        f"Price: {latest_price:.5f}\n"
        f"RSI: {latest_rsi:.2f}\n"
        f"MA20: {latest_ma20:.5f}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    print(f"\nSending to chat {chat_id}...")
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
    print("✓ Sent!")

asyncio.run(test_signal())
