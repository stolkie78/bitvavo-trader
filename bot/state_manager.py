import json
from datetime import datetime
import os
from bot.trading_utils import TradingUtils
import threading
import time  # For sleep in stop loss retry mechanism


class StateManager:
    _lock = threading.Lock()  # Lock to prevent race conditions

    def __init__(self, pair, logger, bitvavo, demo_mode=False, bot_name="TradingBot"):
        """
        Initialiseer de StateManager.

        Args:
            pair (str): Het trading pair (bijv. 'TRUMP-EUR').
            logger: De logger die gebruikt wordt voor logging.
            bitvavo: De Bitvavo API client.
            demo_mode (bool): Indien True, worden orders in demo-mode geplaatst.
            bot_name (str): Naam van de bot voor logregels.
        """
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
        self.bot_name = bot_name
        # Use a list to allow multiple positions per currency pair
        self.positions = []
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trades_file = os.path.join(self.data_dir, "trades.json")
        self.portfolio = self.load_portfolio()

        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Restore positions if they exist in the portfolio for this pair
        if self.pair in self.portfolio:
            stored = self.portfolio[self.pair]
            if isinstance(stored, list):
                self.positions = stored
            else:
                self.positions = [stored]

    def has_position(self):
        """Check if there is at least one open position for the pair using the latest portfolio state."""
        self.portfolio = self.load_portfolio()  # Always load the fresh portfolio
        positions = self.portfolio.get(self.pair, [])
        if not isinstance(positions, list):
            positions = [positions]
        return len(positions) > 0

    def get_open_positions(self):
        """Return a list of open positions for the pair."""
        self.portfolio = self.load_portfolio()  # Ensure portfolio is up-to-date
        positions = self.portfolio.get(self.pair, [])
        if not isinstance(positions, list):
            positions = [positions]
        return positions

    def load_portfolio(self):
        """Load the entire portfolio content from a JSON file."""
        if os.path.exists(self.portfolio_file) and os.path.getsize(self.portfolio_file) > 0:
            try:
                with open(self.portfolio_file, "r") as f:
                    self.portfolio = json.load(f)
                # Ensure positions for the pair are stored as a list
                if self.pair in self.portfolio:
                    stored = self.portfolio[self.pair]
                    if not isinstance(stored, list):
                        self.portfolio[self.pair] = [stored]
                return self.portfolio
            except (json.JSONDecodeError, IOError):
                self.logger.log(
                    f"[{self.bot_name}] 👽❗ Error loading portfolio.json, resetting file.",
                    to_console=True
                )
                return {}
        return {}

    def save_portfolio(self):
        """Save the portfolio content to a JSON file."""
        with self._lock:  # Prevent race conditions
            try:
                with open(self.portfolio_file, "w") as f:
                    json.dump(self.portfolio, f, indent=4)
                self.portfolio = self.load_portfolio()  # Reload to confirm changes
                self.logger.log(
                    f"[{self.bot_name}] 👽 Portfolio successfully updated: {json.dumps(self.portfolio, indent=4)}",
                    to_console=True
                )
            except Exception as e:
                self.logger.log(
                    f"[{self.bot_name}] 👽❌ Error saving portfolio: {e}", to_console=True)

    def adjust_quantity(self, pair, quantity):
        """Adjust the quantity to meet market requirements."""
        market_info = self.bitvavo.markets()
        for market in market_info:
            if market['market'] == pair:
                min_amount = float(market.get('minOrderInBaseAsset', 0.0))
                precision = int(market.get('decimalPlacesBaseAsset', 6))
                adjusted_quantity = max(min_amount, round(quantity, precision))
                return adjusted_quantity
        self.logger.log(
            f"[{self.bot_name}] {pair}: ⚠️ Market info not found. Returning original quantity.",
            to_console=True
        )
        return quantity
    
    def calculate_profit(self, current_price, fee_percentage):
        """
        Calculate aggregated profit or loss for all open positions.

        Returns:
            float or None: The aggregated profit or loss as a percentage of the initial investment,
                        or None if no positions exist.
        """
        open_positions = self.get_open_positions()
        if not open_positions:
            self.logger.log(
                f"[{self.bot_name}] {self.pair}: ❌ No active position,  Skipping profit calculation.",
                to_console=True
            )
            return None

        total_cost = 0
        total_revenue = 0
        for position in open_positions:
            quantity = position.get("quantity", 0)
            cost_basis = position.get("spent", position["price"] * quantity)
            revenue = current_price * quantity * (1 - fee_percentage / 100)
            total_cost += cost_basis
            total_revenue += revenue
        profit = total_revenue - total_cost
        return (profit / total_cost) * 100 if total_cost != 0 else 0

    def calculate_profit_for_position(self, position, current_price, fee_percentage):
        """
        Calculate the profit or loss for a specific position.

        Args:
            position (dict): The position data.
            current_price (float): The current market price of the asset.
            fee_percentage (float): The trading fee percentage.

        Returns:
            float: The profit or loss as a percentage of the initial investment.
        """
        quantity = position.get("quantity", 0)
        cost_basis = position.get("spent", position["price"] * quantity)
        revenue = current_price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis
        return (profit / cost_basis) * 100 if cost_basis != 0 else 0

    def log_trade(self, trade_type, price, quantity, profit=None):
        """
        Log trade details to a JSON file.

        Args:
            trade_type (str): "buy" of "sell".
            price (float): Trade price.
            quantity (float): Quantity traded.
            profit (float, optional): Profit from the trade in euros (only applicable for sell trades).
        """
        trade = {
            "pair": self.pair,
            "type": trade_type,
            "price": price,
            "quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }
        # Add profit in EUR to all sell trades
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
            self.logger.log(
                f"[{self.bot_name}] ❌ Error logging trade: {e}", to_console=True, to_slack=False)

    def get_actual_trade_profit(self, order_id, position, fee_percentage):
        """
        Retrieve the actual order details and calculate the true profit in euros.

        Args:
            order_id (str): The executed order ID.
            position (dict): The original position details.
            fee_percentage (float): The transaction fee percentage.

        Returns:
            float or None: The calculated true profit or None if retrieval fails.
        """
        try:
            order_details = TradingUtils.get_order_details(
                self.bitvavo, order_id)
            total_executed_value = 0.0
            total_fee = 0.0

            for trade in order_details.get("trades", []):
                trade_price = float(trade.get("price", 0))
                trade_quantity = float(trade.get("quantity", 0))
                fee = trade.get("fee")
                if fee is not None:
                    fee = float(fee)
                else:
                    fee = trade_price * trade_quantity * (fee_percentage / 100)
                total_executed_value += trade_price * trade_quantity
                total_fee += fee

            cost_basis = position.get(
                "spent", position["price"] * position["quantity"])
            actual_profit = total_executed_value - cost_basis - total_fee
            return actual_profit
        except Exception as e:
            self.logger.log(
                f"[{self.bot_name}] ❌ Error retrieving actual trade details for order {order_id}: {e}",
                to_console=True
            )
            return None
        
    def get_price_history(self):
        """
        Haal de laatste prijs geschiedenis op van de markt.
        """
        return self.price_history if hasattr(self, "price_history") else []

    @staticmethod
    def show_all_open_positions():
        data_dir = "data"
        portfolio_file = os.path.join(data_dir, "portfolio.json")
        if os.path.exists(portfolio_file) and os.path.getsize(portfolio_file) > 0:
            with open(portfolio_file, "r") as file:
                portfolio = json.load(file)
                for pair, positions in portfolio.items():
                    print(f"Pair: {pair}")
                    for position in positions:
                        print(f"  Position: {position}")
        else:
            print("Portfolio file does not exist or is empty.")

    def get_balance(self):
            """Returns the current available balance of the asset."""
            response = self.bitvavo.balance()
            for asset in response:
                if asset["symbol"] == self.pair.split("-")[0]:  # BTC-EUR → BTC
                    return float(asset["available"])
            return 0.0  # Als asset niet gevonden is, is het saldo 0

    def remove_position(self, position):
        """Removes the position from the portfolio after a failed stoploss."""
        if self.pair in self.portfolio:
            try:
                self.portfolio[self.pair].remove(position)
                self.logger.log(
                    f"🔄 [{self.pair}] Removed failed stoploss position from portfolio.", 
                    to_console=True, to_slack=True
                )
                self.save_portfolio()  # Save immediately
            except ValueError:
                self.logger.log(
                    f"⚠️ [{self.pair}] Position not found in portfolio, cannot remove.", 
                    to_console=True, to_slack=True
                )

######################
# BUY Logic
######################
    def buy(self, price, budget, fee_percentage):
        """
        Voert een kooporder uit op basis van een budget.

        Args:
            price (float): De koopprijs per eenheid.
            budget (float): Het beschikbare budget in EUR.
            fee_percentage (float): Het handelskostenpercentage.
        """
        if budget <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid budget provided: {budget}",
                to_console=True, to_slack=True
            )
            return

        quantity = (budget / price) * (1 - fee_percentage / 100)
        self._execute_buy(price, quantity, fee_percentage)


    def buy_dynamic(self, price, quantity, fee_percentage):
        """
        Voert een kooporder uit op basis van een opgegeven hoeveelheid.

        Args:
            price (float): De koopprijs per eenheid.
            quantity (float): De hoeveelheid die gekocht moet worden.
            fee_percentage (float): Het handelskostenpercentage.
        """
        if quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid quantity provided: {quantity}",
                to_console=True, to_slack=True
            )
            return

        self._execute_buy(price, quantity, fee_percentage)


    def _execute_buy(self, price, quantity, fee_percentage):
        """
        Interne functie die de daadwerkelijke kooptransactie uitvoert.

        Args:
            price (float): De koopprijs per eenheid.
            quantity (float): De hoeveelheid die gekocht moet worden.
            fee_percentage (float): Het handelskostenpercentage.
        """
        try:
            available_balance = TradingUtils.get_account_balance(self.bitvavo, asset="EUR")
        except Exception as e:
            self.logger.log(
                f"[{self.bot_name}] ❌ Error retrieving account balance: {e}",
                to_console=True, to_slack=True
            )
            return

        total_cost = price * quantity
        if available_balance < total_cost:
            self.logger.log(
                f"[{self.bot_name}] ❌ {self.pair}: Insufficient funds."
                f" Needed: {total_cost:.2f} EUR, Available: {available_balance:.2f} EUR",
                to_console=True, to_slack=True
            )
            return

        # Pas de quantity aan conform de markteisen
        quantity = self.adjust_quantity(self.pair, quantity)
        if quantity <= 0:
            self.logger.log(
                f"[{self.bot_name}] ❌ Invalid quantity for {self.pair}: {quantity}",
                to_console=True, to_slack=True
            )
            return

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode
        )

        if order.get("status") == "demo" or "orderId" in order:
            spent = price * quantity * (1 + fee_percentage / 100)

            new_position = {
                "price": price,
                "quantity": quantity,
                "spent": spent,
                "timestamp": datetime.now().isoformat()
            }

            if self.pair not in self.portfolio:
                self.portfolio[self.pair] = []
            elif not isinstance(self.portfolio[self.pair], list):
                self.portfolio[self.pair] = [self.portfolio[self.pair]]
            self.portfolio[self.pair].append(new_position)

            self.save_portfolio()
            self.log_trade("buy", price, quantity)
            self.logger.log(
                f"[{self.bot_name}] {self.pair}: 👽 Bought Price={price:.2f}, Quantity={quantity:.6f}",
                to_console=True, to_slack=False
            )
        else:
            self.logger.log(
                f"[{self.bot_name}] ❌ {self.pair}: Failed to execute buy order {order}",
                to_console=True, to_slack=True
            )

