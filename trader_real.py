#!/usr/bin/env python3
import json
import requests
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
    def __init__(self, config_path='config_real.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.bot = Bot(token=self.config['telegram']['bot_token'])
        self.chat_id = int(self.config['telegram']['chat_id'].strip())
        self.api_key = self.config['alpha_vantage']['api_key']
        self.pairs = self.config['trading']['pairs']
        self.rsi_period = self.config['indicators']['rsi_period']
        self.ma_short = self.config['indicators']['ma_short']
        self.ma_long = self.config['indicators']['ma_long']
        self.rsi_oversold = self.config['indicators']['rsi_oversold']
        self.rsi_overbought = self.config['indicators']['rsi_overbought']
        self.base_url = "https://www.alphavantage.co/query"
        
    def calculate_rsi(self, prices, period=14):
        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)
        
        avg_gain = gains.rolling(window=period).mean()
        avg_loss = losses.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def fetch_forex_data(self, from_currency, to_currency):
        """Fetch forex data from Alpha Vantage"""
        try:
            params = {
                'function': 'FX_INTRADAY',
                'from_symbol': from_currency,
                'to_symbol': to_currency,
                'interval': '60min',
                'apikey': self.api_key,
                'outputsize': 'full'
            }
            
            logger.info(f"Fetching {from_currency}/{to_currency} from Alpha Vantage...")
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if 'Error Message' in data:
                logger.error(f"API Error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"API Limit: {data['Note']}")
                return None
            
            if 'Time Series (60min)' not in data:
                logger.error(f"No data for {from_currency}/{to_currency}")
                return None
            
            ts = data['Time Series (60min)']
            times = []
            closes = []
            
            for time_str in sorted(ts.keys(), reverse=True)[:100]:
                times.append(pd.Timestamp(time_str))
                closes.append(float(ts[time_str]['4. close']))
            
            times.reverse()
            closes.reverse()
            
            df = pd.DataFrame({'Close': closes}, index=times)
            return df
        
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return None
    
    def get_signal(self, pair):
        try:
            from_currency = pair['from_currency']
            to_currency = pair['to_currency']
            symbol = pair['symbol']
            
            data = self.fetch_forex_data(from_currency, to_currency)
            
            if data is None or len(data) < self.ma_long:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            close = data['Close']
            
            rsi = self.calculate_rsi(close, self.rsi_period)
            ma_short = close.rolling(window=self.ma_short).mean()
            ma_long = close.rolling(window=self.ma_long).mean()
            
            latest_price = close.iloc[-1]
            latest_rsi = rsi.iloc[-1]
            latest_ma_short = ma_short.iloc[-1]
            latest_ma_long = ma_long.iloc[-1]
            
            signal = None
            reason = ""
            
            if latest_rsi < self.rsi_oversold and latest_price > latest_ma_short:
                signal = "BUY"
                reason = f"RSI {latest_rsi:.2f} < {self.rsi_oversold} (oversold)"
            elif latest_rsi > self.rsi_overbought and latest_price < latest_ma_short:
                signal = "SELL"
                reason = f"RSI {latest_rsi:.2f} > {self.rsi_overbought} (overbought)"
            
            return {
                'pair': symbol,
                'signal': signal,
                'price': latest_price,
                'rsi': latest_rsi,
                'ma20': latest_ma_short,
                'ma50': latest_ma_long,
                'reason': reason,
                'timestamp': datetime.now()
            }
        
        except Exception as e:
            logger.error(f"Error processing {pair['symbol']}: {str(e)}")
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
        logger.info("Forex Signal Bot started with real data (Alpha Vantage)")
        logger.info(f"API Key: {self.api_key[:10]}...")
        
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
