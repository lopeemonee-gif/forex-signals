#!/usr/bin/env python3
import json
import yfinance as yf
import pandas as pd
import schedule
import time
import logging
from datetime import datetime
from telegram import Bot
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('forex_signals.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ForexSignalBot:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.bot = Bot(token=self.config['telegram']['bot_token'])
        self.chat_id = self.config['telegram']['chat_id']
        self.pairs = self.config['trading']['pairs']
        self.rsi_period = self.config['indicators']['rsi_period']
        self.ma_short = self.config['indicators']['ma_short']
        self.ma_long = self.config['indicators']['ma_long']
        self.rsi_oversold = self.config['indicators']['rsi_oversold']
        self.rsi_overbought = self.config['indicators']['rsi_overbought']
        self.lookback = self.config['trading']['lookback_period']
        
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI (Relative Strength Index)"""
        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)
        
        avg_gain = gains.rolling(window=period).mean()
        avg_loss = losses.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def get_signal(self, pair):
        """Fetch data dan generate signal untuk pair"""
        try:
            logger.info(f"Fetching data for {pair}")
            data = yf.download(pair, period='3mo', interval='1h', progress=False)
            
            if len(data) < self.lookback:
                logger.warning(f"Insufficient data for {pair}")
                return None
            
            data = data[-self.lookback:]
            close = data['Close']
            
            # Calculate indicators
            rsi = self.calculate_rsi(close, self.rsi_period)
            ma_short = close.rolling(window=self.ma_short).mean()
            ma_long = close.rolling(window=self.ma_long).mean()
            
            # Latest values
            latest_price = close.iloc[-1]
            latest_rsi = rsi.iloc[-1]
            latest_ma_short = ma_short.iloc[-1]
            latest_ma_long = ma_long.iloc[-1]
            
            signal = None
            reason = ""
            
            # BUY signal: RSI oversold + price above short MA
            if latest_rsi < self.rsi_oversold and latest_price > latest_ma_short:
                signal = "BUY"
                reason = f"RSI {latest_rsi:.2f} < {self.rsi_oversold} (oversold)"
            
            # SELL signal: RSI overbought + price below short MA
            elif latest_rsi > self.rsi_overbought and latest_price < latest_ma_short:
                signal = "SELL"
                reason = f"RSI {latest_rsi:.2f} > {self.rsi_overbought} (overbought)"
            
            return {
                'pair': pair,
                'signal': signal,
                'price': latest_price,
                'rsi': latest_rsi,
                'ma20': latest_ma_short,
                'ma50': latest_ma_long,
                'reason': reason,
                'timestamp': datetime.now()
            }
        
        except Exception as e:
            logger.error(f"Error processing {pair}: {str(e)}")
            return None
    
    async def send_signal(self, signal_data):
        """Kirim signal ke Telegram"""
        if not signal_data or not signal_data['signal']:
            return
        
        try:
            message = (
                f"🚨 <b>{signal_data['signal']}</b> Signal\n\n"
                f"Pair: {signal_data['pair']}\n"
                f"Price: {signal_data['price']:.5f}\n"
                f"RSI: {signal_data['rsi']:.2f}\n"
                f"MA20: {signal_data['ma20']:.5f}\n"
                f"MA50: {signal_data['ma50']:.5f}\n\n"
                f"Reason: {signal_data['reason']}\n"
                f"Time: {signal_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"Signal sent: {signal_data['pair']} - {signal_data['signal']}")
        
        except Exception as e:
            logger.error(f"Error sending signal: {str(e)}")
    
    def check_signals(self):
        """Check semua pairs dan kirim signals"""
        for pair in self.pairs:
            signal = self.get_signal(pair)
            if signal:
                asyncio.run(self.send_signal(signal))
            time.sleep(1)  # rate limit
    
    def run(self):
        """Jalankan bot dengan schedule"""
        logger.info("Forex Signal Bot started")
        
        interval = self.config['trading'].get('check_interval_minutes', 60)
        schedule.every(interval).minutes.do(self.check_signals)
        
        # Initial check
        self.check_signals()
        
        while True:
            schedule.run_pending()
            time.sleep(10)

if __name__ == "__main__":
    bot = ForexSignalBot()
    bot.run()