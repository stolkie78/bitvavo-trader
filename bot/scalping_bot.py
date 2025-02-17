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
    Async Scalping Bot met dynamische stoploss en dynamische risicodeling.
    """
    VERSION = "0.3.1"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args: argparse.Namespace):
        """
        Initialisatie van de ScalpingBot.

        Args:
            config (dict): Configuratieparameters uit de config.json.
            logger (LoggingFacility): Logging module.
            state_managers (dict): Een dict met StateManager-instanties per trading pair.
            bitvavo: De Bitvavo API client.
            args (argparse.Namespace): Commandline-argumenten.
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

        # RSI en EMA instellingen
        self.rsi_points = config.get("RSI_POINTS", 14)
        self.rsi_interval = config.get("RSI_INTERVAL", "1M").lower()
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.ema_points = config.get("EMA_POINTS", 14)
        self.ema_history = {pair: [] for pair in config["PAIRS"]}
        self.ema_buy_threshold = self.config.get("EMA_BUY_THRESHOLD", 0.002)
        self.ema_sell_threshold = self.config.get("EMA_SELL_THRESHOLD", -0.002)

        # Haal historische prijzen op voor elke pair (voor RSI en EMA)
        for pair in config["PAIRS"]:
            try:
                required_candles = max(self.rsi_points, self.ema_points)
                historical_prices = TradingUtils.fetch_historical_prices(
                    self.bitvavo, pair, limit=required_candles, interval=self.rsi_interval
                )
                if len(historical_prices) >= required_candles:
                    self.price_history[pair] = historical_prices.copy()
                    self.ema_history[pair] = historical_prices.copy()
                    self.log_message(
                        f"✅ {pair}: {len(historical_prices)} historische prijzen geladen voor EMA en RSI.")
                else:
                    self.log_message(
                        f"⚠️ {pair}: Onvoldoende data ({len(historical_prices)} candles, benodigd: {required_candles}).")
            except Exception as e:
                self.log_message(
                    f"❌ Fout bij het ophalen van historische prijzen voor {pair}: {e}")
                self.price_history[pair] = []
                self.ema_history[pair] = []

        # Bereken per pair het toegewezen budget
        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] *
                self.config["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
        }

        self.log_startup_parameters()
        self.logger.log(
            f"📂 Portfolio geladen:\n{json.dumps(self.portfolio, indent=4)}", to_console=True)

    def load_portfolio(self):
        """
        Laad de portfolio uit het portfolio.json-bestand.

        Returns:
            dict: De huidige portfolio.
        """
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log(
                        "Portfolio succesvol geladen.", to_console=True)
                    return portfolio
            except Exception as e:
                self.logger.log(
                    f"❌ Fout bij het laden van de portfolio: {e}", to_console=True)
        return {}

    def log_message(self, message: str, to_slack: bool = False):
        """
        Log een bericht met de standaard prefix.

        Args:
            message (str): Het bericht.
            to_slack (bool): Indien True, stuur bericht ook naar Slack.
        """
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        """
        Toon de startup-parameters.
        """
        startup_info = {**self.config}
        self.log_message("🚀 ScalpingBot wordt gestart.", to_slack=True)
        self.log_message(
            f"⚠️ Startup info:\n{json.dumps(startup_info, indent=2)}", to_slack=True)

    async def run(self):
        """
        Hoofdlus van de bot.
        """
        self.log_message(f"📊 Trading gestart op {datetime.now()}")
        atr_period = self.config.get("ATR_PERIOD", 14)
        atr_multiplier = self.config.get("ATR_MULTIPLIER", 1.5)
        risk_percentage = self.config.get("RISK_PERCENTAGE", 0.01)
        try:
            while True:
                self.log_message(f"🐌 Nieuwe cyclus gestart op {datetime.now()}")
                for pair in self.config["PAIRS"]:
                    # Haal de huidige prijs op
                    current_price = await asyncio.to_thread(
                        TradingUtils.fetch_current_price, self.bitvavo, pair
                    )

                    # Update prijs- en EMA-historie
                    self.price_history[pair].append(current_price)
                    if len(self.price_history[pair]) > self.rsi_points:
                        self.price_history[pair].pop(0)

                    self.ema_history[pair].append(current_price)
                    if len(self.ema_history[pair]) > self.ema_points:
                        self.ema_history[pair].pop(0)

                    # Bereken EMA en RSI als er voldoende data is
                    ema = None
                    if len(self.ema_history[pair]) >= self.ema_points:
                        ema = await asyncio.to_thread(
                            TradingUtils.calculate_ema, self.ema_history[pair], self.ema_points
                        )
                    rsi = None
                    if len(self.price_history[pair]) >= self.rsi_points:
                        rsi = await asyncio.to_thread(
                            TradingUtils.calculate_rsi, self.price_history[pair], self.rsi_points
                        )

                    # Formatteer de prijs en EMA voor logging
                    open_positions = self.state_managers[pair].get_open_positions()
                    price_str = f"{current_price:.8f}" if current_price < 1 else f"{current_price:.2f}"
                    if ema is not None:
                        ema_str = f"{ema:.8f}" if ema < 1 else f"{ema:.2f}"
                        self.log_message(
                            f"💎 {pair}[{len(open_positions)}]: Price={price_str} EUR - RSI={rsi:.2f} - EMA={ema_str}"
                        )

                    # --- (Optioneel) Dynamische stoploss voor open posities ---
                    for position in open_positions:
                        try:
                            candle_data = await asyncio.to_thread(
                                TradingUtils.fetch_historical_candles, self.bitvavo, pair,
                                limit=self.config.get("ATR_PERIOD", 14) + 1, interval=self.rsi_interval
                            )
                            atr_value = TradingUtils.calculate_atr(
                                candle_data, period=self.config.get("ATR_PERIOD", 14)
                            )
                        except Exception as e:
                            self.log_message(
                                f"❌ Fout bij ATR berekening voor {pair}: {e}")
                            atr_value = None

                        if atr_value is not None:
                            dynamic_stoploss = position["price"] - \
                                (atr_value * self.config.get("ATR_MULTIPLIER", 1.5))
                            precision = 8 if current_price < 1 else 2
                            self.log_message(
                                f"〽️ {pair}: Dynamic Stoploss: {dynamic_stoploss:.{precision}f} (ATR: {atr_value:.{precision}f})"
                            )
                        else:
                            dynamic_stoploss = position["price"] * \
                                (1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)

                        if current_price <= dynamic_stoploss:
                            self.log_message(
                                f"⛔️ {pair}: Stoploss getriggerd: current price {current_price:.2f} ligt onder {dynamic_stoploss:.2f}",
                                to_slack=True
                            )
                            await asyncio.to_thread(
                                self.state_managers[pair].sell_position_with_retry,
                                position,
                                current_price,
                                self.config["TRADE_FEE_PERCENTAGE"],
                                self.config.get("STOP_LOSS_MAX_RETRIES", 3),
                                self.config.get("STOP_LOSS_WAIT_TIME", 5)
                            )

                    # --- Koop-/verkooplogica met EMA thresholds en dynamische risicodeling ---
                    if rsi is not None and ema is not None:
                        # Bereken het procentuele verschil tussen huidige prijs en EMA
                        ema_diff = (current_price - ema) / ema
                        # Formatteer EMA voor logging
                        ema_str = f"{ema:.8f}" if ema < 1 else f"{ema:.2f}"

                        # Verkooplogica:
                        # Als RSI boven drempel ligt en de prijs ligt relatief tot de EMA onder de EMA_SELL_THRESHOLD
                        if rsi >= self.config["RSI_SELL_THRESHOLD"] and ema_diff <= self.config.get("EMA_SELL_THRESHOLD", -0.002):
                            if open_positions:
                                for pos in open_positions:
                                    profit_percentage = self.state_managers[pair].calculate_profit_for_position(
                                        pos, current_price, self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                    if profit_percentage >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                                        self.log_message(
                                            f"🔴 Verkopen {pair}: Berekende winst {profit_percentage:.2f}% | EMA diff: {ema_diff:.4f}",
                                            to_slack=True
                                        )
                                        await asyncio.to_thread(
                                            self.state_managers[pair].sell_position,
                                            pos,
                                            current_price,
                                            self.config["TRADE_FEE_PERCENTAGE"]
                                        )
                        # Kooplogica:
                        # Als RSI onder de koopdrempel ligt en de prijs ligt relatief tot de EMA boven de EMA_BUY_THRESHOLD
                        elif rsi <= self.config["RSI_BUY_THRESHOLD"] and ema_diff >= self.config.get("EMA_BUY_THRESHOLD", 0.002):
                            max_trades = self.config.get("MAX_TRADES_PER_PAIR", 1)
                            if len(open_positions) < max_trades:
                                try:
                                    candle_data = await asyncio.to_thread(
                                        TradingUtils.fetch_historical_candles, self.bitvavo, pair,
                                        limit=self.config.get("ATR_PERIOD", 14) + 1, interval=self.rsi_interval
                                    )
                                    atr_value = TradingUtils.calculate_atr(
                                        candle_data, period=self.config.get(
                                            "ATR_PERIOD", 14)
                                    )
                                except Exception as e:
                                    self.log_message(
                                        f"❌ Fout bij ATR berekening voor {pair}: {e}")
                                    atr_value = None

                                if atr_value is not None:
                                    total_budget = self.config.get(
                                        "TOTAL_BUDGET", 10000.0)
                                    risk_percentage = self.config.get(
                                        "RISK_PERCENTAGE", 0.01)
                                    atr_multiplier = self.config.get(
                                        "ATR_MULTIPLIER", 1.5)
                                    risk_amount = total_budget * risk_percentage
                                    risk_per_unit = atr_multiplier * atr_value
                                    dynamic_quantity = risk_amount / risk_per_unit

                                    # Zorg dat het bedrag binnen het budget voor het pair valt
                                    allocated_budget = self.pair_budgets[pair] / \
                                        max_trades
                                    max_quantity = allocated_budget / current_price
                                    final_quantity = min(
                                        dynamic_quantity, max_quantity)

                                    self.log_message(
                                        f"🟢 Koopt {pair}: Price={current_price:.2f}, RSI={rsi:.2f}, EMA={ema_str}, EMA diff={ema_diff:.4f} | "
                                        f"Dynamic Quantity={final_quantity:.6f} (Risk per unit: {risk_per_unit:.2f})",
                                        to_slack=True
                                    )
                                    await asyncio.to_thread(
                                        self.state_managers[pair].buy_dynamic,
                                        current_price,
                                        final_quantity,
                                        self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                else:
                                    self.log_message(
                                        f"❌ Kan ATR niet berekenen voor {pair}. Koopaankoop overgeslagen.",
                                        to_slack=True
                                    )
                            else:
                                self.log_message(
                                    f"{pair}: 🤚 Skipping buy ({len(open_positions)}) - max trades ({max_trades}) bereikt.",
                                    to_slack=True
                                )
                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("🛑 ScalpingBot gestopt door gebruiker.", to_slack=True)
        finally:
            self.log_message("✅ ScalpingBot trading beëindigd.", to_slack=True)






            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Async scalping bot met dynamische stoploss en risicodeling"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="scalper.json",
        help="Pad naar JSON config bestand (default: scalper.json)"
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

def check_stop_loss(self, pair, current_price):
    """ Controleert of een stop-loss moet worden geactiveerd en verkoopt de positie indien nodig. """
    open_positions = self.state_managers[pair].get_open_positions()
    for position in open_positions:
        stop_loss_price = position["price"] * (1 + self.config.get("STOP_LOSS_PERCENTAGE", -5) / 100)

        if current_price <= stop_loss_price:
            self.log_message(
                f"⛔️ {pair}: Stop loss triggered for {pair}: current price {current_price:.2f} is below threshold {stop_loss_price:.2f}",
                to_slack=True
            )

            # Probeer de verkoop met een retry-mechanisme
            sell_success = self.state_managers[pair].sell_position_with_retry(
                position,
                current_price,
                self.config["TRADE_FEE_PERCENTAGE"],
                self.config.get("STOP_LOSS_MAX_RETRIES", 3),
                self.config.get("STOP_LOSS_WAIT_TIME", 5)
            )

            if sell_success:
                self.log_message(f"✅ {pair}: Stop-loss verkoop geslaagd voor {current_price:.2f}", to_slack=True)
            else:
                self.log_message(f"❌ {pair}: Stop-loss verkoop mislukt, herproberen...", to_slack=True)
