import json
import pandas as pd
from datetime import datetime


def calculate_daily_profit_per_crypto(trades_file):
    """
    Calculate the daily profit/loss per crypto pair from trades.json.

    Args:
        trades_file (str): Path to the trades.json file.

    Returns:
        pd.DataFrame: DataFrame with date, crypto pair and daily profit/loss in euros.
    """
    try:
        # Trades laden uit het JSON-bestand
        with open(trades_file, "r") as f:
            trades = json.load(f)

        if not trades:
            print("❌ No trades found in trades.json")
            return pd.DataFrame(columns=["date", "pair", "profit_eur"])

        # Zet de trades om naar een DataFrame en verwerk de timestamp
        df = pd.DataFrame(trades)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date

        # Select only sell transactions
        df_sells = df[df["type"] == "sell"]

        if df_sells.empty:
            print("❌ No sell transactions found in trades.json")
            return pd.DataFrame(columns=["date", "pair", "profit_eur"])

        # Group by date and pair and sum the profit in euros
        daily_profit_per_crypto = df_sells.groupby(
            ["date", "pair"])["profit_eur"].sum().reset_index()
        return daily_profit_per_crypto

    except Exception as e:
        print(f"❌ Error calculating daily profit per crypto: {e}")
        return pd.DataFrame(columns=["date", "pair", "profit_eur"])


if __name__ == "__main__":
    trades_file = "data/trades.json"
    daily_profit_per_crypto_df = calculate_daily_profit_per_crypto(trades_file)
    print(daily_profit_per_crypto_df)
