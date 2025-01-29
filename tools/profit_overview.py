import json
import pandas as pd
from datetime import datetime


def calculate_daily_profit_per_crypto(trades_file):
    """
    Bereken de dagelijkse winst/verlies per crypto-paar uit trades.json.
    
    Args:
        trades_file (str): Pad naar het trades.json-bestand.
    
    Returns:
        pd.DataFrame: DataFrame met datum, crypto-paar en dagelijkse winst/verlies.
    """
    try:
        # Trades laden uit JSON-bestand
        with open(trades_file, "r") as f:
            trades = json.load(f)

        if not trades:
            print("❌ Geen trades gevonden in trades.json")
            return pd.DataFrame(columns=["date", "pair", "profit"])

        # Trades omzetten naar DataFrame
        df = pd.DataFrame(trades)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date

        # Alleen verkooptransacties selecteren
        df_sells = df[df["type"] == "sell"]

        if df_sells.empty:
            print("❌ Geen verkooptransacties gevonden in trades.json")
            return pd.DataFrame(columns=["date", "pair", "profit"])

        # Dagelijkse winst/verlies per crypto berekenen
        daily_profit_per_crypto = df_sells.groupby(
            ["date", "pair"])["profit"].sum().reset_index()
        return daily_profit_per_crypto

    except Exception as e:
        print(f"❌ Fout bij het berekenen van dagelijkse winst per crypto: {e}")
        return pd.DataFrame(columns=["date", "pair", "profit"])


if __name__ == "__main__":
    trades_file = "data/trades.json"
    daily_profit_per_crypto_df = calculate_daily_profit_per_crypto(trades_file)
    print(daily_profit_per_crypto_df)
