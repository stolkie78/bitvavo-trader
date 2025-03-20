import argparse
import pandas as pd
from bot.trading_utils import TradingUtils


def generate_features_and_labels(candles, price_threshold=0.01):
    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    volumes = [float(c[5]) for c in candles]

    data = pd.DataFrame({
        "close": closes,
        "high": highs,
        "low": lows,
        "volume": volumes
    })

    data["rsi"] = TradingUtils.calculate_rsi(closes, 14)
    macd, signal, macd_hist = TradingUtils.calculate_macd(closes)
    data["macd"] = macd
    data["signal"] = signal
    data["macd_hist"] = macd_hist
    data["ema_fast"] = TradingUtils.calculate_ema(closes, 12)
    data["ema_slow"] = TradingUtils.calculate_ema(closes, 26)
    support, resistance = TradingUtils.calculate_support_resistance(closes, window_size=20)
    data["support"] = support
    data["resistance"] = resistance
    data["atr"] = TradingUtils.calculate_atr(highs, lows, closes, window=14)
    data["momentum"] = TradingUtils.calculate_momentum(closes, window=10)
    data["volume_change"] = TradingUtils.calculate_volume_change(volumes)

    # Derived features for model consistency
    data["price"] = data["close"]
    data["macd_diff"] = data["macd"] - data["signal"]
    data["ema_diff"] = data["ema_fast"] - data["ema_slow"]
    data["price_minus_support"] = data["price"] - data["support"]
    data["resistance_minus_price"] = data["resistance"] - data["price"]

    # Label: 1 = price increases > threshold over next X candles
    future_prices = data["close"].shift(-3)
    data["label"] = (future_prices > data["close"] * (1 + price_threshold)).astype(int)

    # Drop rows with NaNs
    data = data.dropna()
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--interval", type=str, default="1h")
    parser.add_argument("--output", type=str, default="data/training_output.csv")
    args = parser.parse_args()

    from bot.bitvavo_client import bitvavo
    from bot.config_loader import ConfigLoader
    bv = bitvavo(ConfigLoader.load_config("bitvavo.json"))

    print(f"📥 Fetching raw candles for {args.pair}...")
    candles = TradingUtils.fetch_raw_candles(bv, args.pair, limit=args.limit, interval=args.interval)
    df = generate_features_and_labels(candles)
    df.to_csv(args.output, index=False)
    print(f"✅ Training data saved to {args.output} with {len(df)} rows")


if __name__ == "__main__":
    main()

