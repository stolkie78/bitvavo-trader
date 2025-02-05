import asyncio
import numpy as np
import pandas as pd
from bot.config_loader import ConfigLoader
# Zorg dat deze versie multi-posities en stop loss ondersteunt
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.bitvavo_client import bitvavo
from bot.logging_facility import LoggingFacility
import os
from datetime import datetime, timedelta
import argparse
import json


class ScalpingBot:
    VERSION = "0.1.19"

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
        # Dictionaries om de RSI los van de CHECK_INTERVAL bij te houden.
        self.last_rsi_update = {pair: None for pair in config["PAIRS"]}
        self.cached_rsi = {pair: None for pair in config["PAIRS"]}

        # Log startup parameters
        self.log_startup_parameters()

        # Log portfolio
        self.logger.log(f"📂 Loaded Portfolio:\n{json.dumps(
            self.portfolio, indent=4)}", to_console=True)

    def load_portfolio(self):
        """Laadt de portfolio uit een JSON-bestand."""
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

    async def run(self):
        self.log_message(f"📊 Trading started at {datetime.now()}")
        try:
            while True:
                self.log_message(f"📊 New cycle started at {datetime.now()}")
                self.log_message(f"📈 Current budget per pair: {
                                 self.pair_budgets}")
                current_time = datetime.now()

                # Itereer over elk crypto-paar
                for pair in self.config["PAIRS"]:
                    # Haal de huidige prijs asynchroon op (via een thread)
                    current_price = await asyncio.to_thread(TradingUtils.fetch_current_price, self.bitvavo, pair)

                    # Werk de prijs geschiedenis bij
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.config["WINDOW_SIZE"]:
                        self.price_history[pair].pop(0)

                    # Bepaal of het tijd is om de RSI opnieuw te berekenen
                    rsi_interval = self.config.get(
                        "RSI_INTERVAL", self.config["CHECK_INTERVAL"])
                    last_update = self.last_rsi_update[pair]
                    if last_update is None or (current_time - last_update).total_seconds() >= rsi_interval:
                        rsi = await asyncio.to_thread(TradingUtils.calculate_rsi, self.price_history[pair], self.config["WINDOW_SIZE"])
                        self.cached_rsi[pair] = rsi
                        self.last_rsi_update[pair] = current_time
                    else:
                        rsi = self.cached_rsi[pair]

                    # --- STOP LOSS CHECK ---
                    open_positions = self.state_managers[pair].get_open_positions(
                    )
                    if open_positions:
                        for position in open_positions:
                            # Bereken de stop loss drempel (bijv. -5% van de aankoopprijs)
                            stop_loss_threshold = position["price"] * (
                                1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
                            if current_price <= stop_loss_threshold:
                                self.log_message(
                                    f"⛔️ Stop loss triggered for {pair}: current price {
                                        current_price:.2f} is below threshold {stop_loss_threshold:.2f}",
                                    to_slack=True
                                )
                                await asyncio.to_thread(
                                    self.state_managers[pair].sell_position_with_retry,
                                    position,
                                    current_price,
                                    self.config["TRADE_FEE_PERCENTAGE"],
                                    self.config.get(
                                        "STOP_LOSS_MAX_RETRIES", 3),
                                    self.config.get("STOP_LOSS_WAIT_TIME", 5)
                                )

                    # --- RSI GEBASEERDE TRADING LOGICA ---
                    if rsi is not None:
                        self.log_message(f"✅ Current price for {pair}: {
                                         current_price:.2f} EUR, RSI={rsi:.2f}")

                        # Verkooplogica: Als de RSI boven de SELL_THRESHOLD komt en de winst voldoet aan de drempel
                        if rsi >= self.config["SELL_THRESHOLD"]:
                            if open_positions:
                                for pos in open_positions:
                                    # Bereken het winstpercentage via de StateManager
                                    profit_percentage = self.state_managers[pair].calculate_profit_for_position(
                                        pos, current_price, self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                    # Bereken de absolute winst in valuta
                                    absolute_profit = (current_price * pos["quantity"] * (
                                        1 - self.config["TRADE_FEE_PERCENTAGE"] / 100)) - (pos["price"] * pos["quantity"])

                                    if profit_percentage >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                        self.log_message(
                                            f"🔴 Selling trade for {pair} (bought at {pos['price']:.2f}). Current RSI={rsi:.2f}, Price: {
                                                current_price:.2f}, Profit: {profit_percentage:.2f}% / {absolute_profit:.2f} EUR",
                                            to_slack=True
                                        )
                                        await asyncio.to_thread(
                                            self.state_managers[pair].sell_position,
                                            pos,
                                            current_price,
                                            self.config["TRADE_FEE_PERCENTAGE"]
                                        )
                                    else:
                                        self.log_message(
                                            f"⚠️ Skipping sell for trade in {pair} (bought at {pos['price']:.2f}): Profit {
                                                profit_percentage:.2f}% / {absolute_profit:.2f} EUR below threshold.",
                                            to_slack=False
                                        )

                        # Kooplogica: Als de RSI onder de BUY_THRESHOLD ligt
                        elif rsi <= self.config["BUY_THRESHOLD"]:
                            max_trades = self.config.get(
                                "MAX_TRADES_PER_PAIR", 1)
                            if len(open_positions) < max_trades:
                                # Verdeel het totaal toegewezen budget voor dit paar over het maximaal aantal trades
                                investment_per_trade = self.pair_budgets[pair] / max_trades
                                self.log_message(
                                    f"🟢 Buying {pair}. Price: {current_price:.2f}, RSI={rsi:.2f}. Open trades: {
                                        len(open_positions)} (max allowed: {max_trades}). "
                                    f"Investeringsbedrag per trade: {
                                        investment_per_trade:.2f}",
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
                                    f"ℹ️ Not buying {pair} as open trades ({len(open_positions)}) reached the limit of {
                                        max_trades}.",
                                    to_slack=False
                                )

                # Wacht asynchroon de CHECK_INTERVAL af
                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 ScalpingBot stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ ScalpingBot finished trading.", to_slack=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Asynchroon ScalpingBot met dynamische configuratie, multi-trade ondersteuning en een aparte RSI-interval."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="scalper.json",
        help="Pad naar het JSON-configuratiebestand (default: scalper.json)"
    )
    parser.add_argument(
        "--bot-name",
        type=str,
        required=True,
        help="Unieke naam voor de bot-instantie (verplicht)"
    )
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuratiebestand niet gevonden: {config_path}")

    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))

    state_managers = {
        pair: StateManager(pair, logger, bitvavo_instance,
                           demo_mode=config.get("DEMO_MODE", False))
        for pair in config["PAIRS"]
    }

    bot = ScalpingBot(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())
