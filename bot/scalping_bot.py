import numpy as np
import pandas as pd
from bot.config_loader import ConfigLoader
# Ensure this is the updated version with multi-position and stop loss logic.
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import bitvavo
from bot.logging_facility import LoggingFacility
import os
import time
from datetime import datetime, timedelta
import argparse
import json


class ScalpingBot:
    VERSION = "0.1.16"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()
        self.bot_name = args.bot_name
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] *
                   self.config["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }

        # Log startup parameters
        self.log_startup_parameters()

        # Log portfolio
        self.logger.log(f"📂 Loaded Portfolio:\n{json.dumps(
            self.portfolio, indent=4)}", to_console=True)

    def load_portfolio(self):
        """Load the portfolio content from a JSON file."""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log(
                        "Portfolio loaded successfully.", to_console=True)
                    return portfolio
            except Exception as e:
                self.logger.log(f"👽❌ Error loading portfolio: {
                                e}", to_console=True)
        return {}

    def log_message(self, message: str, to_slack: bool = False):
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        startup_info = {
            "version": self.VERSION,
            "bot_name": self.bot_name,
            "startup_parameters": vars(self.args),
            "config_file": self.args.config,
            "trading_pairs": self.config.get("PAIRS", []),
            "total_budget": self.config.get("TOTAL_BUDGET", "N/A"),
        }
        self.log_message("🚀 Starting ScalpingBot", to_slack=True)
        self.log_message(f"📊 Startup Info: {json.dumps(
            startup_info, indent=2)}", to_slack=True)

    def run(self):
        self.log_message(f"📊 Trading started at {datetime.now()}")
        try:
            while True:
                self.log_message(f"📊 New cycle started at {datetime.now()}")
                self.log_message(f"📈 Current budget per pair: {
                                 self.pair_budgets}")
                for pair in self.config["PAIRS"]:
                    current_price = TradingUtils.fetch_current_price(
                        self.bitvavo, pair)
                    rsi = TradingUtils.calculate_rsi(
                        self.price_history[pair], self.config["WINDOW_SIZE"])

                    # --- STOP LOSS CHECK ---
                    open_positions = self.state_managers[pair].get_open_positions(
                    )
                    if open_positions:
                        for position in open_positions:
                            # Calculate stop loss threshold based on the original buy price and the configured percentage.
                            stop_loss_threshold = position["price"] * (
                                1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
                            if current_price <= stop_loss_threshold:
                                self.log_message(
                                    f"⛔️ Stop loss triggered for {pair}: current price {
                                        current_price:.2f} is below threshold {stop_loss_threshold:.2f}",
                                    to_slack=True
                                )
                                self.state_managers[pair].sell_position_with_retry(
                                    position,
                                    current_price,
                                    self.config["TRADE_FEE_PERCENTAGE"],
                                    max_retries=self.config.get(
                                        "STOP_LOSS_MAX_RETRIES", 3),
                                    wait_time=self.config.get(
                                        "STOP_LOSS_WAIT_TIME", 5)
                                )

                    # --- TRADING LOGIC BASED ON RSI ---
                    if rsi is not None:
                        self.log_message(f"✅ Current price for {pair}: {
                                         current_price:.2f} EUR, RSI={rsi:.2f}")

                        # Selling logic when RSI is high and profit meets threshold.
                        if rsi >= self.config["SELL_THRESHOLD"]:
                            if open_positions:
                                for pos in open_positions:
                                    profit = self.state_managers[pair].calculate_profit_for_position(
                                        pos, current_price, self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                    if profit >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                        self.log_message(
                                            f"🔴 Selling trade for {pair} (bought at {pos['price']:.2f}). Current RSI={
                                                rsi:.2f}, Price: {current_price:.2f}, Profit={profit:.2f}%",
                                            to_slack=True
                                        )
                                        self.state_managers[pair].sell_position(
                                            pos, current_price, self.config["TRADE_FEE_PERCENTAGE"])
                                    else:
                                        self.log_message(
                                            f"⚠️ Skipping sell for trade in {pair} (bought at {pos['price']:.2f}): Profit {
                                                profit:.2f}% below threshold.",
                                            to_slack=False
                                        )

                        # Buying logic when RSI is low.
                        elif rsi <= self.config["BUY_THRESHOLD"]:
                            max_trades = self.config.get(
                                "MAX_TRADES_PER_PAIR", 1)
                            if len(open_positions) < max_trades:
                                self.log_message(
                                    f"🟢 Buying {pair}. Price: {current_price:.2f}, Current RSI={
                                        rsi:.2f}. Open trades: {len(open_positions)} (max allowed: {max_trades})",
                                    to_slack=True
                                )
                                self.state_managers[pair].buy(
                                    current_price,
                                    self.pair_budgets[pair],
                                    self.config["TRADE_FEE_PERCENTAGE"]
                                )
                            else:
                                self.log_message(
                                    f"ℹ️ Not buying {pair} as open trades ({len(open_positions)}) reached the limit of {
                                        max_trades}.",
                                    to_slack=False
                                )

                    # Update price history for RSI calculation.
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.config["WINDOW_SIZE"]:
                        self.price_history[pair].pop(0)

                time.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 ScalpingBot stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ ScalpingBot finished trading.", to_slack=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ScalpingBot with dynamic configuration, multi-trade support, and stop loss."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="scalper.json",
        help="Path to the JSON configuration file (default: scalper.json)"
    )
    parser.add_argument(
        "--bot-name",
        type=str,
        required=True,
        help="Unique name for the bot instance (required)"
    )
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Initialize bitvavo client and load configurations.
    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))

    # Create a StateManager for each trading pair.
    state_managers = {
        pair: StateManager(pair, logger, bitvavo_instance,
                           demo_mode=config.get("DEMO_MODE", False))
        for pair in config["PAIRS"]
    }

    bot = ScalpingBot(config, logger, state_managers, bitvavo_instance, args)
    bot.run()
