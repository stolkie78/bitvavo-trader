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
        Voert automatisch retries uit bij tijdelijke fouten.
        
        :param bitvavo: Geconfigureerde Bitvavo API-client.
        :param pair: Trading pair, bijvoorbeeld "BTC-EUR".
        :param retries: Aantal pogingen voordat een fout wordt opgegooid (default: 3).
        :param delay: Wachtduur in seconden tussen pogingen (default: 2).
        :return: Huidige prijs als float.
        :raises: RuntimeError als geen geldige response wordt ontvangen na alle pogingen.
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
                    "Poging %d om huidige prijs op te halen voor %s mislukt: %s", attempt, pair, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error fetching current price for {pair}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def calculate_rsi(price_history, window_size):
        """
        Calculates the RSI based on the price history.
        
        :param price_history: Lijst met historische prijzen.
        :param window_size: Het venster voor de RSI-berekening.
        :return: De meest recente RSI-waarde of None indien er onvoldoende data is.
        """
        if len(price_history) < window_size:
            return None
        rsi_indicator = RSIIndicator(
            pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]

    @staticmethod
    def get_account_balance(bitvavo, asset="EUR", retries=3, delay=2):
        """
        Haalt het accountsaldo op voor het opgegeven asset via de Bitvavo API met retry-opties.
        
        :param bitvavo: De Bitvavo API-client.
        :param asset: Het asset symbool waarvan het saldo wordt opgehaald (default "EUR").
        :param retries: Aantal pogingen voordat een fout wordt opgegooid (default: 3).
        :param delay: Wachtduur in seconden tussen pogingen (default: 2).
        :return: Het beschikbare saldo voor het asset als float.
        :raises: RuntimeError indien het ophalen van het saldo mislukt na alle pogingen.
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
                                f"Saldo voor asset {asset} niet gevonden in flat dict")
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
                raise ValueError(f"Saldo voor asset {asset} niet gevonden")
            except Exception as e:
                logging.warning(
                    "Poging %d om account balance voor %s op te halen mislukt: %s", attempt, asset, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error fetching account balance for {asset}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def place_order(bitvavo, market, side, amount, demo_mode=False, retries=3, delay=2):
        """
        Plaatst een buy of sell order via de Bitvavo API of simuleert deze in demo mode,
        met retry-opties voor tijdelijke fouten.
        
        :param bitvavo: Geconfigureerde Bitvavo API-client.
        :param market: Trading pair, bv. "BTC-EUR".
        :param side: "buy" of "sell".
        :param amount: De hoeveelheid om te kopen of verkopen.
        :param demo_mode: Of de order gesimuleerd wordt (default: False).
        :param retries: Aantal pogingen voordat een fout wordt opgegooid (default: 3).
        :param delay: Wachtduur in seconden tussen pogingen (default: 2).
        :return: Response van de Bitvavo API of een gesimuleerde order.
        :raises: RuntimeError indien de orderplaatsing mislukt na alle pogingen.
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
                    "Poging %d voor orderplaatsing op %s mislukt: %s", attempt, market, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error placing {side} order for {market}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def get_order_details(bitvavo, order_id, retries=3, delay=2):
        """
        Haalt de order details op via de Bitvavo API.
        
        :param bitvavo: Geconfigureerde Bitvavo API-client.
        :param order_id: Het order ID waarvan de details moeten worden opgehaald.
        :param retries: Aantal pogingen voordat een fout wordt opgegooid (default: 3).
        :param delay: Wachtduur in seconden tussen pogingen (default: 2).
        :return: Een dictionary met order details.
        :raises: RuntimeError als na alle pogingen de details niet opgehaald kunnen worden.
        """
        for attempt in range(1, retries + 1):
            try:
                # Voorbeeld: maak een API-aanroep naar de order status endpoint.
                order_details = bitvavo.orderStatus(order_id)
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
                    "Poging %d om order details voor %s op te halen mislukt: %s", attempt, order_id, e)
                if attempt == retries:
                    raise RuntimeError(
                        f"Error retrieving order details for {order_id}: {e}") from e
                time.sleep(delay)

    @staticmethod
    def fetch_historical_prices(bitvavo, pair, limit=14, interval="1m"):
        """
        Haalt historische sluitingsprijzen op voor een gegeven trading pair met één API-aanroep.

        :param bitvavo: Geconfigureerde Bitvavo API-client.
        :param pair: Trading pair, bijvoorbeeld "BTC-EUR".
        :param limit: Aantal historische datapoints (default: 14).
        :param interval: Candle-interval (bijv. "1m" voor 1 minuut).
        :return: Een lijst met sluitingsprijzen (floats).
        :raises: RuntimeError als de historische data niet in het verwachte format wordt teruggegeven.
        """
        # Geef de parameters mee als dictionary (wat vaak wel de API verwacht)
        candles = bitvavo.candles(pair, interval, {"limit": limit})
        if isinstance(candles, str):
            candles = json.loads(candles)
        # Controleer of we een lijst met candles hebben en dat elk candle een iterabele is
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
