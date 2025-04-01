import asyncio
import numpy as np
import pandas as pd
from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import bitvavo
from bot.logging_facility import LoggingFacility
from bot.ai_decider import AIDecider
import os
from datetime import datetime, timedelta
import argparse
import json

class Trader:
    VERSION = "0.1.5"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args

        self.bot_name = config.get("PROFILE", "AITRADER")
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()
        self.price_history = {}
        self.allow_sell = self.config.get("ALLOW_SELL", True)
        self.candles = config.get("CANDLES", 60)
        self.candle_interval = config.get("CANDLE_INTERVAL", "1h")
        self.ai_decider = AIDecider(pair_models=config["PAIR_MODELS"], logger=logger)

        for pair in config["PAIRS"]:
            try:
                historical_prices = TradingUtils.fetch_raw_candles(
                    self.bitvavo,
                    pair,
                    limit=self.candles,
                    interval=self.candle_interval
                )
                self.price_history[pair] = {
                    "open": [],
                    "high": [],
                    "low": [],
                    "close": [],
                    "volume": []
                }
                for candle in historical_prices:
                    self.price_history[pair]["open"].append(float(candle[1]))
                    self.price_history[pair]["high"].append(float(candle[2]))
                    self.price_history[pair]["low"].append(float(candle[3]))
                    self.price_history[pair]["close"].append(float(candle[4]))
                    self.price_history[pair]["volume"].append(float(candle[5]))
                self.log_message(f"🕯️  {pair}: Price candles loaded: {len(historical_prices)}")
            except Exception as e:
                self.log_message(f"⚠️ {pair}: Price candles unavailable: {e}")
                self.price_history[pair] = {
                    "open": [], "high": [], "low": [], "close": [], "volume": []
                }

        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] * self.config["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }

        self.log_startup_parameters()
        self.logger.log(
            f"📂 Loaded Portfolio:\n{json.dumps(self.portfolio, indent=4)}",
            to_console=True
        )

    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log("Portfolio loaded successfully.", to_console=True)
                    return portfolio
            except Exception as e:
                self.logger.log(f"❌ Error loading portfolio: {e}", to_console=True)
        return {}

    def log_message(self, message: str, to_slack: bool = False):
        prefixed_message = f"[{self.bot_name}]  {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        startup_info = {**self.config}
        self.log_message("🚀 Starting AI Trader", to_slack=True)
        self.log_message(f"⚙️ Startup Info: {json.dumps(startup_info, indent=2)}", to_slack=True)

    async def run(self):
        self.log_message(f"📊 Trading started at {datetime.now()}")

        try:
            while True:
                self.log_message(f"🐌 New evaluation cycle at {datetime.now()}")

                ranked_coins = TradingUtils.rank_coins(
                    self.bitvavo,
                    self.config["PAIRS"],
                    self.price_history,
                    rsi_window=self.candles
                )
                rank_dict = {pair: score for pair, score in ranked_coins}
                top_pairs = [pair for pair, _ in ranked_coins[:self.config.get("TOP_N_PAIRS", len(ranked_coins))]]
                self.log_message(f"🔍 Top pairs selected for evaluation: {top_pairs}")
                for pair in top_pairs:
                    
                    current_price = await asyncio.to_thread(TradingUtils.fetch_current_price, self.bitvavo, pair)
                    self.price_history[pair]["close"].append(current_price)
                    if len(self.price_history[pair]["close"]) > self.candles:
                        self.price_history[pair]["close"].pop(0)

                    rsi = TradingUtils.calculate_rsi(self.price_history[pair]["close"], window_size=self.candles)
                    macd, signal, macd_histogram = TradingUtils.calculate_macd(self.price_history[pair]["close"])
                    ema_fast = TradingUtils.calculate_ema(self.price_history[pair]["close"], window_size=12)
                    ema_slow = TradingUtils.calculate_ema(self.price_history[pair]["close"], window_size=26)
                    support, resistance = TradingUtils.calculate_support_resistance(self.price_history[pair]["close"], window_size=20)
                    atr = TradingUtils.calculate_atr(
                        self.price_history[pair]["high"],
                        self.price_history[pair]["low"],
                        self.price_history[pair]["close"],
                        14
                    )
                    momentum = TradingUtils.calculate_momentum(self.price_history[pair]["close"])
                    volume_change = TradingUtils.calculate_volume_change(self.price_history[pair]["volume"])

                    macd_diff = macd - signal if macd is not None and signal is not None else 0.0
                    ema_diff = ema_fast - ema_slow if ema_fast is not None and ema_slow is not None else 0.0
                    price_minus_support = current_price - support if support is not None else 0.0
                    resistance_minus_price = resistance - current_price if resistance is not None else 0.0

                    self.log_message(
                        f"🔎 {pair}: Price={current_price:.4f}, RSI={rsi:.2f}, MACD={macd:.4f}, Signal={signal:.4f}, ATR={atr:.4f}, MOM={momentum:.4f}"
                    )

                    # SELL
                    sell_result = self.ai_decider.should_sell(
                        pair, rsi, macd, signal, macd_histogram, ema_fast, ema_slow,
                        support, resistance, atr, momentum, volume_change,
                        current_price, macd_diff, ema_diff, price_minus_support, resistance_minus_price
                    )
                    if isinstance(sell_result, dict):
                        sell_decision = sell_result.get("decision", False)
                        sell_probability = sell_result.get("probability", 0.0)
                    else:
                        sell_decision = sell_result
                        sell_probability = 0.0

                    if sell_decision and sell_probability >= self.config.get("SELL_PROBABILITY_THRESHOLD", 0.9):
                        self.log_message(f"🔴 {pair}: AI-decider triggered SELL at {current_price:.4f}")
                        try:
                            self.state_managers[pair].sell_position(current_price, self.config["TRADE_FEE_PERCENTAGE"])
                        except Exception as e:
                            self.log_message(f"❌ Error during sell for {pair}: {e}")

                    # BUY
                    buy_result = self.ai_decider.should_buy(
                        pair, rsi, macd, signal, macd_histogram, ema_fast, ema_slow,
                        support, resistance, atr, momentum, volume_change,
                        current_price, macd_diff, ema_diff, price_minus_support, resistance_minus_price,
                        coin_rank_score=rank_dict.get(pair, 0.0)  # <- voeg coin rank score toe
                    )

                    if isinstance(buy_result, dict):
                        buy_decision = buy_result.get("decision", False)
                        buy_probability = buy_result.get("probability", 0.0)
                        risk_multiplier = buy_result.get("multiplier", 1.0)
                    else:
                        buy_decision = buy_result
                        buy_probability = 0.0
                        risk_multiplier = 1.0

                    if buy_decision and buy_probability >= self.config.get("BUY_PROBABILITY_THRESHOLD", 0.9):
                        max_budget = self.pair_budgets.get(pair, 0)
                        invest_amount = round(max_budget * risk_multiplier, 2)

                        if invest_amount > 0:
                            self.log_message(
                                f"🟢 {pair}: AI-decider triggered BUY at {current_price:.4f}, probability={buy_probability:.4f}, multiplier={risk_multiplier:.2f}, investing {invest_amount:.2f} EUR"
                            )
                            try:
                                self.state_managers[pair].buy(
                                    current_price,
                                    invest_amount,
                                    self.config["TRADE_FEE_PERCENTAGE"]
                                )
                            except Exception as e:
                                self.log_message(f"❌ Error during buy for {pair}: {e}")
                        else:
                            self.log_message(f"⚠️ {pair}: Calculated invest amount is 0 EUR, skipping BUY")



                self.log_message(f"💤 Next run starts in {self.config['CHECK_INTERVAL']} seconds.")
                await asyncio.sleep(self.config["CHECK_INTERVAL"])

        except KeyboardInterrupt:
            self.log_message("🛑 AITrader stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ AITrader finished.", to_slack=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Trader Bot")
    parser.add_argument("--config", type=str, default="config/ai_trader.json")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuratiebestand niet gevonden: {config_path}")

    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))

    state_managers = {
        pair: StateManager(
            pair,
            logger,
            bitvavo_instance,
            demo_mode=config.get("DEMO_MODE", False),
            bot_name=config.get("PROFILE", "AITRADER")
        )
        for pair in config["PAIRS"]
    }

    bot = Trader(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())

