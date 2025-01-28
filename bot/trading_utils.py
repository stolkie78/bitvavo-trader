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
        rsi_indicator = RSIIndicator(pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]

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
