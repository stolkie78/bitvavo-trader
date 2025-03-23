import asyncio
import os
import json
from datetime import datetime, date
from bot.config_loader import ConfigLoader
from bot.trading_utils import TradingUtils
from bot.state_manager import StateManager
from bot.logging_facility import LoggingFacility
from bot.bitvavo_client import bitvavo


class HodlBot:
    VERSION = "0.1.9"

    def __init__(self, config: dict, logger: LoggingFacility, state_managers: dict, bitvavo, args):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args

        self.bot_name = config.get("PROFILE", "HODL")
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trade_log_file = os.path.join(self.data_dir, "daily_trades.json")
        self.portfolio = self.load_portfolio()

        self.candles = config.get("CANDLES", 60)
        self.candle_interval = config.get("CANDLE_INTERVAL", "1d").lower()
        self.price_history = {}

        for pair in config["PAIRS"]:
            try:
                historical_prices = TradingUtils.fetch_historical_prices(
                    self.bitvavo, pair, limit=self.candles, interval=self.candle_interval
                )
                self.price_history[pair] = historical_prices
                self.logger.log(f"🕯️  {pair}: Price candles loaded: {len(historical_prices)}", to_console=True)
            except Exception as e:
                self.logger.log(f"⚠️ {pair}: Failed to load price history: {e}", to_console=True)
                self.price_history[pair] = []

        self.logger.log(f"📂 Loaded Portfolio:\n{json.dumps(self.portfolio, indent=4)}", to_console=True)

    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    return portfolio
            except Exception as e:
                self.logger.log(f"❌ Error loading portfolio: {e}", to_console=True)
        return {}

    def load_daily_trades(self):
        if os.path.exists(self.trade_log_file):
            try:
                with open(self.trade_log_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_daily_trades(self, trade_log):
        with open(self.trade_log_file, "w") as f:
            json.dump(trade_log, f, indent=4)

    def log_message(self, message: str, to_slack: bool = False):
        self.logger.log(f"[{self.bot_name}] {message}", to_console=True, to_slack=to_slack)

    async def run(self):
        self.log_message(f"🚀 Starting HODL Bot at {datetime.now()}")
        try:
            while True:
                self.log_message(f"📊 New evaluation cycle at {datetime.now()}")

                try:
                    available_balance = TradingUtils.get_account_balance(self.bitvavo, asset="EUR")
                    min_reserve = self.config.get("MIN_EUR_RESERVE", 0)
                    available_budget = max(0, available_balance - min_reserve)
                    self.log_message(f"💶 EUR balance check: {available_balance:.2f} EUR total, {available_budget:.2f} EUR available for HODL")

                    if available_budget <= 0:
                        self.log_message(f"❌ No available EUR budget to invest (balance below reserve threshold of {min_reserve:.2f} EUR). Waiting for next cycle.")
                        await asyncio.sleep(self.config["CHECK_INTERVAL"])
                        continue
                except Exception as e:
                    self.log_message(f"❌ Error fetching EUR balance at start of cycle: {e}")
                    await asyncio.sleep(self.config["CHECK_INTERVAL"])
                    continue

                ranked_coins = TradingUtils.rank_coins(
                    self.bitvavo,
                    self.config["PAIRS"],
                    self.price_history,
                    rsi_window=self.candles
                )

                if not ranked_coins:
                    self.log_message("⚠️ No valid coin rankings available.")
                    await asyncio.sleep(self.config["CHECK_INTERVAL"])
                    continue

                best_pair, best_score = ranked_coins[0]
                current_price = await asyncio.to_thread(TradingUtils.fetch_current_price, self.bitvavo, best_pair)

                self.price_history[best_pair].append(current_price)
                if len(self.price_history[best_pair]) > self.candles:
                    self.price_history[best_pair].pop(0)

                rsi = TradingUtils.calculate_rsi(self.price_history[best_pair], self.candles)
                macd, signal, _ = TradingUtils.calculate_macd(self.price_history[best_pair])

                macd_str = f"{macd:.4f}" if macd is not None else "n/a"
                signal_str = f"{signal:.4f}" if signal is not None else "n/a"
                rsi_str = f"{rsi:.2f}" if rsi is not None else "n/a"
                score_str = f"{best_score:.2f}" if best_score is not None else "n/a"

                self.log_message(
                    f"🔎 {best_pair}: Price={current_price:.2f}, RSI={rsi_str}, MACD={macd_str}, Signal={signal_str}, Score={score_str}"
                )

                open_positions = self.state_managers[best_pair].get_open_positions()

                daily_trade_log = self.load_daily_trades()
                today_str = date.today().isoformat()
                trades_today = daily_trade_log.get(today_str, {}).get(best_pair, 0)
                max_daily_trades = self.config.get("MAX_DAILY_TRADES_PER_PAIR", 1)

                if rsi is not None and macd is not None and signal is not None:
                    if macd > signal:
                        for dca_layer in self.config.get("DCA_LAYERS", []):
                            threshold = dca_layer.get("RSI_THRESHOLD")
                            amount = dca_layer.get("AMOUNT")

                            if rsi <= threshold and trades_today < max_daily_trades:
                                investment = min(available_budget, amount)

                                if investment <= 0:
                                    self.log_message(f"⚠️ Skipping DCA buy. Not enough EUR budget available after reserving {min_reserve:.2f} EUR.")
                                else:
                                    self.log_message(
                                        f"🟢 {best_pair}: DCA Buy triggered. RSI={rsi:.2f} ≤ {threshold}, Investing {investment:.2f} EUR"
                                    )
                                    await asyncio.to_thread(
                                        self.state_managers[best_pair].buy,
                                        current_price,
                                        investment,
                                        self.config["TRADE_FEE_PERCENTAGE"]
                                    )
                                    if today_str not in daily_trade_log:
                                        daily_trade_log[today_str] = {}
                                    if best_pair not in daily_trade_log[today_str]:
                                        daily_trade_log[today_str][best_pair] = 0
                                    daily_trade_log[today_str][best_pair] += 1
                                    self.save_daily_trades(daily_trade_log)
                                    break
                    else:
                        self.log_message(f"🤚 {best_pair}: No buy signal — MACD crossover not confirmed.")

                await asyncio.sleep(self.config["CHECK_INTERVAL"])

        except KeyboardInterrupt:
            self.log_message("🛑 HODL Bot stopped by user.")

        finally:
            self.log_message("✅ HODL Bot finished.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Async HODL Bot")
    parser.add_argument("--config", type=str, default="hodl.json", help="Path to HODL config JSON")
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
            bot_name=config.get("PROFILE", "HODL")
        ) for pair in config["PAIRS"]
    }

    bot = HodlBot(config, logger, state_managers, bitvavo_instance, args)
    asyncio.run(bot.run())