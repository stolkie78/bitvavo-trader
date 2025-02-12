import json
from datetime import datetime
import os
from bot.trading_utils import TradingUtils
import threading
import time  # For sleep in stop loss retry mechanism


class StateManager:
    _lock = threading.Lock()  # Lock to prevent race conditions

    def __init__(self, pair, logger, bitvavo, demo_mode=False):
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
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
                    "👽❗ Error loading portfolio.json, resetting file.", to_console=True)
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
                    f"👽 Portfolio successfully updated: {
                        json.dumps(self.portfolio, indent=4)}",
                    to_console=True
                )
            except Exception as e:
                self.logger.log(f"👽❌ Error saving portfolio: {
                                e}", to_console=True)

    def adjust_quantity(self, pair, quantity):
        """Adjust the quantity to meet market requirements."""
        market_info = self.bitvavo.markets()
        for market in market_info:
            if market['market'] == pair:
                min_amount = float(market.get('minOrderInBaseAsset', 0.0))
                precision = int(market.get('decimalPlacesBaseAsset', 6))
                adjusted_quantity = max(min_amount, round(quantity, precision))
                return adjusted_quantity
        self.logger.log(f"⚠️ Market info not found for {
                        pair}. Returning original quantity.", to_console=True)
        return quantity

    def buy(self, price, budget, fee_percentage):
        """
        Execute a buy order and add a new position for the pair.
        Performs a budget check before placing the order.

        Args:
            price (float): The purchase price.
            budget (float): The budget allocated for the purchase.
            fee_percentage (float): The transaction fee in percent.
        """
        try:
            available_balance = TradingUtils.get_account_balance(
                self.bitvavo, asset="EUR")
        except Exception as e:
            self.logger.log(f"Error retrieving account balance: {
                            e}", to_console=True)
            return

        if available_balance < budget:
            self.logger.log(
                f"Insufficient funds to buy {self.pair}. Required: {
                    budget:.2f} EUR, available: {available_balance:.2f} EUR",
                to_console=True
            )
            return

        # The fee is applied on the quantity: we buy less crypto than the full budget allows.
        quantity = (budget / price) * (1 - fee_percentage / 100)
        quantity = self.adjust_quantity(self.pair, quantity)

        if quantity <= 0:
            self.logger.log(f"👽❌ Invalid quantity for {self.pair}: {
                            quantity}", to_console=True, to_slack=False)
            return

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode
        )

        if order.get("status") == "demo" or "orderId" in order:
            # Store the actual budget spent as the cost basis (includes buy fee)
            new_position = {
                "price": price,
                "quantity": quantity,
                "spent": budget,
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
                f"👽 Bought {self.pair}: Price={
                    price:.2f}, Quantity={quantity:.6f}",
                to_console=True, to_slack=False
            )
        else:
            self.logger.log(
                f"👽 Failed to execute buy order for {self.pair}: {order}",
                to_console=True, to_slack=False
            )

    def sell(self, price, fee_percentage):
        """
        Execute a sell order for all open positions and remove them from the portfolio.
        For multiple positions it is recommended to use sell_position() for individual trades.
        
        Args:
            price (float): The sell price.
            fee_percentage (float): The transaction fee in percent.
        """
        open_positions = self.get_open_positions()
        if not open_positions:
            self.logger.log(f"👽 No position to sell for {
                            self.pair}.", to_console=True)
            return

        for position in list(open_positions):
            self.sell_position(position, price, fee_percentage)

    def sell_position(self, position, price, fee_percentage):
        """
        Execute a sell order for a specific position and remove it from the portfolio.
        If possible, retrieve actual order details to calculate the true profit.

        Args:
            position (dict): The position to sell.
            price (float): The sell price.
            fee_percentage (float): The transaction fee in percent.
        """
        open_positions = self.get_open_positions()
        if position not in open_positions:
            self.logger.log(f"👽 No matching position to sell for {
                            self.pair}.", to_console=True)
            return

        quantity = position.get("quantity", 0)
        quantity = self.adjust_quantity(self.pair, quantity)
        if quantity <= 0:
            self.logger.log(f"👽 Invalid quantity for {self.pair}: {
                            quantity}", to_console=True, to_slack=False)
            return

        # Add spent column with real buy amount
        cost_basis = position.get("spent", position["price"] * quantity)
        revenue = price * quantity * (1 - fee_percentage / 100)
        estimated_profit = revenue - cost_basis

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode
        )

        if order.get("status") == "demo" or "orderId" in order:
            order_id = order.get("orderId")
            actual_profit = None
            if order_id:
                actual_profit = self.get_actual_trade_profit(
                    order_id, position, fee_percentage)
            profit_to_log = actual_profit if actual_profit is not None else estimated_profit

            self.log_trade("sell", price, quantity, profit=profit_to_log)
            if self.pair in self.portfolio and isinstance(self.portfolio[self.pair], list):
                try:
                    self.portfolio[self.pair].remove(position)
                except ValueError:
                    self.logger.log(f"👽❌ Position not found in portfolio for {
                                    self.pair}.", to_console=True)
            self.save_portfolio()
            self.logger.log(
                f"👽 Sold {self.pair}: Price={
                    price:.2f}, Profit={profit_to_log:.2f}",
                to_console=True, to_slack=False
            )
        else:
            self.logger.log(
                f"👽 Failed to execute sell order for {self.pair}: {order}",
                to_console=True, to_slack=False
            )

    def sell_position_with_retry(self, position, current_price, fee_percentage, max_retries=3, wait_time=5):
        """
        Execute a stop loss sell order for a specific position with a retry mechanism.

        Args:
            position (dict): The position to sell.
            current_price (float): The current market price triggering the stop loss.
            fee_percentage (float): The trading fee percentage.
            max_retries (int): Maximum number of retries.
            wait_time (int): Time in seconds to wait between retries.

        Returns:
            bool: True if the sell order succeeded, False otherwise.
        """
        quantity = position.get("quantity", 0)
        quantity = self.adjust_quantity(self.pair, quantity)
        if quantity <= 0:
            self.logger.log(
                f"👽❌ Invalid quantity for {
                    self.pair} during stop loss sell: {quantity}",
                to_console=True, to_slack=False
            )
            return False

        cost_basis = position.get("spent", position["price"] * quantity)
        for attempt in range(1, max_retries + 1):
            revenue = current_price * quantity * (1 - fee_percentage / 100)
            profit = revenue - cost_basis
            self.logger.log(
                f"⛔️ Stop loss attempt {attempt} for {self.pair}: Trying to sell at {
                    current_price:.2f} (Profit: {profit:.2f})",
                to_console=True
            )

            order = TradingUtils.place_order(
                self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)
            if order.get("status") == "demo" or "orderId" in order:
                self.log_trade("sell", current_price, quantity, profit)
                if self.pair in self.portfolio and isinstance(self.portfolio[self.pair], list):
                    try:
                        self.portfolio[self.pair].remove(position)
                    except ValueError:
                        self.logger.log(f"👽❌ Position not found in portfolio for {
                                        self.pair}.", to_console=True)
                self.save_portfolio()
                self.logger.log(
                    f"👽 Stop loss sold {self.pair}: Price={
                        current_price:.2f}, Profit={profit:.2f}",
                    to_console=True, to_slack=False
                )
                return True
            else:
                self.logger.log(
                    f"👽 Stop loss sell attempt {
                        attempt} failed for {self.pair}: {order}",
                    to_console=True
                )
                time.sleep(wait_time)
        self.logger.log(f"👽❌ Stop loss sell failed for {self.pair} after {max_retries} attempts.",
                        to_console=True)
        return False

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
                f"⚠️ No active position for {
                    self.pair}. Skipping profit calculation.",
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
            trade_type (str): "buy" or "sell".
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
            self.logger.log(f"👽❗ Error logging trade: {
                            e}", to_console=True, to_slack=False)

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
            self.logger.log(f"Error retrieving actual trade details for order {order_id}: {e}",
                            to_console=True)
            return None
