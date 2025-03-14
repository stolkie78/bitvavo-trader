import os
import json
from datetime import datetime
from bot.config_loader import ConfigLoader
from bot.trading_utils import TradingUtils
from bot.state_manager import StateManager
from bot.logging_facility import LoggingFacility
from bot.bitvavo_client import bitvavo


def calculate_pnl_for_portfolio(portfolio, current_prices, fee_percentage):
    pnl_report = {}
    for pair, positions in portfolio.items():
        current_price = current_prices.get(pair)
        if current_price is None:
            pnl_report[pair] = "No price available"
            continue

        total_cost = 0.0
        total_value = 0.0
        for pos in positions:
            quantity = pos.get("quantity", 0.0)
            spent = pos.get("spent", pos.get("price", 0.0) * quantity)
            value_now = quantity * current_price * (1 - fee_percentage / 100)

            total_cost += spent
            total_value += value_now

        profit = total_value - total_cost
        profit_pct = ((profit / total_cost) * 100) if total_cost > 0 else 0.0

        pnl_report[pair] = {
            "spent": round(total_cost, 2),
            "value_now": round(total_value, 2),
            "profit_eur": round(profit, 2),
            "profit_pct": round(profit_pct, 2)
        }

    return pnl_report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check current profit/loss per pair")
    parser.add_argument("--config", type=str, default="hodl.json", help="Path to config file")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))
    bitvavo_instance = bitvavo(ConfigLoader.load_config("bitvavo.json"))

    state_managers = {
        pair: StateManager(
            pair, logger, bitvavo_instance, demo_mode=config.get("DEMO_MODE", False), bot_name="PNL_CHECK"
        ) for pair in config["PAIRS"]
    }

    portfolio = {}
    for pair, sm in state_managers.items():
        portfolio[pair] = sm.get_open_positions()

    current_prices = {
        pair: TradingUtils.fetch_current_price(bitvavo_instance, pair) for pair in config["PAIRS"]
    }

    pnl = calculate_pnl_for_portfolio(portfolio, current_prices, fee_percentage=config.get("TRADE_FEE_PERCENTAGE", 0.25))

    print("\n📈 Portfolio Profit/Loss Report:")
    for pair, result in pnl.items():
        if isinstance(result, str):
            print(f" - {pair}: {result}")
        else:
            print(f" - {pair}: Spent={result['spent']} EUR | Value Now={result['value_now']} EUR | Profit={result['profit_eur']} EUR ({result['profit_pct']}%)")
