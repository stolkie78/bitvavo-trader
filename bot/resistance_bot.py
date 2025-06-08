import asyncio
import os
import json
import argparse
from datetime import datetime
from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.logging_facility import LoggingFacility
from bot.bitvavo_client import bitvavo
from bot.ai_decider import AIDecider

class ResistanceBot:
    """AI powered trading bot using support and resistance levels."""

    VERSION = "0.1.0"

    def __init__(self, config, logger, state_managers, bitvavo, args):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args

        self.mode = config.get("MODE", "DAYTRADE").lower()
        self.bot_name = config.get("PROFILE", "RESIST")
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()
        self.price_history = {}
        self.candles = config.get("CANDLES", 20)
        self.candle_interval = config.get("CANDLE_INTERVAL", "1h")
        self.buy_tolerance = config.get("SUPPORT_TOLERANCE", 0.01)
        self.sell_tolerance = config.get("RESISTANCE_TOLERANCE", 0.01)
        self.buy_threshold = config.get("BUY_PROBABILITY_THRESHOLD", 0.6)
        self.sell_threshold = config.get("SELL_PROBABILITY_THRESHOLD", 0.6)
        self.ai_decider = AIDecider(pair_models=config.get("PAIR_MODELS", {}), logger=logger)

        for pair in config["PAIRS"]:
            try:
                candles = TradingUtils.fetch_raw_candles(
                    self.bitvavo, pair, limit=self.candles, interval=self.candle_interval
                )
                self.price_history[pair] = {
                    "open": [float(c[1]) for c in candles],
                    "high": [float(c[2]) for c in candles],
                    "low": [float(c[3]) for c in candles],
                    "close": [float(c[4]) for c in candles],
                    "volume": [float(c[5]) for c in candles],
                }
                self.log_message(f"🕯️  {pair}: Loaded {len(candles)} candles")
            except Exception as e:
                self.log_message(f"⚠️ {pair}: Failed to load candles: {e}")
                self.price_history[pair] = {"open": [], "high": [], "low": [], "close": [], "volume": []}

        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] * self.config["PORTFOLIO_ALLOCATION"].get(pair, 0) / 100)
            for pair in self.config["PAIRS"]
        }

        self.log_message("🚀 ResistanceBot initialized")

    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def log_message(self, msg, to_slack=False):
        self.logger.log(f"[{self.bot_name}] {msg}", to_console=True, to_slack=to_slack)

    async def run(self):
        self.log_message(f"Starting in {self.mode.upper()} mode")
        try:
            while True:
                for pair in self.config["PAIRS"]:
                    try:
                        candle = TradingUtils.fetch_raw_candles(
                            self.bitvavo, pair, limit=1, interval=self.candle_interval
                        )[0]
                        ph = self.price_history[pair]
                        for key, idx in [("open",1),("high",2),("low",3),("close",4),("volume",5)]:
                            ph[key].append(float(candle[idx]))
                            if len(ph[key]) > self.candles:
                                ph[key].pop(0)
                        closes = ph["close"]
                        highs = ph["high"]
                        lows = ph["low"]
                        vols = ph["volume"]
                        current_price = closes[-1]

                        rsi = TradingUtils.calculate_rsi(closes, self.candles)
                        macd, signal, macd_hist = TradingUtils.calculate_macd(closes)
                        ema_fast = TradingUtils.calculate_ema(closes, 12)
                        ema_slow = TradingUtils.calculate_ema(closes, 26)
                        support, resistance = TradingUtils.calculate_support_resistance(closes, self.candles)
                        atr = TradingUtils.calculate_atr(highs, lows, closes, 14)
                        momentum = TradingUtils.calculate_momentum(closes)
                        vol_change = TradingUtils.calculate_volume_change(vols)

                        macd_diff = macd - signal if macd is not None and signal is not None else 0.0
                        ema_diff = ema_fast - ema_slow if ema_fast is not None and ema_slow is not None else 0.0
                        price_minus_support = current_price - support if support is not None else 0.0
                        resistance_minus_price = resistance - current_price if resistance is not None else 0.0

                        self.log_message(
                            f"{pair}: price={current_price:.4f} support={support:.4f} resistance={resistance:.4f} rsi={rsi:.2f}"
                        )

                        open_pos = self.state_managers[pair].get_open_positions()
                        buy = self.ai_decider.should_buy(
                            pair, rsi, macd, signal, macd_hist, ema_fast, ema_slow,
                            support, resistance, atr, momentum, vol_change,
                            current_price, macd_diff, ema_diff,
                            price_minus_support, resistance_minus_price,
                            coin_rank_score=0.0
                        )
                        buy_decision = buy.get("decision", False) and buy.get("probability", 0) >= self.buy_threshold
                        near_support = support is not None and current_price <= support * (1 + self.buy_tolerance)
                        if buy_decision and near_support:
                            max_trades = self.config.get("MAX_TRADES_PER_PAIR", 1)
                            if self.mode == "hodl":
                                max_trades = 1
                            if len(open_pos) < max_trades:
                                invest = self.pair_budgets[pair] / max_trades
                                self.log_message(f"🟢 {pair}: BUY {invest:.2f} EUR @ {current_price:.4f}")
                                await asyncio.to_thread(
                                    self.state_managers[pair].buy,
                                    current_price,
                                    invest,
                                    self.config["TRADE_FEE_PERCENTAGE"]
                                )
                        sell_prob = self.ai_decider.should_sell(
                            pair, rsi, macd, signal, macd_hist, ema_fast, ema_slow,
                            support, resistance, atr, momentum, vol_change,
                            current_price, macd_diff, ema_diff,
                            price_minus_support, resistance_minus_price
                        )
                        sell_decision = sell_prob >= self.sell_threshold
                        near_resistance = resistance is not None and current_price >= resistance * (1 - self.sell_tolerance)
                        if open_pos and sell_decision and near_resistance:
                            self.log_message(f"🔴 {pair}: SELL @ {current_price:.4f}")
                            await asyncio.to_thread(
                                self.state_managers[pair].sell_position,
                                current_price,
                                self.config["TRADE_FEE_PERCENTAGE"]
                            )
                    except Exception as e:
                        self.log_message(f"⚠️ Error processing {pair}: {e}")
                await asyncio.sleep(self.config["CHECK_INTERVAL"])
        except KeyboardInterrupt:
            self.log_message("Stopped by user")
        finally:
            self.log_message("Finished trading")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resistance based trader")
    parser.add_argument("--config", type=str, default="config/resistance_bot.json")
    args = parser.parse_args()

    conf_path = os.path.abspath(args.config)
    if not os.path.exists(conf_path):
        raise FileNotFoundError(f"Config file not found: {conf_path}")

    bv = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    conf = ConfigLoader.load_config(os.path.basename(conf_path))
    log = LoggingFacility(ConfigLoader.load_config("slack.json"))

    states = {
        p: StateManager(
            p, log, bv,
            demo_mode=conf.get("DEMO_MODE", False),
            bot_name=conf.get("PROFILE", "RESIST")
        )
        for p in conf["PAIRS"]
    }

    bot = ResistanceBot(conf, log, states, bv, args)
    asyncio.run(bot.run())