#################           
# SELL Logic
#################
def sell(self, price, fee_percentage, max_retries=3, wait_time=5, is_stoploss=False):
    """
    Verkoop alle open posities met retry-mechanisme.

    Args:
        price (float): De verkoopprijs.
        fee_percentage (float): De transactiekosten in procenten.
        max_retries (int): Aantal retries bij een mislukte verkoop.
        wait_time (int): Tijd in seconden tussen retries.
        is_stoploss (bool): True als het om een stoploss gaat (snellere actie vereist).
    """
    open_positions = self.get_open_positions()
    if not open_positions:
        self.logger.log(
            f"[{self.bot_name}] {self.pair}: 👽 No position to sell.", to_console=True
        )
        return

    for position in list(open_positions):
        self._execute_sell(position, price, fee_percentage, max_retries, wait_time, is_stoploss)


def _execute_sell(self, position, price, fee_percentage, max_retries, wait_time, is_stoploss):
    """
    Voert een verkoop uit met optioneel retry-mechanisme.

    Args:
        position (dict): De positie die verkocht moet worden.
        price (float): De verkoopprijs.
        fee_percentage (float): De transactiekosten in procenten.
        max_retries (int): Aantal retries bij een mislukte verkoop.
        wait_time (int): Tijd in seconden tussen retries.
        is_stoploss (bool): True als het om een stoploss-verkoop gaat.

    Returns:
        bool: True als de verkoop slaagt, anders False.
    """
    quantity = position.get("quantity", 0)
    quantity = self.adjust_quantity(self.pair, quantity)
    if quantity <= 0:
        self.logger.log(
            f"[{self.bot_name}] {self.pair}: ❌ Invalid quantity sell: {quantity}",
            to_console=True, to_slack=True
        )
        return False

    available_balance = TradingUtils.get_account_balance(self.bitvavo, asset=self.pair.split("-")[0])
    if available_balance < quantity:
        self.logger.log(
            f"[{self.bot_name}] ❌ {self.pair}: Not enough balance to sell. Expected {quantity}, available: {available_balance}",
            to_console=True, to_slack=True
        )
        return False

    if is_stoploss:
        self.logger.log(
            f"[{self.bot_name}] ⚠️ {self.pair}: Stoploss triggered, selling immediately!",
            to_console=True, to_slack=True
        )

    cost_basis = position.get("spent", position["price"] * quantity)
    for attempt in range(1, max_retries + 1):
        revenue = price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis
        self.logger.log(
            f"[{self.bot_name}] ⛔️ {self.pair}: Sell attempt {attempt}: Price={price:.2f} (Profit: {profit:.2f})",
            to_console=True
        )

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode
        )
        if order.get("status") == "demo" or "orderId" in order:
            self.log_trade("sell", price, quantity, profit)
            if self.pair in self.portfolio and isinstance(self.portfolio[self.pair], list):
                try:
                    self.portfolio[self.pair].remove(position)
                except ValueError:
                    self.logger.log(
                        f"[{self.bot_name}] ❌ Position not found in portfolio for {self.pair}.",
                        to_console=True
                    )
            self.save_portfolio()
            self.logger.log(
                f"[{self.bot_name}] 👽 {self.pair}: Sold! Price={price:.2f}, Profit={profit:.2f}",
                to_console=True, to_slack=False
            )
            return True
        else:
            self.logger.log(
                f"[{self.bot_name}] 👽 {self.pair}: Sell attempt {attempt} failed for {order}",
                to_console=True
            )
            time.sleep(wait_time)

    self.logger.log(f"[{self.bot_name}] ❌ Sell failed for {self.pair} after {max_retries} attempts.",
                    to_console=True)
    return False