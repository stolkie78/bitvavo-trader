import os
import json
from datetime import datetime
from bot.config_loader import ConfigLoader
from bot.trading_utils import TradingUtils
from bot.state_manager import StateManager
from bot.logging_facility import LoggingFacility
from bot.bitvavo_client import bitvavo


def calculate_equal_weights(pairs):
    weight = 1 / len(pairs)
    return {pair: weight for pair in pairs}


def calculate_momentum_weights(pairs, price_history, bitvavo_client, rsi_window):
    scores = TradingUtils.rank_coins(bitvavo_client, pairs, price_history, rsi_window=rsi_window)
    total_score = sum(score for _, score in scores)
    if total_score == 0:
        return calculate_equal_weights(pairs)
    return {pair: score / total_score for pair, score in scores}


def calculate_portfolio_value(portfolio, current_prices):
    total = 0.0
    for pair, positions in portfolio.items():
        if pair in current_prices:
            price = current_prices[pair]
            for pos in positions:
                total += pos.get("quantity", 0) * price
    return total


def get_current_allocations(portfolio, current_prices, total_value):
    allocations = {}
    for pair, positions in portfolio.items():
        if pair in current_prices:
            price = current_prices[pair]
            position_value = sum(pos.get("quantity", 0) * price for pos in positions)
            allocations[pair] = position_value / total_value if total_value > 0 else 0
    return allocations


def rebalance_portfolio(config, logger, state_managers, bitvavo_client):
    pairs = config["PAIRS"]
    exclude_pairs = config.get("REBALANCE_EXCLUDE_PAIRS", [])
    rebalance_pairs = [pair for pair in pairs if pair not in exclude_pairs]

    rsi_window = config.get("RSI_POINTS", 30)
    strategy = config.get("REBALANCE_STRATEGY", "equal")
    fee = config.get("TRADE_FEE_PERCENTAGE", 0.25)
    min_trade_value = config.get("REBALANCE_MIN_TRADE_VALUE", 10)
    min_holdings = config.get("REBALANCE_MIN_HOLDINGS", {})

    logger.log("\n📊 Starting portfolio rebalance...", to_console=True)

    price_history = {
        pair: TradingUtils.fetch_historical_prices(bitvavo_client, pair, limit=rsi_window, interval=config.get("RSI_INTERVAL", "1d"))
        for pair in rebalance_pairs
    }

    current_prices = {
        pair: TradingUtils.fetch_current_price(bitvavo_client, pair) for pair in rebalance_pairs
    }

    portfolio = {}
    for pair, sm in state_managers.items():
        portfolio[pair] = sm.get_open_positions()

    total_value = calculate_portfolio_value(portfolio, current_prices)
    current_allocs = get_current_allocations(portfolio, current_prices, total_value)

    if strategy == "momentum":
        target_allocs = calculate_momentum_weights(rebalance_pairs, price_history, bitvavo_client, rsi_window)
    else:
        target_allocs = calculate_equal_weights(rebalance_pairs)

    logger.log(f"Current total portfolio value: {total_value:.2f} EUR", to_console=True)
    logger.log("Current allocations:", to_console=True)
    for pair, alloc in current_allocs.items():
        logger.log(f" - {pair}: {alloc*100:.2f}%", to_console=True)
    logger.log("Target allocations:", to_console=True)
    for pair, alloc in target_allocs.items():
        logger.log(f" - {pair}: {alloc*100:.2f}%", to_console=True)

    for pair in rebalance_pairs:
        sm = state_managers[pair]
        current_value = current_allocs.get(pair, 0) * total_value
        target_value = target_allocs.get(pair, 0) * total_value
        delta = target_value - current_value

        if abs(delta) < min_trade_value:
            logger.log(f"🔸 {pair}: Skip rebalance, delta {delta:.2f} < min trade value", to_console=True)
            continue

        price = current_prices[pair]

        if delta > 0:
            logger.log(f"🟢 {pair}: Buy for rebalance (+{delta:.2f} EUR)", to_console=True)
            sm.buy(price, delta, fee)
        else:
            total_quantity = sum(pos.get("quantity", 0) for pos in sm.get_open_positions())
            asset = pair.split("-")[0]
            min_qty = min_holdings.get(pair, 0)
            quantity_to_sell = abs(delta) / price
            if total_quantity - quantity_to_sell < min_qty:
                logger.log(f"🚫 {pair}: Skip sell — maintaining minimum holding of {min_qty} {asset}", to_console=True)
                continue

            logger.log(f"🔴 {pair}: Sell for rebalance ({delta:.2f} EUR)", to_console=True)
            sm.sell_position(price, fee_percentage=fee)

    logger.log("✅ Rebalance complete.", to_console=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monthly portfolio rebalance tool")
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
            pair, logger, bitvavo_instance, demo_mode=config.get("DEMO_MODE", True), bot_name="REBALANCER"
        ) for pair in config["PAIRS"]
    }

    rebalance_portfolio(config, logger, state_managers, bitvavo_instance)
