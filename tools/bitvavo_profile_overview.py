#!/usr/bin/env python3
import json
import time
import hmac
import hashlib
import logging
import requests

# Stel het logniveau in op DEBUG voor uitgebreidere logging.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_bitvavo_config() -> dict:
    """
    Laadt de Bitvavo-configuratie uit het bestand 'bitvavo.json'.
    """
    try:
        with open("bitvavo.json", "r") as f:
            config = json.load(f)
        # Debug: log een deel van de API_KEY (niet de volledige sleutel)
        api_key = config.get("API_KEY", "")
        if not api_key:
            logging.error("API_KEY is leeg in bitvavo.json!")
        else:
            logging.debug("API_KEY geladen: %s...", api_key[:5])
        return config
    except Exception as e:
        logging.error("Fout bij laden van bitvavo.json: %s", e)
        raise


def bitvavo_request(method: str, endpoint: str, params: dict = None,
                    body: dict = None, config: dict = None) -> dict:
    """
    Voert een geauthenticeerde request uit naar de Bitvavo API en logt extra informatie
    voor debugdoeleinden.
    """
    if config is None:
        raise Exception("Bitvavo-configuratie niet meegegeven.")

    api_key = config.get("API_KEY")
    api_secret = config.get("API_SECRET")
    rest_url = config.get("RESTURL")
    access_window = config.get("ACCESSWINDOW", 10000)

    timestamp = str(int(time.time() * 1000))
    body_str = json.dumps(body) if body else ""
    message = timestamp + method.upper() + endpoint + body_str
    signature = hmac.new(
        api_secret.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    headers = {
        "Bitvavo-Access": timestamp,
        "Bitvavo-Key": api_key,
        "Bitvavo-Signature": signature,
        "Bitvavo-Timestamp": timestamp,
        "Bitvavo-Receive-Window": str(access_window),
        "Content-Type": "application/json"
    }

    url = rest_url + endpoint
    logging.debug("URL: %s", url)
    logging.debug(
        "Headers: Bitvavo-Access: %s, Bitvavo-Timestamp: %s", timestamp, timestamp)

    try:
        response = requests.request(
            method, url, params=params, data=body_str, headers=headers, timeout=10
        )
        logging.debug("Response status: %s", response.status_code)
        logging.debug("Response body: %s", response.text)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error("Fout bij Bitvavo API-aanroep: %s", e)
        logging.error("Response body: %s", getattr(
            e.response, "text", "Geen response beschikbaar"))
        raise Exception("Bitvavo API-aanroep mislukt.") from e


def get_account_history(config: dict) -> list:
    """
    Haalt de account history op via de endpoint '/account/history'.
    """
    endpoint = "/account/history"
    logging.info("Ophalen van account history via: %s",
                 config.get("RESTURL") + endpoint)
    try:
        transactions = bitvavo_request(
            "GET", endpoint, params=None, config=config)
        logging.info("Account history opgehaald: %d transacties",
                     len(transactions))
        return transactions
    except Exception as e:
        logging.error("Kon account history niet ophalen: %s", e)
        raise


def main():
    """
    Main functie voor debuggen: laadt de configuratie en probeert de account history op te halen.
    """
    try:
        config = load_bitvavo_config()
        transactions = get_account_history(config)
        logging.info("Aantal opgehaalde transacties: %d", len(transactions))
    except Exception as e:
        logging.error("Er is een fout opgetreden: %s", e)


if __name__ == "__main__":
    main()
