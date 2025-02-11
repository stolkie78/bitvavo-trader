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


class ScalpingBot:
    """
    Asynchroon ScalpingBot met ondersteuning voor multi-posities en stop loss.
    """
    VERSION = "0.1.25"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        """
        Initialiseert de ScalpingBot.
        
        De botnaam wordt ingeladen vanuit de JSON-configuratie via het veld "PROFILE".
        """
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args

        self.bot_name = config.get("PROFILE", "SCALPINGBOT")
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()

        # Haal de nieuwe RSI-opties uit de config (in uppercase) met fallback-waarden.
        self.rsi_points = config.get("RSI_POINTS", 14)  # aantal RSI punten
        # RSI_INTERVAL is het candle-interval. Omdat de API meestal lowercase verwacht, converteren we deze:
        self.rsi_interval = config.get("RSI_INTERVAL", "1M").lower()

        # Pre-populeer de prijsgeschiedenis per trading pair met historische data
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
                self.log_message(
                    f"Historische prijzen voor {pair} ingeladen: {historical_prices}")
            except Exception as e:
                self.log_message(
                    f"⚠️ Historische prijzen voor {pair} konden niet worden opgehaald: {e}")
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
        """Laadt de portfolio uit een JSON-bestand."""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log(
                        "Portfolio loaded successfully.", to_console=True)
                    return portfolio
            except Exception as e:
                self.logger.log(
                    f"👽❌ Error loading portfolio: {e}", to_console=True)
        return {}

    def log_message(self, message: str, to_slack: bool = False):
        """Voegt de botnaam toe aan het bericht en logt het."""
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        """Logt de opstartparameters van de bot."""
        startup_info = {
            "version": self.VERSION,
            "bot_name": self.bot_name,
            "startup_parameters": vars(self.args),
            "config_file": self.args.config,
            "trading_pairs": self.config.get("PAIRS", []),
            "total_budget": self.config.get("TOTAL_BUDGET", "N/A"),
            "RSI_POINTS": self.rsi_points,
            # laten we hier de waarde in uppercase tonen
            "RSI_INTERVAL": self.rsi_interval.upper()
        }
        self.log_message("🚀 Starting ScalpingBot", to_slack=True)
        self.log_message(
            f"📊 Startup Info: {json.dumps(startup_info, indent=2)}", to_slack=True)

    async def run(self):
        """Voert de hoofdloop van de bot asynchroon uit."""
        self.log_message(f"📊 Trading started at {datetime.now()}")
        try:
            while True:
                self.log_message(f"📊 New cycle started at {datetime.now()}")
                self.log_message(
                    f"📈 Current budget per pair: {self.pair_budgets}")
                current_time = datetime.now()

                # Itereer over elk crypto-paar
                for pair in self.config["PAIRS"]:
                    current_price = await asyncio.to_thread(
                        TradingUtils.fetch_current_price, self.bitvavo, pair
                    )

                    # Voeg de nieuwe prijs toe en behoud altijd het RSI_POINTS aantal prijzen
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.rsi_points:
                        self.price_history[pair].pop(0)

                    # Bereken de RSI op basis van de beschikbare data
                    if len(self.price_history[pair]) >= self.rsi_points:
                        rsi = await asyncio.to_thread(
                            TradingUtils.calculate_rsi, self.price_history[pair], self.rsi_points
                        )
                    else:
                        rsi = None

                    # --- STOP LOSS CHECK ---
                    open_positions = self.state_managers[pair].get_open_positions(
                    )
                    if open_positions:
                        for position in open_positions:
                            stop_loss_threshold = position["price"] * (
                                1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)
                            if current_price <= stop_loss_threshold:
                                self.log_message(
                                    f"⛔️ Stop loss triggered for {pair}: current price {current_price:.2f} is below threshold {stop_loss_threshold:.2f}",
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
                        self.log_message(
                            f"✅ Current price for {pair}: {current_price:.2f} EUR, RSI={rsi:.2f}")

                        # Verkooplogica
                        if rsi >= self.config["SELL_THRESHOLD"]:
                            if open_positions:
                                for pos in open_positions:
                                    profit_percentage = self.state_managers[pair].calculate_profit_for_position(
                                        pos, current_price, self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                    absolute_profit = (current_price * pos["quantity"] * (
                                        1 - self.config["TRADE_FEE_PERCENTAGE"] / 100)) - (pos["price"] * pos["quantity"])
                                    if profit_percentage >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                        self.log_message(
                                            f"🔴 Selling trade for {pair} (bought at {pos['price']:.2f}). Current RSI={rsi:.2f}, Price: {current_price:.2f}, Profit: {profit_percentage:.2f}% / {absolute_profit:.2f} EUR",
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
                                            f"⚠️ Skipping sell for trade in {pair} (bought at {pos['price']:.2f}): Profit {profit_percentage:.2f}% / {absolute_profit:.2f} EUR below threshold.",
                                            to_slack=False
                                        )

                        # Kooplogica
                        elif rsi <= self.config["BUY_THRESHOLD"]:
                            max_trades = self.config.get(
                                "MAX_TRADES_PER_PAIR", 1)
                            if len(open_positions) < max_trades:
                                investment_per_trade = self.pair_budgets[pair] / max_trades
                                self.log_message(
                                    f"🟢 Buying {pair}. Price: {current_price:.2f}, RSI={rsi:.2f}. Open trades: {len(open_positions)} (max allowed: {max_trades}). "
                                    f"Investeringsbedrag per trade: {investment_per_trade:.2f}",
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
                                    f"ℹ️ Not buying {pair} as open trades ({len(open_positions)}) reached the limit of {max_trades}.",
                                    to_slack=False
                                )

                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 ScalpingBot stopped by user.", to_slack=True)
        finally:
            self.log_message("✅ ScalpingBot finished trading.", to_slack=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Asynchroon ScalpingBot met dynamische configuratie, multi-trade ondersteuning en historische data voor directe RSI-berekening."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="scalper.json",
        help="Pad naar het JSON-configuratiebestand (default: scalper.json)"
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
