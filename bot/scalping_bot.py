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


class ScalpingBot:
    """
    Async Scalping Bot with dynamic stoploss and risk allocation.
    """
    VERSION = "0.4.3"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        """
        Initializes the ScalpingBot.

        Args:
            config (dict): Configuration parameters from the config.json.
            logger (LoggingFacility): Logging module.
            state_managers (dict): A dict with StateManager instances per trading pair.
            bitvavo: The Bitvavo API client.
            args (argparse.Namespace): Commandline arguments.
        """
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args

        self.bot_name = config.get("PROFILE", "SCALPINGBOT")
        self.data_dir = "data"

        # Load dynamic portfolio allocation via StateManager
        self.pair_budgets = StateManager.initialize_portfolio(
            config, self.data_dir, self.logger
        )

        # RSI and EMA settings
        self.rsi_points = config.get("RSI_POINTS", 14)
        self.rsi_interval = config.get("RSI_INTERVAL", "1M").lower()
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.ema_profiles = config.get(
            "EMA_PROFILES", {"ULTRASHORT": 9, "SHORT": 21, "MEDIUM": 50, "LONG": 200})
        self.selected_ema = self.ema_profiles.get(
            config.get("EMA_PROFILE", "MEDIUM"), 50)
        self.ema_history = {pair: [] for pair in config["PAIRS"]}

        # RSI en EMA instellingen
        self.ema_buy_threshold = config.get("EMA_BUY_THRESHOLD", 0.995)
        self.ema_sell_threshold = config.get("EMA_SELL_THRESHOLD", 1.005)

        # Load historical prices for each pair (for RSI and EMA)
        for pair in config["PAIRS"]:
            try:
                required_candles = max(self.rsi_points, self.selected_ema)
                historical_prices = TradingUtils.fetch_historical_prices(
                    self.bitvavo, pair, limit=required_candles, interval=self.rsi_interval
                )
                if len(historical_prices) >= required_candles:
                    self.price_history[pair] = historical_prices.copy()
                    self.ema_history[pair] = historical_prices.copy()
                    self.log_message(
                        f"✅ {pair}: Loaded {len(historical_prices)} historical prices for EMA and RSI.")
                else:
                    self.log_message(
                        f"⚠️ {pair}: Insufficient data ({len(historical_prices)} candles, required: {required_candles}).")
            except Exception as e:
                self.log_message(
                    f"❌ Error fetching historical prices for {pair}: {e}")
                self.price_history[pair] = []
                self.ema_history[pair] = []

        self.log_startup_parameters()
        self.logger.log(
            f"📂 Portfolio loaded:\n{json.dumps(self.pair_budgets, indent=4)}", to_console=True)

    def log_message(self, message: str, to_slack: bool = False):
        """
        Logs a message with the standard prefix.

        Args:
            message (str): The message.
            to_slack (bool): If True, also send the message to Slack.
        """
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        """
        Logs the startup parameters.
        """
        startup_info = {**self.config}
        self.log_message("🚀 ScalpingBot starting up.", to_slack=True)
        self.log_message(
            f"⚠️ Startup info:\n{json.dumps(startup_info, indent=2)}", to_slack=True)

    async def run(self):
        """
        Main loop of the bot.
        """
        self.log_message(f"📊 Trading started on {datetime.now()}")
        atr_period = self.config.get("ATR_PERIOD", 14)
        atr_multiplier = self.config.get("ATR_MULTIPLIER", 1.5)
        risk_percentage = self.config.get("RISK_PERCENTAGE", 0.01)
        fee_percentage = self.config["TRADE_FEE_PERCENTAGE"]

        try:
            while True:
                self.log_message(f"🐌 New cycle started on {datetime.now()}")
                for pair in self.config["PAIRS"]:
                    # Get current price
                    current_price = await asyncio.to_thread(
                        TradingUtils.fetch_current_price, self.bitvavo, pair
                    )

                    # Update price and EMA histories
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.rsi_points:
                        self.price_history[pair].pop(0)

                    self.ema_history[pair].append(current_price)
                    if len(self.ema_history[pair]) > self.selected_ema:
                        self.ema_history[pair].pop(0)

                    # Calculate EMA and RSI if sufficient data is available
                    ema = None
                    if len(self.ema_history[pair]) >= self.selected_ema:
                        ema = await asyncio.to_thread(
                            TradingUtils.calculate_ema, self.ema_history[pair], self.selected_ema
                        )
                    rsi = None
                    if len(self.price_history[pair]) >= self.rsi_points:
                        rsi = await asyncio.to_thread(
                            TradingUtils.calculate_rsi, self.price_history[pair], self.rsi_points
                        )

                    # Log current open positions for the pair
                    open_positions = self.state_managers[pair].get_open_positions()
                    open_positions_len = len(open_positions)

                    # Log price, RSI and EMA
                    if rsi is not None:
                        price_str = f"{current_price:.8f}" if current_price < 1 else f"{current_price:.2f}"
                    if ema is not None:
                        ema_str = f"{ema:.8f} EUR" if ema < 1 else f"{ema:.2f} EUR"
                        self.log_message(
                            f"💎 {pair}: Price={price_str} EUR - RSI={rsi:.2f} - EMA:{ema_str} - Positions={open_positions_len}"
                        )

            

                    # Check open positions and execute dynamic stoploss via StateManager
                    try:
                        # Fetch candle-data for ATR calculation
                        candle_data = await asyncio.to_thread(
                            TradingUtils.fetch_historical_candles, self.bitvavo, pair,
                            limit=atr_period + 1, interval=self.rsi_interval
                        )
                        atr_value = TradingUtils.calculate_atr(
                            candle_data, period=atr_period)
                    except Exception as e:
                        self.log_message(
                            f"❌ Error calculating ATR for {pair}: {e}")
                        atr_value = None

                    # Let the StateManager handle Stoploss checking for this pair
                    await asyncio.to_thread(
                        self.state_managers[pair].check_stop_loss,
                        current_price, fee_percentage, atr_value, atr_multiplier
                    )


                    # Buy logic with dynamic risk allocation
                    if rsi is not None and ema is not None:
                        # Sell if RSI is above threshold and price is below EMA * EMA_SELL_THRESHOLD
                        if rsi >= self.config["RSI_SELL_THRESHOLD"] and current_price < ema * self.ema_sell_threshold:
                            if open_positions:
                                for pos in open_positions:
                                    profit_percentage = self.state_managers[pair].calculate_profit_for_position(
                                        pos, current_price, fee_percentage
                                    )
                                    if profit_percentage >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                        self.log_message(
                                            f"🔴 Selling {pair}: Price={current_price:.2f}, RSI={rsi:.2f}, EMA={ema:.2f}, Threshold={self.ema_sell_threshold}, Profit={profit_percentage:.2f}%",
                                            to_slack=True
                                        )
                                        await asyncio.to_thread(
                                            self.state_managers[pair].sell_position,
                                            pos,
                                            current_price,
                                            fee_percentage
                                        )
                                        # ✅ Update het budget na verkoop
                                        revenue = current_price * \
                                            pos["quantity"] * (1 - fee_percentage / 100)
                                        self.pair_budgets[pair] += revenue
                                        self.log_message(
                                            f"📊 Updated budget for {pair}: {self.pair_budgets[pair]:.2f} EUR")

                        # Buy when RSI is below threshold and price is above EMA * EMA_BUY_THRESHOLD
                        elif rsi <= self.config["RSI_BUY_THRESHOLD"] and current_price > ema * self.ema_buy_threshold:
                            max_trades = self.config.get("MAX_TRADES_PER_PAIR", 1)
                            if len(open_positions) < max_trades:
                                # Calculate the remaining budget for this pair.
                                allocated_budget = self.pair_budgets[pair]
                                total_spent = sum(pos.get("spent", 0) for pos in open_positions)
                                remaining_budget = allocated_budget - total_spent

                                # ✅ Extra check om te voorkomen dat de bot koopt met negatief budget
                                if remaining_budget > 0 and self.pair_budgets[pair] >= 0:
                                    try:
                                        candle_data = await asyncio.to_thread(
                                            TradingUtils.fetch_historical_candles, self.bitvavo, pair,
                                            limit=atr_period + 1, interval=self.rsi_interval
                                        )
                                        atr_value = TradingUtils.calculate_atr(
                                            candle_data, period=atr_period)
                                    except Exception as e:
                                        self.log_message(
                                            f"❌ Error calculating ATR for {pair}: {e}")
                                        atr_value = None

                                    if atr_value is not None:
                                        total_budget = self.config.get("TOTAL_BUDGET", 10000.0)
                                        risk_amount = total_budget * risk_percentage
                                        risk_per_unit = atr_multiplier * atr_value
                                        dynamic_quantity = risk_amount / risk_per_unit

                                        max_quantity = remaining_budget / current_price
                                        final_quantity = min(dynamic_quantity, max_quantity)

                                        self.log_message(
                                            f"🟢 Buying {pair}: Price={current_price:.2f}, RSI={rsi:.2f}, EMA={ema:.2f}, Threshold={self.ema_buy_threshold}, "
                                            f"Dynamic Quantity={final_quantity:.6f} (Risk per unit: {risk_per_unit:.2f})",
                                            to_slack=True
                                        )
                                        await asyncio.to_thread(
                                            self.state_managers[pair].buy_dynamic,
                                            current_price,
                                            final_quantity,
                                            fee_percentage
                                        )
                                    else:
                                        self.log_message(
                                            f"❌ Cannot calculate ATR for {pair}. Skipping buy.", to_slack=True)
                                else:
                                    self.log_message(
                                        f"🤚 Not enough budget remaining for {pair}. Remaining: {remaining_budget:.2f} EUR",
                                        to_slack=False
                                    )
                            else:
                                self.log_message(
                                    f"🤚 Skipping buy for {pair} (open trades: {len(open_positions)}) – max trades reached.",
                                    to_slack=False
                                )



                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 ScalpingBot stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ ScalpingBot trading ended.", to_slack=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Async scalping bot with dynamic stoploss and risk allocation"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="scalper.json",
        help="Path to JSON config file (default: scalper.json)"
    )
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))

    state_managers = {
        pair: StateManager(
            pair,
            logger,
            bitvavo_instance,
            demo_mode=config.get("DEMO_MODE", False),
            bot_name=config.get("PROFILE", "SCALPINGBOT")
        )
        for pair in config["PAIRS"]
    }

    bot = ScalpingBot(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())
