import json
from datetime import datetime
import os
from bot.trading_utils import TradingUtils


class StateManager:
    def __init__(self, pair, logger, bitvavo, demo_mode=False):
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
        self.position = None  # Ensure only one position per crypto
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()

        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Restore position if it exists in the portfolio
        if self.pair in self.portfolio:
            self.position = self.portfolio[self.pair]

    def has_position(self):
        """Check if a position exists for the pair."""
        return self.position is not None

    def load_portfolio(self):
        """Load the portfolio content from a JSON file."""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    portfolio = json.load(f)
                    self.logger.log(
                        f"👽 Portfolio loaded successfully.", to_console=True)
                    return portfolio
            except Exception as e:
                self.logger.log(f"👽❌ Error loading portfolio: {
                                e}", to_console=True)
        self.logger.log(
            f"ℹ️ No portfolio file found. Starting with an empty portfolio.", to_console=True)
        return {}

    def save_portfolio(self):
        """Save the portfolio content to a JSON file."""
        try:
            with open(self.portfolio_file, "w") as f:
                json.dump(self.portfolio, f, indent=4)
            self.logger.log(f"👽 Portfolio saved to {
                            self.portfolio_file}.", to_console=True)
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
            self.logger.log(f"👽❌ Cannot open a new position for {
                            self.pair}. Position already exists.", to_console=True)
            return

        quantity = (budget / price) * (1 - fee_percentage / 100)
        quantity = self.adjust_quantity(self.pair, quantity)

        if quantity <= 0:
            self.logger.log(f"👽❌ Invalid quantity for {self.pair}: {
                            quantity}", to_console=True, to_slack=False)
            return

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "demo":
            self.logger.log(f"👽 [DEMO] Simulated buy for {self.pair}: Quantity={
                            quantity:.6f}", to_console=True, to_slack=False)
        elif "orderId" in order:
            self.position = {"price": price, "quantity": quantity,
                            "timestamp": datetime.now().isoformat()}
            self.portfolio[self.pair] = self.position
            self.save_portfolio()
            self.logger.log(f"👽 Bought {self.pair}: Price={price:.2f}, Quantity={
                            quantity:.6f}", to_console=True, to_slack=False)
        else:
            self.logger.log(f"👽 Failed to execute buy order for {self.pair}: {
                            order}", to_console=True, to_slack=False)

    def sell(self, price, fee_percentage):
        """Execute a sell order and remove the position from the portfolio."""
        if not self.has_position():
            self.logger.log(f"👽 No position to sell for {
                            self.pair}.", to_console=True)
            return

        quantity = self.position["quantity"]
        quantity = self.adjust_quantity(self.pair, quantity)

        if quantity <= 0:
            self.logger.log(f"👽 Invalid quantity for {self.pair}: {
                            quantity}", to_console=True, to_slack=False)
            return

        cost_basis = self.position["price"] * quantity
        revenue = price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "demo":
            self.logger.log(f"👽 [DEMO] Simulated sell for {self.pair}: Quantity={
                            quantity:.6f}", to_console=True, to_slack=False)
        elif "orderId" in order:
            self.position = None
            if self.pair in self.portfolio:
                del self.portfolio[self.pair]
            self.save_portfolio()
            self.logger.log(f"👽 Sold {self.pair}: Price={price:.2f}, Profit={
                            profit:.2f}", to_console=True, to_slack=False)
        else:
            self.logger.log(f"👽 Failed to execute sell order for {self.pair}: {
                            order}", to_console=True, to_slack=False)


    def calculate_profit(self, current_price, fee_percentage):
        """
        Calculate the profit or loss for the current position.

        Args:
            current_price (float): The current market price of the asset.
            fee_percentage (float): The trading fee percentage.

        Returns:
            float: The profit or loss as a percentage of the initial investment.
        """
        if not self.position:
            raise RuntimeError(
                f"No position to calculate profit for {self.pair}.")

        quantity = self.position["quantity"]
        cost_basis = self.position["price"] * quantity
        revenue = current_price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        return (profit / cost_basis) * 100  # Return profit as a percentage

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
