
import json
from datetime import datetime
import os

class StateManager:
    def __init__(self, pair, logger):
        self.pair = pair
        self.logger = logger
        self.position = None  # Represents an open position (price, quantity, timestamp)
        self.data_dir = "data"  # Directory for storing JSON files
        self.trades_file = os.path.join(self.data_dir, "trades.json")

        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def has_position(self):
        return self.position is not None

    def buy(self, price, budget, fee_percentage):
        quantity = (budget / price) * (1 - fee_percentage / 100)
        self.position = {"price": price, "quantity": quantity, "timestamp": datetime.now().isoformat()}
        self.logger.log(f"🟢 Bought {self.pair}: Price={price:.2f}, Quantity={quantity:.6f}", to_console=True, to_slack=True)
        self.log_trade("buy", price, quantity)

    def sell(self, price, fee_percentage):
        if not self.position:
            raise RuntimeError(f"No position to sell for {self.pair}.")

        quantity = self.position["quantity"]
        cost_basis = self.position["price"] * quantity
        revenue = price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        self.logger.log(f"🔴 Sold {self.pair}: Price={price:.2f}, Profit={profit:.2f}", to_console=True, to_slack=True)
        self.log_trade("sell", price, quantity, profit)
        self.position = None

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
            raise RuntimeError(f"No position to calculate profit for {self.pair}.")

        quantity = self.position["quantity"]
        cost_basis = self.position["price"] * quantity
        revenue = current_price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        return (profit / cost_basis) * 100  # Return profit as a percentage

    def log_trade(self, trade_type, price, quantity, profit=None):
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
            self.logger.log(f"❗ Error logging trade: {e}", to_console=True, to_slack=False)
