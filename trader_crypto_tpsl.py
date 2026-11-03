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
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crypto_signals.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CryptoSignalBot:
    def __init__(self, config_path='config_crypto.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.bot = Bot(token=self.config['telegram']['bot_token'])
        self.chat_id = int(self.config['telegram']['chat_id'].strip())
        self.pairs = self.config['trading']['pairs']
        self.lookback_days = self.config['trading']['lookback_days']
        self.rsi_period = self.config['indicators']['rsi_period']
        self.ma_short = self.config['indicators']['ma_short']
        self.ma_long = self.config['indicators']['ma_long']
        self.rsi_oversold = self.config['indicators']['rsi_oversold']
        self.rsi_overbought = self.config['indicators']['rsi_overbought']
        self.tp_percent = self.config['trading'].get('take_profit_percent', 10)
        self.sl_percent = self.config['trading'].get('stop_loss_percent', 5)
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self.positions_file = 'positions.json'
        self.positions = self.load_positions()
        
    def load_positions(self):
        """Load open positions from file"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_positions(self):
        """Save positions to file"""
        with open(self.positions_file, 'w') as f:
            json.dump(self.positions, f, indent=2)
    
    def calculate_rsi(self, prices, period=14):
        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)
        
        avg_gain = gains.rolling(window=period).mean()
        avg_loss = losses.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def fetch_crypto_data(self, coingecko_id):
        """Fetch crypto price history from CoinGecko"""
        try:
            url = f"{self.coingecko_url}/coins/{coingecko_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': self.lookback_days,
                'interval': 'daily'
            }
            
            logger.info(f"Fetching {coingecko_id} data from CoinGecko...")
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'prices' not in data:
                logger.error(f"No price data for {coingecko_id}")
                return None
            
            prices = data['prices']
            timestamps = [datetime.fromtimestamp(p[0]/1000) for p in prices]
            closes = [p[1] for p in prices]
            
            df = pd.DataFrame({'Close': closes}, index=timestamps)
            return df
        
        except Exception as e:
            logger.error(f"Error fetching {coingecko_id}: {str(e)}")
            return None
    
    def get_signal(self, pair):
        try:
            symbol = pair['symbol']
            coingecko_id = pair['coingecko_id']
            
            data = self.fetch_crypto_data(coingecko_id)
            
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
            
            if latest_rsi < self.rsi_oversold:
                signal = "BUY"
                reason = f"RSI {latest_rsi:.2f} < {self.rsi_oversold} (oversold)"
            elif latest_rsi > self.rsi_overbought:
                signal = "SELL"
                reason = f"RSI {latest_rsi:.2f} > {self.rsi_overbought} (overbought)"
            
            return {
                'pair': symbol,
                'coingecko_id': coingecko_id,
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
    
    def check_position_levels(self, pair_symbol, current_price):
        """Check if current price hit TP or SL"""
        if pair_symbol not in self.positions:
            return None
        
        pos = self.positions[pair_symbol]
        entry_price = pos['entry_price']
        tp_price = pos['tp_price']
        sl_price = pos['sl_price']
        
        if current_price >= tp_price:
            return {'type': 'TP', 'price': tp_price, 'profit': (current_price - entry_price) / entry_price * 100}
        elif current_price <= sl_price:
            return {'type': 'SL', 'price': sl_price, 'loss': (current_price - entry_price) / entry_price * 100}
        
        return None
    
    async def send_signal(self, signal_data):
        if not signal_data or not signal_data['signal']:
            return
        
        try:
            pair_symbol = signal_data['pair']
            current_price = signal_data['price']
            
            if signal_data['signal'] == "BUY":
                # Open position
                tp_price = current_price * (1 + self.tp_percent / 100)
                sl_price = current_price * (1 - self.sl_percent / 100)
                
                self.positions[pair_symbol] = {
                    'entry_price': current_price,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'timestamp': signal_data['timestamp'].isoformat()
                }
                self.save_positions()
                
                message = (
                    f"🚨 *{signal_data['signal']}* Signal\n\n"
                    f"Pair: {signal_data['pair']}\n"
                    f"Entry Price: ${current_price:.2f}\n"
                    f"Take Profit: ${tp_price:.2f} (+{self.tp_percent}%)\n"
                    f"Stop Loss: ${sl_price:.2f} (-{self.sl_percent}%)\n"
                    f"RSI: {signal_data['rsi']:.2f}\n\n"
                    f"Reason: {signal_data['reason']}\n"
                    f"Time: {signal_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                # Close position
                if pair_symbol in self.positions:
                    del self.positions[pair_symbol]
                    self.save_positions()
                
                message = (
                    f"🚨 *{signal_data['signal']}* Signal\n\n"
                    f"Pair: {signal_data['pair']}\n"
                    f"Exit Price: ${current_price:.2f}\n"
                    f"RSI: {signal_data['rsi']:.2f}\n"
                    f"MA20: ${signal_data['ma20']:.2f}\n"
                    f"MA50: ${signal_data['ma50']:.2f}\n\n"
                    f"Reason: {signal_data['reason']}\n"
                    f"Time: {signal_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Signal sent: {signal_data['pair']} - {signal_data['signal']}")
        
        except Exception as e:
            logger.error(f"Error sending signal: {str(e)}")
    
    async def send_tp_sl_alert(self, pair_symbol, level_data, current_price):
        """Send alert when TP or SL hit"""
        try:
            level_type = level_data['type']
            entry_price = self.positions[pair_symbol]['entry_price']
            pnl_percent = level_data.get('profit', level_data.get('loss', 0))
            
            message = (
                f"📍 *{level_type} HIT*\n\n"
                f"Pair: {pair_symbol}\n"
                f"Entry: ${entry_price:.2f}\n"
                f"Exit: ${current_price:.2f}\n"
                f"P&L: {pnl_percent:+.2f}%\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"{level_type} hit for {pair_symbol} at ${current_price:.2f}")
        
        except Exception as e:
            logger.error(f"Error sending TP/SL alert: {str(e)}")
    
    def check_signals(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for pair in self.pairs:
                signal = self.get_signal(pair)
                if signal:
                    # Check TP/SL first
                    level = self.check_position_levels(signal['pair'], signal['price'])
                    if level:
                        loop.run_until_complete(self.send_tp_sl_alert(signal['pair'], level, signal['price']))
                        if signal['pair'] in self.positions:
                            del self.positions[signal['pair']]
                            self.save_positions()
                    
                    # Send new signal
                    loop.run_until_complete(self.send_signal(signal))
                
                time.sleep(1)
        finally:
            loop.close()
    
    def run(self):
        logger.info("Crypto Signal Bot started (with TP/SL tracking)")
        
        interval = self.config['trading'].get('check_interval_minutes', 60)
        schedule.every(interval).minutes.do(self.check_signals)
        
        # Initial check
        self.check_signals()
        
        while True:
            schedule.run_pending()
            time.sleep(10)

if __name__ == "__main__":
    bot = CryptoSignalBot()
    bot.run()
