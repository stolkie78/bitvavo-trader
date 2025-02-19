import asyncio
import logging
import json
from datetime import datetime

from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils


class HodlBot:
    """
    HODL Bot met Dollar-Cost Averaging (DCA).
    Dit script beheert DCA-aankopen zonder verkoopfunctionaliteit.
    """

    def __init__(self, config, logger, state_managers, bitvavo):
        """
        Initialisatie van de HODL Bot.

        Args:
            config (dict): Configuratieparameters uit de config.json.
            logger: Logging module.
            state_managers (dict): Een dict met StateManager-instanties per trading pair.
            bitvavo: De Bitvavo API client.
        """
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.profile = "HODL"
        self.last_dca_time = {pair: None for pair in config["PAIRS"]}

        self.log_message(f"🚀 HODL Bot gestart met DCA: {'Enabled' if self.config.get('DCA_ENABLED', False) else 'Disabled'}")

    def log_message(self, message: str, to_slack: bool = False):
        """
        Log een bericht met de standaard prefix.

        Args:
            message (str): Het bericht.
            to_slack (bool): Indien True, stuur bericht ook naar Slack.
        """
        prefixed_message = f"[HODL] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    async def run(self):
        """
        Hoofdlus van de bot.
        """
        self.log_message(f"📊 HODL DCA gestart op {datetime.now()}")
        try:
            while True:
                self.log_message(f"🐌 Nieuwe HODL DCA cyclus gestart op {datetime.now()}")

                for pair in self.config["PAIRS"]:
                    # Haal de huidige prijs op
                    current_price = await asyncio.to_thread(
                        TradingUtils.fetch_current_price, self.bitvavo, pair
                    )

                    # Haal RSI en EMA op
                    rsi = await asyncio.to_thread(
                        TradingUtils.calculate_rsi, self.state_managers[pair].get_price_history(), self.config["RSI_POINTS"]
                    )
                    ema = await asyncio.to_thread(
                        TradingUtils.calculate_ema, self.state_managers[pair].get_price_history(), self.config["EMA_POINTS"]
                    )

                    # --- DCA Logic ---
                    if self.config.get("DCA_ENABLED", False):
                        now = datetime.now()
                        last_trade_time = self.last_dca_time.get(pair)

                        if last_trade_time is None or (now - last_trade_time).total_seconds() >= self.config["DCA_INTERVAL_HOURS"] * 3600:
                            self.execute_dca_buy(pair, current_price, rsi, ema)
                            self.last_dca_time[pair] = now

                await asyncio.sleep(self.config["CHECK_INTERVAL"])

        except KeyboardInterrupt:
            self.log_message("🛑 HODL Bot gestopt door gebruiker.", to_slack=True)
        finally:
            self.log_message("✅ HODL Bot trading beëindigd.", to_slack=True)

    def execute_dca_buy(self, pair, current_price, rsi, ema):
        """
        Voert een DCA aankoop uit als de voorwaarden zijn voldaan.
        """
        try:
            # Controleer of EMA beschikbaar is
            if ema is None:
                self.log_message(f"⚠️ {pair}: EMA niet beschikbaar, DCA-buy overgeslagen.")
                return
    
            # Bereken DCA budget
            dca_budget = self.config["TOTAL_BUDGET"] * (self.config["DCA_BUDGET_PERCENTAGE"] / 100)
            max_trades = self.config["DCA_MAX_TRADES"]
            allocated_budget = dca_budget / max_trades
    
            # Bereken koop hoeveelheid
            max_quantity = allocated_budget / current_price
            final_quantity = max_quantity  
    
            # RSI-check (optioneel)
            if rsi is not None and rsi > self.config.get("DCA_MIN_RSI", 40):
                self.log_message(f"⚠️ {pair}: RSI ({rsi:.2f}) te hoog voor DCA-buy (min: {self.config['DCA_MIN_RSI']})")
                return
    
            # EMA-check (optioneel)
            ema_diff = (current_price - ema) / ema
            if ema_diff > self.config.get("DCA_MAX_PRICE_ABOVE_EMA", 0.005):
                self.log_message(f"⚠️ {pair}: Prijs ({current_price:.2f}) is te ver boven EMA ({ema:.2f}), overslaan.")
                return
    
            # Koop de asset
            self.log_message(
                f"🟢 {pair}: DCA BUY Price={current_price:.2f}, Budget={allocated_budget:.2f}, Quantity={final_quantity:.6f}",
                to_slack=True
            )
    
            asyncio.create_task(
                self.state_managers[pair].buy_dynamic(
                    current_price, final_quantity, self.config["TRADE_FEE_PERCENTAGE"]
                )
            )
        except Exception as e:
            self.log_message(f"❌ Fout bij DCA aankoop: {e}", to_slack=True)

if __name__ == "__main__":
    import argparse
    from bot.config_loader import ConfigLoader
    from bot.logging_facility import LoggingFacility
    from bot.bitvavo_client import bitvavo

    parser = argparse.ArgumentParser(description="HODL bot met DCA")
    parser.add_argument("--config", type=str, default="hodl_config.json", help="Pad naar JSON config bestand")
    args = parser.parse_args()

    # Laad configuratie en API-clients
    config = ConfigLoader.load_config(args.config)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))
    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))

    state_managers = {
        pair: StateManager(pair, logger, bitvavo_instance, demo_mode=config.get("DEMO_MODE", False))
        for pair in config["PAIRS"]
    }

    bot = HodlBot(config, logger, state_managers, bitvavo_instance)

    # Start de bot
    asyncio.run(bot.run())

