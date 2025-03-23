import json
import time
import logging
from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange


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
    def place_order(bitvavo, market, side, amount, demo_mode=False, max_retries=3):
        """
        Attempts to place an order with retries. If it fails due to insufficient balance, it logs the error and skips the trade.
        
        :param bitvavo: Bitvavo API client instance
        :param market: Market string (e.g., 'ADA-EUR')
        :param side: 'buy' or 'sell'
        :param amount: Amount to buy or sell (float or str)
        :param demo_mode: If True, simulate the order without placing it
        :param max_retries: Number of retries before giving up
        :return: Order response dict or None
        """
        asset = market.split('-')[1] if side == 'buy' else market.split('-')[0]
        balance = TradingUtils.get_account_balance(bitvavo, asset)
    
        if balance < float(amount):
            logging.error(
                f"Insufficient balance for {side} order on {market}. Required: {amount}, Available: {balance}"
            )
            return None
    
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(
                    f"Attempt {attempt} to place {side} order for {market} with amount {amount}"
                )
    
                if demo_mode:
                    logging.info(
                        f"Demo mode: Simulated {side} order for {market} ({amount})"
                    )
                    return {"status": "success", "orderId": "demo_order"}
    
                body = {
                    "market": market,
                    "side": side,
                    "orderType": "market",
                    "amount": str(amount)
                }
                order = bitvavo.placeOrder(body)
    
                if isinstance(order, str):
                    order = json.loads(order)
    
                if "error" in order:
                    raise ValueError(f"API error: {order.get('error')}")
    
                return order
    
            except ValueError as e:
                logging.warning(f"Attempt {attempt} to place order on {market} failed: {e}")
    
                if "insufficient balance" in str(e).lower():
                    logging.error(
                        f"Skipping trade for {market} due to insufficient balance."
                    )
                    return None
    
            except Exception as e:
                logging.error(
                    f"Unexpected error during {side} order on {market}: {e}"
                )
    
            if attempt < max_retries:
                logging.info("Retrying...")
    
        logging.error(f"Failed to place {side} order for {market} after {max_retries} attempts.")
        return None




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
    def calculate_atr(high, low, close, window_size):
        """
        Calculates the Average True Range (ATR) based on high, low, and close prices.
        
        :param high: List of high prices.
        :param low: List of low prices.
        :param close: List of close prices.
        :param window_size: The window for the ATR calculation.
        :return: The most recent ATR value or None if there is insufficient data.
        """
        if len(high) < window_size or len(low) < window_size or len(close) < window_size:
            return None
        high_series = pd.Series(high)
        low_series = pd.Series(low)
        close_series = pd.Series(close)
        tr = pd.concat([high_series - low_series, 
                        (high_series - close_series.shift()).abs(), 
                        (low_series - close_series.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=window_size).mean()
        return atr.iloc[-1]
    
    @staticmethod
    def calculate_ema(prices, window_size):
        """
        Calculates the Exponential Moving Average (EMA) based on the price history.
        
        :param prices: List of historical prices.
        :param window_size: The window for the EMA calculation.
        :return: The most recent EMA value or None if there is insufficient data.
        """
        if len(prices) < window_size:
            return None
        ema = pd.Series(prices).ewm(span=window_size, adjust=False).mean()
        return ema.iloc[-1]
    
    @staticmethod
    def calculate_adx(high, low, close, window_size):
        """
        Calculates the Average Directional Index (ADX) based on high, low, and close prices.
        
        :param high: List of high prices.
        :param low: List of low prices.
        :param close: List of close prices.
        :param window_size: The window for the ADX calculation.
        :return: The most recent ADX value or None if there is insufficient data.
        """
        if len(high) < window_size or len(low) < window_size or len(close) < window_size:
            return None
        high_series = pd.Series(high)
        low_series = pd.Series(low)
        close_series = pd.Series(close)
        plus_dm = high_series.diff()
        minus_dm = low_series.diff()
        tr = pd.concat([high_series - low_series, 
                        (high_series - close_series.shift()).abs(), 
                        (low_series - close_series.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=window_size).mean()
        plus_di = 100 * (plus_dm.rolling(window=window_size).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=window_size).mean() / atr)
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
        adx = dx.rolling(window=window_size).mean()
        return adx.iloc[-1]
    
    @staticmethod
    def calculate_macd(price_history, window_slow=26, window_fast=12, window_sign=9):
        """
        Calculates the MACD (Moving Average Convergence Divergence) based on the price history.

        :param price_history: List of historical prices.
        :param window_slow: The slow window for the MACD calculation (default: 26).
        :param window_fast: The fast window for the MACD calculation (default: 12).
        :param window_sign: The signal window for the MACD calculation (default: 9).
        :return: A tuple (macd, signal, histogram).
        """
        if len(price_history) < max(window_slow, window_fast, window_sign):
            return None, None, None

        macd_indicator = MACD(
            pd.Series(price_history),
            window_slow=window_slow,
            window_fast=window_fast,
            window_sign=window_sign
        )

        macd_line = macd_indicator.macd().iloc[-1]
        signal_line = macd_indicator.macd_signal().iloc[-1]
        macd_histogram = macd_indicator.macd_diff().iloc[-1]

        return macd_line, signal_line, macd_histogram

    
    @staticmethod
    def calculate_bb(prices, window_size, num_std_dev):
        """
        Calculates the Bollinger Bands (BB) based on the price history.
        
        :param prices: List of historical prices.
        :param window_size: The window for the moving average calculation.
        :param num_std_dev: The number of standard deviations for the bands.
        :return: A tuple (middle_band, upper_band, lower_band) or None if there is insufficient data.
        """
        if len(prices) < window_size:
            return None
        prices_series = pd.Series(prices)
        middle_band = prices_series.rolling(window=window_size).mean()
        std_dev = prices_series.rolling(window=window_size).std()
        upper_band = middle_band + (std_dev * num_std_dev)
        lower_band = middle_band - (std_dev * num_std_dev)
        return middle_band.iloc[-1], upper_band.iloc[-1], lower_band.iloc[-1]
    
    @staticmethod
    def calculate_obv(prices, volumes):
        """
        Calculates the On-Balance Volume (OBV) based on the price and volume history.
        
        :param prices: List of historical prices.
        :param volumes: List of historical volumes.
        :return: The most recent OBV value.
        """
        if len(prices) != len(volumes):
            raise ValueError("Prices and volumes must have the same length")
        obv = [0]
        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                obv.append(obv[-1] + volumes[i])
            elif prices[i] < prices[i - 1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
        return obv[-1]
    @staticmethod
    def calculate_vwap(high, low, close, volume):
        """
        Calculates the Volume Weighted Average Price (VWAP) based on high, low, close prices and volume.
        
        :param high: List of high prices.
        :param low: List of low prices.
        :param close: List of close prices.
        :param volume: List of volumes.
        :return: The most recent VWAP value.
        """
        typical_price = [(h + l + c) / 3 for h, l, c in zip(high, low, close)]
        cumulative_tp_vol = sum(tp * v for tp, v in zip(typical_price, volume))
        cumulative_vol = sum(volume)
        return cumulative_tp_vol / cumulative_vol if cumulative_vol != 0 else None
    
    @staticmethod
    def calculate_atr(high, low, close, window=14):
        """
        Calculates Average True Range (ATR) as a measure of volatility.
        :param high: List of high prices.
        :param low: List of low prices.
        :param close: List of close prices.
        :param window: Number of periods for ATR (default 14).
        :return: Most recent ATR value or None.
        """
        if len(high) < window or len(low) < window or len(close) < window:
            return None
        df = pd.DataFrame({"high": high, "low": low, "close": close})
        atr = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=window)
        return atr.average_true_range().iloc[-1]
    
    @staticmethod
    def calculate_momentum(price_history, window=10):
        """
        Calculates simple momentum indicator (Price[t] - Price[t-n]).
        :param price_history: List of prices.
        :param window: Number of periods for momentum (default 10).
        :return: Momentum value or None.
        """
        if len(price_history) < window:
            return None
        return price_history[-1] - price_history[-window]
    @staticmethod
    def calculate_volume_change(volumes, window=10):
        """
        Calculates volume deviation from moving average.
        :param volumes: List of volume data.
        :param window: Number of periods for moving average (default 10).
        :return: Volume change ratio (current / MA).
        """
        if len(volumes) < window:
            return None
        vol_series = pd.Series(volumes)
        vol_ma = vol_series.rolling(window=window).mean().iloc[-1]
        return (vol_series.iloc[-1] / vol_ma) if vol_ma else 0.0
    
    @staticmethod
    def normalize_features(features):
        """
        Normalizes features using min-max normalization.
        :param features: Numpy array of features.
        :return: Normalized numpy array in range [0,1].
        """
        min_vals = features.min(axis=0)
        max_vals = features.max(axis=0)
        denom = (max_vals - min_vals)
        denom[denom == 0] = 1e-6  # avoid division by zero
        return (features - min_vals) / denom
    
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
    def fetch_raw_candles(bitvavo, pair, limit=100, interval="1h"):
        """
        Fetch full candle data (timestamp, open, high, low, close, volume) for a trading pair.

        :param bitvavo: Bitvavo API client
        :param pair: Trading pair, e.g. 'BTC-EUR'
        :param limit: Number of candles
        :param interval: Candle interval, e.g. '1h'
        :return: List of candle data lists
        """
        candles = bitvavo.candles(pair, interval, {"limit": limit})
        if isinstance(candles, str):
            candles = json.loads(candles)
        if not isinstance(candles, list):
            raise ValueError(f"Unexpected candle format: {candles}")
        return candles


    @staticmethod
    def calculate_volume_change(volume_series):
        if not volume_series or len(volume_series) < 2:
            return 0.0
        vol_now = volume_series[-1]
        vol_avg = sum(volume_series[:-1]) / max(1, len(volume_series) - 1)
        return (vol_now - vol_avg) / vol_avg if vol_avg != 0 else 0.0

    @staticmethod
    def rank_coins(bitvavo, pairs: list, price_history: dict, rsi_window: int) -> list:
        """
        Rank coins based on a composite indicator score.
        Returns a sorted list of tuples: (pair, score)
        """
        rankings = []
        for pair in pairs:
            history = price_history.get(pair, [])
            if len(history) < rsi_window:
                continue
            
            try:
                rsi = TradingUtils.calculate_rsi(history, rsi_window)
                macd, signal, _ = TradingUtils.calculate_macd(history)
                if rsi is None or macd is None or signal is None:
                    continue
                
                score = 100 - rsi  # inverse RSI (lagere RSI = aantrekkelijker)
                score += abs(macd - signal) * 100  # MACD verschil als momentum indicator
                rankings.append((pair, score))
            except Exception as e:
                continue
            
        return sorted(rankings, key=lambda x: x[1], reverse=True)







