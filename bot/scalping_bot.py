
import lightgbm as lgb
import numpy as np
import pandas as pd
from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import initialize_bitvavo
from bot.logging_facility import LoggingFacility
import os
import time
from datetime import datetime, timedelta
import argparse

class ScalpingBot:
    VERSION = "1.1.0"  # Updated version with enhanced logic and debugging

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] * self.config["REBALANCE_SETTINGS"]["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }
        self.end_time = datetime.now() + timedelta(hours=self.config["TRADING_PERIOD_HOURS"])

        # Log startup parameters
        self.log_startup_parameters()

        # Train or load LightGBM model
        if self.config.get("TRAIN_MODEL", False):
            self.lgb_model = self.train_lightgbm_model()
        else:
            self.lgb_model = self.load_lightgbm_model()

    def log_message(self, message: str, to_slack: bool = False):
        self.logger.log(message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        self.log_message(f"🚀 Starting ScalpingBot v{self.VERSION}")
        self.log_message(f"🔧 Startup parameters: {self.args}", to_slack=False)
        self.log_message(f"📁 Configuration loaded from: {self.args.config}", to_slack=False)

    def load_lightgbm_model(self):
        try:
            model = lgb.Booster(model_file=self.config["LIGHTGBM_MODEL_PATH"])
            self.log_message("✅ LightGBM model loaded successfully.", to_slack=False)
            return model
        except Exception as e:
            self.log_message(f"❗ Error loading LightGBM model: {e}. Falling back to RSI-based decisions.", to_slack=True)
            return None

    def price_dropped_significantly(self, current_price, price_history, drop_threshold):
        if len(price_history) < 2:
            return False

        previous_price = price_history[-2]
        price_change = (current_price - previous_price) / previous_price * 100
        return price_change <= -drop_threshold

    def run(self):
        self.log_message(f"📊 Trading started at {datetime.now()}")
        try:
            while datetime.now() < self.end_time:
                self.log_message(f"📊 New cycle started at {datetime.now()}")
                self.log_message(f"📈 Current budget per pair: {self.pair_budgets}")
                for pair in self.config["PAIRS"]:
                    current_price = TradingUtils.fetch_current_price(self.bitvavo, pair)
                    rsi = TradingUtils.calculate_rsi(self.price_history[pair], self.config["WINDOW_SIZE"])

                    if rsi is not None:
                        self.log_message(f"✅ Current price for {pair}: {current_price:.2f} EUR, RSI={rsi:.2f}")

                        # Selling logic
                        if rsi >= self.config["SELL_THRESHOLD"]:
                            if self.state_managers[pair].has_position():
                                profit = self.state_managers[pair].calculate_profit(
                                    current_price, self.config["TRADE_FEE_PERCENTAGE"]
                                )
                                if profit >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                    self.log_message(
                                        f"🔴 Selling {pair}. Current RSI={rsi:.2f}, Profit={profit:.2f}%",
                                        to_slack=True
                                    )
                                    self.state_managers[pair].sell(
                                        current_price,
                                        self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                else:
                                    self.log_message(
                                        f"⚠️ Skipping sell for {pair}: Profit {profit:.2f}% below threshold.",
                                        to_slack=False
                                    )

                        # Buying logic
                        elif rsi <= self.config["BUY_THRESHOLD"]:
                            if not self.state_managers[pair].has_position():
                                if self.price_dropped_significantly(
                                    current_price, self.price_history[pair], self.config["PRICE_DROP_THRESHOLD"]
                                ):
                                    self.log_message(
                                        f"🟢 Buying {pair}. Current RSI={rsi:.2f}, Price dropped significantly.",
                                        to_slack=True
                                    )
                                    self.state_managers[pair].buy(
                                        current_price,
                                        self.pair_budgets[pair],
                                        self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                else:
                                    self.log_message(
                                        f"⚠️ Skipping buy for {pair}: Price drop not significant.",
                                        to_slack=False
                                    )

                    # Debugging information
                    if self.config.get("DEBUG_MODE", False):
                        self.log_message(f"🔍 Debug info: {pair} -> Price={current_price:.2f}, RSI={rsi:.2f}")

                    # Update price history
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.config["WINDOW_SIZE"]:
                        self.price_history[pair].pop(0)

                time.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 ScalpingBot stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ ScalpingBot finished trading.", to_slack=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ScalpingBot with dynamic configuration.")
    parser.add_argument(
        "--config",
        type=str,
        default="scalper.json",
        help="Path to the JSON configuration file (default: scalper.json)"
    )
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))
    state_managers = {pair: StateManager(pair, logger) for pair in config["PAIRS"]}
    bitvavo = initialize_bitvavo(ConfigLoader.load_config("bitvavo.json"))

    bot = ScalpingBot(config, logger, state_managers, bitvavo, args)
    bot.run()
