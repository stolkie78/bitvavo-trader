#!/usr/bin/env python3
import asyncio
import os
import json
import argparse
from datetime import datetime
import pandas as pd

from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import bitvavo
from bot.logging_facility import LoggingFacility


class TraderBot:
    VERSION = "0.5.4"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args
        
        self.bot_name = config.get("PROFILE", "TRADER")
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()

        # RSI and EMA settings
        self.rsi_points = config.get("RSI_POINTS", 14)
        self.rsi_interval = config.get("RSI_INTERVAL", "1M").lower()
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.ema_points = config.get("EMA_POINTS", 14)
        self.ema_history = {pair: [] for pair in config["PAIRS"]}
        self.ema_buy_threshold = self.config.get("EMA_BUY_THRESHOLD", 0.002)
        self.ema_sell_threshold = self.config.get("EMA_SELL_THRESHOLD", -0.002)
        self.type = self.config.get("TYPE", "TRADER").upper()

        for pair in config["PAIRS"]:
            try:
                required_candles = max(self.rsi_points, self.ema_points)
                historical_prices = TradingUtils.fetch_historical_prices(
                    self.bitvavo, pair, limit=required_candles, interval=self.rsi_interval
                )
                if len(historical_prices) >= required_candles:
                    self.price_history[pair] = historical_prices.copy()
                    self.ema_history[pair] = historical_prices.copy()
                    self.log_message(f"✅ {pair}: {len(historical_prices)} historical prices loaded for EMA and RSI.")
                else:
                    self.log_message(f"⚠️ {pair}: Insufficient data ({len(historical_prices)} candles, needed: {required_candles}).")
            except Exception as e:
                self.log_message(f"❌ Error fetching historical prices for {pair}: {e}")
                self.price_history[pair] = []
                self.ema_history[pair] = []

        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] * self.config["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }

        self.log_startup_parameters()
        self.logger.log(f"📂 Portfolio loaded:\n{json.dumps(self.portfolio, indent=4)}", to_console=True)

    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log("Portfolio successfully loaded.", to_console=True)
                    return portfolio
            except json.JSONDecodeError as e:
                self.logger.log(f"❌ The portfolio file is invalid: {e}", to_console=True)
            except Exception as e:
                self.logger.log(f"❌ Error loading the portfolio: {e}", to_console=True)
        return {}

    def log_message(self, message: str, to_slack: bool = False):
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        startup_info = {**self.config}
        self.log_message(f"🚀 TraderBot is starting in {self.type} mode.", to_slack=True)
        self.log_message(f"⚠️ Startup info:\n{json.dumps(startup_info, indent=2)}", to_slack=True)

    async def run(self):
        self.log_message(f"📊 Trading started at {datetime.now()}")
        try:
            while True:
                self.log_message(f"🐌 New cycle started at {datetime.now()}")
                for pair in self.config["PAIRS"]:
                    current_price = await asyncio.to_thread(TradingUtils.fetch_current_price, self.bitvavo, pair)
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.rsi_points:
                        self.price_history[pair].pop(0)

                    self.ema_history[pair].append(current_price)
                    if len(self.ema_history[pair]) > self.ema_points:
                        self.ema_history[pair].pop(0)

                    ema = None
                    if len(self.ema_history[pair]) >= self.ema_points:
                        ema = await asyncio.to_thread(TradingUtils.calculate_ema, self.ema_history[pair], self.ema_points)
                    rsi = None
                    if len(self.price_history[pair]) >= self.rsi_points:
                        rsi = await asyncio.to_thread(TradingUtils.calculate_rsi, self.price_history[pair], self.rsi_points)

                    open_positions = self.state_managers[pair].get_open_positions()
                    price_str = f"{current_price:.8f}" if current_price < 1 else f"{current_price:.2f}"

                    if rsi is not None and ema is not None:
                        ema_diff = (current_price - ema) / ema
                        ema_str = f"{ema:.8f}" if ema < 1 else f"{ema:.2f}"
                        self.log_message(f"💎 {pair}[{len(open_positions)}]: Price={price_str} EUR - RSI={rsi:.2f} - EMA={ema_str} - EMA diff: {ema_diff:.4f}")

                        for position in open_positions:
                            atr_value = None
                            try:
                                candle_data = await asyncio.to_thread(TradingUtils.fetch_historical_candles, self.bitvavo, pair, limit=self.config.get("ATR_PERIOD", 14) + 1, interval=self.rsi_interval)
                                atr_value = TradingUtils.calculate_atr(candle_data, period=self.config.get("ATR_PERIOD", 14))
                            except Exception as e:
                                self.log_message(f"❌ Error in ATR calculation for {pair}: {e}")

                            dynamic_stoploss = position["price"] - (atr_value * self.config.get("ATR_MULTIPLIER", 1.5)) if atr_value else position["price"] * (1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
                            if current_price <= dynamic_stoploss:
                                self.log_message(f"⛔️ {pair}: Stoploss triggered: current price {current_price:.2f} is below {dynamic_stoploss:.2f}", to_slack=True)
                                await asyncio.to_thread(self.state_managers[pair].sell_position_with_retry, position, current_price, self.config["TRADE_FEE_PERCENTAGE"], self.config.get("STOP_LOSS_MAX_RETRIES", 3), self.config.get("STOP_LOSS_WAIT_TIME", 5))

                        if self.type == "TRADER":
                            if rsi >= self.config["RSI_SELL_THRESHOLD"] and ema_diff <= self.ema_sell_threshold:
                                if open_positions:
                                    for pos in open_positions:
                                        profit_percentage = self.state_managers[pair].calculate_profit_for_position(pos, current_price, self.config["TRADE_FEE_PERCENTAGE"])
                                        if profit_percentage >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                            self.log_message(f"🔴 {pair}: SELLING Calculated profit {profit_percentage:.2f}% | EMA diff: {ema_diff:.4f}", to_slack=True)
                                            await asyncio.to_thread(self.state_managers[pair].sell_position, pos, current_price, self.config["TRADE_FEE_PERCENTAGE"])
                                        else:
                                            self.log_message(f"{pair}: 🤚 Skipping sell ({len(open_positions)}) - max trades", to_slack=True)
                            elif rsi <= self.config["RSI_BUY_THRESHOLD"] and ema_diff >= self.ema_buy_threshold:
                                max_trades = self.config.get("MAX_TRADES_PER_PAIR", 1)
                                if len(open_positions) < max_trades:
                                    try:
                                        candle_data = await asyncio.to_thread(TradingUtils.fetch_historical_candles, self.bitvavo, pair, limit=self.config.get("ATR_PERIOD", 14) + 1, interval=self.rsi_interval)
                                        atr_value = TradingUtils.calculate_atr(candle_data, period=self.config.get("ATR_PERIOD", 14))
                                    except Exception as e:
                                        self.log_message(f"❌ Error in ATR calculation for {pair}: {e}")
                                        atr_value = None

                                    if atr_value is not None:
                                        total_budget = self.config.get("TOTAL_BUDGET", 10000.0)
                                        risk_percentage = self.config.get("RISK_PERCENTAGE", 0.01)
                                        atr_multiplier = self.config.get("ATR_MULTIPLIER", 1.5)
                                        risk_amount = total_budget * risk_percentage
                                        risk_per_unit = atr_multiplier * atr_value
                                        dynamic_quantity = risk_amount / risk_per_unit

                                        allocated_budget = self.pair_budgets[pair] / max_trades
                                        max_quantity = allocated_budget / current_price
                                        final_quantity = min(dynamic_quantity, max_quantity)

                                        self.log_message(f"🟢 {pair}: BUYING Price={current_price:.2f}, RSI={rsi:.2f}, EMA={ema_str}, EMA diff: {ema_diff:.4f} | Dynamic Quantity={final_quantity:.6f} (Risk per unit: {risk_per_unit:.2f})", to_slack=True)
                                        await asyncio.to_thread(self.state_managers[pair].buy_dynamic, current_price, final_quantity, self.config["TRADE_FEE_PERCENTAGE"])
                                    else:
                                        self.log_message(f"❌ Cannot calculate ATR for {pair}. Purchase skipped.", to_slack=True)
                                else:
                                    self.log_message(f"{pair}: 🤚 Skipping buy ({len(open_positions)}) - max trades ({max_trades}) reached.", to_slack=True)
                        else:
                            if self.config.get("EXPLAIN", False):
                                explanation_lines = []
                                if rsi >= self.config["RSI_SELL_THRESHOLD"]:
                                    if ema_diff > self.ema_sell_threshold:
                                        explanation_lines.append(f"For selling: EMA diff ({ema_diff:.4f}) is too high; must be ≤ {self.ema_sell_threshold}")
                                else:
                                    explanation_lines.append(f"For selling: RSI ({rsi:.2f}) is too low; must be ≥ {self.config['RSI_SELL_THRESHOLD']}")
                                if rsi <= self.config["RSI_BUY_THRESHOLD"]:
                                    if ema_diff < self.ema_buy_threshold:
                                        explanation_lines.append(f"For buying: EMA diff ({ema_diff:.4f}) is too low; must be ≥ {self.ema_buy_threshold}")
                                else:
                                    explanation_lines.append(f"For buying: RSI ({rsi:.2f}) is too high; must be ≤ {self.config['RSI_BUY_THRESHOLD']}")
                                max_trades = self.config.get("MAX_TRADES_PER_PAIR", 1)
                                if len(open_positions) >= max_trades:
                                    explanation_lines.append(f"Maximum open trades reached: {len(open_positions)}/{max_trades}")
                                if explanation_lines:
                                    self.log_message(f"[EXPLAIN] {pair}: " + "; ".join(explanation_lines))

                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 TraderBot stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ TraderBot trading ended.", to_slack=True)

    def check_stop_loss(self, pair, current_price):
        open_positions = self.state_managers[pair].get_open_positions()
    
        for position in open_positions:
            stop_loss_price = position["price"] * (1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
    
            if current_price <= stop_loss_price:
                self.log_message(f"⛔️ {pair}: Stop-loss reached! Price: {current_price:.2f}, Threshold: {stop_loss_price:.2f}", to_slack=True)

                if self.type == "TRADER":
                    sell_success = self.state_managers[pair].sell_position_with_retry(position, current_price, self.config["TRADE_FEE_PERCENTAGE"], self.config.get("STOP_LOSS_MAX_RETRIES", 3), self.config.get("STOP_LOSS_WAIT_TIME", 5))
                    if sell_success:
                        self.log_message(f"✅ {pair}: Stoploss sale successful at {current_price:.2f}", to_slack=True)
                    else:
                        self.log_message(f"❌ {pair}: Stoploss sale failed, retrying...", to_slack=True)
                else:
                    self.log_message(f"🛑 {pair}: Stoploss reached, but no sale in HODL mode.", to_slack=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async Trader bot with dynamic stoploss and risk management")
    parser.add_argument("--config", type=str, default="trader.json", help="Path to JSON config file (default: trader.json)")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))

    state_managers = {
        pair: StateManager(pair, logger, bitvavo_instance, demo_mode=config.get("DEMO_MODE", False), bot_name=config.get("PROFILE", "TRADER"))
        for pair in config["PAIRS"]
    }

    bot = TraderBot(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())