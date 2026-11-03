#!/usr/bin/env python3
import json
import pandas as pd
import numpy as np
import schedule
import time
import logging
from datetime import datetime, timedelta
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
        
    def calculate_rsi(self, prices, period=14):
        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)
        
        avg_gain = gains.rolling(window=period).mean()
        avg_loss = losses.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_mock_data(self, pair, base_price=100):
        """Generate realistic mock OHLCV data"""
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1h')
        
        # Random walk untuk realistic price movement
        returns = np.random.normal(0.001, 0.02, 100)
        prices = base_price * np.exp(np.cumsum(returns))
        
        data = pd.DataFrame({
            'Open': prices * (1 + np.random.uniform(-0.01, 0.01, 100)),
            'High': prices * (1 + np.random.uniform(0, 0.02, 100)),
            'Low': prices * (1 + np.random.uniform(-0.02, 0, 100)),
            'Close': prices,
            'Volume': np.random.randint(1000000, 5000000, 100)
        }, index=dates)
        
        return data
    
    def get_signal(self, pair):
        try:
            logger.info(f"Fetching data for {pair}")
            
            # Use mock data
            base_prices = {'SPY': 380, 'AAPL': 230, 'MSFT': 380, 'GOOGL': 140}
            base = base_prices.get(pair, 100)
            data = self.generate_mock_data(pair, base)
            
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
            
            # BUY signal
            if latest_rsi < self.rsi_oversold and latest_price > latest_ma_short:
                signal = "BUY"
                reason = f"RSI {latest_rsi:.2f} < {self.rsi_oversold} (oversold)"
            
            # SELL signal
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
        for pair in self.pairs:
            signal = self.get_signal(pair)
            if signal:
                asyncio.run(self.send_signal(signal))
            time.sleep(1)
    
    def run(self):
        logger.info("Forex Signal Bot started (MOCK MODE)")
        
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
