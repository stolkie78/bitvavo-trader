from ta.trend import EMAIndicator
import json
import time
import logging
from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator


class TradingUtils:
    @staticmethod
    def fetch_current_price(bitvavo, pair, retries=3, delay=2):
        """
        Fetches the current price of a trading pair using the Bitvavo API.
        Automatically performs retries for temporary errors.
        
        :param bitvavo: Configured Bitvavo API client.
        :param pair: Trading pair, for example "BTC-EUR".
        :param retries: Number of attempts before throwing an error (default: 3).
        :param delay: Delay in seconds between attempts (default: 2).
        :return: Current price as a float.
        :raises: RuntimeError if a valid response is not received after all attempts.
        """
        for attempt in range(1, retries + 1):
            try:
                ticker = bitvavo.tickerPrice({"market": pair})
                if isinstance(ticker, str):
                    ticker = json.loads(ticker)
                if "price" in ticker:
                    price = float(ticker["price"])
                    logging.debug(
                        "Fetched current price for %s: %s", pair, price)
                    return price
                else:
                    raise ValueError(f"Unexpected response format: {ticker}")
            except Exception as e:
                logging.warning(
                    "Attempt %d to fetch current price for %s failed: %s", attempt, pair, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error fetching current price for {pair}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def calculate_rsi(price_history, window_size):
        """
        Calculates the RSI based on the price history.
        
        :param price_history: List of historical prices.
        :param window_size: The window for the RSI calculation.
        :return: The most recent RSI value or None if there is insufficient data.
        """
        if len(price_history) < window_size:
            return None
        rsi_indicator = RSIIndicator(
            pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]

    @staticmethod
    def get_account_balance(bitvavo, asset="EUR", retries=3, delay=2):
        """
        Retrieves the account balance for the specified asset via the Bitvavo API with retry options.
        
        :param bitvavo: The Bitvavo API client.
        :param asset: The asset symbol for which the balance is retrieved (default "EUR").
        :param retries: Number of attempts before throwing an error (default: 3).
        :param delay: Delay in seconds between attempts (default: 2).
        :return: The available balance for the asset as a float.
        :raises: RuntimeError if retrieving the balance fails after all attempts.
        """
        for attempt in range(1, retries + 1):
            try:
                balance_data = bitvavo.balance()
                if isinstance(balance_data, str):
                    balance_data = json.loads(balance_data)

                if isinstance(balance_data, dict) and not isinstance(balance_data, list):
                    if all(isinstance(v, (int, float)) for v in balance_data.values()):
                        if asset in balance_data:
                            balance = float(balance_data[asset])
                            logging.debug(
                                "Fetched account balance for %s: %s", asset, balance)
                            return balance
                        else:
                            raise ValueError(
                                f"Balance for asset {asset} not found in flat dict")
                    else:
                        balance_data = balance_data.values()

                for entry in balance_data:
                    if not isinstance(entry, dict):
                        continue
                    asset_key = entry.get("asset") or entry.get(
                        "symbol") or entry.get("currency")
                    if asset_key == asset:
                        balance = float(entry.get("available", 0.0))
                        logging.debug(
                            "Fetched account balance for %s: %s", asset, balance)
                        return balance
                raise ValueError(f"Balance for asset {asset} not found")
            except Exception as e:
                logging.warning(
                    "Attempt %d to fetch account balance for %s failed: %s", attempt, asset, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error fetching account balance for {asset}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def place_order(bitvavo, market, side, amount, demo_mode=False, retries=3, delay=2):
        """
        Places a buy or sell order via the Bitvavo API or simulates it in demo mode,
        with retry options for temporary errors.
        
        :param bitvavo: Configured Bitvavo API client.
        :param market: Trading pair, e.g. "BTC-EUR".
        :param side: "buy" or "sell".
        :param amount: The amount to buy or sell.
        :param demo_mode: Whether the order is simulated (default: False).
        :param retries: Number of attempts before throwing an error (default: 3).
        :param delay: Delay in seconds between attempts (default: 2).
        :return: Response from the Bitvavo API or a simulated order.
        :raises: RuntimeError if placing the order fails after all attempts.
        """
        if demo_mode:
            simulated_order = {
                "status": "demo",
                "side": side,
                "market": market,
                "amount": amount,
                "order_type": "market",
                "timestamp": datetime.now().isoformat()
            }
            logging.debug("Simulated order: %s", simulated_order)
            return simulated_order

        for attempt in range(1, retries + 1):
            try:
                order = bitvavo.placeOrder(
                    market, side, "market", {"amount": amount})
                if isinstance(order, dict) and order.get("error"):
                    raise ValueError(f"API error: {order.get('error')}")
                logging.debug("Placed order for %s: %s", market, order)
                return order
            except Exception as e:
                logging.warning(
                    "Attempt %d to place order on %s failed: %s", attempt, market, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error placing {side} order for {market}: {e}") from e
                time.sleep(delay)


    class TradingUtils:
        @staticmethod
        def get_order_details(bitvavo, market, order_id, retries=3, delay=2):
            """
            Retrieves the order details via the Bitvavo API.
            
            :param bitvavo: Configured Bitvavo API client.
            :param market: The trading pair (e.g., "BTC-EUR").
            :param order_id: The order ID for which the details need to be retrieved.
            :param retries: Number of attempts before throwing an error (default: 3).
            :param delay: Delay in seconds between attempts (default: 2).
            :return: A dictionary with the order details.
            :raises: RuntimeError if the details cannot be retrieved after all attempts.
            """
            for attempt in range(1, retries + 1):
                try:
                    order_details = bitvavo.get_order(
                        market, order_id)  # ✅ Correct API method
    
                    if isinstance(order_details, str):
                        order_details = json.loads(order_details)
    
                    if "orderId" in order_details:
                        logging.debug(
                            "✅ Fetched order details for %s: %s", order_id, order_details)
                        return order_details
                    else:
                        raise ValueError(
                            f"⚠️ Unexpected response format: {order_details}")
    
                except Exception as e:
                    logging.warning(
                        "❌ Attempt %d to fetch order details for %s failed: %s", attempt, order_id, e)
    
                    if attempt == retries:
                        raise RuntimeError(
                            f"🚨 Error retrieving order details for {order_id}: {e}") from e
    
                    time.sleep(delay)


    @staticmethod
    def fetch_historical_prices(bitvavo, pair, limit=14, interval="1m"):
        """
        Fetches historical closing prices for a given trading pair with a single API call.

        :param bitvavo: Configured Bitvavo API client.
        :param pair: Trading pair, for example "BTC-EUR".
        :param limit: Number of historical datapoints (default: 14).
        :param interval: Candle interval (e.g. "1m" for 1 minute).
        :return: A list of closing prices (floats).
        :raises: RuntimeError if the historical data is not returned in the expected format.
        """
        # Pass parameters as a dictionary
        candles = bitvavo.candles(pair, interval, {"limit": limit})
        if isinstance(candles, str):
            candles = json.loads(candles)
        # Check if the response is a list of candles and that each candle is iterable
        if not isinstance(candles, list) or not candles or not isinstance(candles[0], (list, tuple)):
            raise RuntimeError(
                f"Unexpected response format for candles: {candles}")
        try:
            prices = [float(candle[4]) for candle in candles]
        except Exception as e:
            raise RuntimeError(
                f"Error processing candle data for {pair}: {e}") from e
        logging.debug("Fetched historical prices for %s: %s", pair, prices)
        return prices

    @staticmethod
    def calculate_ema(price_history, window_size):
        """
        Berekent de Exponential Moving Average (EMA) op basis van de prijsgegevens.
    
        :param price_history: Lijst met historische prijzen.
        :param window_size: Het venster voor de EMA-berekening.
        :return: De meest recente EMA-waarde of None als er onvoldoende data is.
        """
        if len(price_history) < window_size:
            return None
        ema_indicator = EMAIndicator(pd.Series(price_history), window=window_size)
        return ema_indicator.ema_indicator().iloc[-1]
    
    @staticmethod
    def fetch_historical_candles(bitvavo, pair, limit=15, interval="1m"):
        """
        Haalt historische candle-data op en geeft een DataFrame terug met kolommen:
        'timestamp', 'open', 'high', 'low', 'close' en 'volume'.
        """
        candles = bitvavo.candles(pair, interval, {"limit": limit})
        if isinstance(candles, str):
            candles = json.loads(candles)
        data = {
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": []
        }
        for candle in candles:
            data["timestamp"].append(candle[0])
            data["open"].append(float(candle[1]))
            data["high"].append(float(candle[2]))
            data["low"].append(float(candle[3]))
            data["close"].append(float(candle[4]))
            data["volume"].append(float(candle[5]))
        return pd.DataFrame(data)

    @staticmethod
    def calculate_atr(data: pd.DataFrame, period: int = 14):
        """
        Bereken de Average True Range (ATR) op basis van de candle-data.
        
        Args:
            data (pd.DataFrame): DataFrame met kolommen 'high', 'low' en 'close'.
            period (int): Het aantal periodes voor de ATR-berekening.
        
        Returns:
            float: De meest recente ATR-waarde.
        """
        high = data["high"]
        low = data["low"]
        close = data["close"]
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period, min_periods=period).mean()
        return atr.iloc[-1]