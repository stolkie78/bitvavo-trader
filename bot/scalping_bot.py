
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
    """A scalping bot with full data pipeline, training, and AI integration."""

    VERSION = "0.1.0"  # Bot version for identification

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo):
        """Initializes the ScalpingBot."""
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] * self.config["REBALANCE_SETTINGS"]["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }
        self.end_time = datetime.now() + timedelta(hours=self.config["TRADING_PERIOD_HOURS"])

        # Train or load LightGBM model
        if self.config.get("TRAIN_MODEL", False):
            self.lgb_model = self.train_lightgbm_model()
        else:
            self.lgb_model = self.load_lightgbm_model()

    def log_message(self, message: str, to_slack: bool = False):
        """Logs a message with optional Slack notification."""
        self.logger.log(message, to_console=True, to_slack=to_slack)

    def load_lightgbm_model(self):
        """Loads the LightGBM model for AI-based predictions."""
        try:
            model = lgb.Booster(model_file=self.config["LIGHTGBM_MODEL_PATH"])
            self.log_message("✅ LightGBM model loaded successfully.", to_slack=False)
            return model
        except Exception as e:
            self.log_message(f"❗ Error loading LightGBM model: {e}. Falling back to RSI-based decisions.", to_slack=True)
            return None

    @staticmethod
    def price_dropped_significantly(current_price, price_history, drop_threshold):
        """Check if the price dropped significantly over the last interval."""
        if len(price_history) < 2:
            return False  # Not enough data to compare

        previous_price = price_history[-2]  # Last known price before current
        price_change = (current_price - previous_price) / previous_price * 100
        return price_change <= -drop_threshold

    def run(self):
        """Runs the scalping bot's main trading loop."""
        self.log_message(f"🚀 Starting ScalpingBot v{self.VERSION} with updated data preparation!", to_slack=True)
        try:
            while datetime.now() < self.end_time:
                self.log_message(f"📊 New cycle started at {datetime.now()}")
                self.log_message(f"📈 Current budget per pair: {self.pair_budgets}")
                for pair in self.config["PAIRS"]:
                    current_price = TradingUtils.fetch_current_price(self.bitvavo, pair)
                    rsi = TradingUtils.calculate_rsi(self.price_history[pair], self.config["WINDOW_SIZE"])

                    self.log_message(f"✅ Current price for {pair}: {current_price:.2f} EUR")
                    if rsi is not None:
                        self.log_message(f"📊 Indicators for {pair}: RSI={rsi:.2f}")

                        # Decision logic for selling
                        if rsi >= self.config["SELL_THRESHOLD"]:
                            if self.state_managers[pair].has_position():
                                self.log_message(
                                    f"🔴 Attempting to sell {pair}. Current RSI={rsi:.2f}, Threshold={self.config['SELL_THRESHOLD']:.2f}"
                                )
                                profit = self.state_managers[pair].sell(
                                    current_price,
                                    self.config["TRADE_FEE_PERCENTAGE"],
                                    self.config.get("MINIMUM_PROFIT_PERCENTAGE", 0.0)
                                )
                                if profit is not None:
                                    self.log_message(f"💰 Profit for {pair}: {profit:.2f} EUR")

                        # Decision logic for buying
                        elif rsi <= self.config["BUY_THRESHOLD"]:
                            if not self.state_managers[pair].has_position():
                                # Check for significant price drop
                                if self.price_dropped_significantly(
                                    current_price, self.price_history[pair], self.config["PRICE_DROP_THRESHOLD"]
                                ):
                                    self.log_message(
                                        f"🟢 Buying {pair}. Current RSI={rsi:.2f}, Price dropped significantly (>{self.config['PRICE_DROP_THRESHOLD']}%)",
                                        to_slack=True
                                    )
                                    self.state_managers[pair].buy(
                                        current_price,
                                        self.pair_budgets[pair],
                                        self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                else:
                                    self.log_message(
                                        f"⚠️ Skipping buy for {pair}: Price drop not significant enough.",
                                        to_slack=False
                                    )
                            else:
                                self.log_message(f"⚠️ Skipping buy for {pair}: Already holding a position.")

                        else:
                            self.log_message(f"🤔 Decision for {pair}: hold")

                    # Update price history for RSI calculation
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

    # Load the configuration based on the provided path
    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))
    state_managers = {pair: StateManager(pair, logger) for pair in config["PAIRS"]}
    bitvavo = initialize_bitvavo(ConfigLoader.load_config("bitvavo.json"))

    # Start the bot with the specified configuration
    bot = ScalpingBot(config, logger, state_managers, bitvavo)
    bot.run()
