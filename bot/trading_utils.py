import json
from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator


class TradingUtils:
    @staticmethod
    def fetch_current_price(bitvavo, pair):
        """Fetches the current price of a trading pair using the Bitvavo API."""
        try:
            ticker = bitvavo.tickerPrice({"market": pair})
            if "price" in ticker:
                return float(ticker["price"])
            else:
                raise ValueError(f"Unexpected response format: {ticker}")
        except Exception as e:
            raise RuntimeError(f"Error fetching current price for {pair}: {e}")

    @staticmethod
    def calculate_rsi(price_history, window_size):
        """Calculates the RSI based on the price history."""
        if len(price_history) < window_size:
            return None
        rsi_indicator = RSIIndicator(
            pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]

    @staticmethod
    def get_account_balance(bitvavo, asset="EUR"):
        """
        Haalt het accountsaldo op voor het opgegeven asset via de Bitvavo API.
        
        Parameters:
            bitvavo: De Bitvavo API-client.
            asset (str): Het asset symbool waarvan het saldo wordt opgehaald (default "EUR").
        
        Returns:
            float: Het beschikbare saldo voor het asset.
        
        Raises:
            RuntimeError: Indien het ophalen van het saldo mislukt.
        """
        try:
            balance_data = bitvavo.balance()

            # Als balance_data een string is, converteren we deze naar een Python-object.
            if isinstance(balance_data, str):
                balance_data = json.loads(balance_data)

            # Check of we een flat dictionary hebben (bijv. {"BTC": 0.001, "ETH": 0.5, "EUR": 60.00})
            if isinstance(balance_data, dict) and not isinstance(balance_data, list):
                # Als alle values numeriek zijn, gaan we ervan uit dat de keys direct de valuta's zijn.
                if all(isinstance(v, (int, float)) for v in balance_data.values()):
                    if asset in balance_data:
                        return float(balance_data[asset])
                    else:
                        raise ValueError(f"Saldo voor asset {
                                         asset} niet gevonden in flat dict")
                else:
                    # Als de dictionary niet flat is, werken we met de values.
                    balance_data = balance_data.values()

            # Ga ervan uit dat balance_data nu een iterabele is van entries (bijv. een lijst van dictionaries)
            for entry in balance_data:
                # Zorg ervoor dat we alleen dictionaries verwerken.
                if not isinstance(entry, dict):
                    continue
                # Controleer op keys "asset", "symbol" of "currency"
                asset_key = entry.get("asset") or entry.get(
                    "symbol") or entry.get("currency")
                if asset_key == asset:
                    return float(entry.get("available", 0.0))
            raise ValueError(f"Saldo voor asset {asset} niet gevonden")
        except Exception as e:
            raise RuntimeError(
                f"Error fetching account balance for {asset}: {e}")

    @staticmethod
    def place_order(bitvavo, market, side, amount, demo_mode=False):
        """
        Place a buy or sell order via the Bitvavo API or simulate it in demo mode.
        
        Args:
            bitvavo (Bitvavo): The initialized Bitvavo API client.
            market (str): Trading pair, e.g., "BTC-EUR".
            side (str): "buy" or "sell".
            amount (float): The amount to buy or sell.
            demo_mode (bool): Whether to simulate the order (default: False).
        
        Returns:
            dict: Response from the Bitvavo API or a simulated order.
        """
        if demo_mode:
            return {
                "status": "demo",
                "side": side,
                "market": market,
                "amount": amount,
                "order_type": "market",
                "timestamp": datetime.now().isoformat()
            }
        try:
            order = bitvavo.placeOrder(
                market, side, "market", {"amount": amount})
            return order
        except Exception as e:
            raise RuntimeError(f"Error placing {side} order for {market}: {e}")
