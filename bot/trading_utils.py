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
                    logging.debug("Fetched current price for %s: %s", pair, price)
                    return price
                else:
                    raise ValueError(f"Unexpected response format: {ticker}")
            except Exception as e:
                logging.warning("Poging %d om huidige prijs op te halen voor %s mislukt: %s", attempt, pair, e)
                if attempt == retries:
                    raise RuntimeError(f"Error fetching current price for {pair}: {e}") from e
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
        rsi_indicator = RSIIndicator(pd.Series(price_history), window=window_size)
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

                # Als we een flat dictionary hebben (bijv. {"BTC": 0.001, "ETH": 0.5, "EUR": 60.00})
                if isinstance(balance_data, dict) and not isinstance(balance_data, list):
                    # Als alle values numeriek zijn, gaan we ervan uit dat de keys direct de valuta's zijn.
                    if all(isinstance(v, (int, float)) for v in balance_data.values()):
                        if asset in balance_data:
                            balance = float(balance_data[asset])
                            logging.debug("Fetched account balance for %s: %s", asset, balance)
                            return balance
                        else:
                            raise ValueError(f"Saldo voor asset {asset} niet gevonden in flat dict")
                    else:
                        balance_data = balance_data.values()

                # Ga ervan uit dat balance_data een iterabele is van entries (bijv. een lijst van dictionaries)
                for entry in balance_data:
                    if not isinstance(entry, dict):
                        continue
                    asset_key = entry.get("asset") or entry.get("symbol") or entry.get("currency")
                    if asset_key == asset:
                        balance = float(entry.get("available", 0.0))
                        logging.debug("Fetched account balance for %s: %s", asset, balance)
                        return balance
                raise ValueError(f"Saldo voor asset {asset} niet gevonden")
            except Exception as e:
                logging.warning("Poging %d om account balance voor %s op te halen mislukt: %s", attempt, asset, e)
                if attempt == retries:
                    raise RuntimeError(f"Error fetching account balance for {asset}: {e}") from e
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
                order = bitvavo.placeOrder(market, side, "market", {"amount": amount})
                # Controleer op een eventuele error in de response
                if isinstance(order, dict) and order.get("error"):
                    raise ValueError(f"API error: {order.get('error')}")
                logging.debug("Placed order for %s: %s", market, order)
                return order
            except Exception as e:
                logging.warning("Poging %d voor orderplaatsing op %s mislukt: %s", attempt, market, e)
                if attempt == retries:
                    raise RuntimeError(f"Error placing {side} order for {market}: {e}") from e
                time.sleep(delay)