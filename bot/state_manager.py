import json
import os
import threading
import time
from datetime import datetime
from bot.trading_utils import TradingUtils


class StateManager:
    _lock = threading.Lock()  # Lock om race conditions te voorkomen

    def __init__(self, pair, logger, bitvavo, demo_mode=False, bot_name="TradingBot"):
        """
        Initialiseer de StateManager.

        Args:
            pair (str): Het trading pair (bijv. 'BTC-EUR').
            logger: De logger voor logging.
            bitvavo: De Bitvavo API client.
            demo_mode (bool): Indien True, worden orders in demo-mode geplaatst.
            bot_name (str): Naam van de bot voor logging.
        """
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
        self.bot_name = bot_name
        self.last_stoploss_time = None

        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trades_file = os.path.join(self.data_dir, "trades.json")
        self.portfolio = self.load_portfolio()

        os.makedirs(self.data_dir, exist_ok=True)

    def load_portfolio(self):
        """Laad de portfolio uit een JSON-bestand."""
        if os.path.exists(self.portfolio_file) and os.path.getsize(self.portfolio_file) > 0:
            try:
                with open(self.portfolio_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                self.logger.log(f"[{self.bot_name}] ❗ Error loading portfolio.json, resetting file.", to_console=True)
        return {}

    def save_portfolio(self):
        """Sla de portfolio op in een JSON-bestand."""
        with self._lock:
            try:
                with open(self.portfolio_file, "w") as f:
                    json.dump(self.portfolio, f, indent=4)
                self.logger.log(f"[{self.bot_name}] ✅ Portfolio successfully updated.", to_console=True)
            except Exception as e:
                self.logger.log(f"[{self.bot_name}] ❌ Error saving portfolio: {e}", to_console=True)

    def get_open_positions(self):
        """Retourneer een lijst van open posities voor het pair."""
        return self.portfolio.get(self.pair, [])

    def get_balance(self):
        """Retourneer het huidige saldo van de crypto."""
        response = self.bitvavo.balance()
        for asset in response:
            if asset["symbol"] == self.pair.split("-")[0]:  # BTC-EUR → BTC
                return float(asset["available"])
        return 0.0

    def adjust_quantity(self, pair, quantity):
        """Pas de hoeveelheid aan volgens de marktvereisten."""
        market_info = self.bitvavo.markets()
        for market in market_info:
            if market['market'] == pair:
                min_amount = float(market.get('minOrderInBaseAsset', 0.0))
                precision = int(market.get('decimalPlacesBaseAsset', 6))
                return max(min_amount, round(quantity, precision))
        return quantity

    def log_trade(self, trade_type, price, quantity, profit=None):
        """Log de details van een trade."""
        trade = {
            "pair": self.pair,
            "type": trade_type,
            "price": price,
            "quantity": quantity,
            "total_cost": price * quantity,
            "timestamp": datetime.now().isoformat()
        }
        if trade_type.lower() == "sell" and profit is not None:
            trade["profit_eur"] = profit

        try:
            if not os.path.exists(self.trades_file):
                with open(self.trades_file, "w") as f:
                    json.dump([trade], f, indent=4)
            else:
                with open(self.trades_file, "r") as f:
                    trades = json.load(f)
                trades.append(trade)
                with open(self.trades_file, "w") as f:
                    json.dump(trades, f, indent=4)
        except Exception as e:
            self.logger.log(f"[{self.bot_name}] ❌ Error logging trade: {e}", to_console=True)


    def calculate_profit_for_position(self, position, current_price, fee_percentage):
        """
        Bereken de winst of het verlies voor een specifieke positie.
    
        Args:
            position (dict): De gegevens van de positie.
            current_price (float): De huidige marktprijs van de asset.
            fee_percentage (float): Het handelskostenpercentage.
    
        Returns:
            float: De winst/verlies in procent van de oorspronkelijke investering.
        """
        quantity = position.get("quantity", 0)
        cost_basis = position.get("spent", position["price"] * quantity)
        revenue = current_price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis
    
        if cost_basis != 0:
            return (profit / cost_basis) * 100
        return 0.0


    ############################
    # KOOP FUNCTIONALITEIT
    ############################
    def buy(self, price, budget, fee_percentage):
        """Voert een kooporder uit op basis van een budget."""
        if budget <= 0:
            self.logger.log(f"[{self.bot_name}] ❌ Invalid budget: {budget} EUR", to_console=True)
            return

        quantity = (budget / price) * (1 - fee_percentage / 100)
        self._execute_buy(price, quantity, fee_percentage)

    def _execute_buy(self, price, quantity, fee_percentage):
        """Interne functie die de daadwerkelijke kooptransactie uitvoert."""
        available_balance = self.get_balance()
        total_cost = price * quantity

        if available_balance < total_cost:
            self.logger.log(f"[{self.bot_name}] ❌ Not enough funds. Needed: {total_cost:.2f} EUR, Available: {available_balance:.2f} EUR", to_console=True)
            return

        quantity = self.adjust_quantity(self.pair, quantity)
        if quantity <= 0:
            self.logger.log(f"[{self.bot_name}] ❌ Invalid quantity: {quantity}", to_console=True)
            return

        order = TradingUtils.place_order(self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode)
        if order.get("status") == "demo" or "orderId" in order:
            spent = total_cost * (1 + fee_percentage / 100)
            new_position = {"price": price, "quantity": quantity, "spent": spent, "timestamp": datetime.now().isoformat()}

            self.portfolio.setdefault(self.pair, []).append(new_position)
            self.save_portfolio()
            self.log_trade("buy", price, quantity)
            self.logger.log(f"[{self.bot_name}] ✅ Bought {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}, Total={spent:.2f} EUR", to_console=True)
        else:
            self.logger.log(f"[{self.bot_name}] ❌ Failed to execute buy order: {order}", to_console=True)

    ############################
    # VERKOOP FUNCTIONALITEIT
    ############################
    def sell(self, price, fee_percentage, max_retries=3, wait_time=5, is_stoploss=False):
        """Verkoop alle open posities met retry-mechanisme."""
        open_positions = self.get_open_positions()
        for position in list(open_positions):
            self._execute_sell(position, price, fee_percentage, max_retries, wait_time, is_stoploss)

    def _execute_sell(self, position, price, fee_percentage, max_retries, wait_time, is_stoploss):
        """Voert een verkoop uit met optioneel retry-mechanisme."""
        quantity = self.adjust_quantity(self.pair, position.get("quantity", 0))
        cost_basis = position.get("spent", position["price"] * quantity)

        for attempt in range(1, max_retries + 1):
            revenue = price * quantity * (1 - fee_percentage / 100)
            profit = revenue - cost_basis

            self.logger.log(f"[{self.bot_name}] 🔴 Sell Attempt {attempt} - {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}, Total={revenue:.2f} EUR, Profit={profit:.2f} EUR", to_console=True)

            order = TradingUtils.place_order(self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)
            if order.get("status") == "demo" or "orderId" in order:
                self.portfolio[self.pair].remove(position)
                self.save_portfolio()
                self.log_trade("sell", price, quantity, profit)
                self.logger.log(f"[{self.bot_name}] ✅ Sold {self.pair}: Price={price:.2f}, Profit={profit:.2f} EUR", to_console=True)
                return
            time.sleep(wait_time)

        self.logger.log(f"[{self.bot_name}] ❌ Sell failed for {self.pair} after {max_retries} attempts.", to_console=True)