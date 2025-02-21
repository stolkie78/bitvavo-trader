#!/usr/bin/env python3
import asyncio
import os
import json
import argparse
import time
from datetime import datetime
from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import bitvavo
from bot.logging_facility import LoggingFacility

class TraderBot:
    VERSION = "0.6.0"

    def __init__(self, config, logger, state_managers, bitvavo, args):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args
        self.bot_name = config.get("PROFILE", "TRADER")
        self.stoploss_cooldown = config.get("STOP_LOSS_COOLDOWN", 300)
        self.last_stoploss_time = {pair: None for pair in config["PAIRS"]}
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.ema_history = {pair: [] for pair in config["PAIRS"]}
        self.load_historical_data()
        self.log_startup()

    def load_historical_data(self):
        for pair in self.config["PAIRS"]:
            try:
                candles = TradingUtils.fetch_historical_prices(
                    self.bitvavo, pair, limit=max(self.config["RSI_POINTS"], self.config["EMA_POINTS"]),
                    interval=self.config.get("RSI_INTERVAL", "1M").lower()
                )
                if candles:
                    self.price_history[pair] = candles.copy()
                    self.ema_history[pair] = candles.copy()
                    self.logger.log(f"✅ {pair}: Loaded {len(candles)} historical prices.", to_console=True)
            except Exception as e:
                self.logger.log(f"❌ Error loading historical prices for {pair}: {e}", to_console=True)

    def log_startup(self):
        self.logger.log(f"🚀 TraderBot {self.VERSION} started.", to_console=True, to_slack=True)

    async def run(self):
        self.logger.log(f"📊 Trading started at {datetime.now()}")
        try:
            while True:
                self.logger.log(f"🐌 New cycle started at {datetime.now()}")
                for pair in self.config["PAIRS"]:
                    await self.process_pair(pair)
                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.logger.log("🛑 TraderBot stopped by user.", to_slack=True)

    async def process_pair(self, pair):
        current_price = await asyncio.to_thread(TradingUtils.fetch_current_price, self.bitvavo, pair)
        if not current_price:
            self.logger.log(f"⚠️ {pair}: Unable to fetch price.", to_console=True)
            return

        rsi, ema, ema_diff = await self.calculate_indicators(pair, current_price)
        open_positions = self.state_managers[pair].get_open_positions()
        self.logger.log(f"💎 {pair}[{len(open_positions)}]: Price={current_price:.2f} EUR - RSI={rsi:.2f} - EMA={ema:.2f} - EMA diff: {ema_diff:.4f}")

        if open_positions:
            await self.handle_stoploss(pair, current_price, open_positions)
        if self.should_sell(rsi, ema_diff):
            await self.sell_positions(pair, current_price, open_positions)
        elif self.should_buy(rsi, ema_diff, pair, open_positions):
            await self.buy_position(pair, current_price)

    async def calculate_indicators(self, pair, current_price):
        self.price_history[pair].append(current_price)
        self.ema_history[pair].append(current_price)
        
        if len(self.price_history[pair]) > self.config["RSI_POINTS"]:
            self.price_history[pair].pop(0)
        if len(self.ema_history[pair]) > self.config["EMA_POINTS"]:
            self.ema_history[pair].pop(0)
        
        ema = await asyncio.to_thread(TradingUtils.calculate_ema, self.ema_history[pair], self.config["EMA_POINTS"])
        rsi = await asyncio.to_thread(TradingUtils.calculate_rsi, self.price_history[pair], self.config["RSI_POINTS"])
        ema_diff = (current_price - ema) / ema if ema else 0
        return rsi, ema, ema_diff

    async def handle_stoploss(self, pair, current_price, open_positions):
        for position in open_positions:
            stop_loss_price = position["price"] * (1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
            if current_price <= stop_loss_price:
                self.logger.log(f"🚫 {pair}: Stoploss triggered at {current_price:.2f}.", to_slack=True)
                await asyncio.to_thread(self.state_managers[pair].sell, current_price, self.config["TRADE_FEE_PERCENTAGE"], is_stoploss=True)
                return

    async def sell_positions(self, pair, current_price, open_positions):
        for position in open_positions:
            profit = self.state_managers[pair].calculate_profit_for_position(position, current_price, self.config["TRADE_FEE_PERCENTAGE"])
            if profit >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                self.logger.log(f"🔴 {pair}: SELLING Profit {profit:.2f}%.", to_slack=True)
                await asyncio.to_thread(self.state_managers[pair].sell, current_price, self.config["TRADE_FEE_PERCENTAGE"])
                return

    async def buy_position(self, pair, current_price):
        budget = self.config.get("TOTAL_BUDGET", 10000.0) / len(self.config["PAIRS"])
        self.logger.log(f"🟢 {pair}: BUYING Price={current_price:.2f} EUR", to_slack=True)
        await asyncio.to_thread(self.state_managers[pair].buy, current_price, budget, self.config["TRADE_FEE_PERCENTAGE"])

    def should_sell(self, rsi, ema_diff):
        return rsi >= self.config["RSI_SELL_THRESHOLD"] and ema_diff <= self.config["EMA_SELL_THRESHOLD"]

    def should_buy(self, rsi, ema_diff, pair, open_positions):
        last_sl_time = self.last_stoploss_time.get(pair)
        cooldown_active = last_sl_time and (time.time() - last_sl_time) < self.stoploss_cooldown
        return not cooldown_active and len(open_positions) < self.config.get("MAX_TRADES_PER_PAIR", 1) and rsi <= self.config["RSI_BUY_THRESHOLD"] and ema_diff >= self.config["EMA_BUY_THRESHOLD"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async Trader bot")
    parser.add_argument("--config", type=str, default="trader.json", help="Path to JSON config file")
    args = parser.parse_args()
    config = ConfigLoader.load_config(args.config)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))
    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    state_managers = {pair: StateManager(pair, logger, bitvavo_instance, demo_mode=config.get("DEMO_MODE", False)) for pair in config["PAIRS"]}
    bot = TraderBot(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())