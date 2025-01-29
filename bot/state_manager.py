import json
from datetime import datetime
import os
from bot.trading_utils import TradingUtils
import threading


class StateManager:
    _lock = threading.Lock()  # Lock om race conditions te voorkomen

    def __init__(self, pair, logger, bitvavo, demo_mode=False):
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
        self.position = None  # Ensure only one position per crypto
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trades_file = os.path.join(self.data_dir, "trades.json")
        self.portfolio = self.load_portfolio()

        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Restore position if it exists in the portfolio
        if self.pair in self.portfolio:
            self.position = self.portfolio[self.pair]


    def has_position(self):
        """Check if a position exists for the pair using the latest portfolio state."""
        self.portfolio = self.load_portfolio()  # ✅ Always load fresh portfolio
        has_position = self.pair in self.portfolio and self.portfolio[self.pair] is not None

        # 🔍 Debugging Log
        #self.logger.log(
        #    f"👽 Checking position for {self.pair}: {'YES' if has_position else 'NO'} "
        #    f"| Current portfolio: {json.dumps(self.portfolio, indent=4)}",
        #    to_console=True
        #)
        return has_position


    def load_portfolio(self):
        """Load the entire portfolio content from a JSON file."""
        if os.path.exists(self.portfolio_file) and os.path.getsize(self.portfolio_file) > 0:
            try:
                with open(self.portfolio_file, "r") as f:
                    # ✅ Assign directly to self.portfolio
                    self.portfolio = json.load(f)

                self.position = self.portfolio.get(
                    self.pair, None)  # ✅ Restore existing positions

                return self.portfolio  # ✅ Ensure this function always returns the correct portfolio
            except (json.JSONDecodeError, IOError):
                self.logger.log(
                    f"👽❗ Error loading portfolio.json, resetting file.", to_console=True)
                return {}  # Reset if corrupted
        return {}  # Return empty if file does not exist or is empty


    def save_portfolio(self):
        """Save the portfolio content to a JSON file without keeping old removed positions."""
        with self._lock:  # Prevent race conditions
            try:
                with open(self.portfolio_file, "w") as f:
                    # ✅ Overwrite with updated data
                    json.dump(self.portfolio, f, indent=4)

                # ✅ Reload the portfolio to confirm changes
                self.portfolio = self.load_portfolio()
                self.logger.log(
                    f"👽 Portfolio successfully updated: {json.dumps(self.portfolio, indent=4)}", to_console=True)

            except Exception as e:
                self.logger.log(f"👽❌ Error saving portfolio: {e}", to_console=True)

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
        """Execute a buy order if no position exists for the pair."""
        if self.has_position():
            self.logger.log(
                f"👽❌ Cannot open a new position for {self.pair}. Position already exists.", to_console=True)
            return

        quantity = (budget / price) * (1 - fee_percentage / 100)
        quantity = self.adjust_quantity(self.pair, quantity)

        if quantity <= 0:
            self.logger.log(
                f"👽❌ Invalid quantity for {self.pair}: {quantity}", to_console=True, to_slack=False)
            return

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "demo" or "orderId" in order:
            new_position = {"price": price, "quantity": quantity,
                            "timestamp": datetime.now().isoformat()}

            # ✅ Ensure the portfolio keeps all pairs and updates only the relevant one
            self.portfolio[self.pair] = new_position
            self.save_portfolio()

            self.log_trade("buy", price, quantity)
            self.logger.log(
                f"👽 Bought {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}", to_console=True, to_slack=False)
        else:
            self.logger.log(
                f"👽 Failed to execute buy order for {self.pair}: {order}", to_console=True, to_slack=False)


    def sell(self, price, fee_percentage):
        """Execute a sell order and remove only the sold asset from the portfolio."""
        if not self.has_position():
            self.logger.log(
                f"👽 No position to sell for {self.pair}.", to_console=True)
            return

        if self.position is None:  # Extra check to prevent NoneType errors
            self.logger.log(
                f"👽❌ Sell failed: No valid position found for {self.pair}.", to_console=True)
            return

        quantity = self.position.get("quantity", 0)
        quantity = self.adjust_quantity(self.pair, quantity)

        if quantity <= 0:
            self.logger.log(
                f"👽 Invalid quantity for {self.pair}: {quantity}", to_console=True, to_slack=False)
            return

        cost_basis = self.position["price"] * quantity
        revenue = price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "demo" or "orderId" in order:
            self.log_trade("sell", price, quantity, profit)

            # 🔍 Debugging: Log before removal
            # self.logger.log(
            #     f"👽 BEFORE removal: Portfolio contains {json.dumps(self.portfolio, indent=4)}", to_console=True)

            # ✅ Properly Remove the Pair
            if self.pair in self.portfolio:
                del self.portfolio[self.pair]  # ✅ Remove from dictionary
                self.save_portfolio()  # ✅ Save changes immediately

                # ✅ Reload to confirm removal
                self.portfolio = self.load_portfolio()

                self.logger.log(
                    f"👽 Sold {self.pair}, removing from portfolio.", to_console=True)

            # 🔍 Debugging: Log after removal
            # self.logger.log(
            #    f"👽 AFTER removal: Portfolio contains {json.dumps(self.portfolio, indent=4)}", to_console=True)

            self.logger.log(
                f"👽 Sold {self.pair}: Price={price:.2f}, Profit={profit:.2f}", to_console=True, to_slack=False)
        else:
            self.logger.log(
                f"👽 Failed to execute sell order for {self.pair}: {order}", to_console=True, to_slack=False)


    def calculate_profit(self, current_price, fee_percentage):
        """
        Calculate the profit or loss for the current position.

        Args:
            current_price (float): The current market price of the asset.
            fee_percentage (float): The trading fee percentage.

        Returns:
            float or None: The profit or loss as a percentage of the initial investment, or None if no position exists.
        """
        if not self.has_position():
            self.logger.log(
                f"⚠️ No active position for {self.pair}. Skipping profit calculation.", to_console=True)
            return None  # Voorkomt crash als er geen positie is

        quantity = self.portfolio[self.pair]["quantity"]
        cost_basis = self.portfolio[self.pair]["price"] * quantity
        revenue = current_price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        return (profit / cost_basis) * 100  # Return profit als percentage

    def log_trade(self, trade_type, price, quantity, profit=None):
        """
        Log trade details to a JSON file.

        Args:
            trade_type (str): "buy" or "sell".
            price (float): Trade price.
            quantity (float): Quantity traded.
            profit (float, optional): Profit from the trade.
        """
        trade = {
            "pair": self.pair,
            "type": trade_type,
            "price": price,
            "quantity": quantity,
            "profit": profit,
            "timestamp": datetime.now().isoformat()
        }
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
