import asyncio
import numpy as np
import pandas as pd
from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import bitvavo
from bot.logging_facility import LoggingFacility
import os
from datetime import datetime, timedelta
import argparse
import json


class Trader:
    """
    Async Scalping bot
    """
    VERSION = "0.1.36"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        """
        Init of the bot
        """
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args

        self.bot_name = config.get("PROFILE", "TRADER")
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()
        self.rsi_points = config.get("RSI_POINTS", 14)  # aantal RSI punten
        self.rsi_interval = config.get("RSI_INTERVAL", "1M").lower()
        self.price_history = {}
        for pair in config["PAIRS"]:
            try:
                historical_prices = TradingUtils.fetch_historical_prices(
                    self.bitvavo,
                    pair,
                    limit=self.rsi_points,
                    interval=self.rsi_interval
                )
                self.price_history[pair] = historical_prices
                historical_prices_len = len(historical_prices)
                self.log_message(
                    f"🕯️  {pair}: Price candles loaded: {historical_prices_len}")
            except Exception as e:
                self.log_message(
                    f"⚠️ {pair}: Price candles unavailable: {e}")
                # fallback indien ophalen mislukt
                self.price_history[pair] = []

        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] *
                self.config["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }

        self.log_startup_parameters()
        self.logger.log(
            f"📂 Loaded Portfolio:\n{json.dumps(self.portfolio, indent=4)}",
            to_console=True
        )

    def load_portfolio(self):
        """Loads portfolio from portfolio.json"""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log(
                        "Portfolio loaded successfully.", to_console=True)
                    return portfolio
            except Exception as e:
                self.logger.log(
                    f"❌ Error loading portfolio: {e}", to_console=True)
        return {}

    def log_message(self, message: str, to_slack: bool = False):
        """Standard log message format"""
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        """Show startup information"""
        startup_info = {
            **self.config
        }
        self.log_message("🚀 Starting Trader", to_slack=True)
        self.log_message(
            f"⚠️ Startup Info: {json.dumps(startup_info, indent=2)}", to_slack=True)

    async def run(self):
        """Main async loop"""
        self.log_message(f"📊 Trading started at {datetime.now()}")
        try:
            while True:
                self.log_message(f"🐌 New cycle started at {datetime.now()}")
                current_time = datetime.now()

                # Fetch current price for RSI calculation
                for pair in self.config["PAIRS"]:
                    current_price = await asyncio.to_thread(
                        TradingUtils.fetch_current_price, self.bitvavo, pair
                    )

                    # Add current price to RSI array
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.rsi_points:
                        self.price_history[pair].pop(0)

                    # Calculate RSI
                    if len(self.price_history[pair]) >= self.rsi_points:
                        rsi = await asyncio.to_thread(
                            TradingUtils.calculate_rsi, self.price_history[pair], self.rsi_points
                        )
                    else:
                        rsi = None

                    # Check stop-loss conditions
                    open_positions = self.state_managers[pair].get_open_positions(
                    )
                    if open_positions:
                        for position in open_positions:
                            stop_loss_threshold = position["price"] * (
                                1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
                            if current_price <= stop_loss_threshold:
                                self.log_message(
                                    f"⛔️ {pair}: Stop loss triggered for current price {current_price:.2f} is below threshold {stop_loss_threshold:.2f}",
                                    to_slack=True
                                )
                                await asyncio.to_thread(
                                    self.state_managers[pair].sell_position,
                                    current_price,
                                    self.config["TRADE_FEE_PERCENTAGE"],
                                    stop_loss=True,
                                    max_retries=self.config.get("STOP_LOSS_MAX_RETRIES", 3),
                                    wait_time=self.config.get("STOP_LOSS_WAIT_TIME", 5)
                                )

                    # Start RSI calculations
                    if rsi is not None:
                        if current_price < 1:
                            # Determine digits for high numerbered cryptos
                            price_str = f"{current_price:.8f}"
                        else:
                            price_str = f"{current_price:.2f}"

                        self.log_message(
                            f"💎 {pair}[{len(open_positions)}] Current price: {price_str} EUR, RSI={rsi:.2f}")

                        # Sell Logic
                        if rsi >= self.config["RSI_SELL_THRESHOLD"]:
                            if open_positions:
                                for pos in open_positions:
                                    profit_percentage = self.state_managers[pair].calculate_profit_for_position(
                                        pos, current_price, self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                    absolute_profit = (current_price * pos["quantity"] * (
                                        1 - self.config["TRADE_FEE_PERCENTAGE"] / 100)) - (pos["price"] * pos["quantity"])
                                    if profit_percentage >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                        self.log_message(
                                            f"🔴 {pair}: Selling trade for (bought at {pos['price']:.2f}). Current RSI={rsi:.2f}, Price: {current_price:.2f}, Profit: {profit_percentage:.2f}% / {absolute_profit:.2f} EUR",
                                            to_slack=True
                                        )
                                        await asyncio.to_thread(
                                            self.state_managers[pair].sell_position,
                                            current_price,
                                            self.config["TRADE_FEE_PERCENTAGE"],
                                            stop_loss=False
                                        )
                                    else:
                                        self.log_message(
                                            f"🤚 {pair}: Skipping sell for trade (bought at {pos['price']:.2f}): Profit {profit_percentage:.2f}% / {absolute_profit:.2f} EUR below threshold.",
                                            to_slack=False
                                        )

                        # Buy Logic
                        elif rsi <= self.config["RSI_BUY_THRESHOLD"]:
                            max_trades = self.config.get(
                                "MAX_TRADES_PER_PAIR", 1)
                            if len(open_positions) < max_trades:
                                investment_per_trade = self.pair_budgets[pair] / max_trades
                                self.log_message(
                                    f"🟢 {pair}: Buying. Price: {current_price:.2f}, RSI={rsi:.2f}. Open trades: {len(open_positions)} (max allowed: {max_trades}). Investeringsbedrag per trade: {investment_per_trade:.2f}",
                                    to_slack=True
                                )
                                await asyncio.to_thread(
                                    self.state_managers[pair].buy,
                                    current_price,
                                    investment_per_trade,
                                    self.config["TRADE_FEE_PERCENTAGE"]
                                )
                            else:
                                self.log_message(
                                    f"🤚 {pair}: Not buying as open trades ({len(open_positions)}) reached the limit of {max_trades}.",
                                    to_slack=False
                                )

                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 Trader stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ Trader finished trading.", to_slack=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Asynchroon Trader met dynamische configuratie, multi-trade ondersteuning en historische data voor directe RSI-berekening."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="trader.json",
        help="Pad naar het JSON-configuratiebestand (default: trader.json)"
    )
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuratiebestand niet gevonden: {config_path}")

    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))

    # Pas de aanroep van StateManager aan zodat de botnaam wordt meegegeven
    state_managers = {
        pair: StateManager(
            pair,
            logger,
            bitvavo_instance,
            demo_mode=config.get("DEMO_MODE", False),
            bot_name=config.get("PROFILE", "TRADER")
        )
        for pair in config["PAIRS"]
    }

    bot = Trader(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())
