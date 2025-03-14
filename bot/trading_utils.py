import json
import time
import logging
from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD


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
                    market=market, side=side, orderType="market", body={"amount": amount})
                if isinstance(order, dict) and order.get("error"):
                    if "sufficient balance" in order.get('error', '').lower():
                        logging.error("Insufficient balance to complete the operation for %s: %s", market, order.get('error'))
                        return None
                    return None
                logging.debug("Placed order for %s: %s", market, order)
                return order
            except Exception as e:
                logging.warning(
                    "Attempt %d to place order on %s failed: %s", attempt, market, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error placing {side} order for {market}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def get_order_details(bitvavo, market, order_id, retries=3, delay=2):
        """
        Retrieves the order details via the Bitvavo API.

        :param bitvavo: Configured Bitvavo API client.
        :param market: Trading pair, e.g. "LTC-EUR".
        :param order_id: The order ID for which the details need to be retrieved.
        :param retries: Number of attempts before throwing an error (default: 3).
        :param delay: Delay in seconds between attempts (default: 2).
        :return: A dictionary with the order details.
        :raises: RuntimeError if the details cannot be retrieved after all attempts.
        """
        for attempt in range(1, retries + 1):
            try:
                order_details = bitvavo.getOrder(market, order_id)
                if isinstance(order_details, str):
                    order_details = json.loads(order_details)
                if "orderId" in order_details:
                    logging.debug("Fetched order details for %s: %s",
                                order_id, order_details)
                    return order_details
                else:
                    raise ValueError(
                        f"Unexpected response format: {order_details}")
            except Exception as e:
                logging.warning(
                    "Attempt %d to fetch order details for %s failed: %s", attempt, order_id, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error retrieving order details for {order_id}: {e}") from e
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
        Calculates the Exponential Moving Average (EMA) based on the price history.
        
        :param price_history: List of historical prices.
        :param window_size: The window for the EMA calculation.
        :return: The most recent EMA value or None if there is insufficient data.
        """
        if len(price_history) < window_size:
            return None
        ema_indicator = EMAIndicator(pd.Series(price_history), window=window_size)
        return ema_indicator.ema_indicator().iloc[-1]

    @staticmethod
    def calculate_macd(price_history, window_slow=26, window_fast=12, window_sign=9):
        """
        Calculates the MACD (Moving Average Convergence Divergence) based on the price history.
        
        :param price_history: List of historical prices.
        :param window_slow: The slow window for the MACD calculation (default: 26).
        :param window_fast: The fast window for the MACD calculation (default: 12).
        :param window_sign: The signal window for the MACD calculation (default: 9).
        :return: A tuple containing the MACD line, signal line, and histogram values.
        """
        if len(price_history) < max(window_slow, window_fast, window_sign):
            return None, None, None
        macd_indicator = MACD(pd.Series(price_history), window_slow=window_slow, window_fast=window_fast, window_sign=window_sign)
        macd_line = macd_indicator.macd().iloc[-1]
        signal_line = macd_indicator.macd_signal().iloc[-1]
        macd_histogram = macd_indicator.macd_diff().iloc[-1]
        return macd_line, signal_line, macd_histogram

    @staticmethod
    def calculate_support_resistance(price_history, window_size):
        """
        Calculates support and resistance levels based on the price history.
        
        :param price_history: List of historical prices.
        :param window_size: The window for the support/resistance calculation.
        :return: A tuple containing the support and resistance levels.
        """
        if len(price_history) < window_size:
            return None, None
        price_series = pd.Series(price_history)
        rolling_max = price_series.rolling(window=window_size).max()
        rolling_min = price_series.rolling(window=window_size).min()
        support = rolling_min.iloc[-1]
        resistance = rolling_max.iloc[-1]
        return support, resistance

    @staticmethod
    def calculate_coin_score(rsi, macd, signal):
        """
        Calculates a technical score for a coin based on RSI and MACD crossover.

        :param rsi: Current RSI value.
        :param macd: Current MACD value.
        :param signal: Current MACD signal line.
        :return: Technical score (higher is better).
        """
        score = 0
        if rsi is not None:
            score += max(0, 100 - rsi)
        if macd is not None and signal is not None:
            if macd > signal:
                score += 20
            score += (macd - signal) * 10
        return score

    @staticmethod
    def rank_coins(bitvavo, pairs, price_history, rsi_window=14):
        """
        Ranks coins by technical score (RSI + MACD crossover)

        :param bitvavo: Bitvavo API client
        :param pairs: List of pairs to evaluate (e.g., ["BTC-EUR", "ETH-EUR"])
        :param price_history: Dict of recent price history per pair
        :param rsi_window: RSI window size (default 14)
        :return: Sorted list of tuples (pair, score)
        """
        scores = []

        for pair in pairs:
            try:
                prices = price_history.get(pair)
                if not prices or len(prices) < rsi_window:
                    continue

                rsi = TradingUtils.calculate_rsi(prices, rsi_window)
                macd, signal, _ = TradingUtils.calculate_macd(prices)
                score = TradingUtils.calculate_coin_score(rsi, macd, signal)
                scores.append((pair, score))

            except Exception as e:
                logging.warning(f"Failed to evaluate {pair}: {e}")
                continue

        return sorted(scores, key=lambda x: x[1], reverse=True)
