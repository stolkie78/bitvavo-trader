
from datetime import datetime

class StateManager:
    def __init__(self, pair, logger):
        self.pair = pair
        self.current_position = None
        self.logger = logger

    def has_position(self):
        """Checks if there's an open position for this pair."""
        return self.current_position is not None

    def buy(self, price, budget, trade_fee_percentage):
        """Executes a buy operation and stores the position."""
        if self.has_position():
            raise RuntimeError(f"Already holding a position for {self.pair}. Cannot buy again.")
        
        # Calculate the quantity based on the budget and price
        quantity = (budget / price) * (1 - trade_fee_percentage / 100)
        self.current_position = {
            "quantity": quantity,
            "price": price,
            "timestamp": datetime.now()
        }

        # Log the buy operation
        self.logger.log(
            f"🟢 Bought {self.pair}: Price=€{price:.2f}, Quantity={quantity:.6f}",
            to_slack=True
        )

    def sell(self, price, trade_fee_percentage, minimum_profit_percentage=0.0):
        """Executes a sell operation and clears the position."""
        if not self.has_position():
            raise RuntimeError(f"No position to sell for {self.pair}.")

        # Calculate profit
        quantity = self.current_position["quantity"]
        purchase_price = self.current_position["price"]
        gross_revenue = quantity * price
        net_revenue = gross_revenue * (1 - trade_fee_percentage / 100)
        profit = net_revenue - (quantity * purchase_price)
        profit_percentage = (profit / (quantity * purchase_price)) * 100

        # Check minimum profit threshold
        if profit_percentage < minimum_profit_percentage:
            self.logger.log(
                f"⚠️ Skipping sell for {self.pair}: Profit=€{profit:.2f} ({profit_percentage:.2f}%) is below threshold.",
                to_slack=True
            )
            return None  # Skip the sell action

        # Clear position
        self.current_position = None

        # Log the sell operation
        self.logger.log(
            f"🔴 Sold {self.pair}: Price=€{price:.2f}, Profit=€{profit:.2f} ({profit_percentage:.2f}%)",
            to_slack=True
        )

        return profit
